# 华东水文预报特化 FastAPI 服务

## 项目概述

本项目是基于 FastAPI 的水文预报特化服务，提供完整的水文预报计算链路，包括数据分析、多模型径流预测、集合预测、风险分析、误差解释和预警触发等功能。

### 技术栈

- **框架**: FastAPI + Uvicorn
- **数据处理**: NumPy, Pandas, SciPy, statsmodels, scikit-learn
- **Python**: 3.12+

### 项目结构

```
app/
├── main.py              # FastAPI 主入口
├── config/              # 配置
│   └── settings.py
├── routers/             # API 路由
│   ├── data_analysis.py
│   ├── forecast.py
│   ├── ensemble.py
│   ├── risk.py
│   ├── error_analysis.py
│   └── warning.py
├── schemas/             # Pydantic 数据模型
│   ├── common.py
│   ├── data_analysis.py
│   ├── forecast.py
│   ├── ensemble.py
│   ├── risk.py
│   ├── error_analysis.py
│   └── warning.py
└── services/            # 业务逻辑实现
    ├── data_analysis.py
    ├── hydrological.py  # 新安江模型
    ├── ml.py            # 随机森林/LSTM
    ├── forecast.py
    ├── ensemble.py
    ├── risk.py
    ├── error_analysis.py
    └── warning.py
```

---

## API 接口文档

### 统一响应格式

所有接口返回统一的 JSON 格式：

```json
{
  "success": true,
  "message": "操作成功消息",
  "data": { /* 返回数据 */ }
}
```

---

### 一、数据分析模块

**基础路径**: `/api/v1/analysis`

#### 1.1 趋势分析

- **接口**: `POST /api/v1/analysis/trend`
- **描述**: Mann-Kendall 趋势检验 + 线性趋势拟合
- **请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| station_id | string | 是 | 站点编码 |
| timestamps | list[string] | 是 | 时间戳列表（ISO8601格式） |
| values | list[float] | 是 | 数值列表 |
| variable | string | 否 | 变量类型（streamflow/rainfall/water_level） |
| unit | string | 否 | 单位（m3/s / mm / m） |

- **响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| trend_direction | string | 趋势方向：increasing / decreasing / no_trend |
| kendall_tau | float | Kendall's τ 相关系数 [-1, 1] |
| p_value | float | 统计显著性 p 值 |
| significant | bool | 是否显著（p < 0.05） |
| slope | float | 线性趋势斜率 |
| intercept | float | 线性趋势截距 |

#### 1.2 周期分析

- **接口**: `POST /api/v1/analysis/cycle`
- **描述**: FFT 功率谱分析，提取主要周期
- **请求参数**: 同趋势分析
- **响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| dominant_period_hours | float | 主要周期（小时） |
| dominant_period_days | float | 主要周期（天） |
| top_frequencies | list[float] | 主要频率列表 |
| top_periods_hours | list[float] | 对应周期（小时）列表 |
| top_powers | list[float] | 对应功率谱密度列表 |

#### 1.3 突变检测

- **接口**: `POST /api/v1/analysis/mutation`
- **描述**: Pettitt 检验 + CUSUM 突变检测
- **请求参数**: 同趋势分析
- **响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| has_mutation | bool | 是否检测到显著突变 |
| change_point_index | int/null | 突变点索引位置 |
| change_point_timestamp | string/null | 突变点时间戳 |
| p_value | float | Pettitt 检验 p 值 |
| statistic | float | Pettitt U 统计量 |
| mean_before | float/null | 突变点前均值 |
| mean_after | float/null | 突变点后均值 |

#### 1.4 综合分析摘要

- **接口**: `POST /api/v1/analysis/summary`
- **描述**: 综合趋势、周期、突变三项分析，输出可读性摘要
- **请求参数**: 同趋势分析
- **响应参数**: 包含 trend、cycle、mutation 三个结果及 summary_text 摘要

---

### 二、径流预测模块

**基础路径**: `/api/v1/forecast`

#### 2.1 获取可用模型列表

- **接口**: `GET /api/v1/forecast/models`
- **描述**: 返回所有内置水文预测模型信息
- **响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| model_id | string | 模型标识（xinanjiang/rf/lstm） |
| name | string | 模型显示名称 |
| type | string | 模型类型（hydrological/ml/dl） |
| description | string | 模型简介 |
| available | bool | 是否可用 |
| params | dict | 主要参数说明 |

#### 2.2 多站点并行径流预测

