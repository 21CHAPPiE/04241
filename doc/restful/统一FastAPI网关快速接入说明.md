# 统一 FastAPI 网关快速接入说明

## 1. 这是什么

这是一个**统一 FastAPI 网关服务**，把两个项目合并到一个 HTTP 服务里：

- `HuadongCode`
  - 路径前缀：`/huadong`
- `TanKengCode`
  - 路径前缀：`/tanken`

也就是说：

- 只需要启动**一个服务**
- 通过不同路径访问两个项目的能力

---

## 2. 项目位置

统一网关项目在：

- [UnifiedGateway](</H:/0424/UnifiedGateway>)

相关文档和示例在：

- [统一FastAPI网关部署与使用说明.md](</H:/0424/doc/restful/统一FastAPI网关部署与使用说明.md>)
- [接口示例包_README.md](</H:/0424/doc/restful/接口示例包_README.md>)

接口示例目录：

- `H:\0424\doc\restful\examples\gateway`
- `H:\0424\doc\restful\examples\huadong`
- `H:\0424\doc\restful\examples\tanken`

---

## 3. 如何启动

## 3.1 进入目录

```powershell
cd H:\0424\UnifiedGateway
```

## 3.2 安装依赖

```powershell
uv sync
```

## 3.3 启动服务

推荐命令：

```powershell
uv run unified-rest
```

也可以直接用模块启动：

```powershell
uv run python -m gateway.server
```

---

## 4. 启动地址和端口

默认配置：

- `Host`: `0.0.0.0`
- `Port`: `8010`

默认访问地址：

```text
http://localhost:8010
```

### 常用地址

- 网关根地址
  - `http://localhost:8010/`
- 网关健康检查
  - `http://localhost:8010/health`
- 华东功能健康检查
  - `http://localhost:8010/huadong/health`
- 滩坑功能健康检查
  - `http://localhost:8010/tanken/health`

### 如果要改地址或端口

可以设置环境变量：

```powershell
$env:UNIFIED_REST_HOST='127.0.0.1'
$env:UNIFIED_REST_PORT='9000'
uv run unified-rest
```

---

## 5. 访问规则

## 5.1 HuadongCode

所有华东水文相关接口都走：

```text
/huadong/...
```

例如：

- `POST /huadong/dataset/profile`
- `POST /huadong/forecast`
- `POST /huadong/analysis`
- `POST /huadong/ensemble`
- `POST /huadong/correction`
- `POST /huadong/risk`
- `POST /huadong/warning`
- `POST /huadong/training/jobs`
- `GET /huadong/jobs/{job_id}`

## 5.2 TanKengCode

所有滩坑调度相关接口都走：

```text
/tanken/...
```

例如：

- `GET /tanken/cases`
- `GET /tanken/cases/{case_id}`
- `POST /tanken/cases/{case_id}/status`
- `POST /tanken/cases/{case_id}/rules`
- `POST /tanken/cases/{case_id}/optimize`
- `POST /tanken/cases/{case_id}/simulate`
- `POST /tanken/cases/{case_id}/evaluate`
- `POST /tanken/cases/{case_id}/run-jobs`
- `GET /tanken/jobs/{job_id}`

---

## 6. 如何对接 API

## 6.1 同步接口怎么调

同步接口特点：

- `POST` 发送 JSON 请求体
- 直接返回最终结果

例如华东预测接口：

```http
POST /huadong/forecast
```

请求体示例见：

- [forecast.request.jsonc](</H:/0424/doc/restful/examples/huadong/forecast.request.jsonc>)

响应体示例见：

- [forecast.response.jsonc](</H:/0424/doc/restful/examples/huadong/forecast.response.jsonc>)

例如滩坑优化接口：

```http
POST /tanken/cases/6.4.1/optimize
```

请求体示例见：

- [optimize.request.jsonc](</H:/0424/doc/restful/examples/tanken/optimize.request.jsonc>)

响应体示例见：

