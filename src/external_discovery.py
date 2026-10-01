from __future__ import annotations

import hashlib
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from .agent_planner import (
    DeterministicFallbackPlanner,
    OpenRouterPlanner,
    PlannerDecision,
    PlannerError,
    PlannerResponseError,
    PlannerTransportError,
)
from .agent_tools import LocalResearchTools, extract_local_features
from .schemas import Candidate, EvidenceChunk, ResearchRequest


SEC_ALLOWED_HOSTS = {"efts.sec.gov", "data.sec.gov", "www.sec.gov"}
ANNUAL_FORMS = {"20-F", "20-F/A", "40-F", "40-F/A", "10-K", "10-K/A"}
FRAMEWORK_STATUSES = {
    "IFRS_AS_ISSUED_BY_IASB_VERIFIED",
    "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED",
    "LOCAL_STANDARDS_SUBSTANTIALLY_CONVERGED_WITH_IFRS",
    "US_GAAP",
    "OTHER",
    "PENDING_INSUFFICIENT_EVIDENCE",
}


class ExternalDiscoveryError(RuntimeError):
    """Base class for bounded external-discovery failures."""


class ExternalNetworkError(ExternalDiscoveryError):
    """Raised when an allow-listed SEC request fails safely."""


class DuplicateExternalRequest(ExternalDiscoveryError):
    """Raised when the lane attempts an identical network request twice."""


class ExternalPolicyError(ExternalDiscoveryError):
    """Raised when the controller or source boundary is violated."""


SecTransport = Callable[[str, dict[str, str], float], tuple[bytes, str, str]]


def _default_sec_transport(
    url: str, headers: dict[str, str], timeout: float
) -> tuple[bytes, str, str]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            encoding = response.headers.get("Content-Encoding", "").casefold()
            if encoding == "gzip":
                body = gzip.decompress(body)
            elif encoding == "deflate":
                body = zlib.decompress(body)
            return (
                body,
                response.headers.get("Content-Type", "application/octet-stream"),
                response.geturl(),
            )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ExternalNetworkError(
            f"SEC request failed safely: {type(exc).__name__}"
        ) from exc