- **接口**: `POST /api/v1/forecast/multi-station`
- **描述**: 使用指定模型并行预测多站点来水

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| stations | list[StationInput] | 是 | 各站点输入数据列表 |
| model_type | string | 否 | 模型类型（xinanjiang/rf/lstm），默认 xinanjiang |
| horizon | int | 否 | 预测步长（小时），默认 72h |
| timestep_hours | int | 否 | 时间步长（小时），默认 1h |

**StationInput**:

| 字段 | 类型 | 描述 |
|------|------|------|
| station_id | string | 站点编码 |
| timestamps | list[string] | 输入时间戳列表 |
| rainfall | list[float] | 降雨量序列 (mm/h) |
| pet | list[float] | 潜在蒸发量序列（可选） |
| streamflow_obs | list[float] | 历史实测流量（用于 RF 模型） |
| initial_state | InitialState | 模型初始状态（新安江模型专用） |

**InitialState**:

| 字段 | 类型 | 描述 |
|------|------|------|
| wu | float | 上层土壤含水量 (mm) |
| wl | float | 下层土壤含水量 (mm) |
| wd | float | 深层土壤含水量 (mm) |
| s | float | 自由水蓄水量 (mm) |
| qi | float | 壤中流初始流量 (m³/s) |
| qg | float | 地下径流初始流量 (m³/s) |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| forecast_id | string | 本次预测唯一 ID |
| model_type | string | 使用的模型类型 |
| horizon | int | 预测步长 |
| stations | list[StationForecastResult] | 各站点预测结果 |

**StationForecastResult**:

| 字段 | 类型 | 描述 |
|------|------|------|
| station_id | string | 站点编码 |
| model_type | string | 使用的模型类型 |
| forecast_timestamps | list[string] | 预测时间戳列表 |
| forecast_values | list[float] | 预测流量序列 (m³/s) |
| uncertainty | UncertaintyBand | 不确定性区间 |
| metrics | dict | 误差指标（如有观测值） |

**UncertaintyBand**:

| 字段 | 类型 | 描述 |
|------|------|------|
| lower | list[float] | 置信区间下界 |
| upper | list[float] | 置信区间上界 |
| confidence | float | 置信水平（如 0.9 表示 90%） |

---

### 三、集合预测模块

**基础路径**: `/api/v1/ensemble`

#### 3.1 加权平均集合预测

- **接口**: `POST /api/v1/ensemble/weighted-mean`
- **描述**: 对多模型预测结果进行加权平均

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[list[float]] | 是 | 多模型预测结果列表 |
| weights | list[float] | 否 | 权重列表（不提供则等权重） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| ensemble_forecast | list[float] | 加权平均后的预测序列 |
| weights_used | list[float] | 实际使用的权重 |
| n_models | int | 模型数量 |

#### 3.2 贝叶斯模型平均（BMA）

- **接口**: `POST /api/v1/ensemble/bma`
- **描述**: 使用 EM 算法进行贝叶斯模型平均，滑动窗口更新权重

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[list[float]] | 是 | 多模型预测结果列表 |
| observations | list[float] | 否 | 用于权重更新的历史实测流量 |
| weights | list[float] | 否 | 初始权重列表 |
| window_size | int | 否 | 滑动窗口大小（默认 30） |
| initial_weights | list[float] | 否 | 初始权重（优先级高于 weights） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| ensemble_forecast | list[float] | BMA 加权后的预测序列 |
| weights_used | list[float] | 更新后的权重 |
| n_models | int | 模型数量 |
| weight_history | list[list[float]] | 权重更新历史 |

#### 3.3 模型质量门控筛选

- **接口**: `POST /api/v1/ensemble/screen`
- **描述**: 基于 RMSE/NSE/偏差阈值筛选低质量模型

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[list[float]] | 是 | 多模型预测结果列表 |
| observations | list[float] | 否 | 实测流量序列 |
| rmse_threshold | float | 否 | RMSE 阈值 |
| nse_threshold | float | 否 | NSE 阈值 |
| bias_threshold | float | 否 | 偏差阈值 |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| passed_models | list[int] | 通过筛选的模型索引列表 |
| rejected_models | list[int] | 被剔除的模型索引列表 |
| model_metrics | dict | 各模型的误差指标 |
| rejection_reasons | dict | 各模型被剔除的原因 |

#### 3.4 趋势一致性检验

- **接口**: `POST /api/v1/ensemble/consistency`
- **描述**: 计算各模型预测趋势的 Kendall's τ

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[list[float]] | 是 | 多模型预测结果列表 |
| method | string | 否 | 检验方法（默认 kendall） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| trend_correlations | dict | 各模型与集合均值的 τ 值 |
| consistency_ratio | float | 一致性比例（τ > 0 的模型占比） |
| ensemble_mean | list[float] | 集合均值序列 |

