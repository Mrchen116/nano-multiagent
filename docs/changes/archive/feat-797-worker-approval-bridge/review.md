# 实现与契约审查

独立 reviewer 使用 change-code-review 与 agent-context-review 审查 bf20e1da2..1c49d0a6e。设计 Gate 2 R2 已通过。最终结论为通过，corrected-delta aligned，无待修问题。

| 首轮问题 | 修正与复核结果 |
|---|---|
| AGY 明确拒绝达到累计阈值后可能被转人工或由无人值守 fallback 放行；审核期间的撤回同样可能被 fallback 覆盖。 | 990508d67 保留拒绝计数，终局拒绝直接阻断。证据变化使审核结果失效，有人值守转人工，无人值守安全拒绝。独立 reviewer 对照修复前后行为。 |
| AGY 转人工时缺少升级原因。 | 451bd2c86 把升级原因写入卡；审核不可用的技术异常留在原审计，主人能区分需要权限与审核期间授权发生变化。 |
| 用内部 send_message 续派空闲 Worker 时可能沿用旧派工调用 ID。 | 1c49d0a6e 让两个入口都传本次调用身份。类型要求必传。独立复跑 manager 三项协议测试通过。 |

Context 审查者亲读两条实际出站 fixture 审核请求，验证 A 派工原话、B 后续上下文及完整待审动作在输入中的角色。撤回后的失效见执行测试。Codex/Claude 使用原生 Auto，宿主没有第二次模型调用。Worker 问题和拒绝回到所属父级，父级回复只作为新的业务输入。审查覆盖协议、根会话与 Worker 归属、Web/IM 主人身份与生命周期，以及飞书和原生 DSH 的边界。

用户旅程使用 Chromium、真实 IM HTTP/WebSocket、产品审批接线、独立 DSH 进程与协议 fixture CLI。主人点击后原调用获得单次放行，刷新可读终态。iOS 仅检查现有组件和协议，本次未跑真机。复现与范围见 [M1 验证](M1-worker-approval/verification.md)。
