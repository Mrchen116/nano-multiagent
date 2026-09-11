# SDK Boundary — feat-552 delta

目标：`docs/specs/kernel/sdk-boundary.md`。依据 design D6 与 M2 共享 runtime 接线细化；只扩展已有 SDK-owned 类型，不新增 DTO、provider、导出或 `build_kernel` 参数。

## ADDED Requirements

### Requirement: 应用通过完整 session runtime 选择 Auto 交互方式

既有 `SessionRuntimeConfig` 增加可选字段 `auto_mode_interaction: Literal["return_to_agent"] | None = None`。应用经原有 `create_session(runtime=...)` / `reconfigure_session(runtime=...)` 提供该值；它随完整 runtime 持久化、读回并参与 identity。

#### Scenario: 选择交互并在后续会话操作中保留
- **WHEN** 应用把 `auto_mode_interaction="return_to_agent"` 作为完整 runtime 的一部分创建或重配 session
- **THEN** `get_session_runtime` 返回的 runtime 保留该值，`identify_runtime` 对该字段的变化产生不同 identity；既有重配的忙闲与未来运行边界不变。
- **AND** 普通运行按该选择返回未获准原因，由 Agent 继续处理；实际无人值守入口及普通 child 仍遵守各自运行路由，不仅凭该字段判定来源或覆盖工具硬限制。

#### Scenario: 省略或清除交互选择
- **WHEN** 应用省略该字段，或在完整 runtime 中显式传入 `None`
- **THEN** 不增加 session 级 Auto 交互覆盖，继续既有路由；读回缺少该字段的既有完整 runtime 时，该字段为 `None`，不要求配置迁移或新增装配步骤。