- [optimize.response.jsonc](</H:/0424/doc/restful/examples/tanken/optimize.response.jsonc>)

## 6.2 异步接口怎么调

异步接口特点：

1. 先提交任务
2. 返回 `job_id`
3. 再轮询查询结果

### 华东训练任务示例

提交：

```http
POST /huadong/training/jobs
```

请求体示例：

- [training-job.request.jsonc](</H:/0424/doc/restful/examples/huadong/training-job.request.jsonc>)

第一跳返回示例：

- [training-job.submit.response.jsonc](</H:/0424/doc/restful/examples/huadong/training-job.submit.response.jsonc>)

查询：

```http
GET /huadong/jobs/{job_id}
```

完成态返回示例：

- [training-job.completed.response.jsonc](</H:/0424/doc/restful/examples/huadong/training-job.completed.response.jsonc>)

### 滩坑场景运行任务示例

提交：

```http
POST /tanken/cases/6.4.2/run-jobs
```

请求体示例：

- [run-case-job.request.jsonc](</H:/0424/doc/restful/examples/tanken/run-case-job.request.jsonc>)

第一跳返回示例：

- [run-case-job.submit.response.jsonc](</H:/0424/doc/restful/examples/tanken/run-case-job.submit.response.jsonc>)

查询：

```http
GET /tanken/jobs/{job_id}
```

完成态返回示例：

- [run-case-job.completed.response.jsonc](</H:/0424/doc/restful/examples/tanken/run-case-job.completed.response.jsonc>)

---

## 7. 请求参数怎么理解

## 7.1 Huadong 常见参数

Huadong 常见请求字段：

- `dataset_path`
  - 原始数据文件路径
- `file_path`
  - 上一步生成的结果文件路径
- `output_root`
  - 输出目录
- `options`
  - 额外参数对象

简单理解：

- 第一步通常用 `dataset_path`
- 后续串联常用 `file_path`

例如：

1. `/huadong/forecast`
   - 传 `dataset_path`
2. `/huadong/ensemble`
   - 传 `file_path=forecast.csv`
3. `/huadong/correction`
   - 传 `file_path=ensemble.csv`

## 7.2 Tanken 常见参数

Tanken 常见请求字段：

- `case_id`
  - 场景编号，通常写在 URL 上
- `event_csv_path`
  - 事件过程文件路径
- `reservoir_config_path`
  - 水库配置文件路径
- `target_outflow`
  - 目标下泄流量
- `module_type`
  - 调度模块类型
- `module_parameters`
  - 模块参数
- `persist_result`
  - 是否将结果落盘

简单理解：

- 先确定场景：例如 `/tanken/cases/6.4.1/...`
- 再传该场景使用的事件文件

---

## 8. 返回值怎么理解

## 8.1 Huadong 返回值

Huadong 的同步接口大多返回统一结构：

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

你重点看：

- `status`
  - 是否成功
- `artifact_paths`
  - 结果文件路径
- `small_summary`
  - 简要说明

## 8.2 Tanken 返回值

Tanken 的同步接口更偏业务结果。

例如状态接口：

- `scenario_id`
- `current_level_m`
- `current_inflow_m3s`
- `forecast_inflow_m3s`

例如优化接口：

- `selected_module_type`
- `selected_module_parameters`
- `avg_release_m3s`
- `final_level_m`

例如评估接口：

- `overall_score`
- `flood_control_score`
- `water_supply_score`
- `power_generation_score`
- `ecological_score`
- `constraint_violations_count`

你重点看：

- 当前状态
- 选中的方案
- 综合评分

## 8.3 异步任务返回值

异步接口第一跳统一返回：

- `job_id`
- `status`
- `operation`
- `input`
- `result`
- `error`

规则是：

- 第一次提交后，`result` 通常是 `null`
- 轮询 `GET /.../jobs/{job_id}` 后
  - 如果完成，`result` 里才是最终业务结果

---

## 9. 最常见的对接流程

