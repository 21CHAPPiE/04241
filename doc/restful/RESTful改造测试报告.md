# RESTful 改造测试报告

## 1. 结论

本轮 `RESTful` 改造已经完成，两个项目都已形成“`REST + MCP` 双栈”能力，并完成回归测试。

最终状态：

- `HuadongCode`
  - `REST` 接口已完成
  - 现有 `MCP` 保留
  - 全量测试结果：`21 passed, 4 skipped`
- `TanKengCode`
  - `REST` 接口已完成
  - 现有 `MCP` 保留
  - 全量测试结果：`35 passed`

因此，从“功能实现 + 自动化验证”的角度看，这一轮工作已经完成。

---

## 2. 改造目标

本次改造目标是：

1. 保留原有 `MCP` 能力
2. 在两个项目上新增 `FastAPI` 风格的 `RESTful` 接口
3. 对耗时操作增加异步 `job` 机制
4. 完成 `REST + MCP` 双栈回归测试

---

## 3. 交付内容

## 3.1 HuadongCode

新增文件：

- [app/rest_api.py](</H:/0424/HuadongCode/app/rest_api.py>)
- [app/rest_jobs.py](</H:/0424/HuadongCode/app/rest_jobs.py>)
- [app/rest_server.py](</H:/0424/HuadongCode/app/rest_server.py>)
- [tests/test_rest_api.py](</H:/0424/HuadongCode/tests/test_rest_api.py>)

调整文件：

- [app/core/trained_models.py](</H:/0424/HuadongCode/app/core/trained_models.py>)
- [agents/huadong_workflow.py](</H:/0424/HuadongCode/agents/huadong_workflow.py>)
- [tests/test_huadong_agno_workflow_contract.py](</H:/0424/HuadongCode/tests/test_huadong_agno_workflow_contract.py>)
- [pyproject.toml](</H:/0424/HuadongCode/pyproject.toml>)

新增脚本入口：

- `huadong-rest`

## 3.2 TanKengCode

新增文件：

- [tanken_rest_api.py](</H:/0424/TanKengCode/tanken_rest_api.py>)
- [tanken_rest_jobs.py](</H:/0424/TanKengCode/tanken_rest_jobs.py>)
- [tanken_rest_server.py](</H:/0424/TanKengCode/tanken_rest_server.py>)
- [tests/test_tanken_rest_api.py](</H:/0424/TanKengCode/tests/test_tanken_rest_api.py>)

调整文件：

- [agents/tanken_workflow.py](</H:/0424/TanKengCode/agents/tanken_workflow.py>)
- [project/__init__.py](</H:/0424/TanKengCode/project/__init__.py>)
- [pyproject.toml](</H:/0424/TanKengCode/pyproject.toml>)

新增脚本入口：

- `pyresops-tanken-rest`

---

## 4. REST 接口范围

## 4.1 HuadongCode REST 接口

### 同步接口

- `GET /health`
- `POST /dataset/profile`
- `POST /model-assets/profile`
- `POST /train-model-bundle`
- `POST /forecast`
- `POST /analysis`
- `POST /ensemble`
- `POST /correction`
- `POST /risk`
- `POST /warning`

### 异步接口

- `POST /training/jobs`
- `POST /calibration/jobs`
- `POST /hpo/jobs`
- `POST /lifecycle-smoke/jobs`
- `GET /jobs/{job_id}`

## 4.2 TanKengCode REST 接口

### 同步接口

- `GET /health`
- `GET /cases`
- `GET /cases/{case_id}`
- `POST /cases/{case_id}/status`
- `POST /cases/{case_id}/rules`
- `POST /cases/{case_id}/optimize`
- `POST /cases/{case_id}/simulate`
- `POST /cases/{case_id}/evaluate`

### 异步接口

- `POST /cases/{case_id}/run-jobs`
- `POST /cases/run-all-jobs`
- `GET /jobs/{job_id}`

---

## 5. 测试执行情况

## 5.1 HuadongCode

### 新增 REST 测试

文件：

- [tests/test_rest_api.py](</H:/0424/HuadongCode/tests/test_rest_api.py>)

覆盖内容：

- `health` 检查
- 数据集 profile
- 模型资产 profile
- 模型训练包构建
- `forecast -> analysis -> ensemble -> correction -> risk -> warning` 整链
- 异步任务接口：
  - `training`
  - `calibration`
  - `hpo`
  - `lifecycle-smoke`

### 全量测试结果

```text
21 passed, 4 skipped
```

说明：

- `21 passed`：当前核心功能和新增 REST 层都通过
- `4 skipped`：原有仓库中预留的契约测试跳过项，不是本次改造引入的问题

## 5.2 TanKengCode

### 新增 REST 测试

文件：

- [tests/test_tanken_rest_api.py](</H:/0424/TanKengCode/tests/test_tanken_rest_api.py>)

覆盖内容：

- `health`
- `cases` 列表
- 场景详情
- 单场景状态、规则、优化、仿真、评估
- 单场景运行异步任务
- 全场景运行异步任务

### 全量测试结果

```text
35 passed
```

说明：

- 现有 `MCP`
- 现有 workflow
- 新增 REST
- 新增 job 查询

全部已经一起通过。

---

## 6. 关键技术调整说明

