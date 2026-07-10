# M3 pa-gateway-on-sdk — tasks

## 目标

personal_assistant gateway 从「spawn 内核 uvicorn 子进程 + HTTP」改为进程内持有 `Kernel`。

## 退出标准

- `[worker]` personal_assistant 相关单测全绿，不新增红测
- `[reviewer]` Review-B 全部 Scenario（IM 工具型任务/后台回发/heartbeat/多 agent/stop·restart）pass
- gateway stop·restart 干净无残留 kernel 子进程（已无子进程）
- progress.md 给出经 e2e-up.sh 起栈跑通的证据

## 测试策略

**类型：重构（行为不变）**

原有行为：inbound_pipeline 经 kernel_api_client HTTP 调用内核 → 执行任务 → 回发。
新行为：inbound_pipeline 经 agent.sdk.Kernel 进程内调用 → 执行任务 → 回发。

从外部（IM / channel 用户）看行为完全不变。

### 测试计划

1. **保持现有 contract/unit 测试全绿**（行为不变，测试不应改）
2. **pipeline 单测**：`inbound_pipeline` 里的 kernel_client 调用被换成 kernel SDK 调用，
   测试里的 mock 从 `KernelApiClient` 换成 `Kernel` mock，行为覆盖不变。
3. **build_runtime 单测**：验证 `build_runtime(config)` 在 M3 后返回的 `GatewayRuntime`
   不再包含 `GatewayProcessManager`（无子进程），且 `InboundPipeline` 用的是
   `Kernel` 而非 `KernelApiClient`。
4. **e2e-up.sh smoke test**（最终验证）：e2e-up.sh 起栈后 gateway 能正常启动（无 api.pid）。

## UI 状态矩阵
N/A — 纯后端重构

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 写失败测试（C1）：InboundPipeline 接受 Kernel 替代 KernelApiClient | DONE |
| R2 | 实现：改造 InboundPipeline 使用 Kernel SDK | DONE |
| R3 | 实现：main.py 删子进程逻辑，build_runtime 改用 build_kernel | DONE |
| R4 | 实现：删除 kernel_app.py 和 kernel_api_client.py，更新 e2e-up.sh | DONE |
| R5 | 文档 + progress 补齐 | DONE |
