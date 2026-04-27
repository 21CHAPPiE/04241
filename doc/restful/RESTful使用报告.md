# RESTful 使用报告

## 1. 目标

本报告用于说明：

1. 两个项目现在怎么启动 `RESTful` 服务
2. 主要接口怎么调用
3. 输入输出怎么放
4. 主要返回值是什么意思

本报告面向实际使用和联调，不展开实现细节。

---

## 2. 总体说明

两个项目现在都是“双栈”：

- 一套 `RESTful`
- 一套 `MCP`

你可以按场景选择：

- 如果是外部系统、前端、脚本、HTTP 调用：用 `REST`
- 如果是 Agent、LLM 工具调用：继续用 `MCP`

---

## 3. HuadongCode 使用说明

## 3.1 启动方式

在项目目录下启动：

```powershell
uv run huadong-rest
```

或者：

```powershell
uv run python -m app.rest_server
```

默认监听：

- `host`: `0.0.0.0`
- `port`: `8000`

如果配置文件未改，访问地址一般是：

```text
http://localhost:8000
```

## 3.2 HuadongCode 主要接口

### 健康检查

```http
GET /health
```

返回示例：

```json
{
  "status": "ok",
  "service": "huadong-rest",
  "protocol": "rest",
  "mcp_compatibility": "preserved"
}
```

字段中文说明：

- `status`
  - 服务状态
- `service`
  - 服务名
- `protocol`
  - 当前访问协议
- `mcp_compatibility`
  - 是否保留了 MCP 兼容

### 数据集概况

```http
POST /dataset/profile
```

请求示例：

```json
{
  "dataset_path": "H:\\0424\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\dataset",
  "options": {}
}
```

主要字段中文说明：

- `dataset_path`
  - 输入数据文件路径
- `output_root`
  - 输出目录
- `options`
  - 额外参数

### 模型资产概况

```http
POST /model-assets/profile
```

请求示例：

```json
{
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\assets",
  "options": {}
}
```

### 预测

```http
POST /forecast
```

请求示例：

```json
{
  "dataset_path": "H:\\0424\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\forecast",
  "options": {}
}
```

输出中最重要的值：

- `artifact_paths.forecast`
  - 预测结果 CSV
- `artifact_paths.forecast_metrics`
  - 指标 JSON
- `small_summary`
  - 简要说明

### 数据分析

```http
POST /analysis
```

请求示例：

```json
{
  "dataset_path": "H:\\0424\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\analysis",
  "options": {
    "column": "streamflow"
  }
}
```

### 集合预测

```http
POST /ensemble
```

请求示例：

```json
{
  "file_path": "H:\\0424\\doc\\restful\\outputs\\huadong\\forecast\\...\\forecast.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\ensemble",
  "options": {
    "method": "bma",
    "observation_dataset": "H:\\0424\\HuadongCode\\data\\basin_001_hourly.csv",
    "observation_column": "streamflow"
  }
}
```

字段中文说明：

- `file_path`
  - 上一步生成的预测 CSV
- `method`
  - 集成方法，这里通常用 `bma`
- `observation_dataset`
  - 观测数据路径
- `observation_column`
  - 观测列名

### 误差订正

```http
POST /correction
```

请求示例：

```json
{
  "file_path": "H:\\0424\\doc\\restful\\outputs\\huadong\\ensemble\\...\\ensemble.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\correction",
  "options": {
    "observation_dataset": "H:\\0424\\HuadongCode\\data\\basin_001_hourly.csv",
    "observation_column": "streamflow"
  }
}
```

### 风险分析

```http
POST /risk
```

请求示例：

```json
{
  "file_path": "H:\\0424\\doc\\restful\\outputs\\huadong\\correction\\...\\corrected.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\risk",
  "options": {
    "thresholds": {
      "flood": 300.0,
      "severe": 500.0
    },
    "model_columns": [
      "corrected_forecast"
    ]
  }
}
```

### 预警

```http
POST /warning
```

请求示例：

```json
{
  "file_path": "H:\\0424\\doc\\restful\\outputs\\huadong\\correction\\...\\corrected.csv",
  "output_root": "H:\\0424\\doc\\restful\\outputs\\huadong\\warning",
  "options": {
    "forecast_column": "corrected_forecast",
    "warning_threshold": 300.0,
    "lead_time_hours": 24
  }
}
```

### 异步训练类接口

这些接口不会直接返回最终结果，而是先返回任务：