## 6.1 双栈保留

本次不是“用 REST 替换 MCP”，而是：

- 原有 `MCP` 保留
- 新增 `REST`

优点：

- 现有 Agent / Workflow 不需要全部推翻
- 外部系统可以直接走 HTTP
- 内部智能编排仍可以继续走 MCP

## 6.2 异步任务机制

对耗时较长的操作，新增了轻量本地 `job` 机制。

### Job 返回结构示例

```json
{
  "job_id": "8d8b8a8f...",
  "status": "queued",
  "submitted_at": "2026-04-25T17:20:00+00:00",
  "started_at": null,
  "completed_at": null,
  "operation": "training",
  "input": {},
  "result": null,
  "error": null
}
```

### 主要字段中文说明

- `job_id`
  - 任务唯一编号，用于后续查询
- `status`
  - 任务状态，可能是：
    - `queued`：已提交，排队中
    - `running`：执行中
    - `completed`：执行完成
    - `failed`：执行失败
- `submitted_at`
  - 提交时间
- `started_at`
  - 开始执行时间
- `completed_at`
  - 完成时间
- `operation`
  - 本次任务的业务类型，例如 `training`、`run-case:6.4.2`
- `input`
  - 任务输入参数快照
- `result`
  - 成功时的结果
- `error`
  - 失败时的错误信息

## 6.3 Workflow 默认 MCP 启动方式修正

为了避免以前 `uv run` 带来的环境与 Python 解释器问题，本次把工作流默认子进程入口调整为：

- `python -m app.server`
- `python -m project.tanken_mcp_server`

并保证当前解释器目录优先进入 `PATH`。

这一步是让现有 `Agno workflow` 更稳定，不是 REST 功能本身的一部分，但它直接影响双栈回归是否能通过。

## 6.4 TanKengCode 任务锁调整

`TanKengCode` 的异步 `job` 查询中，增加了可重入锁，避免 Windows 文件替换瞬间读写冲突。

主要解决的问题是：

- job 文件正在更新时被轮询读取
- Windows 下 `replace/read` 时间窗口导致 `PermissionError`

---

## 7. 主要返回值说明

## 7.1 HuadongCode 同步接口返回值

大多数同步接口最终都返回类似结构：

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

### 字段中文说明

- `status`
  - 执行状态，正常应为 `completed`
- `operation`
  - 当前操作名称，例如 `forecast`、`ensemble`
- `run_id`
  - 本次运行唯一编号
- `run_dir`
  - 该次执行的产物目录
- `output_manifest_path`
  - 本次执行的 manifest 文件路径
- `artifact_paths`
  - 各类产物路径集合
- `small_summary`
  - 面向人阅读的简短结果摘要

## 7.2 TanKengCode 同步接口返回值

### 例 1：状态接口

```json
{
  "scenario_id": "6.4.1",
  "current_level_m": 157.5,
  "current_inflow_m3s": 1234.0,
  "forecast_inflow_m3s": 2345.0,
  "forecast_sequence_summary": {}
}
```

主要字段中文说明：

- `scenario_id`
  - 场景编号
- `current_level_m`
  - 当前库水位，单位米
- `current_inflow_m3s`
  - 当前入流，单位立方米每秒
- `forecast_inflow_m3s`
  - 预测入流，单位立方米每秒
- `forecast_sequence_summary`
  - 预测序列摘要

### 例 2：优化接口

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

主要字段中文说明：

- `program_id`
  - 本次调度程序编号
- `selected_module_type`
  - 选中的调度模块类型
- `selected_module_parameters`
  - 该模块的参数
- `avg_release_m3s`
  - 平均下泄流量
- `final_level_m`
  - 仿真末水位

### 例 3：整场景运行结果

```json
{
  "case_id": "6.4.2",
  "kind": "plan_compare",
  "decision_summary": {},
  "candidate_plans": [],
  "simulation_evidence": {},
  "alerts": []
}
```

主要字段中文说明：

- `case_id`
  - 场景编号
- `kind`
  - 场景类型，例如 `plan_compare`
- `decision_summary`
  - 决策摘要，是最终最重要的业务结论
- `candidate_plans`
  - 候选方案列表
- `simulation_evidence`
  - 仿真证据
- `alerts`
  - 告警信息

---

## 8. 风险与已知限制

本轮交付已经完成，但有几项边界需要明确：

1. 当前 `RESTful v1` 使用的是“文件路径输入”，不是上传文件模式
2. 异步任务是本地文件型 job 系统，不是数据库/消息队列型任务中心
3. 本次保留 MCP，不是协议迁移
4. `HuadongCode` 的旧 `API文档.md` 仍然写着 FastAPI/routers，和当前真实代码不一致，需要后续统一文档

---

## 9. 最终判定

从当前代码、接口、自动化测试结果来看：

```text
本轮 RESTful 改造与双栈回归工作已经完成。
```

完成标准已满足：

- 两个项目都新增了 `RESTful` 接口
- 两个项目都保留了原有 `MCP`
- `HuadongCode` 全量回归通过
- `TanKengCode` 全量回归通过
- 新增 `REST` 测试通过
- 主要返回值与任务机制都已稳定

文档位置：

- `H:\0424\doc\restful\RESTful改造测试报告.md`