---

### 四、风险分析模块

**基础路径**: `/api/v1/risk`

#### 4.1 超限概率统计

- **接口**: `POST /api/v1/risk/exceed-prob`
- **描述**: 基于集合预报，计算各时间步超过给定阈值的概率

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| ensemble_predictions | list[list[float]] | 是 | 集合预报成员列表 |
| threshold | float | 是 | 阈值 |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| exceed_prob | list[float] | 超限概率序列 |
| threshold | float | 使用的阈值 |
| n_ensemble | int | 集合成员数 |

#### 4.2 分位数风险指标

- **接口**: `POST /api/v1/risk/quantile-risk`
- **描述**: 计算集合预报的分位数序列

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| ensemble_predictions | list[list[float]] | 是 | 集合预报成员列表 |
| quantiles | list[float] | 否 | 分位数列表（默认 [0.1, 0.25, 0.5, 0.75, 0.9]） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| quantile_values | dict | 各分位数的序列（如 P10, P25, P50, P75, P90） |
| iqr | list[float] | 四分位距序列 |
| iqr_value | float | 四分位距均值 |

#### 4.3 历史同期对比

- **接口**: `POST /api/v1/risk/historical-compare`
- **描述**: 与历史同期流量分布对比

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| current_forecast | list[float] | 是 | 当前预报序列 |
| historical_data | list[float] | 是 | 历史同期数据 |
| method | string | 否 | 对比方法（默认 percentile） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| percentile_ranks | list[float] | 当前预报在历史分布中的百分位排名 |
| historical_mean | float | 历史均值 |
| historical_std | float | 历史标准差 |
| historical_percentiles | dict | 历史分位数 |

---

### 五、误差解释模块

**基础路径**: `/api/v1/error`

#### 5.1 误差指标计算

- **接口**: `POST /api/v1/error/metrics`
- **描述**: 计算 RMSE/MAE/NSE/Bias/峰值误差/峰现时间误差等水文预测误差指标

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[float] | 是 | 预测值序列 |
| observations | list[float] | 是 | 观测值序列 |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| RMSE | float | 均方根误差 |
| MAE | float | 平均绝对误差 |
| NSE | float | Nash-Sutcliffe 效率系数 |
| Bias | float | 系统性偏差 |
| Correlation | float | Pearson 相关系数 |
| peak_error | float | 峰值误差 |
| peak_time_error | int | 峰现时间误差（步数） |

#### 5.2 滑动窗口误差统计

- **接口**: `POST /api/v1/error/sliding-window`
- **描述**: 对预测误差进行滑动窗口统计

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[float] | 是 | 预测值序列 |
| observations | list[float] | 是 | 观测值序列 |
| window_size | int | 否 | 窗口大小（默认 24） |
| step | int | 否 | 滑动步长（默认 1） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| error_series | list[float] | 滑动窗口误差序列 |
| error_means | list[float] | 各窗口的误差均值 |
| error_stds | list[float] | 各窗口的标准差 |
| drift_detected | bool | 是否检测到漂移 |
| drift_points | list[int] | 漂移点索引 |

#### 5.3 误差异常标记

- **接口**: `POST /api/v1/error/anomaly-detect`
- **描述**: 使用 3σ 阈值检测误差异常点

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[float] | 是 | 预测值序列 |
| observations | list[float] | 是 | 观测值序列 |
| threshold_sigma | float | 否 | 阈值倍数（默认 3.0） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| anomaly_indices | list[int] | 异常点索引列表 |
| anomaly_types | list[string] | 异常类型列表（spike/drift） |
| anomaly_timestamps | list[int] | 对应时间戳 |

#### 5.4 误差归因摘要

- **接口**: `POST /api/v1/error/attribution`
- **描述**: 生成可读性的误差归因摘要和改进建议

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| predictions | list[float] | 是 | 预测值序列 |
| observations | list[float] | 是 | 观测值序列 |
| model_names | list[string] | 否 | 模型名称列表 |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| summary_text | string | 可读性摘要 |
| error_metrics | dict | 误差指标 |
| anomaly_info | dict | 异常信息 |
| recommendations | list[string] | 改进建议 |

---

### 六、预警模块

**基础路径**: `/api/v1/warning`

#### 6.1 洪水预警触发

