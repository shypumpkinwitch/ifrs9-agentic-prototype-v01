from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from src.agent_loop_hardened import run_bounded_agent
from src.authority_registry import (
    AUTHORITY_LEVEL_STANDARD,
    authority_cards_for_planner,
    authority_index_status,
    build_separated_research_handoff,
    identify_ifrs9_research_topics,
    load_authority_registry,
    retrieve_authority_cards,
)
from src.final_submission import load_final_submission_snapshot
from src.private_runtime import (
    audit_private_bundle,
    default_private_bundle,
    load_private_baseline,
)
from src.schemas import ResearchRequest
from src.source_registry import (
    load_candidates,
    load_corpus,
    load_guidance_links,
    load_private_corpus_read_only,
)


PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC_DATA = PROJECT_ROOT / "data" / "public_demo"
AUTHORITY_REGISTRY = PUBLIC_DATA / "ifrs_authority_registry_v01.json"

DISPLAY_LABELS = {
    "provider_reported_api_cost_usd": "Provider-reported API cost (USD)",
    "IFRS_AS_ISSUED_BY_IASB_VERIFIED": "IFRS as issued by IASB — verified",
    "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED": "IFRS as adopted by a jurisdiction — verified",
    "LOCAL_STANDARDS_SUBSTANTIALLY_CONVERGED": "Local standards substantially converged with IFRS",
    "US_GAAP": "US GAAP",
    "PENDING_INSUFFICIENT_EVIDENCE": "Pending — insufficient evidence",
    "COMPANY_DISCLOSURE": "Company disclosure",
    "IFRS_FOUNDATION_OFFICIAL": "Official IFRS Foundation material",
    "PROFESSIONAL_COMMENTARY": "Professional interpretation",
    "rejected_business_before_deep_analysis": "Rejected — business model differs",
    "rejected_framework": "Rejected — reporting framework does not meet the requirement",
    "input_tokens": "Input tokens",
    "output_tokens": "Output tokens",
    "weighted_score": "Comparability score",
}


def _display_label(value: str) -> str:
    """Presentation only; machine-readable values are preserved in exports."""
    return DISPLAY_LABELS.get(value, value.replace("_", " "))


def _display_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            _display_label(key): _display_label(value) if isinstance(value, str) else value
            for key, value in row.items()
        }
        for row in rows
    ]

# Manually reviewed, non-verbatim descriptions of existing local evidence.
# Display a description only when that exact chunk is selected in the current run.
ALLIED_HANDOFF_DESCRIPTIONS = {
    "ALLIED_REIT2025_P150_C01": (
        "A development-partner loan disclosure describes an additional credit facility, "
        "variable interest terms, property security subordinated to construction lenders, "
        "and assignments of rents and leases."
    ),
    "ALLIED_REIT2025_P41_C02": (
        "The performance discussion reports an expected credit loss on loans receivable "
        "for the reporting year."
    ),
    "ALLIED_REIT2025_P132_C01": (
        "The impairment policy discusses ECL for amortised-cost financial assets, "
        "a separate trade-receivable approach, and a twelve-month cash-shortfall horizon "
        "for loans and notes when credit risk has not increased significantly."
    ),
}