## 9.1 如果你要接华东水文预测

推荐流程：

1. `GET /huadong/health`
2. `POST /huadong/dataset/profile`
3. `POST /huadong/model-assets/profile`
4. `POST /huadong/forecast`
5. `POST /huadong/ensemble`
6. `POST /huadong/correction`
7. `POST /huadong/risk`
8. `POST /huadong/warning`

## 9.2 如果你要接滩坑调度

推荐流程：

1. `GET /tanken/health`
2. `GET /tanken/cases`
3. `GET /tanken/cases/{case_id}`
4. `POST /tanken/cases/{case_id}/status`
5. `POST /tanken/cases/{case_id}/rules`
6. `POST /tanken/cases/{case_id}/optimize`
7. `POST /tanken/cases/{case_id}/simulate`
8. `POST /tanken/cases/{case_id}/evaluate`
9. `POST /tanken/cases/{case_id}/run-jobs`

---

## 10. 示例文件怎么用

推荐你按下面方式看示例：

### 网关基础

- [root.response.jsonc](</H:/0424/doc/restful/examples/gateway/root.response.jsonc>)
- [health.response.jsonc](</H:/0424/doc/restful/examples/gateway/health.response.jsonc>)

### Huadong 示例

- [dataset-profile.request.jsonc](</H:/0424/doc/restful/examples/huadong/dataset-profile.request.jsonc>)
- [dataset-profile.response.jsonc](</H:/0424/doc/restful/examples/huadong/dataset-profile.response.jsonc>)
- [forecast.request.jsonc](</H:/0424/doc/restful/examples/huadong/forecast.request.jsonc>)
- [forecast.response.jsonc](</H:/0424/doc/restful/examples/huadong/forecast.response.jsonc>)
- [ensemble.request.jsonc](</H:/0424/doc/restful/examples/huadong/ensemble.request.jsonc>)
- [warning.response.jsonc](</H:/0424/doc/restful/examples/huadong/warning.response.jsonc>)
- [training-job.submit.response.jsonc](</H:/0424/doc/restful/examples/huadong/training-job.submit.response.jsonc>)
- [training-job.completed.response.jsonc](</H:/0424/doc/restful/examples/huadong/training-job.completed.response.jsonc>)

### Tanken 示例

- [cases.response.jsonc](</H:/0424/doc/restful/examples/tanken/cases.response.jsonc>)
- [case-detail.response.jsonc](</H:/0424/doc/restful/examples/tanken/case-detail.response.jsonc>)
- [status.request.jsonc](</H:/0424/doc/restful/examples/tanken/status.request.jsonc>)
- [status.response.jsonc](</H:/0424/doc/restful/examples/tanken/status.response.jsonc>)
- [rules.response.jsonc](</H:/0424/doc/restful/examples/tanken/rules.response.jsonc>)
- [optimize.request.jsonc](</H:/0424/doc/restful/examples/tanken/optimize.request.jsonc>)
- [optimize.response.jsonc](</H:/0424/doc/restful/examples/tanken/optimize.response.jsonc>)
- [run-case-job.submit.response.jsonc](</H:/0424/doc/restful/examples/tanken/run-case-job.submit.response.jsonc>)
- [run-case-job.completed.response.jsonc](</H:/0424/doc/restful/examples/tanken/run-case-job.completed.response.jsonc>)
- [run-all-jobs.completed.response.jsonc](</H:/0424/doc/restful/examples/tanken/run-all-jobs.completed.response.jsonc>)

---

## 11. 一句话总结

现在你只要记住三件事：

1. 启动统一服务：

```powershell
cd H:\0424\UnifiedGateway
uv run unified-rest
```

2. 默认地址：

```text
http://localhost:8010
```

3. 路径切换：

- 华东功能：`/huadong/...`
- 滩坑功能：`/tanken/...`

文档位置：

- `H:\0424\doc\restful\统一FastAPI网关快速接入说明.md`