- **接口**: `POST /api/v1/warning/flood`
- **描述**: 基于预报流量序列触发洪水预警

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| forecast_streamflow | list[float] | 是 | 预报流量序列 |
| warning_threshold | float | 是 | 预警阈值 |
| lead_time_hours | int | 否 | 预警提前时间要求 |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| warning_level | string | 预警级别（blue/yellow/orange/red/none） |
| warning_events | list[dict] | 预警事件列表 |
| earliest_warning_time | int | 最早预警时间索引 |
| lead_time | int | 提前量（小时） |
| warning_threshold | float | 预警阈值 |

**洪水预警分级**:

| 级别 | 阈值比例 | 名称 |
|------|----------|------|
| 蓝色预警 | 50% | 警戒级 |
| 黄色预警 | 70% | 警戒级 |
| 橙色预警 | 85% | 警戒级 |
| 红色预警 | 100% | 警戒级 |

#### 6.2 干旱预警触发

- **接口**: `POST /api/v1/warning/drought`
- **描述**: 基于流量时间序列计算 SPI 指数，触发干旱预警

**请求参数**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| streamflow | list[float] | 是 | 流量时间序列 |
| spi_threshold | float | 否 | SPI 阈值（默认 -1.0） |
| scale | int | 否 | SPI 计算尺度（默认 3） |

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| warning_level | string | 预警级别（blue/yellow/orange/red/none） |
| warning_events | list[dict] | 预警事件列表 |
| spi_values | list[float] | SPI 指数序列 |
| drought_start_index | int | 干旱起始时间索引 |
| spi_threshold | float | SPI 阈值 |

**干旱预警分级**:

| 级别 | SPI 阈值 | 名称 |
|------|----------|------|
| 蓝色预警 | -1.0 | 轻度干旱 |
| 黄色预警 | -1.5 | 中度干旱 |
| 橙色预警 | -2.0 | 严重干旱 |
| 红色预警 | -2.5 | 极端干旱 |

#### 6.3 获取预警规则配置

- **接口**: `GET /api/v1/warning/rules`
- **描述**: 返回当前预警阈值配置

**响应参数**:

| 字段 | 类型 | 描述 |
|------|------|------|
| flood_levels | dict | 洪水预警分级配置 |
| default_flood_threshold | float | 默认洪水预警阈值 |
| default_spi_threshold | float | 默认 SPI 阈值 |
| default_spi_scale | int | 默认 SPI 尺度 |

---

## 服务启动

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
uvicorn app.main:app --reload
```

### 访问文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 功能实现说明

### 1. 数据分析模块

实现了基于统计学的水文时间序列分析方法：
- **趋势分析**: Mann-Kendall 非参数趋势检验 + 线性回归拟合
- **周期分析**: FFT 功率谱分析，提取主要周期成分
- **突变检测**: Pettitt 非参数检验识别突变点

### 2. 径流预测模块

实现了三类水文预测模型：

| 模型 | 类型 | 说明 |
|------|------|------|
| 新安江模型 | 水文概念模型 | 三水源概念模型，分地表径流、壤中流、基流 |
| 随机森林 | 机器学习 | 使用滞后特征和降雨特征 |
| LSTM | 深度学习 | 简化版 LSTM 模拟预测器 |

### 3. 集合预测模块

实现了多模型集合预报方法：
- **加权平均**: 简单加权平均，支持自定义权重
- **贝叶斯模型平均 (BMA)**: 基于历史表现滑动窗口更新权重
- **模型筛选**: 基于 RMSE/NSE/偏差阈值筛选
- **趋势一致性检验**: Kendall's τ 检验多模型趋势一致性

### 4. 风险分析模块

基于集合预报提供风险评估：
- **超限概率**: 集合成员计数法计算各时间步超限概率
- **分位数风险**: 计算 P10/P25/P50/P75/P90 分位数及 IQR
- **历史同期对比**: 百分位排名法评估当前预报风险等级

### 5. 误差解释模块

提供预测质量评估和异常检测：
- **误差指标**: RMSE、MAE、NSE、Bias、峰值误差、峰现时间误差
- **滑动窗口统计**: 滑动窗口误差监控和漂移检测
- **异常标记**: 3σ 阈值检测，标记 spike（突发）和 drift（漂移）类型
- **归因摘要**: 基于指标的自动归因和建议生成

### 6. 预警模块

基于阈值和规则的预警触发：
- **洪水预警**: 四级预警（蓝/黄/橙/红），基于预报流量阈值触发
- **干旱预警**: 基于 SPI（标准化降水蒸散发指数）的四级预警

---

## 开发说明

本服务严格按照参考文档《项目功能分析.md》和《业务场景设计.md》要求实现，所有 API 接口均已通过功能测试。