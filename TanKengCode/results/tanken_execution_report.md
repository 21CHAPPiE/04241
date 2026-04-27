# Tanken 6.4 Execution Summary

## Run Overview

- Command: `python project/run_tanken_demo.py all`
- Tests: `python -m pytest project/tests`
- Result directory: `project/results/`

## Core Execution Flow

All scenarios now run through the same project execution path:

1. Load reservoir bootstrap through the provider layer.
2. Build the runtime scenario from case config, event rows, and rule context.
3. Execute the in-process tool chain:
   - `get_reservoir_status`
   - `query_dispatch_rules`
   - `optimize_release_plan`
   - `simulate_dispatch_program`
   - `evaluate_dispatch_result`
4. Apply project post/report plugins when configured.
5. Save per-case JSON and regenerate the summary report.

## Workflow Verification

The deterministic Agno workflow now drives the same fixed MCP chain through the project-local entrypoint:

- Workflow command: `pyresops-tanken-workflow --case-id 6.4.1`
- Batch workflow command: `pyresops-tanken-workflow --case-id all`
- Internal MCP command: `uv run python -m project.tanken_mcp_server`
- Workflow tests: `uv run pytest project/tests/test_tanken_agno_workflow.py project/tests/test_tanken_mcp_server.py -q`

- Verified on: `2026-04-24`

- `uv run pyresops-tanken-workflow --case-id 6.4.1`: `passed`
- `uv run pyresops-tanken-workflow --case-id all`: `passed`
- `uv run pytest project/tests/test_tanken_agno_workflow.py project/tests/test_tanken_mcp_server.py -q`: `passed`

## Scenario Table

| Case | Input file | Step hours | Main conclusion |
| --- | --- | ---: | --- |
| 6.4.1 | `2024072617.csv` | 3 | Pre-release triggered, target level 156.5 m, recommended release 1272.095 m3/s |
| 6.4.2 | `2024061623.csv` | 3 | Recommended Plan A - Conservative, release 3462.691 m3/s |
| 6.4.3 | `2024072617_with_pred.csv` | 3 | 3 rolling updates, final release 448.704 m3/s |
| 6.4.4 | `2024061623.csv` | 3 | Emergency band 162.84m-163.54m, cap 9270.0 m3/s |

## 6.4.1 Pre-release trigger and alert demonstration

- Input file: `E:\PyCode\PyResOps\data\flood_event\2024072617.csv`
- Current level: `157.5` m
- Step size: `3` h
- Tool chain: `status -> rules -> optimize -> simulate -> evaluate`
- Pre-release triggered: `True`
- Target control level: `156.5` m
- Recommended release: `1272.095` m3/s, overall score `72.1049`
- Baseline final level: `157.132` m, recommended final level: `156.5` m

Known gaps:
- Cases 6.4.1, 6.4.2, and 6.4.4 still rely on historical flood processes as forecast-proxy inputs.

## 6.4.2 Release plan generation and comparison demonstration

- Input file: `E:\PyCode\PyResOps\data\flood_event\2024061623.csv`
- Current level: `160.6` m
- Step size: `3` h
- Tool chain: `status -> rules -> optimize -> simulate -> evaluate`
- Recommended plan: `Plan A - Conservative`
- Recommended release: `3462.691` m3/s
- Plan A - Conservative: release `3462.691` m3/s, score `77.0911`, downstream safe `True`
- Plan B - Balanced: release `3011.036` m3/s, score `76.5716`, downstream safe `True`
- Plan C - Constraint-first: release `2559.381` m3/s, score `75.9046`, downstream safe `True`
- Post plugin: `tanken_hecheng_downstream`

Known gaps:
- Cases 6.4.1, 6.4.2, and 6.4.4 still rely on historical flood processes as forecast-proxy inputs.
- Hecheng interval inflow is still estimated heuristically in project scope.

## 6.4.3 Dynamic dispatch update demonstration

- Input file: `E:\PyCode\PyResOps\data\2024072617_with_pred.csv`
- Current level: `156.8` m
- Step size: `3` h
- Tool chain: `status -> rules -> optimize -> simulate -> evaluate`
- Forecast case: `2024072617_with_pred.csv`
- Prediction column: `predict`
- T0: window `8`, release `468.672` m3/s, MAE `24.887` m3/s, instruction delta `Initial dispatch instruction generated.`
- T1: window `16`, release `246.075` m3/s, MAE `64.925` m3/s, instruction delta `Decrease release recommendation`
- T2: window `24`, release `448.704` m3/s, MAE `61.0` m3/s, instruction delta `Increase release recommendation`
- Report plugin: `tanken_forecast_error_summary` + `tanken_case_report`

Known gaps:
- Cases 6.4.1, 6.4.2, and 6.4.4 still rely on historical flood processes as forecast-proxy inputs.
- Only one forecast-enabled sample is currently connected: 2024072617_with_pred.csv.

## 6.4.4 Emergency dispatch under communication isolation

- Input file: `E:\PyCode\PyResOps\data\flood_event\2024061623.csv`
- Current level: `162.9` m
- Step size: `3` h
- Tool chain: `status -> rules -> optimize -> simulate -> evaluate`
- Emergency band: `162.84m-163.54m`
- Recommended release: `2508.8` m3/s
- Downstream safe: `True`, max downstream flow `3197.2` m3/s
- Constraint violation count: `0`
- Post plugin: `tanken_hecheng_downstream`

Known gaps:
- Cases 6.4.1, 6.4.2, and 6.4.4 still rely on historical flood processes as forecast-proxy inputs.

## Reliability Note

- The project flow is reliable enough for internal demonstration and scenario walkthroughs.
- It is not yet strong enough to support strong claims about forecast realism or operational deployment.
- The remaining limitations are listed per case above and should be closed before external delivery.