- `POST /training/jobs`
- `POST /calibration/jobs`
- `POST /hpo/jobs`
- `POST /lifecycle-smoke/jobs`

然后用：

```http
GET /jobs/{job_id}
```

查询结果。

## 3.3 HuadongCode 返回值说明

同步接口统一返回：

```json
{
  "status": "completed",
  "operation": "forecast",
  "run_id": "20260425T080348Z-f746c7ec",
  "run_dir": "H:\\0424\\...\\forecast\\20260425T080348Z-f746c7ec",
  "output_manifest_path": "H:\\0424\\...\\manifest.json",
  "artifact_paths": {
    "forecast": "H:\\0424\\...\\forecast.csv",
    "summary": "H:\\0424\\...\\summary.txt",
    "forecast_metrics": "H:\\0424\\...\\forecast_metrics.json",
    "manifest": "H:\\0424\\...\\manifest.json"
  },
  "small_summary": "Forecasted 96 steps with 4 models..."
}
```

中文说明：

- `status`
  - 执行状态
- `operation`
  - 当前功能名称
- `run_id`
  - 本次执行编号
- `run_dir`
  - 产物目录
- `output_manifest_path`
  - manifest 文件路径
- `artifact_paths`
  - 所有输出文件路径集合
- `small_summary`
  - 对本次运行的简短文字总结

## 3.4 HuadongCode 推荐使用顺序

最常见流程：

1. `/dataset/profile`
2. `/model-assets/profile`
3. `/forecast`
4. `/ensemble`
5. `/correction`
6. `/risk`
7. `/warning`

如果要做训练类流程：

1. `/training/jobs`
2. `/jobs/{job_id}`

---

## 4. TanKengCode 使用说明

## 4.1 启动方式

在项目目录下启动：

```powershell
uv run pyresops-tanken-rest
```

或者：

```powershell
uv run python -m project.tanken_rest_server
```

默认监听：

- `host`: `0.0.0.0`
- `port`: `8001`

访问地址一般是：

```text
http://localhost:8001
```

## 4.2 TanKengCode 主要接口

### 健康检查

```http
GET /health
```

返回示例：

```json
{
  "status": "ok",
  "service": "tanken-rest",
  "protocol": "rest",
  "mcp_compatibility": "preserved"
}
```

### 场景列表

```http
GET /cases
```

主要返回：

- `cases`
- `count`
- `recommended_step_sequence`

中文说明：

- `cases`
  - 场景定义列表
- `count`
  - 场景数量
- `recommended_step_sequence`
  - 推荐的调用顺序

### 场景详情

```http
GET /cases/{case_id}
```

示例：

```http
GET /cases/6.4.3
```

主要返回：

- `case_id`
- `section_title`
- `kind`
- `description`
- `default_event`
- `preferred_modules`
- `prediction_column`

### 查询状态

```http
POST /cases/{case_id}/status
```

请求示例：

```json
{
  "event_csv_path": "H:\\0424\\TanKengCode\\data\\flood_event\\2024072617.csv",
  "reservoir_config_path": null
}
```

### 查询规则

```http
POST /cases/{case_id}/rules
```

请求示例：

```json
{
  "event_csv_path": "H:\\0424\\TanKengCode\\data\\flood_event\\2024072617.csv"
}
```

### 优化调度方案

```http
POST /cases/{case_id}/optimize
```

请求示例：

```json
{
  "event_csv_path": "H:\\0424\\TanKengCode\\data\\flood_event\\2024072617.csv",
  "horizon_hours": 0,
  "requested_module_type": "",
  "min_flow": 50.0,
  "max_flow": 0.0,
  "control_interval_seconds": 0
}
```

### 仿真

```http
POST /cases/{case_id}/simulate
```

请求示例：

```json
{
  "event_csv_path": "H:\\0424\\TanKengCode\\data\\flood_event\\2024072617.csv",
  "target_outflow": 2283.657,
  "module_type": "constant_release",
  "module_parameters": {
    "target_release": 2283.657
  }
}
```

### 评估

```http
POST /cases/{case_id}/evaluate
```

请求示例：

```json
{
  "event_csv_path": "H:\\0424\\TanKengCode\\data\\flood_event\\2024072617.csv",
  "target_outflow": 2283.657,
  "module_type": "constant_release",
  "module_parameters": {
    "target_release": 2283.657
  },
  "eco_min_flow": 50.0
}
```

### 单场景运行任务

```http
POST /cases/{case_id}/run-jobs
```

请求示例：

