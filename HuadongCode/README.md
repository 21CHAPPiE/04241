# Huadong Hydro Forecast

本项目提供华东水文预报 FastMCP 工具层，并额外提供一条确定性 Agno Workflow 链路，用于在无 Agent、无 LLM 推理介入的情况下执行 `experiments` 中的 6.3.x 场景逻辑。

## 安装依赖

```powershell
uv sync
```

`pyproject.toml` 已声明 `agno>=2.6.0` 和 `fastmcp>=3.2.4`。

## MCP Server

启动当前项目 MCP Server：

```powershell
uv run python -m app.server
```

脚本入口：

```powershell
uv run huadong-mcp
```

当前 MCP 工具包括：

- `dataset_profile_from_paths`
- `model_asset_profile`
- `data_analysis_from_paths`
- `forecast_from_paths`
- `ensemble_from_paths`
- `correction_from_paths`
- `risk_from_paths`
- `warning_from_paths`
- `training_from_paths`
- `calibration_from_paths`
- `hpo_from_paths`
- `lifecycle_smoke_from_paths`

## Agno Workflow

Workflow 文件位于：

- `agents/huadong_workflow.py`
- `agents/run_huadong_workflow.py`

执行单个场景：

```powershell
uv run python -m agents.run_huadong_workflow --scenario-id 6.3.1
```

执行全部场景：

```powershell
uv run python -m agents.run_huadong_workflow --scenario-id all
```

脚本入口：

```powershell
uv run huadong-agno-workflow --scenario-id 6.3.3
```

运行产物默认写入：

```text
results/agno-workflow-runs/
```

## Workflow 输入格式

```json
{
  "scenario_id": "6.3.1",
  "output_root": "results/agno-workflow-runs",
  "start_time": null,
  "end_time": null,
  "initial_end_time": null,
  "updated_end_time": null,
  "basin_dataset_path": "data/basin_001_hourly.csv",
  "multistation_dataset_path": "data/rain_15stations_flow.csv"
}
```

`scenario_id` 支持 `6.3.1`、`6.3.2`、`6.3.3`、`6.3.4`；CLI 额外支持 `all`。

## 固定调用流程

Agno Workflow 使用 `Workflow` 和 `Step` 编排，直接通过 `MCPTools(command="uv run python -m app.server")` 调用本地 MCP Server。不创建 `agno.agent.Agent`，不使用模型推理。

通用流程：

1. `prepare_inputs`：按场景时间窗口切出输入 CSV。
2. `primary_dataset_profile` -> `dataset_profile_from_paths`
3. `model_asset_profile` -> `model_asset_profile`
4. `initial_forecast` -> `forecast_from_paths`
5. `assemble_result`：汇总 `workflow_report.json` 和 `workflow_report.md`

场景扩展：

- `6.3.2` 增加 `data_analysis` -> `data_analysis_from_paths`
- `6.3.3` 增加辅助多站数据 profile、`ensemble_from_paths`、`correction_from_paths`
- `6.3.4` 先跑初始 forecast/ensemble/correction，再对新增观测窗口跑 updated forecast/ensemble/correction，并输出前后对比

## Workflow 输出格式

单场景输出顶层结构：

```json
{
  "workflow": {
    "name": "Huadong MCP Fixed Workflow",
    "mode": "deterministic_mcp_steps",
    "mcp_command": "uv run python -m app.server"
  },
  "request": {},
  "scenario_id": "6.3.1",
  "scenario_dir": "results/agno-workflow-runs/...",
  "report": {},
  "steps": {}
}
```

批量输出顶层结构：

```json
{
  "workflow": {
    "name": "Huadong MCP Fixed Workflow",
    "mode": "deterministic_mcp_steps_batch",
    "mcp_command": "uv run python -m app.server"
  },
  "scenario_ids": ["6.3.1", "6.3.2", "6.3.3", "6.3.4"],
  "results": {}
}
```

接口测试 contract 保存在：

```text
results/huadong_agno_workflow_io_contract.json
```

## 运行时 I/O 抓取

如果需要类似 `TanKengCode/results/workflow_pydantic_io_capture.json` 的完整运行时记录，使用 Python 脚本真实执行 workflow 并抓取：

```powershell
uv run python -m agents.capture_huadong_workflow_io --scenario-id all
```

脚本入口：

```powershell
uv run huadong-agno-capture --scenario-id all
```

默认输出：

```text
results/huadong_workflow_pydantic_io_capture.json
```

该文件不是大模型生成的静态文档，而是脚本运行后写出的真实 JSON，包含：

- `pydantic_models.HuadongWorkflowRequest.json_schema`
- 每个场景的 `workflow_request_json`
- `intermediate_variables_json`：场景配置、时间窗口、切片路径、运行目录等中间变量
- `tool_calls[].arguments_json`：每一步 MCP 工具调用参数
- `tool_calls[].response_json`：每一步 MCP 工具真实响应
- `step_outputs_json`：Agno workflow 每个 step 的完整输出
- `workflow_output_json`：最终 workflow 输出