def _render_company_handoff(result, recorded_candidates: list[dict]) -> None:
    route = result.handoff["scenario_routing"]
    if not route["in_scope"]:
        st.info(route["scope_message"])
        return
    if route["instrument"] != "development_loans":
        selected = result.handoff["selected_candidates"]
        if not selected:
            st.info("No verified suitable comparator within available evidence.")
        for selected_candidate in selected:
            assessment = next(item for item in result.comparability if item["company"] == selected_candidate["company"])
            with st.container(border=True):
                st.markdown(f"**{assessment['company']}**")
                st.write(f"Business comparability: {assessment['rating'].capitalize()}")
                st.write("Authority level: Company disclosure")
                st.write("Reporting-framework verification status: pending")
                st.write(assessment["comparability_explanation"])
                for item in result.retrieved_evidence:
                    if item["company"] == assessment["company"]:
                        st.caption(f"Report year: {item.get('year')} · PDF page: {item.get('pdf_page')} · Chunk: {item['chunk_id']}")
                st.write("Limitations: comparable company practice does not establish instrument-specific IFRS applicability or the client's accounting treatment.")
        return
    allied_evidence = [
        item for item in result.retrieved_evidence if item["company"] == "Allied_REIT"
    ]
    assessment = next(
        (item for item in result.comparability if item["company"] == "Allied_REIT"), None
    )
    with st.container(border=True):
        years = sorted({str(item["year"]) for item in allied_evidence if item.get("year")})
        st.markdown("**Allied_REIT**" + (f" · Report year: {', '.join(years)}" if years else ""))
        st.write(
            "Business comparability: "
            + (assessment["rating"].capitalize() if assessment and allied_evidence else "Not assessed from selected local evidence")
        )
        st.write("Authority level: Company disclosure")
        st.write("Reporting-framework verification status: pending")
        if allied_evidence:
            st.caption("Current local run · selected annual-report evidence")
            for item in allied_evidence:
                description = ALLIED_HANDOFF_DESCRIPTIONS.get(item["chunk_id"])
                if description:
                    st.write(description)
                st.caption(
                    f"Report year: {item.get('year') or 'not supplied'} · "
                    f"PDF page: {item.get('pdf_page') or 'not supplied'} · Chunk: {item['chunk_id']}"
                )
            if any(item["chunk_id"] in ALLIED_HANDOFF_DESCRIPTIONS for item in allied_evidence):
                st.write(
                    "Usefulness: these selected disclosures provide a starting point for reviewing "
                    "loan terms, security and ECL presentation alongside the audit exposure."
                )
            st.write(
                "Limitations: selected extracts do not establish the exact reporting framework "
                "or complete transaction-specific accounting treatment. Review the full local "
                "report and the client's facts before applying any comparison."
            )
        else:
            st.info("No Allied_REIT disclosure was selected in this run; no disclosure features are claimed.")
    if not result.handoff["selected_candidates"]:
        st.info("No verified suitable comparator within available evidence.")


def _render_historical_discovery(recorded_candidates: list[dict]) -> None:
    st.caption(
        "Recorded Gate 5.1 evidence below comes from the preserved discovery checkpoint, "
        "not the current local run. Post-live Shinhan hardening was tested offline; "
        "no second live external-discovery run was performed."
    )
    for candidate in recorded_candidates:
        if candidate["company"] != "Logistic Properties of the Americas":
            continue
        with st.container(border=True):
            st.markdown("**Logistic Properties of the Americas**")
            st.write("Business comparability: Partial comparator — retained for auditor review")
            st.write("Reporting framework: IFRS as issued by IASB — verified")
            st.write("Authority level: Company disclosure")
            st.write(candidate["rationale"])
            st.write(
                "Usefulness: the established property, ECL, receivable, collateral, counterparty "
                "and construction/leasing features provide a partial disclosure comparison."
            )
            st.write(
                "Limitation: development-partner financing was not established. These features "
                "do not establish equivalent loan terms, risk or accounting treatment."
            )
            st.markdown(
                f"[Official SEC filing · {candidate['form']} · {candidate['accession_number']}]"
                f"({candidate['filing_url']})"
            )
    st.markdown("**Rejected financial-institution candidates**")
    for candidate in recorded_candidates:
        if candidate["decision"].startswith("rejected"):
            st.write(f"{candidate['company']}: Rejected. {candidate['rationale']}")
    st.caption(
        "IFRS framework compatibility alone does not establish economic comparability "
        "with a property-development lender."
    )
    for candidate in recorded_candidates:
        st.write(f"{candidate['company']} · Status: {_display_label(candidate['framework_status'])}")


def load_public_assets():
    candidates = load_candidates(PUBLIC_DATA / "candidate_registry_v01.json")
    chunks = load_corpus(PUBLIC_DATA / "disclosures_v01.json")
    guidance = load_guidance_links(PUBLIC_DATA / "guidance_links_v01.json")
    return candidates, chunks, guidance


def _display_link(label: str, value: str | None) -> None:
    if not value:
        st.write(f"{label}: not supplied")
    elif value.startswith(("https://", "http://")):
        st.markdown(f"{label}: [{value}]({value})")
    else:
        st.write(f"{label}: {value}")


