# TanKengCode

一个从原项目中抽离出来的、可独立运行的 Tanken 水库调度演示仓库，包含：

- 一个本地 MCP Server：在 `pyresops` 标准工具之上增加 Tanken 场景工具。
- 一个确定性 Agno Workflow：按固定 MCP 工具链执行调度流程，不依赖模型推理。
- 四个内置演示案例：预泄触发、方案比选、动态更新、孤岛应急。
- 一套可复现的 pytest 测试。

## 1. 功能概览

当前仓库提供两条主要运行链路：

1. MCP Server
   - 入口模块：`project.tanken_mcp_server`
   - 能暴露标准 `pyresops` 工具以及 Tanken 自定义工具，例如：
     - `list_tanken_cases`
     - `get_tanken_case_status`
     - `query_tanken_dispatch_rules`
     - `optimize_tanken_release_plan`
     - `simulate_tanken_dispatch_program`
     - `evaluate_tanken_dispatch_result`
     - `run_tanken_case`
     - `run_all_tanken_cases`

2. Deterministic Workflow
   - 入口模块：`project.agents.run_tanken_workflow`
   - 固定执行顺序：
     - `describe_tanken_case`
     - `get_tanken_case_status`
     - `query_tanken_dispatch_rules`
     - `optimize_tanken_release_plan`
     - `simulate_tanken_dispatch_program`
     - `evaluate_tanken_dispatch_result`
     - 可选 `run_tanken_case`

## 2. 环境要求

- Python `>=3.14`
- `uv`

仓库已经内置本地 wheel 依赖：

- `libs/pyresops-0.2.0-py3-none-any.whl`

安装依赖：

```powershell
uv sync
```

## 3. 目录说明

```text
.
├─ agents/                  Agno workflow
├─ configs/                 案例、规则、workflow 配置
├─ data/                    当前仓库自带的示例 CSV 与事件摘要模块
├─ plugins/                 报告与下游安全插件
├─ results/                 运行输出
├─ tests/                   pytest 测试
├─ utils/                   事件读取、配置加载、Muskingum 等工具
├─ tanken_mcp_server.py     MCP server 入口
├─ scenario_executor.py     案例执行编排
└─ run_tanken_demo.py       项目级演示入口
```

## 4. 推荐运行方式

由于这个仓库是从原项目抽离出来的，为了兼容历史 `project.*` 导入，当前最稳定的方式是：

- 直接使用模块入口运行；
- 在 PowerShell 中执行测试或脚本入口前，先设置一次 `PYTHONPATH`。

```powershell
$env:PYTHONPATH='.'
```

如果你只用下面的“模块方式”命令，通常也能直接运行；但为了避免环境里旧安装副本干扰，建议保持上面的环境变量。

## 5. 启动 MCP Server

推荐：

```powershell
$env:PYTHONPATH='.'
uv run python -m project.tanken_mcp_server
```

如果你希望走脚本入口：

```powershell
$env:PYTHONPATH='.'
uv run pyresops-tanken-server
```

## 6. 运行 Workflow

单案例：

```powershell
$env:PYTHONPATH='.'
uv run python -m project.agents.run_tanken_workflow --case-id 6.4.1
```

批量运行全部案例：

```powershell
$env:PYTHONPATH='.'
uv run python -m project.agents.run_tanken_workflow --case-id all
```

只跑固定 MCP 工具链，不执行最终案例报告步骤：

```powershell
$env:PYTHONPATH='.'
uv run python -m project.agents.run_tanken_workflow --case-id all --skip-case-report
```

如需把结果写入 `results/`：

```powershell
$env:PYTHONPATH='.'
uv run python -m project.agents.run_tanken_workflow --case-id 6.4.1 --persist-result
```

## 7. 运行项目级 Demo

单案例：

```powershell
$env:PYTHONPATH='.'
uv run python .\run_tanken_demo.py 6.4.2 --no-save
```

全部案例：

```powershell
$env:PYTHONPATH='.'
uv run python .\run_tanken_demo.py all
```

## 8. 运行测试

推荐测试命令：

```powershell
$env:PYTHONPATH='.'
uv run --with pytest pytest -q
```

## 9. 我已完成的实际验证

我在当前仓库中完成了以下验证：

- `uv sync`
- `uv run python -m project.agents.run_tanken_workflow --case-id 6.4.2 --skip-case-report`
- `$env:PYTHONPATH='.'; uv run pyresops-tanken-workflow --case-id 6.4.1 --skip-case-report`
- `$env:PYTHONPATH='.'; uv run python -m project.agents.run_tanken_workflow --case-id all --skip-case-report`
- `$env:PYTHONPATH='.'; uv run --with pytest pytest -q`
- `uv run python -m compileall project data agents plugins utils tests`

验证结果：

- MCP Server 可被 workflow 正常拉起并完成工具调用。
- Workflow 可运行单案例和批量案例。
- pytest 共 `33` 项测试，全部通过。

## 10. 抽离版仓库的兼容性说明

本次整理后，仓库已补齐以下内容：

- 仓库内 `project` 兼容包，避免原始 `project.*` 导入失效。
- 本地 `data/` 示例数据与 `data.summarize_flood_events` 模块，不再依赖原项目目录。
- 对带预测列的 CSV 兼容处理。
- `pyproject.toml` 中本地 `pyresops` wheel 依赖声明。

仍建议注意：

- 如果你的当前 shell 里曾安装过旧版同名包，执行脚本入口或测试前最好先设置：

```powershell
$env:PYTHONPATH='.'
```

- 最稳妥的调用方式仍然是模块命令：

```powershell
uv run python -m project.tanken_mcp_server
uv run python -m project.agents.run_tanken_workflow --case-id 6.4.1
```
