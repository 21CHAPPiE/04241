# HuadongCode API 文档

## 1. 目标

本文档用于说明当前 `HuadongCode` 项目的实际接口使用方式，重点回答：

1. 怎么启动 `RESTful` 服务
2. 主要接口怎么调用
3. 输入输出文件怎么组织
4. 主要返回值是什么意思

本文档面向实际使用和联调，不展开内部实现细节。

---

## 2. 总体说明

当前 `HuadongCode` 采用“双栈”方式运行：

- 一套 `RESTful`
- 一套 `MCP`

推荐使用方式：

- 如果是外部系统、前端、脚本、HTTP 联调：使用 `REST`
- 如果是 Agent、LLM 工具编排：继续使用 `MCP`

本文档聚焦当前真实可用的 `RESTful` 接口。

---

## 3. 启动方式

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

如果配置未改，访问地址一般是：

```text
http://localhost:8000
```

健康检查地址：

```text
http://localhost:8000/health
```

---

## 4. 主要接口

## 4.1 健康检查

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

字段说明：

- `status`
  - 服务状态
- `service`
  - 服务名称
- `protocol`
  - 当前访问协议
- `mcp_compatibility`
  - 是否保留了 MCP 兼容能力

## 4.2 数据集概况

```http
POST /dataset/profile
```

请求示例：

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\dataset",
  "options": {}
}
```

多站点数据集示例：

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\rain_15stations_flow.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\dataset-multi",
  "options": {
    "profile_type": "multistation"
  }
}
```

主要字段说明：

- `dataset_path`
  - 输入数据文件路径
- `output_root`
  - 输出目录
- `options`
  - 额外参数

## 4.3 模型资产概况

```http
POST /model-assets/profile
```

请求示例：

```json
{
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\assets",
  "options": {}
}
```

## 4.4 训练模型包

```http
POST /train-model-bundle
```

请求示例：

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\train-bundle",
  "options": {
    "max_rows": 96,
    "sequence_length": 4,
    "lstm_epochs": 1,
    "bundle_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\train-bundle\\bundle.pt"
  }
}
```

主要字段说明：

- `max_rows`
  - 训练时截取的数据行数
- `sequence_length`
  - 序列长度
- `lstm_epochs`
  - LSTM 训练轮数
- `bundle_path`
  - 训练产出的模型包路径

## 4.5 预测

```http
POST /forecast
```

请求示例：

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast",
  "options": {}
}
```

输出中最重要的值：

- `artifact_paths.forecast`
  - 预测结果 CSV
- `artifact_paths.forecast_metrics`
  - 指标 JSON
- `small_summary`
  - 简短结果说明

## 4.6 数据分析

```http
POST /analysis
```