def _historical_metrics(private_summary_path: str | None = None) -> dict:
    if private_summary_path:
        return load_private_baseline(private_summary_path)
    with (PUBLIC_DATA / "historical_metrics_v01.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    st.set_page_config(
        page_title="IFRS 9 Auditor Research Assistant",
        page_icon="🔎",
        layout="wide",
    )
    st.title("IFRS 9 Auditor Research Assistant")
    st.caption("Bounded research prototype · company-disclosure research only · human auditor review required")

    final_snapshot = load_final_submission_snapshot(PROJECT_ROOT)
    st.markdown(
        "**Audit scenario → Identify IFRS 9 research topics → Retrieve official IFRS "
        "authority cards → Discover / assess comparable companies → Show comparable "
        "disclosures → Separate authoritative requirement from company practice → "
        "Research handoff**"
    )
    st.info(
        "Authority boundary: a small set of structured, non-verbatim official IFRS 9 "
        "authority cards is indexed for the flagship ECL topics. Full Standard text and "
        "professional interpretation are not indexed; company disclosures remain separate."
    )

    detected_bundle = default_private_bundle(PROJECT_ROOT)
    detected_corpus = detected_bundle / "working_corpus_v01.json"
    private_audit = None
    private_setup_error = None

    with st.sidebar:
        st.header("Data boundary")
        st.write("Public mode uses only self-authored, redistributable fixtures.")
        enable_private = st.checkbox(
            "Enable private local corpus",
            value=detected_corpus.is_file(),
            help="Optional and local-only. Disable this to run the redistributable public fixture.",
        )
        private_path = ""
        if enable_private:
            with st.expander("Local input settings"):
                private_path = st.text_input(
                    "Private corpus location (hidden)",
                    value=str(detected_corpus) if detected_corpus.is_file() else "",
                    type="password",
                    help="Loaded read-only. The path and raw chunks are never sent to an API.",
                )
            try:
                if not private_path.strip():
                    raise ValueError("A private corpus path is required when private mode is enabled.")
                supplied_path = Path(private_path).expanduser().resolve(strict=True)
                if (supplied_path.parent / "freeze_manifest_v02.json").is_file():
                    private_audit = audit_private_bundle(supplied_path.parent)
                    st.caption("Private local corpus: loaded")
                    st.success(
                        f"Validated {private_audit['record_count']} records and "
                        f"{private_audit['unique_chunk_ids']} unique chunk IDs."
                    )
                    with st.expander("Corpus integrity hashes"):
                        st.code(
                            "Raw file bytes\n"
                            f"{private_audit['raw_corpus_sha256']}\n\n"
                            "Canonical JSON content\n"
                            f"{private_audit['canonical_corpus_sha256']}\n\n"
                            "Historical manifest\n"
                            f"{private_audit['manifest_corpus_sha256']}",
                            language=None,
                        )
                    if not private_audit["canonical_hash_matches_manifest"]:
                        st.warning(
                            "Canonical JSON content hash differs from the frozen manifest. "
                            "The manifest is preserved unchanged; see Gate 3 audit."
                        )
                    if private_audit["missing_manifest_files"]:
                        st.warning(
                            "Manifest-referenced files missing from supplied bundle: "
                            + ", ".join(private_audit["missing_manifest_files"])
                        )
            except Exception as exc:
                private_setup_error = f"{type(exc).__name__}: {exc}"
                st.error("Private input validation failed. Check the local corpus location and required files.")
        if os.getenv("OPENROUTER_API_KEY", "").strip():
            st.caption(
                "Planner: OpenRouter model layer enabled. Raw annual-report text remains local."
            )
        else:
            st.caption(
                "Planner: deterministic fallback workflow (no OpenRouter key detected)."
            )

    if enable_private and private_audit:
        st.warning(
            "Private local corpus enabled. Annual-report text may be previewed locally but is "
            "excluded from downloads and model payloads. Some local-source reporting-framework "
            "verification remains pending."
        )
    else:
        st.warning(
            "Public-fixture mode contains no real annual-report corpus. Allied_REIT and RBC remain "
            "metadata-only candidates until the private local input is enabled."
        )

    with st.form("research_request"):
        scenario = st.text_area(
            "Audit scenario",
            value=(
                "A property company has made secured development and project loans, and the "
                "auditor wants relevant ECL topics and comparable public disclosure examples."
            ),
            height=110,
        )
        left, right = st.columns(2)
        with left:
            topic_selection = st.selectbox("IFRS 9 topic", ["Auto — route from scenario", "expected credit losses", "authority handling"])
            topic = "" if topic_selection == "Auto — route from scenario" else topic_selection
            industry = st.text_input("Industry (optional)", value="Property / REIT")
        with right:
            transaction_type = st.text_input(
                "Transaction type (optional)", value="Development/project loans"
            )
            reporting_period = st.text_input("Reporting period (optional)", value="2025")
        st.text_input(
            "Required financial-reporting framework",
            value="IFRS Accounting Standards as issued by IASB",
            disabled=True,
        )
        submitted = st.form_submit_button("Run bounded research agent", type="primary")

    metrics = _historical_metrics(private_audit["summary_path"] if private_audit else None)

    if not submitted:
        st.info("Submit the scenario to run the bounded research loop and create a downloadable trace.")
        return
    if not scenario.strip():
        st.error("Enter an audit scenario.")
        return
    if enable_private and private_setup_error:
        st.error("Fix or disable the private input before running research.")
        return

    try:
        candidates, chunks, guidance = load_public_assets()
        if enable_private and private_path.strip():
            private_chunks, _ = load_private_corpus_read_only(private_path.strip())
            chunks = private_chunks
        request = ResearchRequest(
            scenario=scenario.strip(),
            topic=topic,
            industry=industry.strip(),
            transaction_type=transaction_type.strip(),
            reporting_period=reporting_period.strip(),
        )
        authority_registry = load_authority_registry(AUTHORITY_REGISTRY)
        authority_topics = identify_ifrs9_research_topics(request)
        authority_cards = retrieve_authority_cards(authority_registry, authority_topics)
        authority_planner_payload = authority_cards_for_planner(authority_cards)
        authority_status = authority_index_status(authority_cards)
        scenario_route = request.scenario_routing()
        result = run_bounded_agent(
            request,
            candidates=candidates,
            chunks=chunks,
        )
    except Exception as exc:
        st.error(f"The bounded research run stopped safely: {type(exc).__name__}: {exc}")
        return

    if result.mode == "model-planned bounded agent":
        st.success(f"Completed a bounded model-planned run using {result.planner_model}.")
    else:
        st.success(
            "Completed with the deterministic fallback workflow; no model planning is claimed."
        )
    if not scenario_route["in_scope"]:
        st.warning(scenario_route["scope_message"])
    (
        needs_tab,
        official_tab,
        plan_tab,
        candidate_tab,
        framework_tab,
        comparison_tab,
        evidence_tab,
        authority_tab,
        review_tab,
        evaluation_tab,
    ) = st.tabs(
        [
            "Evidence needs",
            "Official IFRS authority",
            "Plan / action trace",
            "Candidate discovery",
            "Framework verification",
            "Comparability",
            "Company evidence",
            "Authority / gaps",
            "Research handoff",
            "Evaluation",
        ]
    )

    with plan_tab:
        st.subheader("Research plan and bounded agent trace")
        st.caption(
            "These are concise action/reason summaries, not hidden chain-of-thought. "
            f"Mode: {result.mode}. Steps: {result.step_count}/{result.step_limit}."
        )
        st.markdown("#### Authority-first preparation")
        st.dataframe(
            [
                {
                    "step": 1,
                    "action": "identify_ifrs9_research_topics",
                    "result": f"Identified {len(authority_topics)} topic(s).",
                    "data_boundary": "scenario metadata only",
                },
                {
                    "step": 2,
                    "action": "retrieve_official_authority_cards",
                    "result": f"Retrieved {len(authority_cards)} structured official-source card(s).",
                    "data_boundary": "non-verbatim summaries and metadata only",
                },
            ],
            width="stretch",
            hide_index=True,
        )
        st.markdown("#### Comparable-company lane")
        st.caption(
            "The existing bounded company-disclosure trace follows the authority lookup. "
            "Its internal authority check describes the frozen company corpus only."
        )
        st.dataframe(_display_rows(result.trace), width="stretch", hide_index=True)
        integrated_handoff_for_export = build_separated_research_handoff(
            authority_cards,
            result.handoff,
            final_snapshot["recorded_candidates"],
            request=request,
        )
        safe_trace = result.safe_export()
        safe_trace["authority"] = authority_status
        safe_trace["missing_evidence"] = [
            item for item in safe_trace.get("missing_evidence", [])
            if item != "IFRS_FOUNDATION_OFFICIAL"
        ]
        safe_trace["handoff"] = integrated_handoff_for_export
        safe_trace["company_disclosure_lane_authority_check"] = {
            key: value for key, value in result.authority.items()
            if key != "required_message"
        }
        safe_trace["gate61_authority_layer"] = {
            "topics": authority_topics,
            "cards": authority_planner_payload,
            "raw_ifrs_source_text_in_export": False,
        }
        trace_payload = json.dumps(safe_trace, indent=2, ensure_ascii=False)
        st.download_button(
            "Download trace JSON",
            trace_payload,
            file_name="agent_research_trace_v01.json",
            mime="application/json",
        )

    with needs_tab:
        st.subheader("IFRS 9 research topics and evidence needs")
        st.markdown("#### Official-authority topics")
        for authority_topic in authority_topics:
            st.markdown(f"- {authority_topic}")
        st.markdown("#### Comparable-company evidence needs")
        if result.evidence_needs:
            for need in result.evidence_needs:
                st.markdown(f"- {need}")
        else:
            st.info("The scenario did not identify a supported accounting evidence need.")
        if scenario_route["in_scope"] and scenario_route["instrument"] == "development_loans":
            st.caption("Flagship research specification (recorded project evidence)")
            for need in final_snapshot["research_needs"]:
                st.markdown(f"- {need}")

    with official_tab:
        st.subheader("Official IFRS authority cards")
        st.success(authority_status["status_message"])
        st.caption(
            "Cards contain manually reviewable, non-verbatim summaries and official links. "
            "They are not a substitute for reading the licensed source."
        )
        standard_cards = [
            card for card in authority_cards
            if card.authority_level == AUTHORITY_LEVEL_STANDARD
        ]
        supporting_cards = [
            card for card in authority_cards
            if card.authority_level != AUTHORITY_LEVEL_STANDARD
        ]
        st.markdown("#### IFRS Standard / official authority")
        for card in standard_cards:
            with st.container(border=True):
                st.markdown(f"**{card.display_title}** · `{card.authority_id}`")
                st.write(card.non_verbatim_verified_summary)
                st.write(f"Paragraph reference: `{card.display_paragraph_reference}`")
                st.markdown(f"[Open official IFRS Foundation source]({card.official_url})")
                st.caption(f"Source type: {card.display_source_type} · Review: {_display_label(card.review_status)}")
        st.markdown("#### IFRS Foundation supporting or educational material")
        for card in supporting_cards:
            with st.container(border=True):
                st.markdown(f"**{card.display_title}** · `{card.authority_id}`")
                st.write(card.non_verbatim_verified_summary)
                st.write(f"Paragraph reference: `{card.display_paragraph_reference}`")
                st.markdown(f"[Open official IFRS Foundation source]({card.official_url})")
                st.caption(
                    f"Source type: {card.display_source_type}. This is not labelled as IFRS Standard text."
                )
        st.markdown("#### Professional interpretation")
        st.warning("Professional interpretation is not indexed in this prototype.")

    with candidate_tab:
        st.subheader("Candidate discovery")
        st.caption(
            "An indexed candidate is not automatically economically comparable. Framework "
            "status remains pending unless separately evidenced."
        )
        st.markdown("#### Current local run")
        if not result.candidates:
            st.info("No candidate metadata was available from the bounded local search.")
        for candidate in result.candidates:
            with st.container(border=True):
                st.markdown(f"#### {candidate['company']}")
                badges = st.columns(3)
                badges[0].metric("Framework", _display_label(candidate["framework_status"]))
                badges[1].metric("Evidence", _display_label(candidate["evidence_status"]))
                badges[2].metric("Report year", ", ".join(map(str, candidate["years"])) or "not supplied")
                st.write(f"Industry: {candidate['industry']}")
                st.write(f"PDF pages indexed: {', '.join(map(str, candidate['pdf_pages']))}")
                st.caption(
                    "Authority: " + ", ".join(_display_label(value) for value in candidate["authority_classes"])
                )

    with framework_tab:
        st.subheader("Reporting-framework verification")
        st.caption(
            "Issuer-specific evidence is required. Form 20-F, country, exchange, issuer "
            "name, and IFRS terminology are not sufficient on their own."
        )
        for candidate in result.candidates:
            with st.container(border=True):
                st.markdown(f"#### {candidate['company']}")
                st.write(f"Status: {_display_label(candidate['framework_status'])}")
                st.write("Current local metadata only; no issuer-specific framework confirmation is added by this run.")
        if not result.candidates:
            st.info("No candidate framework verification applies to this run.")

    with comparison_tab:
        st.subheader("Comparability assessment")
        st.caption(
            "Ratings use explicit dimensions. Shared IFRS 9 or ECL terminology alone is not enough."
        )
        if not result.comparability:
            st.info("Comparability could not be assessed from the available evidence.")
        for assessment in result.comparability:
            with st.expander(
                f"{assessment['company']} · {assessment['rating']} · score {assessment['weighted_score']:.3f}"
            ):
                rows = [
                    {
                        "dimension": name.replace("_", " "),
                        "score": detail["score"],
                        "reason": detail["reason"],
                    }
                    for name, detail in assessment["dimensions"].items()
                ]
                st.dataframe(rows, width="stretch", hide_index=True)
                st.caption(assessment["caution"])
    with evidence_tab:
        st.subheader("Retrieved company-disclosure evidence")
        st.caption(
            "Source bodies remain local, are collapsed by default, and are excluded from planner/API payloads and trace downloads."
        )
        if not result.retrieved_evidence:
            st.info("No local evidence was selected for the research handoff.")
        evidence_scores = {
            item["chunk_id"]: item.get("score")
            for item in result.handoff.get("evidence", [])
        }
        for item in result.retrieved_evidence:
            score = evidence_scores.get(item["chunk_id"])
            label = f"{item['chunk_id']} · {_display_label(item['authority_class'])}"
            if score is not None:
                label += f" · BM25 retrieval score {score:.3f}"
            with st.expander(label):
                st.write(
                    f"Source: {item['source_id'] or 'not supplied in corpus'} · "
                    f"PDF page: {item['pdf_page'] or 'not applicable'}"
                )
                st.write(f"Entity: {item['company']} · Year: {item['year'] or 'not supplied'}")
                st.caption(f"Source authority label: {item['authority_level']}")
                st.write(item["text"])
                st.caption("Local preview only. Retrieval does not grant permission for model submission.")
    with authority_tab:
        st.subheader("Authority and company-practice boundary")
        st.success(authority_status["status_message"])
        authority_rows = [
            {"source level": "IFRS Standard / official authority", "status": "structured cards indexed", "permitted use": "Authoritative research starting point; verify source and applicability"},
            {"source level": "IFRS Foundation supporting or educational material", "status": "structured cards indexed", "permitted use": "Implementation context; never labelled as Standard text"},
            {"source level": "Professional interpretation", "status": "not indexed", "permitted use": "Obtain separately when needed"},
            {"source level": "Company disclosure", "status": "available locally or as recorded metadata", "permitted use": "Comparable practice only; cannot establish an IFRS requirement"},
        ]
        st.dataframe(authority_rows, width="stretch", hide_index=True)
        with st.expander("Company-lane authority check"):
            st.caption(
                "This preserved result describes authority classes inside the frozen company-disclosure corpus. "
                "The Gate 6.1 official registry is separate and does not mutate that corpus."
            )
            st.json(
                {
                    key: value for key, value in result.authority.items()
                    if key != "required_message"
                }
            )
        st.subheader("Missing evidence and limitations")
        remaining_missing_evidence = [
            item for item in result.missing_evidence
            if item != "IFRS_FOUNDATION_OFFICIAL"
        ]
        if remaining_missing_evidence:
            for item in remaining_missing_evidence:
                st.markdown(f"- {_display_label(item)}")
        else:
            st.info("No additional evidence request was recorded, subject to human review.")
        if result.guardrails_triggered:
            st.subheader("Guardrails triggered")
            for item in result.guardrails_triggered:
                st.markdown(f"- {_display_label(item)}")

    with review_tab:
        st.subheader("Research handoff")
        st.markdown("#### 1. What official IFRS sources indicate")
        for card in authority_cards:
            with st.container(border=True):
                st.markdown(f"**{card.display_title}**")
                if card.paragraph_reference != "pending":
                    st.caption(f"Verified IFRS 9 paragraph reference: {card.paragraph_reference}")
                st.write(card.non_verbatim_verified_summary)
                st.markdown(f"[Official source]({card.official_url})")
                st.caption(card.display_source_type)
        st.markdown("#### 2. How comparable companies disclosed similar exposures")
        _render_company_handoff(result, final_snapshot["recorded_candidates"])
        st.markdown("#### Evidence gaps / limitations")
        st.write("Full IFRS Standard text is not indexed.")
        for gap in result.handoff["authority_coverage"]["instrument_specific_authority_gaps"]:
            st.warning(gap)
        st.write(result.handoff["abstention"])
        st.write("Professional interpretation is not indexed.")
        if scenario_route["instrument"] == "development_loans" and scenario_route["in_scope"]:
            st.write("Allied_REIT reporting framework remains unverified.")
        st.write("Comparable-company disclosures do not themselves establish IFRS requirements.")
        st.markdown("#### Auditor judgement / further review required")
        st.error("Auditor judgement / further review required.")
        st.subheader("Run status")
        if result.mode != "model-planned bounded agent":
            st.caption("Current run: deterministic fallback; no live model planning is claimed.")
        else:
            st.caption(f"Current run: bounded model planning using {result.planner_model}.")
        st.caption("Recorded Gate 4.6 and Gate 5.1 live-model results are shown separately in Evaluation.")
        status_cols = st.columns(4)
        status_cols[0].metric("Steps", f"{result.step_count}/{result.step_limit}")
        status_cols[1].metric(
            "Planner tokens", result.planner_input_tokens + result.planner_output_tokens
        )
        status_cols[2].metric("Provider cost", f"US${result.provider_cost_usd:.6f}")
        status_cols[3].metric("Approx. latency", f"{result.approximate_latency_ms:.1f} ms")

    with evaluation_tab:
        if scenario_route["in_scope"] and scenario_route["instrument"] == "development_loans":
            with st.expander("Historical property-development discovery — Gate 5.1 (not current results)"):
                _render_historical_discovery(final_snapshot["recorded_candidates"])
                caveat = final_snapshot["gate51_integrity_caveat"]
                st.caption(caveat["correction"] + " No second live external-discovery run was performed.")
        st.subheader("Historical fixed-corpus retrieval results")
        st.write(metrics["source_note"])
        st.caption(
            "Holdout n = 38. These frozen company-report retrieval results are separate "
            "from all later agent-workflow evaluations and were not recomputed or tuned in Gate 6."
        )
        cols = st.columns(4)
        cols[0].metric("BM25 Hit@1", f"{metrics['bm25']['hit_at_1']:.1%}")
        cols[1].metric("BM25 Hit@5", f"{metrics['bm25']['hit_at_5']:.1%}")
        cols[2].metric("Semantic Hit@1", f"{metrics['semantic']['hit_at_1']:.1%}")
        cols[3].metric("Semantic Hit@5", f"{metrics['semantic']['hit_at_5']:.1%}")
        st.caption(metrics["labels_note"] + " " + metrics["immutability_note"])

        st.subheader("Recorded model and API-cost summary")
        st.dataframe(_display_rows(final_snapshot["model_cost_summary"]), width="stretch", hide_index=True)
        reduction = final_snapshot["gate5_to_gate51_input_token_reduction"]
        st.caption(
            f"Gate 5 → Gate 5.1 input-token reduction: {reduction['tokens']:,} "
            f"tokens ({reduction['percent']:.2f}%). Provider-reported API cost is not "
            "total cost-to-serve and excludes engineering, infrastructure, and human review."
        )


if __name__ == "__main__":
    main()
