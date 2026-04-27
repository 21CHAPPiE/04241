# Huadong 预测过程参数传递说明

## 1. 文档目标

本文档专门总结 `HuadongCode` 在统一网关模式下的**预测过程参数传递**，回答以下问题：

1. 预测主链的每个模块分别是什么
2. 每个模块的输入参数和输出参数是什么
3. 下一个模块如何拿到上一个模块的结果
4. 哪些模块是主链必经步骤，哪些模块是扩展步骤
5. 像 `file_path` 这样的路径参数是否应该改成数组，或者用其他方式传参

本文档只聚焦 `Huadong` 预测过程，不包含 `TanKengCode` 调度链，也不展开训练、率定、HPO 等异步训练类接口。

---

## 2. 对外接入方式

对外统一连接：

- `UnifiedGateway`

默认地址：

```text
http://localhost:8010
```

预测相关接口统一走：

```text
/huadong/...
```

最小健康检查：

- `GET /health`
- `GET /huadong/health`

这意味着外部系统不需要直接连接 `HuadongCode` 子项目，只需要通过统一网关访问 `/huadong/...` 前缀即可。

---

## 3. 预测过程的总链路

## 3.1 核心主链

当前项目中，预测过程的核心主链为：

```text
dataset/profile
-> model-assets/profile
-> forecast
-> ensemble
-> correction
```

这条链的作用分别是：

1. `dataset/profile`
   - 校验输入数据是否可读、结构是否正确
2. `model-assets/profile`
   - 校验模型资产是否可用
3. `forecast`
   - 生成多模型预测结果
4. `ensemble`
   - 对预测结果做集成
5. `correction`
   - 对集成结果做误差订正

## 3.2 扩展模块

在核心主链之外，还有 3 个常见扩展模块：

- `analysis`
  - 直接读取原始输入数据，做趋势/周期/突变分析
- `risk`
  - 读取订正后的结果文件，做风险分析
- `warning`
  - 读取订正后的结果文件，做预警分析

扩展关系可以理解为：

```text
dataset/profile -> analysis
correction -> risk
correction -> warning
```

因此：

- `analysis` 不是 `forecast -> ensemble -> correction` 主链的必经输入
- `risk` 和 `warning` 是订正后的下游消费模块

---

## 4. 统一请求和统一响应结构

## 4.1 统一请求结构

从代码看，华东侧最常用的请求结构是：

```json
{
  "dataset_path": "string | null",
  "file_path": "string | null",
  "output_root": "string | null",
  "options": {}
}
```

字段含义：

- `dataset_path`
  - 原始输入数据文件路径
- `file_path`
  - 上一步已经生成的产物文件路径
- `output_root`
  - 当前模块输出目录
- `options`
  - 当前模块的扩展参数

补充：

- `model-assets/profile` 使用的是简化结构，只需要：

```json
{
  "output_root": "string | null",
  "options": {}
}
```

## 4.2 统一同步响应结构

同步接口最终都收敛为统一结构：

```json
{
  "status": "completed",
  "operation": "forecast",
  "run_id": "20260425T080348Z-f746c7ec",
  "run_dir": "H:\\04241\\...\\forecast\\20260425T080348Z-f746c7ec",
  "output_manifest_path": "H:\\04241\\...\\manifest.json",
  "artifact_paths": {
    "forecast": "H:\\04241\\...\\forecast.csv",
    "summary": "H:\\04241\\...\\summary.txt",
    "forecast_metrics": "H:\\04241\\...\\forecast_metrics.json",
    "manifest": "H:\\04241\\...\\manifest.json"
  },
  "small_summary": "..."
}
```

统一字段含义：

- `status`
  - 执行状态
- `operation`
  - 当前模块名称
- `run_id`
  - 本次执行编号
- `run_dir`
  - 当前步骤产物目录
- `output_manifest_path`
  - 当前步骤 manifest 文件
- `artifact_paths`
  - 当前步骤产物集合
- `small_summary`
  - 适合日志或界面显示的简短总结

最关键的规则是：

```text
上下游参数传递，主要依赖 artifact_paths。
```

---

## 5. 模块逐项输入输出与参数传递

## 5.1 `POST /huadong/dataset/profile`

### 作用

- 检查输入数据文件是否可读
- 输出数据模式、字段、行数等基本信息

