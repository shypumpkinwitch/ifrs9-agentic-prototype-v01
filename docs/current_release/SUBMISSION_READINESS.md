# PE6201 submission readiness

This checklist reflects the instructor's final announcement and the current post-hardening release. It is not the final report and does not assign predicted marks.

## Deliverable status

| Instructor requirement | Current coverage | Remaining work |
| --- | --- | --- |
| Approximately 1,200-word report (±10–15%) | Official four-heading evidence map exists in `docs/final_submission/REPORT_OUTLINE_RUBRIC_MAPPING.md`; current product/data/architecture evidence is documented under `docs/current_release/`. | Final report has not been drafted. Target range is approximately 1,020–1,380 words if applying the announced tolerance around 1,200. Confirm the instructor's preferred interpretation before final submission. |
| Approximately five-minute demo, maximum eight minutes, face and screen visible | Historical demo scripts and a current reproducible UI exist. | Video has not been recorded. Recording must show both face and screen and stay at or below eight minutes. |
| Transparent data and evaluation submission | This directory documents every evaluation layer, schemas, counts, hashes, QA protocol and reproduction. `evaluations/public_retrieval_benchmark_v1/` publishes all 50 questions and all 58 accepted mappings without report text. | Exact metrics still require the private corpus. The full exclusion-reason audit and private QA/source bundle remain restricted. |
| Clear README run instructions | Root `README.md` contains setup, application, test, privacy-audit and platform notes. | Verify commands on the final submission machine after copying the package. |
| File-level and module-level code documentation | `ARCHITECTURE_AND_MODULES.md` maps every runtime module, public surface, retained legacy module and test concern. | Inline docstrings are uneven in legacy modules; the external module map is the submission documentation and avoids changing frozen source identities. |
| Persona, Input, Output, Architecture, Target Metrics, Achieved Metrics | `PRODUCT.md` covers all six headings and keeps evaluation layers separate. | No missing section identified. |

## Recommended submission contents

Include:

- root `README.md`, `requirements.txt`, `.gitignore`, application source and tests;
- `docs/current_release/`;
- public-demo fixtures and the non-verbatim authority registry;
- sanitized evaluation cases, protocols, traces, manifests and release-verification files;
- the final report and video/link only after they are separately prepared.

Exclude:

- `private_data/` other than an empty placeholder;
- `external_runtime/` filing bodies;
- `outputs/`, caches, local virtual environments and environment files;
- `docs/GATE1_AUDIT.md`, which is protected historical evidence containing personal local paths; publish `docs/current_release/GATE1_AUDIT_PUBLIC.md` instead;
- API keys, the identifying SEC User-Agent and machine-specific paths;
- raw IFRS Standard, annual-report or SEC filing text.

## Final pre-submission commands

```powershell
& '.\.venv\Scripts\python.exe' evaluations/post_hardening_release_v1/run_release_verification.py
& '.\.venv\Scripts\python.exe' -m src.release_audit
& '.\.venv\Scripts\python.exe' -m streamlit run app.py
```

The first command is the release gate. It explicitly separates current functional/integrity tests from four preserved historical-snapshot errors. The second checks the release-eligible privacy boundary. The third supports manual UI/video review and should be stopped after use.

## Git status

No Git repository is configured in `ifrs9_agentic_prototype_v01` or its parent workspace. Consequently there is no branch, index, commit history or remote to report, and no claim can be made about staged files. This task did not initialise, commit, push or publish a repository.

Before any later publication, initialise or connect the intended repository only with explicit authorisation, inspect the exact staged file list, and use the hosting platform's secret scanning.

## Truthful presentation reminders

- Call the 50-question result a historical fixed-corpus retrieval benchmark.
- State that the grounding pilot used self-authored educational material, not private annual-report text.
- Keep Gate 4.5, Gate 4.6, Gate 5 and Gate 5.1 as separate small workflow experiments.
- State that the post-Gate-5.1 Shinhan hardening was tested offline and did not receive a second live discovery run.
- Call S01–S08 post-fix results diagnostic regression, not independent unseen-holdout performance.
- Do not report a v1.1 scenario pass rate while manual reviews are pending.
- Do not claim live planning for the current deterministic run or when planner tokens are zero.
- Keep official authority, supporting/educational material, professional interpretation and company practice visibly separate.