```json
{
  "event_csv_path": "H:\\0424\\TanKengCode\\data\\flood_event\\2024061623.csv",
  "persist_result": false
}
```

### 全场景运行任务

```http
POST /cases/run-all-jobs
```

请求示例：

```json
{
  "reservoir_config_path": null,
  "persist_result": false
}
```

### 查询任务

```http
GET /jobs/{job_id}
```

## 4.3 TanKengCode 返回值说明

### 状态接口返回示例

```json
{
  "scenario_id": "6.4.1",
  "current_level_m": 157.5,
  "current_inflow_m3s": 1234.0,
  "forecast_inflow_m3s": 2345.0,
  "forecast_sequence_summary": {
    "step_count": 8,
    "first_inflow_m3s": 1234.0,
    "max_inflow_m3s": 5678.0,
    "min_inflow_m3s": 1000.0
  }
}
```

字段中文说明：

- `scenario_id`
  - 当前场景编号
- `current_level_m`
  - 当前库水位，单位米
- `current_inflow_m3s`
  - 当前入流，单位立方米每秒
- `forecast_inflow_m3s`
  - 当前预测入流
- `forecast_sequence_summary`
  - 预测序列摘要

### 优化接口返回示例

```json
{
  "scenario_id": "6.4.1",
  "program_id": "6.4.1_optimized",
  "selected_module_type": "constant_release",
  "selected_module_parameters": {
    "target_release": 2283.657
  },
  "avg_release_m3s": 2283.657,
  "final_level_m": 156.3
}
```

字段中文说明：

- `program_id`
  - 本次调度程序 ID
- `selected_module_type`
  - 被选中的调度模块类型
- `selected_module_parameters`
  - 该模块参数
- `avg_release_m3s`
  - 平均下泄流量
- `final_level_m`
  - 仿真末水位

### 场景运行结果返回示例

```json
{
  "case_id": "6.4.2",
  "kind": "plan_compare",
  "decision_summary": {
    "recommended_plan": "Plan B"
  },
  "candidate_plans": [],
  "simulation_evidence": {},
  "alerts": []
}
```

字段中文说明：

- `case_id`
  - 场景编号
- `kind`
  - 场景类型
- `decision_summary`
  - 最终决策摘要，最重要
- `candidate_plans`
  - 候选方案列表
- `simulation_evidence`
  - 仿真证据
- `alerts`
  - 告警列表

### 异步任务返回结构

跟 `HuadongCode` 一致，主要是：

- `job_id`
- `status`
- `submitted_at`
- `started_at`
- `completed_at`
- `operation`
- `input`
- `result`
- `error`

---

## 5. 输入输出怎么放

## 5.1 HuadongCode

输入通常是：

- `dataset_path`
- `file_path`
- `output_root`
- `options`

推荐输出目录：

```text
H:\0424\doc\restful\outputs\huadong\
```

例如：

- `...\\dataset`
- `...\\forecast`
- `...\\ensemble`
- `...\\correction`
- `...\\risk`
- `...\\warning`

## 5.2 TanKengCode

输入通常是：

- `case_id`
- `event_csv_path`
- `reservoir_config_path`
- `target_outflow`
- `module_type`
- `module_parameters`

推荐输出目录：

- 场景结果仍由项目内部按既有逻辑管理
- 如果需要单独整理，可后续再给 `persist_result=true` 时指定独立存储策略

---

## 6. 推荐联调顺序

## 6.1 HuadongCode

推荐顺序：

1. `GET /health`
2. `POST /dataset/profile`
3. `POST /model-assets/profile`
4. `POST /forecast`
5. `POST /ensemble`
6. `POST /correction`
7. `POST /risk`
8. `POST /warning`

## 6.2 TanKengCode

推荐顺序：

1. `GET /health`
2. `GET /cases`
3. `GET /cases/{case_id}`
4. `POST /cases/{case_id}/status`
5. `POST /cases/{case_id}/rules`
6. `POST /cases/{case_id}/optimize`
7. `POST /cases/{case_id}/simulate`
8. `POST /cases/{case_id}/evaluate`
9. `POST /cases/{case_id}/run-jobs`

---

## 7. 最终说明

现在两个项目都已经具备：

- 面向 HTTP 的 `RESTful` 调用方式
- 面向 Agent 的 `MCP` 调用方式

因此后续可以按调用方分流：

- 外部系统、联调平台、前端：走 `REST`
- Agent、LLM 工具调用：走 `MCP`

文档位置：

- `H:\0424\doc\restful\RESTful使用报告.md`