### 典型输入

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\dataset",
  "options": {}
}
```

### 关键输入字段

- `dataset_path`
  - 原始流域数据文件
- `output_root`
  - 本步产物目录

### 典型输出

```json
{
  "status": "completed",
  "operation": "dataset-profile",
  "artifact_paths": {
    "dataset_profile": "...\\dataset_profile.json",
    "summary": "...\\summary.txt",
    "manifest": "...\\manifest.json"
  }
}
```

### 输出产物说明

- `artifact_paths.dataset_profile`
  - 数据集概况 JSON
- `artifact_paths.summary`
  - 文字摘要

### 下一个模块怎么接

这一步通常**不把** `dataset_profile.json` 传给下一步。

正确理解是：

- `dataset/profile` 的作用是“校验和理解输入”
- `forecast`、`analysis` 等下一步仍然继续使用原始 `dataset_path`

因此这里的连接方式是：

```text
dataset/profile 校验成功
-> 后续模块继续使用同一个 dataset_path
```

---

## 5.2 `POST /huadong/model-assets/profile`

### 作用

- 检查模型资产包是否存在
- 查看可用模型资产概况

### 典型输入

```json
{
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\assets",
  "options": {}
}
```

### 典型输出

```json
{
  "status": "completed",
  "operation": "model-asset-profile",
  "artifact_paths": {
    "model_assets_profile": "...\\model_assets_profile.json",
    "summary": "...\\summary.txt",
    "manifest": "...\\manifest.json"
  }
}
```

### 输出产物说明

- `artifact_paths.model_assets_profile`
  - 模型资产概况 JSON

### 下一个模块怎么接

和 `dataset/profile` 一样，这一步的作用是“确认模型资产存在且可用”，不是把 `model_assets_profile.json` 当作下一步输入。

因此连接方式是：

```text
model-assets/profile 校验成功
-> forecast 继续使用原始 dataset_path
```

---

## 5.3 `POST /huadong/forecast`

### 作用

- 读取原始流域数据
- 生成多模型预测结果

### 典型输入

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast",
  "options": {}
}
```

### 关键输入字段

- `dataset_path`
  - 核心输入数据
- `output_root`
  - 预测产物目录

### 典型输出

```json
{
  "status": "completed",
  "operation": "forecast",
  "artifact_paths": {
    "forecast": "...\\forecast.csv",
    "summary": "...\\summary.txt",
    "forecast_metrics": "...\\forecast_metrics.json",
    "manifest": "...\\manifest.json"
  }
}
```

### 输出产物说明

- `artifact_paths.forecast`
  - 预测结果主文件
- `artifact_paths.forecast_metrics`
  - 各模型指标 JSON

### `forecast.csv` 中包含什么

从实现看，`forecast.csv` 主要包含以下列：

- `timestamp`
- `rainfall`
- `pet`
- `observed`
- `forecast_xinanjiang`
- `forecast_gr4j`
- `forecast_rf`
- `forecast_lstm`

### 下一个模块怎么接

`ensemble` 读取的不是原始 `dataset_path`，而是这一步产出的：

```json
{
  "file_path": "<forecast.artifact_paths.forecast>"
}
```

也就是说：

```text
forecast.artifact_paths.forecast
-> ensemble.file_path
```

---

## 5.4 `POST /huadong/analysis`

### 作用

- 读取原始输入数据
- 对指定列做趋势、周期、突变分析

### 典型输入

```json
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\analysis",
  "options": {
    "column": "streamflow"
  }
}
```

### 典型输出

```json
{
  "status": "completed",
  "operation": "data-analysis",
  "artifact_paths": {
    "analysis": "...\\data_analysis.json",
    "summary": "...\\summary.txt",
    "manifest": "...\\manifest.json"
  }
}
```

### 输出产物说明

- `artifact_paths.analysis`
  - 包含 `trend`、`cycle`、`mutation`

### 下一个模块怎么接

`analysis` 是**旁路分析模块**，不作为 `forecast -> ensemble -> correction` 主链输入。

因此它的作用是：

- 为业务说明提供解释性结果
- 但不会把产物传回主链

也就是说：

```text
dataset_path
-> analysis
-> 输出分析结论
```

而不是：

```text
analysis -> forecast
```

---

## 5.5 `POST /huadong/ensemble`

### 作用

- 读取 `forecast.csv`
- 对多模型结果做集成

### 典型输入

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

### 关键输入字段

- `file_path`
  - 必须指向 `forecast.csv`
- `options.method`
  - 集成方法，如 `bma`
- `options.observation_dataset`
  - 用于权重更新的观测数据
- `options.observation_column`
  - 常见为 `streamflow`

### 典型输出

```json
{
  "status": "completed",
  "operation": "ensemble",
  "artifact_paths": {
    "ensemble": "...\\ensemble.csv",
    "summary": "...\\summary.txt",
    "ensemble_details": "...\\ensemble_details.json",
    "manifest": "...\\manifest.json"
  }
}
```

### 输出产物说明

- `artifact_paths.ensemble`
  - 集成结果主文件
- `artifact_paths.ensemble_details`
  - 权重、筛选、集成细节

### `ensemble.csv` 中包含什么