请求示例：

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\analysis",
  "options": {
    "column": "streamflow"
  }
}
```

## 4.7 集合预测

```http
POST /ensemble
```

请求示例：

```json
{
  "file_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\...\\forecast.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\ensemble",
  "options": {
    "method": "bma",
    "observation_dataset": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
    "observation_column": "streamflow"
  }
}
```

主要字段说明：

- `file_path`
  - 上一步预测生成的 `forecast.csv`
- `method`
  - 集成方法，当前常用 `bma`
- `observation_dataset`
  - 观测数据路径
- `observation_column`
  - 观测列名

## 4.8 误差订正

```http
POST /correction
```

请求示例：

```json
{
  "file_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\ensemble\\...\\ensemble.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\correction",
  "options": {
    "observation_dataset": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
    "observation_column": "streamflow"
  }
}
```

## 4.9 风险分析

```http
POST /risk
```

请求示例：

```json
{
  "file_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\correction\\...\\corrected.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\risk",
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

主要字段说明：

- `thresholds`
  - 风险阈值配置
- `model_columns`
  - 参与风险判断的预测列

## 4.10 预警

```http
POST /warning
```

请求示例：

```json
{
  "file_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\correction\\...\\corrected.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\warning",
  "options": {
    "forecast_column": "corrected_forecast",
    "warning_threshold": 300.0,
    "lead_time_hours": 24
  }
}
```

主要字段说明：

- `forecast_column`
  - 用于预警的预测列
- `warning_threshold`
  - 预警阈值
- `lead_time_hours`
  - 预警提前量

## 4.11 异步任务接口

这些接口不会直接返回最终业务结果，而是先返回一个任务对象：

- `POST /training/jobs`
- `POST /calibration/jobs`
- `POST /hpo/jobs`
- `POST /lifecycle-smoke/jobs`

然后用下面的接口轮询任务结果：

```http
GET /jobs/{job_id}
```

异步请求示例：

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\training",
  "options": {}
}
```

---

## 5. 返回值说明

## 5.1 同步接口返回结构

大多数同步接口统一返回类似结构：

```json
{
  "status": "completed",
  "operation": "forecast",
  "run_id": "20260425T080348Z-f746c7ec",
  "run_dir": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\20260425T080348Z-f746c7ec",
  "output_manifest_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\20260425T080348Z-f746c7ec\\manifest.json",
  "artifact_paths": {
    "forecast": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\...\\forecast.csv",
    "summary": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\...\\summary.txt",
    "forecast_metrics": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\...\\forecast_metrics.json",
    "manifest": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast\\...\\manifest.json"
  },
  "small_summary": "Forecasted 96 steps with 4 models..."
}
```

字段说明：

- `status`
  - 执行状态
- `operation`
  - 当前功能名称
- `run_id`
  - 本次执行编号
- `run_dir`
  - 本次运行产物目录
- `output_manifest_path`
  - manifest 文件路径
- `artifact_paths`
  - 本次运行输出文件集合
- `small_summary`
  - 面向人的简短结果摘要

## 5.2 异步任务返回结构

异步任务提交后先返回：

```json
{
  "job_id": "8d8b8a8f...",
  "status": "queued",
  "submitted_at": "2026-04-25T17:20:00+00:00",
  "started_at": null,
  "completed_at": null,
  "operation": "training",
  "input": {
    "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
    "file_path": null,
    "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\training",
    "options": {}
  },
  "result": null,
  "error": null
}
```

任务完成后，`GET /jobs/{job_id}` 会返回完整结果。

主要字段说明：

- `job_id`
  - 任务唯一编号
- `status`
  - 任务状态，常见值为 `queued`、`running`、`completed`、`failed`
- `submitted_at`
  - 提交时间
- `started_at`
  - 开始执行时间
- `completed_at`
  - 执行完成时间
- `operation`
  - 当前任务类型
- `input`
  - 任务输入参数快照
- `result`
  - 成功后的结果
- `error`
  - 失败时的错误信息

---

## 6. 输入输出怎么放

## 6.1 常见输入字段

当前接口普遍使用路径式输入，常见字段有：

- `dataset_path`
- `file_path`
- `output_root`
- `options`

常用输入文件：

- `H:\04241\HuadongCode\data\basin_001_hourly.csv`
- `H:\04241\HuadongCode\data\rain_15stations_flow.csv`

说明：

- `dataset_path` 常用于原始数据集输入
- `file_path` 常用于接收上一步已经生成的产物文件
- `output_root` 由调用方指定输出目录
- `options` 用于补充业务参数

## 6.2 推荐输出目录

推荐把 REST 联调产物统一放在：

```text
H:\04241\doc\restful\outputs\huadong\
```

例如：

- `...\\dataset`
- `...\\dataset-multi`
- `...\\assets`
- `...\\train-bundle`
- `...\\forecast`
- `...\\analysis`
- `...\\ensemble`
- `...\\correction`
- `...\\risk`
- `...\\warning`
- `...\\training`

---

## 7. 推荐联调顺序

最常见的同步联调流程：

1. `GET /health`
2. `POST /dataset/profile`
3. `POST /model-assets/profile`
4. `POST /forecast`
5. `POST /analysis`
6. `POST /ensemble`
7. `POST /correction`
8. `POST /risk`
9. `POST /warning`

如果要补做训练能力验证，可增加：

1. `POST /train-model-bundle`

如果要联调耗时任务流程：

1. `POST /training/jobs`
2. `GET /jobs/{job_id}`

或者：

1. `POST /calibration/jobs`
2. `GET /jobs/{job_id}`

或者：

1. `POST /hpo/jobs`
2. `GET /jobs/{job_id}`

或者：

1. `POST /lifecycle-smoke/jobs`
2. `GET /jobs/{job_id}`

---

## 8. 最终说明

当前 `HuadongCode` 已具备：

- 面向 HTTP 的 `RESTful` 调用方式
- 面向 Agent 的 `MCP` 调用方式

因此后续建议按调用方分流：

- 外部系统、联调平台、前端：走 `REST`
- Agent、LLM 工具调用：走 `MCP`

文档位置：

- `H:\04241\HuadongCode\API文档.md`
