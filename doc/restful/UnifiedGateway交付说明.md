# UnifiedGateway 交付说明

## 1. 交付结论

当前交付入口已经统一到：

- [UnifiedGateway](</H:/0424/UnifiedGateway>)

以后用于安装依赖和运行服务的目录就是：

```text
H:\0424\UnifiedGateway
```

不再使用之前 `H:\0424\doc` 下的 `uv sync` 环境作为交付入口。

## 2. 现在应该怎么交付

交付时，使用方只需要关注这三个目录：

- `H:\0424\UnifiedGateway`
- `H:\0424\HuadongCode`
- `H:\0424\TanKengCode`

其中：

- `UnifiedGateway`
  - 统一 FastAPI 单入口
- `HuadongCode`
  - 华东水文功能源码
- `TanKengCode`
  - 滩坑调度功能源码

## 3. 安装与启动方式

### 3.1 安装依赖

```powershell
cd H:\0424\UnifiedGateway
uv sync --extra dev
```

说明：

- `uv.lock` 已经放在 `UnifiedGateway` 目录下
- `.python-version` 也已经放在 `UnifiedGateway` 目录下
- 交付后在该目录执行 `uv sync` 即可

### 3.2 启动服务

```powershell
cd H:\0424\UnifiedGateway
uv run unified-rest
```

或者：

```powershell
uv run python -m gateway.server
```

## 4. 默认地址

默认：

- `Host`: `0.0.0.0`
- `Port`: `8010`

访问地址：

- `http://localhost:8010`
- `http://localhost:8010/health`
- `http://localhost:8010/huadong/health`
- `http://localhost:8010/tanken/health`

## 5. 路径切换规则

统一网关启动后：

- `HuadongCode` 的接口都走：
  - `/huadong/...`
- `TanKengCode` 的接口都走：
  - `/tanken/...`

## 6. 已完成验证

已经完成：

- `UnifiedGateway` 独立 `uv lock`
- `UnifiedGateway` 独立 `uv sync --extra dev`
- 统一网关测试通过：

```text
2 passed
```

## 7. 推荐保留的文档

交付建议保留以下文档：

- [统一FastAPI网关快速接入说明.md](</H:/0424/doc/restful/统一FastAPI网关快速接入说明.md>)
- [统一FastAPI网关部署与使用说明.md](</H:/0424/doc/restful/统一FastAPI网关部署与使用说明.md>)
- [RESTful改造测试报告.md](</H:/0424/doc/restful/RESTful改造测试报告.md>)
- [接口示例包_README.md](</H:/0424/doc/restful/接口示例包_README.md>)

以及：

- `examples/`

目录中的全部 `jsonc` 接口示例。