从实现看，`ensemble.csv` 至少包含：

- `index`
- `timestamp`（若原文件含时间列）
- `ensemble_forecast`

### 下一个模块怎么接

`correction` 读取的就是这一步返回的：

```json
{
  "file_path": "<ensemble.artifact_paths.ensemble>"
}
```

也就是说：

```text
forecast.artifact_paths.forecast
-> ensemble.file_path
-> ensemble.artifact_paths.ensemble
-> correction.file_path
```

---

## 5.6 `POST /huadong/correction`

### 作用

- 读取 `ensemble.csv`
- 结合观测数据做误差订正

### 典型输入

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

### 关键输入字段

- `file_path`
  - 必须指向 `ensemble.csv`
- `options.observation_dataset`
  - 观测数据文件
- `options.observation_column`
  - 观测列名

### 典型输出

```json
{
  "status": "completed",
  "operation": "correction",
  "artifact_paths": {
    "correction": "...\\corrected.csv",
    "summary": "...\\summary.txt",
    "correction_details": "...\\correction_details.json",
    "manifest": "...\\manifest.json"
  }
}
```

### 输出产物说明

- `artifact_paths.correction`
  - 订正后的主结果文件
- `artifact_paths.correction_details`
  - 误差指标和订正说明

### `corrected.csv` 中包含什么

从实现看，`corrected.csv` 至少包含：

- `index`
- `timestamp`（若可识别）
- `ensemble_forecast`
- `observed`
- `corrected_forecast`

### 下一个模块怎么接

`risk` 和 `warning` 都继续消费这一步返回的：

```json
{
  "file_path": "<correction.artifact_paths.correction>"
}
```

也就是说：

```text
correction.artifact_paths.correction
-> risk.file_path
correction.artifact_paths.correction
-> warning.file_path
```

---

## 5.7 `POST /huadong/risk`

### 作用

- 读取订正结果文件
- 根据阈值和指定列生成风险分析

### 典型输入

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

### 关键输入字段

- `file_path`
  - 指向 `corrected.csv`
- `options.thresholds`
  - 风险阈值字典
- `options.model_columns`
  - 默认常用 `["corrected_forecast"]`

### 典型输出

```json
{
  "status": "completed",
  "operation": "risk",
  "artifact_paths": {
    "risk": "...\\risk.json",
    "summary": "...\\summary.txt",
    "manifest": "...\\manifest.json"
  }
}
```

### 下一个模块怎么接

`risk` 一般作为终端消费模块，通常不会继续回流到主链。

---

## 5.8 `POST /huadong/warning`

### 作用

- 读取订正结果文件
- 根据阈值和预警提前量生成预警结果

### 典型输入

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

### 关键输入字段

- `file_path`
  - 指向 `corrected.csv`
- `options.forecast_column`
  - 一般为 `corrected_forecast`
- `options.warning_threshold`
  - 预警阈值
- `options.lead_time_hours`
  - 提前量

### 典型输出

```json
{
  "status": "completed",
  "operation": "warning",
  "artifact_paths": {
    "warning": "...\\warning.json",
    "summary": "...\\summary.txt",
    "manifest": "...\\manifest.json"
  }
}
```

### 下一个模块怎么接

`warning` 一般也是终端消费模块，不再继续作为下游主链输入。

---

## 6. 核心参数传递规则总结

## 6.1 主链真实传递对象

当前预测主链中，真正发生上下游传递的关键对象如下：

| 上游模块 | 上游输出字段 | 下游模块 | 下游输入字段 |
| --- | --- | --- | --- |
| `forecast` | `artifact_paths.forecast` | `ensemble` | `file_path` |
| `ensemble` | `artifact_paths.ensemble` | `correction` | `file_path` |
| `correction` | `artifact_paths.correction` | `risk` | `file_path` |
| `correction` | `artifact_paths.correction` | `warning` | `file_path` |

## 6.2 非文件传递关系

有两步不是“产物文件传递”模式：

### 1. `dataset/profile`

- 用于校验输入
- 不把 `dataset_profile.json` 传给主链
- 后续继续使用原始 `dataset_path`

### 2. `model-assets/profile`

- 用于校验模型资产
- 不把 `model_assets_profile.json` 传给主链
- 后续继续使用原始 `dataset_path`

### 3. `analysis`

- 是从原始 `dataset_path` 分叉出来的分析模块
- 输出分析结论
- 不反向喂给 `forecast / ensemble / correction`

---

## 7. 为什么文档中的 `...\\corrected.csv` 不能直接传

像下面这种写法：

```json
"file_path": "H:\\0424\\doc\\restful\\outputs\\huadong\\correction\\...\\corrected.csv"
```

只是**文档示意**，不是可直接复制的真实路径。

原因是：