class SecEdgarClient:
    """Allow-listed, rate-limited, auditable SEC client with no crawler behavior."""

    def __init__(
        self,
        user_agent: str,
        *,
        transport: SecTransport | None = None,
        minimum_interval_seconds: float = 0.25,
        timeout_seconds: float = 30.0,
    ):
        if not user_agent.strip() or "@" not in user_agent:
            raise ValueError(
                "SEC User-Agent must identify the operator and contain a contact email."
            )
        self.user_agent = user_agent.strip()
        self.transport = transport or _default_sec_transport
        self.minimum_interval_seconds = max(0.1, minimum_interval_seconds)
        self.timeout_seconds = timeout_seconds
        self.request_log: list[dict[str, Any]] = []
        self._seen_urls: set[str] = set()
        self._last_request_at = 0.0

    @classmethod
    def from_environment(
        cls, *, transport: SecTransport | None = None
    ) -> "SecEdgarClient":
        value = os.getenv("SEC_USER_AGENT", "").strip()
        if not value:
            raise ValueError(
                "SEC_USER_AGENT is required for live EDGAR access; use an operator/company name and contact email."
            )
        return cls(value, transport=transport)

    @staticmethod
    def _validate_url(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in SEC_ALLOWED_HOSTS:
            raise ExternalPolicyError("External request target is not an allow-listed SEC HTTPS host.")
        return urllib.parse.urlunparse(parsed._replace(fragment=""))

    def get_bytes(self, url: str, *, purpose: str) -> tuple[bytes, str]:
        normalized = self._validate_url(url)
        if normalized in self._seen_urls:
            raise DuplicateExternalRequest("Duplicate external request blocked.")
        self._seen_urls.add(normalized)
        wait = self.minimum_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        started = time.perf_counter()
        try:
            body, content_type, final_url = self.transport(
                normalized,
                {
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/json,text/html,application/xhtml+xml,text/plain,application/pdf",
                },
                self.timeout_seconds,
            )
            self._last_request_at = time.monotonic()
            final_normalized = self._validate_url(final_url)
            entry = {
                "request_number": len(self.request_log) + 1,
                "purpose": purpose,
                "url": normalized,
                "final_url": final_normalized,
                "status": "success",
                "byte_count": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
            self.request_log.append(entry)
            return body, content_type
        except Exception as exc:
            if not isinstance(exc, (ExternalNetworkError, ExternalPolicyError)):
                exc = ExternalNetworkError(
                    f"SEC request failed safely: {type(exc).__name__}"
                )
            self.request_log.append(
                {
                    "request_number": len(self.request_log) + 1,
                    "purpose": purpose,
                    "url": normalized,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
            raise exc

    def get_json(self, url: str, *, purpose: str) -> dict[str, Any]:
        body, _ = self.get_bytes(url, purpose=purpose)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalNetworkError("SEC endpoint returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ExternalNetworkError("SEC endpoint returned a non-object JSON response.")
        return payload


class _VisibleTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def extract_visible_text(body: bytes, content_type: str) -> str:
    if "pdf" in content_type.casefold() or body.startswith(b"%PDF"):
        return ""
    decoded = body.decode("utf-8", errors="replace")
    if "html" not in content_type.casefold() and "<html" not in decoded[:1000].casefold():
        return re.sub(r"\s+", " ", decoded).strip()
    parser = _VisibleTextExtractor()
    parser.feed(decoded)
    return parser.text()


def _strip_markup(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def _first(value: Any, default: Any = None) -> Any:
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def parse_sec_search_response(
    payload: dict[str, Any], *, query_label: str
) -> list[dict[str, Any]]:
    hits = payload.get("hits", {}).get("hits", [])
    if not isinstance(hits, list):
        raise ExternalNetworkError("SEC search response has an invalid hits structure.")
    parsed: list[dict[str, Any]] = []
    for hit in hits:
        source = hit.get("_source", {}) if isinstance(hit, dict) else {}
        form = str(source.get("form") or _first(source.get("root_forms"), "")).upper()
        if form not in ANNUAL_FORMS:
            continue
        raw_cik = str(_first(source.get("ciks"), "")).lstrip("0")
        if not raw_cik.isdigit():
            continue
        hit_id = str(hit.get("_id", ""))
        accession_match = re.search(r"\d{10}-\d{2}-\d{6}", hit_id)
        names = source.get("display_names") or source.get("display_name") or []
        company = _strip_markup(_first(names, names if isinstance(names, str) else ""))
        parsed.append(
            {
                "company": company or f"CIK {raw_cik}",
                "cik": raw_cik.zfill(10),
                "discovery_form": form,
                "discovery_accession": accession_match.group(0) if accession_match else None,
                "filed_date": source.get("file_date"),
                "period_end": source.get("period_ending"),
                "sec_relevance_score": round(float(hit.get("_score") or 0.0), 6),
                "sic": str(source.get("sics") or source.get("sic") or ""),
                "business_location_code": str(_first(source.get("biz_locations"), "")),
                "discovery_query": query_label,
                "authority_class": "COMPANY_DISCLOSURE",
            }
        )
    return parsed


def _recent_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    columns = {
        key: value
        for key, value in recent.items()
        if isinstance(value, list)
    }
    if not columns:
        return []
    count = min(len(value) for value in columns.values())
    return [{key: value[index] for key, value in columns.items()} for index in range(count)]


def parse_sec_submissions(
    payload: dict[str, Any], *, expected_cik: str
) -> dict[str, Any]:
    cik = str(payload.get("cik") or expected_cik).lstrip("0").zfill(10)
    rows = [row for row in _recent_rows(payload) if str(row.get("form", "")).upper() in ANNUAL_FORMS]
    if not rows:
        return {
            "company": str(payload.get("name") or f"CIK {cik}"),
            "cik": cik,
            "filing_found": False,
            "fpi_indicator": False,
            "reason": "No 20-F, 40-F, or 10-K annual filing was found in current SEC submissions metadata.",
        }
    rows.sort(key=lambda item: str(item.get("filingDate", "")), reverse=True)
    has_20f = any(str(row.get("form", "")).upper().startswith("20-F") for row in rows)
    has_40f = any(str(row.get("form", "")).upper().startswith("40-F") for row in rows)
    if has_20f:
        selected = next(row for row in rows if str(row.get("form", "")).upper().startswith("20-F"))
    elif has_40f:
        selected = next(row for row in rows if str(row.get("form", "")).upper().startswith("40-F"))
    else:
        selected = rows[0]
    accession = str(selected.get("accessionNumber", ""))
    primary = str(selected.get("primaryDocument", ""))
    filing_url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{urllib.parse.quote(primary)}"
    )
    addresses = payload.get("addresses", {}) if isinstance(payload.get("addresses"), dict) else {}
    business = addresses.get("business", {}) if isinstance(addresses.get("business"), dict) else {}
    return {
        "company": str(payload.get("name") or f"CIK {cik}"),
        "cik": cik,
        "filing_found": bool(accession and primary),
        "form": str(selected.get("form", "")).upper(),
        "accession_number": accession,
        "filing_date": selected.get("filingDate"),
        "report_date": selected.get("reportDate"),
        "primary_document": primary,
        "filing_url": filing_url,
        "filing_index_url": (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{accession}-index.html"
        ),
        "fpi_indicator": has_20f or has_40f,
        "annual_form_selection": "20-F preferred, then 40-F, then 10-K",
        "business_location_code": str(business.get("stateOrCountry") or ""),
        "business_location_description": str(business.get("stateOrCountryDescription") or ""),
        "authority_class": "COMPANY_DISCLOSURE",
        "source_metadata_url": f"https://data.sec.gov/submissions/CIK{cik}.json",
    }


FRAMEWORK_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "IFRS_AS_ISSUED_BY_IASB_VERIFIED",
        "iasb_ifrs_exact",
        re.compile(
            r"(?:international financial reporting standards|ifrs accounting standards)\s+as issued by\s+(?:the\s+)?international accounting standards board",
            re.IGNORECASE,
        ),
    ),
    (
        "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED",
        "jurisdiction_adopted_ifrs",
        re.compile(
            r"(?:international financial reporting standards|ifrs accounting standards)\s+as adopted by\s+(?:the\s+)?(?:european union|united kingdom|[a-z][a-z ]{2,40})",
            re.IGNORECASE,
        ),
    ),
    (
        "LOCAL_STANDARDS_SUBSTANTIALLY_CONVERGED_WITH_IFRS",
        "local_converged_standards",
        re.compile(
            r"(?:hong kong financial reporting standards|australian accounting standards|brazilian accounting practices)",
            re.IGNORECASE,
        ),
    ),
    (
        "US_GAAP",
        "us_gaap_exact",
        re.compile(
            r"accounting principles generally accepted in (?:the )?united states(?: of america)?|u\.s\.\s+generally accepted accounting principles",
            re.IGNORECASE,
        ),
    ),
]


def verify_framework_from_text(text: str, *, form: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for status, pattern_id, pattern in FRAMEWORK_PATTERNS:
        match = pattern.search(text)
        if match:
            window = text[max(0, match.start() - 120) : min(len(text), match.end() + 120)]
            matches.append(
                {
                    "status": status,
                    "pattern_id": pattern_id,
                    "text_offset": match.start(),
                    "evidence_window_sha256": hashlib.sha256(window.encode("utf-8")).hexdigest(),
                }
            )
    if not matches:
        return {
            "status": "PENDING_INSUFFICIENT_EVIDENCE",
            "verified": False,
            "evidence": [],
            "reason": "No issuer-specific basis-of-preparation or auditor-report pattern was verified in the downloaded filing.",
            "form_is_not_framework_evidence": True,
        }
    statuses = {item["status"] for item in matches}
    if "US_GAAP" in statuses and form.upper().startswith("10-K"):
        chosen = "US_GAAP"
    elif "IFRS_AS_ISSUED_BY_IASB_VERIFIED" in statuses:
        chosen = "IFRS_AS_ISSUED_BY_IASB_VERIFIED"
    elif "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED" in statuses:
        chosen = "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED"
    elif "LOCAL_STANDARDS_SUBSTANTIALLY_CONVERGED_WITH_IFRS" in statuses:
        chosen = "LOCAL_STANDARDS_SUBSTANTIALLY_CONVERGED_WITH_IFRS"
    else:
        chosen = "US_GAAP" if "US_GAAP" in statuses else "OTHER"
    return {
        "status": chosen,
        "verified": chosen != "OTHER",
        "evidence": [item for item in matches if item["status"] == chosen],
        "reason": "Status is based on an issuer-specific phrase match in the downloaded filing; the phrase itself is not sent to the planner.",
        "form_is_not_framework_evidence": True,
    }


EXTERNAL_FEATURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "property_development_business": (
        r"property development",
        r"real estate development",
        r"residential development",
        r"commercial development",
    ),
    "development_partner_financing": (
        r"development loans?",
        r"loans? to (?:joint ventures?|development partners?)",
        r"development loan receivables?",
        r"project loans?",
    ),
    "loan_or_note_receivable": (
        r"loans? receivable",
        r"notes? receivable",
        r"mortgage loans?",
        r"loan portfolio",
    ),
    "collateral_or_security": (
        r"collateral",
        r"secured by",
        r"security interest",
        r"loan.to.value",
    ),
    "borrower_or_counterparty_condition": (
        r"borrower",
        r"counterpart(?:y|ies)",
        r"financial difficulty",
        r"credit quality",
    ),
    "construction_or_leasing_status": (
        r"construction",
        r"leasing status",
        r"lease.up",
        r"occupancy",
    ),
    "ecl_or_sicr": (
        r"expected credit losses?",
        r"significant increase in credit risk",
        r"\bsicr\b",
        r"allowance for credit losses?",
    ),
}


def derive_external_features(text: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    locators: list[dict[str, Any]] = []
    for feature, patterns in EXTERNAL_FEATURE_PATTERNS.items():
        matches: list[re.Match[str]] = []
        for pattern in patterns:
            matches.extend(list(re.finditer(pattern, text, re.IGNORECASE)))
        matches.sort(key=lambda item: item.start())
        counts[feature] = len(matches)
        for match in matches[:3]:
            window = text[max(0, match.start() - 100) : min(len(text), match.end() + 100)]
            locators.append(
                {
                    "feature": feature,
                    "text_offset": match.start(),
                    "evidence_window_sha256": hashlib.sha256(window.encode("utf-8")).hexdigest(),
                }
            )
    return {
        "feature_counts": counts,
        "evidence_locators": locators,
        "raw_text_in_result": False,
        "derived_summary": [name for name, count in counts.items() if count > 0],
    }


class ExternalDiscoveryTools:
    """External network plane plus local filing processing; planner output is metadata-only."""

    def __init__(
        self,
        *,
        sec_client: SecEdgarClient,
        runtime_root: str | Path,
        private_chunks: list[EvidenceChunk],
        local_candidates: list[Candidate],
        jurisdiction_context_path: str | Path,
    ):
        self.sec = sec_client
        self.runtime_root = Path(runtime_root)
        self.private_chunks = list(private_chunks)
        self.local_candidates = list(local_candidates)
        self.jurisdiction_context_path = Path(jurisdiction_context_path)
        self._documents: dict[str, dict[str, Any]] = {}
        self._texts: dict[str, str] = {}

    def raw_external_texts(self) -> list[str]:
        return [value for value in self._texts.values() if len(value) >= 40]

    def analyse_audit_scenario(self, scenario: str) -> dict[str, Any]:
        return LocalResearchTools(self.private_chunks, self.local_candidates).analyse_audit_scenario(scenario)

    def discover_external_candidates(self, *, max_candidates: int = 3) -> dict[str, Any]:
        if max_candidates < 1 or max_candidates > 3:
            raise ExternalPolicyError("At most three external candidates may be discovered.")
        query_specs = [
            ("development loan", "development-loan"),
            ("loans to joint ventures property", "joint-venture-property-loans"),
        ]
        merged: dict[str, dict[str, Any]] = {}
        search_urls = []
        for query, label in query_specs:
            params = urllib.parse.urlencode(
                {
                    "q": query,
                    "forms": "10-K,20-F,40-F",
                    "dateRange": "custom",
                    "startdt": "2022-01-01",
                    "enddt": date.today().isoformat(),
                    "from": 0,
                    "size": 20,
                }
            )
            url = f"https://efts.sec.gov/LATEST/search-index?{params}"
            search_urls.append(url)
            payload = self.sec.get_json(url, purpose=f"candidate discovery: {label}")
            for candidate in parse_sec_search_response(payload, query_label=label):
                previous = merged.get(candidate["cik"])
                if previous is None or candidate["sec_relevance_score"] > previous["sec_relevance_score"]:
                    merged[candidate["cik"]] = candidate
        priority = {"20-F": 3, "20-F/A": 3, "40-F": 2, "40-F/A": 2, "10-K": 1, "10-K/A": 1}
        candidates = sorted(
            merged.values(),
            key=lambda item: (
                -float(item["sec_relevance_score"]),
                -priority.get(item["discovery_form"], 0),
                item["company"],
            ),
        )[:max_candidates]
        return {
            "source": "SEC EDGAR Full-Text Search",
            "candidate_count": len(candidates),
            "candidates": candidates,
            "query_count": len(query_specs),
            "search_urls": search_urls,
            "bounded_to_sec": True,
        }

    def locate_public_filing(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        if not candidates or len(candidates) > 3:
            raise ExternalPolicyError("Locate filings for between one and three discovered candidates.")
        filings = []
        for candidate in candidates:
            cik = str(candidate["cik"]).zfill(10)
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            payload = self.sec.get_json(url, purpose=f"filing metadata for CIK {cik}")
            filing = parse_sec_submissions(payload, expected_cik=cik)
            filing["discovery_company"] = candidate["company"]
            filing["sec_relevance_score"] = candidate["sec_relevance_score"]
            filings.append(filing)
        return {
            "filings": filings,
            "valid_filing_count": sum(bool(item.get("filing_found")) for item in filings),
            "source": "SEC submissions JSON",
        }

    def download_filing_local(
        self, filings: list[dict[str, Any]], *, max_filings: int = 2
    ) -> dict[str, Any]:
        if max_filings < 1 or max_filings > 2:
            raise ExternalPolicyError("At most two annual filings may be downloaded in this Gate 5 run.")
        eligible = [item for item in filings if item.get("filing_found")][:max_filings]
        downloads = []
        for filing in eligible:
            body, content_type = self.sec.get_bytes(
                filing["filing_url"],
                purpose=f"annual filing {filing['accession_number']}",
            )
            accession_key = filing["accession_number"].replace("-", "")
            doc_id = f"SEC-{filing['cik']}-{accession_key}"
            suffix = Path(filing["primary_document"]).suffix or ".bin"
            path = self.runtime_root / "raw" / filing["cik"] / accession_key / f"primary{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            text = extract_visible_text(body, content_type)
            self._documents[doc_id] = {"filing": dict(filing), "path": path, "sha256": digest}
            self._texts[doc_id] = text
            downloads.append(
                {
                    "local_document_id": doc_id,
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "form": filing["form"],
                    "accession_number": filing["accession_number"],
                    "filing_url": filing["filing_url"],
                    "sha256": digest,
                    "byte_count": len(body),
                    "content_type": content_type.split(";", 1)[0],
                    "local_text_available": bool(text),
                    "raw_text_returned_to_planner": False,
                }
            )
        return {
            "downloads": downloads,
            "download_count": len(downloads),
            "download_limit": max_filings,
            "storage_boundary": "external_runtime/raw (gitignored)",
        }

    def _jurisdiction_context(self, code: str) -> dict[str, Any]:
        payload = json.loads(self.jurisdiction_context_path.read_text(encoding="utf-8"))
        profile = payload.get("profiles", {}).get(code.upper())
        return {
            "available": bool(profile),
            "profile": profile,
            "source_url": payload["source"]["url"],
            "contextual_only": True,
            "issuer_framework_inference_allowed": False,
        }

    def verify_reporting_framework(self, document_ids: list[str]) -> dict[str, Any]:
        if not document_ids or len(document_ids) > 2:
            raise ExternalPolicyError("Verify one or two downloaded annual filings.")
        results = []
        for doc_id in document_ids:
            if doc_id not in self._documents:
                raise ExternalPolicyError("Framework verification requires a downloaded filing.")
            record = self._documents[doc_id]
            filing = record["filing"]
            result = verify_framework_from_text(self._texts[doc_id], form=filing["form"])
            if result["status"] not in FRAMEWORK_STATUSES:
                raise ExternalPolicyError("Framework verifier returned an unsupported status.")
            result.update(
                {
                    "local_document_id": doc_id,
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "form": filing["form"],
                    "accession_number": filing["accession_number"],
                    "filing_url": filing["filing_url"],
                    "jurisdiction_context": self._jurisdiction_context(
                        filing.get("business_location_code", "")
                    ),
                    "raw_text_returned_to_planner": False,
                }
            )
            results.append(result)
        return {"framework_results": results}

    def search_external_filing_local(
        self, document_ids: list[str], *, query_features: list[str]
    ) -> dict[str, Any]:
        if not document_ids or len(document_ids) > 2:
            raise ExternalPolicyError("Search one or two downloaded annual filings.")
        searches = []
        for doc_id in document_ids:
            if doc_id not in self._documents:
                raise ExternalPolicyError("External filing must be downloaded before local search.")
            record = self._documents[doc_id]
            filing = record["filing"]
            derived = derive_external_features(self._texts[doc_id])
            derived.update(
                {
                    "local_document_id": doc_id,
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "form": filing["form"],
                    "accession_number": filing["accession_number"],
                    "filing_url": filing["filing_url"],
                    "query_features": list(query_features),
                    "authority_class": "COMPANY_DISCLOSURE",
                }
            )
            searches.append(derived)
        return {"searches": searches}

    @staticmethod
    def _dimension(value: float, reason: str) -> dict[str, Any]:
        return {"score": value, "reason": reason}

    def assess_external_comparability(
        self,
        *,
        discovered_candidates: list[dict[str, Any]],
        framework_results: list[dict[str, Any]],
        searches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        frameworks = {item["cik"]: item for item in framework_results}
        by_cik = {item["cik"]: item for item in searches}
        assessments = []
        for candidate in discovered_candidates:
            cik = candidate["cik"]
            search = by_cik.get(cik)
            framework = frameworks.get(cik)
            if not search:
                assessments.append(
                    {
                        "company": candidate["company"],
                        "cik": cik,
                        "status": "rejected_uninspected",
                        "rating": "insufficient",
                        "weighted_score": 0.0,
                        "rejection_reasons": [
                            "The bounded two-filing download limit was reached before this candidate was inspected."
                        ],
                        "authority_class": "COMPANY_DISCLOSURE",
                    }
                )
                continue
            features = search["feature_counts"]
            business = 1.0 if features["property_development_business"] else 0.0
            development = features["development_partner_financing"] > 0
            generic_loan = features["loan_or_note_receivable"] > 0
            instrument = 1.0 if development else (0.5 if generic_loan else 0.0)
            framework_status = framework["status"] if framework else "PENDING_INSUFFICIENT_EVIDENCE"
            framework_score = {
                "IFRS_AS_ISSUED_BY_IASB_VERIFIED": 1.0,
                "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED": 0.75,
                "LOCAL_STANDARDS_SUBSTANTIALLY_CONVERGED_WITH_IFRS": 0.5,
                "PENDING_INSUFFICIENT_EVIDENCE": 0.25,
                "US_GAAP": 0.0,
                "OTHER": 0.0,
            }[framework_status]
            dimensions = {
                "business_model": self._dimension(business, "Property-development activity was locally detected." if business else "Property-development business evidence was not detected."),
                "instrument_type": self._dimension(instrument, "Development-partner financing was detected." if development else ("Only a generic loan/receivable was detected." if generic_loan else "No matching loan or receivable was detected.")),
                "borrower_or_counterparty": self._dimension(1.0 if features["borrower_or_counterparty_condition"] else 0.0, "Borrower/counterparty-condition features were detected." if features["borrower_or_counterparty_condition"] else "Borrower-condition evidence was not detected."),
                "collateral": self._dimension(1.0 if features["collateral_or_security"] else 0.0, "Collateral/security features were detected." if features["collateral_or_security"] else "Collateral evidence was not detected."),
                "construction_and_leasing": self._dimension(1.0 if features["construction_or_leasing_status"] else 0.0, "Construction/leasing features were detected." if features["construction_or_leasing_status"] else "Construction/leasing evidence was not detected."),
                "ecl_treatment": self._dimension(1.0 if features["ecl_or_sicr"] else 0.0, "ECL/SICR or credit-loss features were detected." if features["ecl_or_sicr"] else "ECL/SICR evidence was not detected."),
                "reporting_framework_status": self._dimension(framework_score, f"Issuer-specific framework status: {framework_status}."),
            }
            weights = {
                "business_model": 0.22,
                "instrument_type": 0.22,
                "borrower_or_counterparty": 0.14,
                "collateral": 0.14,
                "construction_and_leasing": 0.08,
                "ecl_treatment": 0.12,
                "reporting_framework_status": 0.08,
            }
            score = round(sum(dimensions[name]["score"] * weight for name, weight in weights.items()), 3)
            rejection_reasons = []
            if not business:
                rejection_reasons.append("Property-development business evidence was insufficient.")
            if not instrument:
                rejection_reasons.append("Development-loan or relevant receivable evidence was insufficient.")
            if framework_status in {"US_GAAP", "OTHER", "PENDING_INSUFFICIENT_EVIDENCE"}:
                rejection_reasons.append(
                    "The reporting framework does not provide a verified IASB-IFRS match."
                )
            if business and instrument:
                rating = "strong" if score >= 0.70 else "partial"
                if framework_status in {"US_GAAP", "OTHER", "PENDING_INSUFFICIENT_EVIDENCE"}:
                    rating = "partial"
                status = "useful_with_limitations"
            else:
                rating = "weak" if score > 0 else "insufficient"
                status = "rejected"
            assessments.append(
                {
                    "company": search["company"],
                    "cik": cik,
                    "status": status,
                    "rating": rating,
                    "weighted_score": score,
                    "dimensions": dimensions,
                    "framework_status": framework_status,
                    "rejection_reasons": rejection_reasons,
                    "comparability_rationale": (
                        "Economic relevance is based on business, instrument, borrower, collateral, construction/leasing, and credit-loss features; shared ECL terminology alone is not sufficient."
                    ),
                    "filing_url": search["filing_url"],
                    "accession_number": search["accession_number"],
                    "evidence_locators": search["evidence_locators"],
                    "authority_class": "COMPANY_DISCLOSURE",
                }
            )
        assessments.sort(key=lambda item: (-item["weighted_score"], item["company"]))
        return {"assessments": assessments}

    def compare_existing_local_corpus(
        self, *, scenario: str, analysis: dict[str, Any]
    ) -> dict[str, Any]:
        tools = LocalResearchTools(self.private_chunks, self.local_candidates)
        search = tools.search_private_corpus(scenario, top_k=10)
        companies: list[str] = []
        for item in search["results"]:
            if item["company"] not in companies:
                companies.append(item["company"])
            if len(companies) == 3:
                break
        profiles = tools.inspect_candidate_metadata(companies)
        state = {
            "request": {"scenario": scenario},
            "observations": {
                "analyse_audit_scenario": analysis,
                "search_private_corpus": search,
                "inspect_candidate_metadata": profiles,
            },
        }
        comparisons = tools.assess_comparability(companies, state=state)["assessments"]
        allied = next((item for item in comparisons if item["company"] == "Allied_REIT"), None)
        return {
            "existing_loop_tools_invoked": [
                "search_private_corpus",
                "inspect_candidate_metadata",
                "assess_comparability",
            ],
            "local_comparator": allied,
            "local_corpus_boundary": "frozen 76-chunk corpus read only; no external document added",
            "raw_text_returned_to_planner": False,
        }

    @staticmethod
    def check_authority() -> dict[str, Any]:
        return {
            "present_authority_classes": ["COMPANY_DISCLOSURE"],
            "missing_authority_classes": [
                "IFRS_FOUNDATION_OFFICIAL",
                "PROFESSIONAL_COMMENTARY",
            ],
            "company_disclosure_can_establish_general_ifrs_requirements": False,
            "jurisdiction_metadata_is_authoritative_standard_text": False,
            "official_guidance_text_indexed": False,
            "required_message": "Official IFRS 9 guidance not available in this prototype",
        }


GATE5_TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "analyse_audit_scenario": {"intent": "Extract business, instrument, and accounting features.", "arguments": {"scenario": "exact submitted scenario"}},
    "discover_external_candidates": {"intent": "Query bounded official SEC full-text search targets.", "arguments": {"max_candidates": "integer, maximum 3"}},
    "locate_public_filing": {"intent": "Locate official annual filings from SEC submissions metadata.", "arguments": {"candidates": "controller-bound discovered candidates"}},
    "download_filing_local": {"intent": "Download at most two official SEC annual filings to gitignored local storage.", "arguments": {"filings": "controller-bound filings", "max_filings": "integer, maximum 2"}},
    "verify_reporting_framework": {"intent": "Verify issuer framework from filing evidence; never infer from form or jurisdiction.", "arguments": {"document_ids": "controller-bound local document identifiers"}},
    "search_external_filing_local": {"intent": "Derive non-verbatim disclosure features locally.", "arguments": {"document_ids": "controller-bound identifiers", "query_features": "controller-bound research features"}},
    "assess_external_comparability": {"intent": "Assess every discovered candidate and preserve rejection reasons.", "arguments": {"discovered_candidates": "controller-bound", "framework_results": "controller-bound", "searches": "controller-bound"}},
    "compare_existing_local_corpus": {"intent": "Return external findings to the existing local comparison logic.", "arguments": {"scenario": "exact submitted scenario", "analysis": "controller-bound analysis"}},
    "check_authority": {"intent": "Separate company disclosure from authoritative IFRS guidance.", "arguments": {}},
    "stop_and_summarise": {"intent": "Create a research handoff requiring auditor review.", "arguments": {"reason": "concise stop reason"}},
}


class Gate5State(str, Enum):
    START = "START"
    SCENARIO_ANALYSED = "SCENARIO_ANALYSED"
    CANDIDATES_DISCOVERED = "CANDIDATES_DISCOVERED"
    FILINGS_LOCATED = "FILINGS_LOCATED"
    FILINGS_DOWNLOADED = "FILINGS_DOWNLOADED"
    FRAMEWORKS_VERIFIED = "FRAMEWORKS_VERIFIED"
    EXTERNAL_EVIDENCE_SEARCHED = "EXTERNAL_EVIDENCE_SEARCHED"
    EXTERNAL_COMPARABILITY_ASSESSED = "EXTERNAL_COMPARABILITY_ASSESSED"
    LOCAL_COMPARATOR_ASSESSED = "LOCAL_COMPARATOR_ASSESSED"
    AUTHORITY_CHECKED = "AUTHORITY_CHECKED"
    STOPPED = "STOPPED"


GATE5_SEQUENCE: list[tuple[Gate5State, str, Gate5State]] = [
    (Gate5State.START, "analyse_audit_scenario", Gate5State.SCENARIO_ANALYSED),
    (Gate5State.SCENARIO_ANALYSED, "discover_external_candidates", Gate5State.CANDIDATES_DISCOVERED),
    (Gate5State.CANDIDATES_DISCOVERED, "locate_public_filing", Gate5State.FILINGS_LOCATED),
    (Gate5State.FILINGS_LOCATED, "download_filing_local", Gate5State.FILINGS_DOWNLOADED),
    (Gate5State.FILINGS_DOWNLOADED, "verify_reporting_framework", Gate5State.FRAMEWORKS_VERIFIED),
    (Gate5State.FRAMEWORKS_VERIFIED, "search_external_filing_local", Gate5State.EXTERNAL_EVIDENCE_SEARCHED),
    (Gate5State.EXTERNAL_EVIDENCE_SEARCHED, "assess_external_comparability", Gate5State.EXTERNAL_COMPARABILITY_ASSESSED),
    (Gate5State.EXTERNAL_COMPARABILITY_ASSESSED, "compare_existing_local_corpus", Gate5State.LOCAL_COMPARATOR_ASSESSED),
    (Gate5State.LOCAL_COMPARATOR_ASSESSED, "check_authority", Gate5State.AUTHORITY_CHECKED),
    (Gate5State.AUTHORITY_CHECKED, "stop_and_summarise", Gate5State.STOPPED),
]


class Gate5DeterministicPlanner(DeterministicFallbackPlanner):
    mode = "deterministic Gate 5 workflow"

    def choose_next(
        self,
        state: dict[str, Any],
        tool_registry: dict[str, dict[str, Any]],
        remaining_steps: int,
        forbidden_texts: list[str],
    ) -> PlannerDecision:
        if len(tool_registry) != 1:
            raise PlannerResponseError("Gate 5 controller must expose exactly one legal tool.")
        tool = next(iter(tool_registry))
        return PlannerDecision(tool, {}, f"Execute the controller-authorized {tool} step.")


@dataclass(frozen=True)
class Gate5Result:
    mode: str
    planner_model: str | None
    step_count: int
    step_limit: int
    state_transition_sequence: list[str]
    trace: list[dict[str, Any]]
    external_request_log: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    filings: list[dict[str, Any]]
    framework_results: list[dict[str, Any]]
    external_searches: list[dict[str, Any]]
    external_comparability: list[dict[str, Any]]
    local_comparator: dict[str, Any] | None
    authority: dict[str, Any]
    handoff: dict[str, Any]
    guardrails_triggered: list[str]
    network_failures: list[dict[str, Any]]
    planner_input_tokens: int
    planner_output_tokens: int
    provider_cost_usd: float
    auditor_review_required: bool

    def safe_export(self) -> dict[str, Any]:
        return asdict(self)


class Gate5Controller:
    def __init__(self, tools: ExternalDiscoveryTools, *, max_steps: int = 10):
        if max_steps < 1 or max_steps > 10:
            raise ValueError("Gate 5 permits between one and ten total agent/tool steps.")
        self.tools = tools
        self.max_steps = max_steps
        self.current = Gate5State.START
        self.states = [self.current.value]
        self.trace: list[dict[str, Any]] = []
        self.seen_calls: set[str] = set()
        self.guardrails: list[str] = []

    def allowed_registry(self) -> dict[str, dict[str, Any]]:
        for before, tool, _ in GATE5_SEQUENCE:
            if before is self.current:
                return {tool: GATE5_TOOL_CONTRACTS[tool]}
        return {}

    def bind(self, decision: PlannerDecision, state: dict[str, Any]) -> PlannerDecision:
        observations = state["observations"]
        tool = decision.tool
        args: dict[str, Any]
        if tool == "analyse_audit_scenario":
            args = {"scenario": state["request"]["scenario"]}
        elif tool == "discover_external_candidates":
            args = {"max_candidates": 3}
        elif tool == "locate_public_filing":
            args = {"candidates": observations["discover_external_candidates"]["candidates"]}
        elif tool == "download_filing_local":
            args = {"filings": observations["locate_public_filing"]["filings"], "max_filings": 2}
        elif tool == "verify_reporting_framework":
            args = {"document_ids": [item["local_document_id"] for item in observations["download_filing_local"]["downloads"]]}
        elif tool == "search_external_filing_local":
            args = {
                "document_ids": [item["local_document_id"] for item in observations["download_filing_local"]["downloads"]],
                "query_features": observations["analyse_audit_scenario"]["evidence_needs"],
            }
        elif tool == "assess_external_comparability":
            args = {
                "discovered_candidates": observations["discover_external_candidates"]["candidates"],
                "framework_results": observations["verify_reporting_framework"]["framework_results"],
                "searches": observations["search_external_filing_local"]["searches"],
            }
        elif tool == "compare_existing_local_corpus":
            args = {"scenario": state["request"]["scenario"], "analysis": observations["analyse_audit_scenario"]}
        elif tool == "check_authority":
            args = {}
        elif tool == "stop_and_summarise":
            args = {"reason": "The bounded external discovery and local comparison workflow is complete; auditor review is required."}
        else:
            raise ExternalPolicyError("Planner selected an unknown Gate 5 tool.")
        if decision.arguments != args:
            self.guardrails.append(f"Controller bound arguments for {tool} to the current workflow state.")
        return PlannerDecision(tool, args, decision.reason[:300])

    def execute(self, decision: PlannerDecision, state: dict[str, Any]) -> None:
        allowed = self.allowed_registry()
        if decision.tool not in allowed:
            raise ExternalPolicyError("Illegal Gate 5 state transition blocked.")
        signature = hashlib.sha256(
            json.dumps(
                {"tool": decision.tool, "arguments": decision.arguments},
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if signature in self.seen_calls:
            raise ExternalPolicyError("Duplicate Gate 5 tool call blocked.")
        self.seen_calls.add(signature)
        before_count = len(self.tools.sec.request_log)
        before = self.current
        started = time.perf_counter()
        if decision.tool == "stop_and_summarise":
            result = self._handoff(state, decision.arguments["reason"])
        else:
            handler = getattr(self.tools, decision.tool)
            result = handler(**decision.arguments)
        next_state = next(after for expected, tool, after in GATE5_SEQUENCE if expected is before and tool == decision.tool)
        self.current = next_state
        self.states.append(next_state.value)
        state["observations"][decision.tool] = result
        state["completed_tools"].append(decision.tool)
        state["workflow"]["current_state"] = next_state.value
        state["workflow"]["state_history"] = list(self.states)
        self.trace.append(
            {
                "step": len(self.trace) + 1,
                "state_before": before.value,
                "action": decision.tool,
                "reason_summary": decision.reason,
                "arguments_summary": self._argument_summary(decision.arguments),
                "result_summary": self._result_summary(decision.tool, result),
                "state_after": next_state.value,
                "external_requests": self.tools.sec.request_log[before_count:],
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )

    @staticmethod
    def _argument_summary(arguments: dict[str, Any]) -> dict[str, Any]:
        summary = {}
        for key, value in arguments.items():
            if isinstance(value, list):
                summary[key] = f"{len(value)} controller-bound items"
            elif isinstance(value, dict):
                summary[key] = "controller-bound structured metadata"
            elif key == "scenario":
                summary[key] = "submitted scenario"
            else:
                summary[key] = value
        return summary

    @staticmethod
    def _result_summary(tool: str, result: dict[str, Any]) -> str:
        counts = {
            "discover_external_candidates": result.get("candidate_count"),
            "locate_public_filing": result.get("valid_filing_count"),
            "download_filing_local": result.get("download_count"),
            "verify_reporting_framework": len(result.get("framework_results", [])),
            "search_external_filing_local": len(result.get("searches", [])),
            "assess_external_comparability": len(result.get("assessments", [])),
        }
        if tool in counts:
            return f"Completed with {counts[tool]} bounded records."
        if tool == "compare_existing_local_corpus":
            return "Returned one existing local comparator assessment to the handoff."
        if tool == "check_authority":
            return "Separated company disclosure from missing authoritative IFRS guidance."
        if tool == "stop_and_summarise":
            return "Created a human-review research handoff."
        return "Structured the scenario for bounded discovery."

    @staticmethod
    def _handoff(state: dict[str, Any], reason: str) -> dict[str, Any]:
        observations = state["observations"]
        assessments = observations.get("assess_external_comparability", {}).get("assessments", [])
        usable = [item for item in assessments if item.get("status") == "useful_with_limitations"]
        rejected = [item for item in assessments if item.get("status", "").startswith("rejected")]
        return {
            "status": "external_research_handoff" if usable else "insufficient_external_evidence",
            "stop_reason": reason[:300],
            "external_candidates_for_review": [
                {"company": item["company"], "rating": item["rating"], "score": item["weighted_score"]}
                for item in usable
            ],
            "rejected_candidates": [
                {"company": item["company"], "reasons": item.get("rejection_reasons", [])}
                for item in rejected
            ],
            "local_comparator": observations.get("compare_existing_local_corpus", {}).get("local_comparator"),
            "authority_boundary": "All retrieved filing evidence is company disclosure. Authoritative IFRS guidance remains missing.",
            "missing_authority": ["IFRS_FOUNDATION_OFFICIAL", "PROFESSIONAL_COMMENTARY"],
            "auditor_review_required": True,
            "final_audit_judgment_provided": False,
        }


def _planner_view(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "request": dict(state["request"]),
        "completed_tools": list(state["completed_tools"]),
        "observations": dict(state["observations"]),
        "workflow": dict(state["workflow"]),
    }


def _safe_failure_handoff(reason: str) -> dict[str, Any]:
    return {
        "status": "external_discovery_stopped_safely",
        "stop_reason": reason[:300],
        "external_candidates_for_review": [],
        "rejected_candidates": [],
        "authority_boundary": "No external filing evidence was promoted after the failure.",
        "missing_authority": ["IFRS_FOUNDATION_OFFICIAL", "PROFESSIONAL_COMMENTARY"],
        "auditor_review_required": True,
        "final_audit_judgment_provided": False,
    }


def run_gate5_discovery(
    request: ResearchRequest,
    *,
    private_chunks: list[EvidenceChunk],
    local_candidates: list[Candidate],
    sec_client: SecEdgarClient,
    runtime_root: str | Path,
    jurisdiction_context_path: str | Path,
    planner: Gate5DeterministicPlanner | OpenRouterPlanner | Any | None = None,
    max_steps: int = 10,
) -> Gate5Result:
    active_planner = planner or Gate5DeterministicPlanner()
    metered_planners = [active_planner]
    tools = ExternalDiscoveryTools(
        sec_client=sec_client,
        runtime_root=runtime_root,
        private_chunks=private_chunks,
        local_candidates=local_candidates,
        jurisdiction_context_path=jurisdiction_context_path,
    )
    controller = Gate5Controller(tools, max_steps=max_steps)
    state: dict[str, Any] = {
        "request": {
            "scenario": request.scenario,
            "topic": request.topic,
            "industry": request.industry,
            "transaction_type": request.transaction_type,
            "reporting_period": request.reporting_period,
            "required_framework": request.required_framework,
        },
        "completed_tools": [],
        "observations": {},
        "workflow": {
            "lane": "bounded_external_discovery",
            "current_state": Gate5State.START.value,
            "state_history": [Gate5State.START.value],
            "external_candidate_limit": 3,
            "annual_filing_download_limit": 2,
            "step_limit": max_steps,
        },
    }
    network_failures: list[dict[str, Any]] = []
    handoff: dict[str, Any] = {}
    mode = active_planner.mode
    model = getattr(active_planner, "model", None)
    while controller.current is not Gate5State.STOPPED and len(controller.trace) < max_steps:
        registry = controller.allowed_registry()
        if not registry:
            controller.guardrails.append("No legal Gate 5 transition remained.")
            handoff = _safe_failure_handoff("No legal Gate 5 transition remained.")
            break
        remaining = max_steps - len(controller.trace)
        forbidden = [chunk.text for chunk in private_chunks] + tools.raw_external_texts()
        try:
            decision = active_planner.choose_next(
                _planner_view(state), registry, remaining, forbidden
            )
        except PlannerTransportError as exc:
            controller.guardrails.append(f"Model planner transport failed safely: {exc}")
            active_planner = Gate5DeterministicPlanner()
            metered_planners.append(active_planner)
            mode = "deterministic Gate 5 fallback after planner transport error"
            decision = active_planner.choose_next(
                _planner_view(state), registry, remaining, forbidden
            )
        except (PlannerResponseError, PlannerError) as exc:
            controller.guardrails.append(f"Invalid planner response blocked: {exc}")
            handoff = _safe_failure_handoff("The model planner returned an invalid Gate 5 action.")
            break
        try:
            decision = controller.bind(decision, state)
            controller.execute(decision, state)
        except (ExternalNetworkError, DuplicateExternalRequest) as exc:
            network_failures.append(
                {"step": len(controller.trace) + 1, "error_type": type(exc).__name__, "message": str(exc)}
            )
            controller.guardrails.append(str(exc))
            handoff = _safe_failure_handoff("An external SEC request failed; the lane stopped without promoting evidence.")
            break
        except (ExternalPolicyError, KeyError, TypeError, ValueError) as exc:
            controller.guardrails.append(f"Gate 5 policy blocked the action: {type(exc).__name__}")
            handoff = _safe_failure_handoff("The Gate 5 controller blocked an invalid action.")
            break
    if not handoff:
        handoff = state["observations"].get("stop_and_summarise", {})
    if not handoff:
        controller.guardrails.append("Gate 5 step cap reached before a normal handoff.")
        handoff = _safe_failure_handoff("The Gate 5 step cap was reached before the workflow completed.")
    observations = state["observations"]
    return Gate5Result(
        mode=mode,
        planner_model=model,
        step_count=len(controller.trace),
        step_limit=max_steps,
        state_transition_sequence=controller.states,
        trace=controller.trace,
        external_request_log=list(sec_client.request_log),
        candidates=observations.get("discover_external_candidates", {}).get("candidates", []),
        filings=observations.get("locate_public_filing", {}).get("filings", []),
        framework_results=observations.get("verify_reporting_framework", {}).get("framework_results", []),
        external_searches=observations.get("search_external_filing_local", {}).get("searches", []),
        external_comparability=observations.get("assess_external_comparability", {}).get("assessments", []),
        local_comparator=observations.get("compare_existing_local_corpus", {}).get("local_comparator"),
        authority=observations.get("check_authority", {}),
        handoff=handoff,
        guardrails_triggered=controller.guardrails,
        network_failures=network_failures,
        planner_input_tokens=sum(int(getattr(item, "total_input_tokens", 0)) for item in metered_planners),
        planner_output_tokens=sum(int(getattr(item, "total_output_tokens", 0)) for item in metered_planners),
        provider_cost_usd=sum(float(getattr(item, "total_cost_usd", 0.0)) for item in metered_planners),
        auditor_review_required=True,
    )
