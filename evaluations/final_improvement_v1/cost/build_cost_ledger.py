"""Consolidate recorded provider usage without pricing assumptions or recomputation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = Path(__file__).resolve().parent / "cost_ledger_v1.json"
GROUNDING_PATH = PROJECT_ROOT / "evaluations/final_improvement_v1/grounding/live_results_v1.json"
SOURCE_PATHS = {
    "submission_snapshot": PROJECT_ROOT / "data/public_demo/final_submission_snapshot_v01.json",
    "gate45": PROJECT_ROOT / "docs/GATE45_LIVE_PLANNER_AUDIT_v01.json",
    "gate46": PROJECT_ROOT / "docs/GATE46_LIVE_PLANNER_AUDIT_v01.json",
    "gate5": PROJECT_ROOT / "docs/GATE5_LIVE_DISCOVERY_AUDIT_v01.json",
    "gate51": PROJECT_ROOT / "docs/GATE51_LIVE_DISCOVERY_AUDIT_v01.json",
    "gate4_fallback": PROJECT_ROOT / "docs/GATE4_FLAGSHIP_TRACE_v01.json",
    "grounding_v2": GROUNDING_PATH,
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, Any]:
    snapshot = _load(SOURCE_PATHS["submission_snapshot"])
    gate45 = _load(SOURCE_PATHS["gate45"])
    gate46 = _load(SOURCE_PATHS["gate46"])
    gate5 = _load(SOURCE_PATHS["gate5"])
    gate51 = _load(SOURCE_PATHS["gate51"])
    fallback = _load(SOURCE_PATHS["gate4_fallback"])
    grounding = _load(SOURCE_PATHS["grounding_v2"])

    call_records = []
    for case in gate45["cases"]:
        for call in case["sanitized_planner_exchanges"]:
            call_records.append(
                {
                    "stage": "Gate 4.5 live planner",
                    "scenario_id": case["case_id"],
                    "call_number": call["request_number"],
                    "input_tokens": call["input_tokens"],
                    "output_tokens": call["output_tokens"],
                    "provider_reported_cost_usd": call["provider_reported_cost_usd"],
                    "source": "recorded call-level provider usage",
                }
            )
    for case in gate46["cases"]:
        for call in case["planner_calls"]:
            call_records.append(
                {
                    "stage": "Gate 4.6 live planner",
                    "scenario_id": case["case_id"],
                    "call_number": call["call"],
                    "input_tokens": call["input_tokens"],
                    "output_tokens": call["output_tokens"],
                    "provider_reported_cost_usd": call["provider_reported_cost_usd"],
                    "source": "recorded call-level provider usage",
                }
            )
    for number, record in enumerate(grounding["records"], 1):
        call_records.append(
            {
                "stage": "Generation grounding v2",
                "scenario_id": record["case_id"],
                "call_number": number,
                "input_tokens": record["usage"]["input_tokens"],
                "output_tokens": record["usage"]["output_tokens"],
                "provider_reported_cost_usd": record["usage"]["provider_reported_cost_usd"],
                "source": "recorded call-level provider usage",
            }
        )

    historical_pilot = next(
        row for row in snapshot["model_cost_summary"] if row["stage"] == "Generation pilot"
    )
    scenario_records = [
        {
            "stage": "Historical generation pilot",
            "scenario_id": "historical-single-call-pilot",
            "completed": True,
            "input_tokens": historical_pilot["input_tokens"],
            "output_tokens": historical_pilot["output_tokens"],
            "provider_reported_cost_usd": historical_pilot["provider_reported_api_cost_usd"],
            "model_call_count": 1,
            "qualification": "Historical reported result; source prompts and outputs unavailable.",
        }
    ]
    for case in gate45["cases"]:
        scenario_records.append(
            {
                "stage": "Gate 4.5 live planner",
                "scenario_id": case["case_id"],
                "completed": str(case["acceptance"]).startswith("passed"),
                "input_tokens": case["usage"]["input_tokens"],
                "output_tokens": case["usage"]["output_tokens"],
                "provider_reported_cost_usd": case["usage"]["provider_reported_cost_usd"],
                "model_call_count": len(case["sanitized_planner_exchanges"]),
                "qualification": case["acceptance"],
            }
        )
    for case in gate46["cases"]:
        scenario_records.append(
            {
                "stage": "Gate 4.6 live planner",
                "scenario_id": case["case_id"],
                "completed": bool(case["live_model_completed_without_fallback"]),
                "input_tokens": case["usage"]["input_tokens"],
                "output_tokens": case["usage"]["output_tokens"],
                "provider_reported_cost_usd": case["usage"]["provider_reported_cost_usd"],
                "model_call_count": len(case["planner_calls"]),
                "qualification": "controller-governed workflow completed",
            }
        )
    scenario_records.extend(
        [
            {
                "stage": "Gate 5 live discovery",
                "scenario_id": "single-flagship-run",
                "completed": bool(gate5["live_model_completed_without_fallback"]),
                "input_tokens": gate5["planner_usage"]["input_tokens"],
                "output_tokens": gate5["planner_usage"]["output_tokens"],
                "provider_reported_cost_usd": gate5["planner_usage"]["provider_reported_cost_usd"],
                "model_call_count": None,
                "qualification": "Scenario aggregate only; call-level token and cost records were not preserved.",
            },
            {
                "stage": "Gate 5.1 live discovery",
                "scenario_id": "single-ifrs-targeted-run",
                "completed": bool(gate51["live_model_completed_without_fallback"]),
                "input_tokens": gate51["planner_usage"]["gate51_input_tokens"],
                "output_tokens": gate51["planner_usage"]["gate51_output_tokens"],
                "provider_reported_cost_usd": gate51["planner_usage"]["gate51_provider_cost_usd"],
                "model_call_count": None,
                "qualification": "Scenario aggregate only; call-level token and cost records were not preserved.",
            },
        ]
    )
    for record in grounding["records"]:
        scenario_records.append(
            {
                "stage": "Generation grounding v2",
                "scenario_id": record["case_id"],
                "completed": True,
                "input_tokens": record["usage"]["input_tokens"],
                "output_tokens": record["usage"]["output_tokens"],
                "provider_reported_cost_usd": record["usage"]["provider_reported_cost_usd"],
                "model_call_count": 1,
                "qualification": "Structural run complete; manual factual grounding review pending.",
            }
        )

    completed_model_scenarios = [row for row in scenario_records if row["completed"]]
    reconciliations = []
    for stage in (
        "Gate 4.5 live planner",
        "Gate 4.6 live planner",
        "Generation grounding v2",
    ):
        calls = [row for row in call_records if row["stage"] == stage]
        scenarios = [row for row in scenario_records if row["stage"] == stage]
        call_totals = {
            "input_tokens": sum(row["input_tokens"] for row in calls),
            "output_tokens": sum(row["output_tokens"] for row in calls),
            "provider_reported_cost_usd": round(
                sum(row["provider_reported_cost_usd"] for row in calls), 10
            ),
        }
        scenario_totals = {
            "input_tokens": sum(row["input_tokens"] for row in scenarios),
            "output_tokens": sum(row["output_tokens"] for row in scenarios),
            "provider_reported_cost_usd": round(
                sum(row["provider_reported_cost_usd"] for row in scenarios), 10
            ),
        }
        reconciliations.append(
            {
                "stage": stage,
                "call_totals": call_totals,
                "scenario_totals": scenario_totals,
                "matches": call_totals == scenario_totals,
            }
        )
    deterministic = [
        {
            "stage": "Gate 4 flagship deterministic fallback",
            "scenario_count": 1,
            "model_calls": 0,
            "input_tokens": fallback["planner_input_tokens"],
            "output_tokens": fallback["planner_output_tokens"],
            "provider_reported_cost_usd": fallback["provider_cost_usd"],
        },
        {
            "stage": "Post-hardening eight-scenario offline regression",
            "scenario_count": 8,
            "model_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "provider_reported_cost_usd": 0.0,
        },
    ]
    return {
        "evaluation_id": "cost_consolidation_v1",
        "status": "retrospective consolidation of actual provider-reported records",
        "pricing_assumptions_used": False,
        "estimated_savings_reported": False,
        "source_artifacts": {
            name: {
                "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": _sha256(path),
            }
            for name, path in SOURCE_PATHS.items()
        },
        "per_model_call": {
            "records": call_records,
            "record_count": len(call_records),
            "coverage_note": "Call-level records are available for Gate 4.5, Gate 4.6 and grounding v2. Gate 5 and Gate 5.1 remain scenario aggregates; no per-call values were invented.",
        },
        "per_research_scenario": {
            "records": scenario_records,
            "completed_scenario_count": len(completed_model_scenarios),
            "failed_or_partial_scenario_count": sum(
                not row["completed"] for row in scenario_records
            ),
        },
        "call_to_scenario_reconciliation": reconciliations,
        "deterministic_fallback": deterministic,
        "observed_overhead_and_optimisation": [
            {
                "comparison": "Gate 4.5 to Gate 4.6",
                "input_token_reduction": 6677,
                "input_token_reduction_percent": 35.77,
                "qualification": "Recorded aggregate comparison; Gate 4.6 also changed controller behavior.",
            },
            {
                "comparison": "Gate 5 to Gate 5.1",
                "input_token_reduction": gate51["planner_usage"]["input_token_reduction"],
                "input_token_reduction_percent": gate51["planner_usage"]["input_token_reduction_percent"],
                "provider_cost_reduction_usd": gate51["planner_usage"]["cost_reduction_usd"],
                "qualification": "Recorded aggregate comparison; not a pricing estimate and not a controlled performance experiment.",
            },
            {
                "comparison": "Grounding v2 bounded request design",
                "model_calls": grounding["aggregate_usage"]["model_calls"],
                "retries": 0,
                "qualification": "One call per case, only case-relevant approved notes, temperature zero and a 220-token output cap. No counterfactual savings are claimed.",
            },
        ],
        "cost_boundary": "Provider-reported API cost excludes local compute, engineering, storage, governance, source licensing and human review.",
    }


def main() -> None:
    result = build()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "call_level_records": result["per_model_call"]["record_count"],
                "completed_model_scenarios": result["per_research_scenario"]["completed_scenario_count"],
                "failed_or_partial_scenarios": result["per_research_scenario"]["failed_or_partial_scenario_count"],
                "deterministic_rows": len(result["deterministic_fallback"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