- `run_id` 是运行时动态生成的
- 真正的目录结构里会包含时间戳和随机后缀

因此正确做法不是手工拼路径，而是：

1. 调上一步接口
2. 从返回 JSON 中读取 `artifact_paths`
3. 直接把该真实路径传给下一步

正确衔接方式示例：

```json
{
  "file_path": "<correction 返回中的 artifact_paths.correction>"
}
```

---

## 8. `file_path` 是否应该改成数组

## 8.1 当前结论

对当前项目，**不建议**把 `file_path` 或 `dataset_path` 直接改成数组。

原因如下：

### 1. 当前每个模块只消费一个主输入文件

例如：

- `ensemble` 只吃一个 `forecast.csv`
- `correction` 只吃一个 `ensemble.csv`
- `risk` / `warning` 只吃一个 `corrected.csv`

如果改成数组，会引入语义不清的问题：

- 数组里每个文件分别是什么
- 模块是按顺序取值还是按类型取值
- 文件数量必须是多少

### 2. 当前主链适合显式衔接

当前主链最大的优点是：

- 上一步产物明确
- 下一步输入明确
- 排障简单

这套设计非常适合联调、自动编排和日志追踪。

---

## 8.2 更推荐的替代方式

如果后续真的需要多输入，推荐两种扩展方式：

### 方案 A：具名对象

例如：

```json
{
  "input_artifacts": {
    "forecast_csv": "xxx",
    "observation_csv": "yyy",
    "weights_json": "zzz"
  },
  "output_root": "..."
}
```

优点：

- 每个输入的语义明确
- 不依赖数组顺序
- 更容易做校验

### 方案 B：新建 batch 接口

例如：

```text
POST /huadong/ensemble/batch
POST /huadong/correction/batch
```

优点：

- 不破坏现有单文件接口语义
- 可以把批处理能力单独设计

---

## 8.3 对当前项目的最终建议

对当前版本，建议保持以下规则不变：

1. `dataset_path` 保持单字符串
2. `file_path` 保持单字符串
3. 上一步结果通过 `artifact_paths` 显式传递
4. 不要手工拼接带 `...` 的示意路径
5. 如果未来要多输入，优先考虑“具名对象”而不是“裸数组”

---

## 9. 推荐调用示例

## 9.1 核心主链示例

### 第一步：校验数据

```json
POST /huadong/dataset/profile
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\dataset",
  "options": {}
}
```

### 第二步：查看模型资产

```json
POST /huadong/model-assets/profile
{
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\assets",
  "options": {}
}
```

### 第三步：做预测

```json
POST /huadong/forecast
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\forecast",
  "options": {}
}
```

拿到返回：

```json
forecast.artifact_paths.forecast
```

### 第四步：做集成

```json
POST /huadong/ensemble
{
  "file_path": "<forecast.artifact_paths.forecast>",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\ensemble",
  "options": {
    "method": "bma",
    "observation_dataset": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
    "observation_column": "streamflow"
  }
}
```

拿到返回：

```json
ensemble.artifact_paths.ensemble
```

### 第五步：做订正

```json
POST /huadong/correction
{
  "file_path": "<ensemble.artifact_paths.ensemble>",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\correction",
  "options": {
    "observation_dataset": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
    "observation_column": "streamflow"
  }
}
```

拿到返回：

```json
correction.artifact_paths.correction
```

## 9.2 扩展模块示例

### 旁路分析

```json
POST /huadong/analysis
{
  "dataset_path": "H:\\04241\\HuadongCode\\data\\basin_001_hourly.csv",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\analysis",
  "options": {
    "column": "streamflow"
  }
}
```

### 基于订正结果做风险分析

```json
POST /huadong/risk
{
  "file_path": "<correction.artifact_paths.correction>",
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

### 基于订正结果做预警分析

```json
POST /huadong/warning
{
  "file_path": "<correction.artifact_paths.correction>",
  "output_root": "H:\\04241\\doc\\restful\\outputs\\huadong\\warning",
  "options": {
    "forecast_column": "corrected_forecast",
    "warning_threshold": 300.0,
    "lead_time_hours": 24
  }
}
```

---

## 10. 最终结论

当前 `Huadong` 预测过程的参数传递规则可以概括为：

```text
原始数据通过 dataset_path 进入主链，
核心产物通过 artifact_paths 在模块之间显式传递，
真正的主链文件流转为：
forecast.csv -> ensemble.csv -> corrected.csv
```

进一步地：

- `analysis` 从原始数据分叉出去，不回流主链
- `risk` 和 `warning` 继续消费 `corrected.csv`
- 当前版本不建议把 `file_path` 改成数组
- 当前最稳妥的做法是继续使用“单路径 + artifact_paths 显式衔接”
