# Huadong 预测链可运行示例

本目录提供一套**可直接串联执行**的 `Huadong` 预测链示例文件，覆盖以下步骤：

1. `POST /huadong/dataset/profile`
2. `POST /huadong/model-assets/profile`
3. `POST /huadong/analysis`
4. `POST /huadong/forecast`
5. `POST /huadong/ensemble`
6. `POST /huadong/correction`
7. `POST /huadong/risk`
8. `POST /huadong/warning`

目录中的文件说明：

- `huadong-prediction-chain.config.json`
  - 统一配置文件，定义数据集路径、输出目录、风险阈值等
- `run-huadong-prediction-chain.ps1`
  - 面向**已启动 UnifiedGateway** 的 PowerShell 实例脚本
- `verify-huadong-prediction-chain.py`
  - 面向**仓库内自验证**的 Python 脚本，使用 `UnifiedGateway` 的 `TestClient` 顺序调用所有接口

## 推荐使用方式

### 方式 1：对真实网关发 HTTP 请求

先启动网关：

```powershell
cd H:\04241\UnifiedGateway
uv run unified-rest
```

再执行：

```powershell
powershell -ExecutionPolicy Bypass -File H:\04241\doc\restful\examples\pred-src\run-huadong-prediction-chain.ps1
```

### 方式 2：在仓库内直接验证整条链

```powershell
cd H:\04241\UnifiedGateway
uv run python H:\04241\doc\restful\examples\pred-src\verify-huadong-prediction-chain.py
```

## 运行结果

脚本会在配置指定的输出目录下生成：

- `requests/`
  - 每一步真实请求体
- `responses/`
  - 每一步真实响应体
- `pipeline-summary.json`
  - 本次串联执行摘要

默认输出目录：

```text
H:\04241\doc\restful\examples\pred-src\runs\huadong
```

## 关键说明

本目录示例是“能跑通”的版本，做了两件事：

1. 上游结果不手工拼路径，而是从响应里的 `artifact_paths` 读取真实路径
2. `ensemble -> correction -> risk/warning` 的 `file_path` 都由脚本自动填充

因此，本目录中不会把文档中的：

```json
"file_path": "H:\\04241\\doc\\restful\\outputs\\huadong\\correction\\...\\corrected.csv"
```

这种带 `...` 的示意路径硬编码进请求文件。

真正的衔接方式始终是：

- `forecast.artifact_paths.forecast -> ensemble.file_path`
- `ensemble.artifact_paths.ensemble -> correction.file_path`
- `correction.artifact_paths.correction -> risk.file_path`
- `correction.artifact_paths.correction -> warning.file_path`
