# 统一 FastAPI 网关接口示例包

## 说明

本目录用于存放统一 FastAPI 网关的**拆分接口示例**。

为了满足“每个字段都写中文注释”的要求，这里使用的是：

- `jsonc` 文件

也就是：

- JSON 结构
- 允许行内注释

如果后续要导入到程序里使用，请先去掉注释，或转换成标准 JSON。

## 目录结构

- `examples/gateway/`
  - 网关根接口示例
- `examples/huadong/`
  - `HuadongCode` 在统一网关下的接口示例
- `examples/tanken/`
  - `TanKengCode` 在统一网关下的接口示例

## 命名规则

- `*.request.jsonc`
  - 请求体示例
- `*.response.jsonc`
  - 同步接口响应体示例
- `*.submit.response.jsonc`
  - 异步任务提交后的第一跳响应
- `*.completed.response.jsonc`
  - 通过 `/jobs/{job_id}` 查询到的完成态响应

## 路径前缀

统一网关启动后：

- 华东水文功能：`/huadong/...`
- 滩坑调度功能：`/tanken/...`

## 推荐阅读顺序

1. `gateway/health.response.jsonc`
2. `huadong/forecast.request.jsonc`
3. `huadong/forecast.response.jsonc`
4. `huadong/training-job.*.jsonc`
5. `tanken/cases.response.jsonc`
6. `tanken/optimize.*.jsonc`
7. `tanken/run-case-job.*.jsonc`
