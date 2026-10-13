# Skill 禁用名单设计

## 范围与实际流程

用户在实现前确认 Workspace/全局均采用禁用名单，首版设计先于实现记录。实施提交 `11f3ceafc` 之前未执行独立门禁；本轮审查发生在实现之后，不补称事前审批。用户在交付期间明确要求“内部机制调整”“做了逻辑修改就行”，取消额外前端原型、体验设计和产品界面验收。既有 Web/iOS 配置字段适配保留，不进行布局改造。

## 关键决定

- `skills_selection_mode=explicit_denylist` 时，沿用 `skills` 字段存禁用名称，复用配置指纹与同步通道。配置界面勾选仍表示启用，取消项保存；暂缺的禁用名称保留。
- DSH 原生 provider/watcher/registry 负责发现和刷新；Nano 对 list/get 使用相同排除规则，保持 roots、同名优先级与 Agent scope。新名称默认可用，明确禁用名称刷新/重启/同名重建不自动启用。
- 当前 Session 后续步骤可按名加载新文件；prompt目录沿既有会话快照/重建边界，不为文件新增自动重建缓存前缀。
- Node认证连接IM后请求 `/skills/migrate`。IM验证Gateway owner/node，以该Agent真实完整候选减旧已选集合，经既有config operation/CAS同步YAML/runtime/profile。default转空禁用名单；已迁移不重复转换。恢复pending operation后重读canonical profile继续迁移。
- 旧allowlist无候选历史，只能保迁移时已有候选状态；离线不猜候选。迁移失败逐Agent报告并保留旧模式，后续连接重试，不中断DSH或其他Agent恢复。
- 忙碌Session新增禁用立即收紧；放宽沿既有idle replacement。Skill创建事实保留来源记录/通知，不修改启用配置。工具权限及F3/F4进化规则不变。

## 契约增量

[Gateway delta](specs/gateway/agent-capabilities.md) 替代旧allowlist规则，保留离线旧模式、蒸馏禁用及其余未改变场景；[IM delta](specs/im/agents-nodes.md) 统一首次编辑、持久化和认证迁移语义。首版提前修改current的事实保留；本轮已恢复current，在独立核对后再归并。原显式清空保证变为“当时取消的名称持续禁用”，未来新名称默认启用，这是用户确认的变化。

## Milestone

| ID | 依赖 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-selection | 无 | contracts、DSH、PA、Node/IM、Web/iOS字段适配、specs/tests | 原生Session内复制新增可加载；禁用在list/get/显式调用/preview/SlashPicker一致，重启及同名重建保持；旧default/allowlist/空选择经真实候选迁移且指纹/镜像持久化一致；pending恢复继续转换，失败不阻断runtime/其他Agent；工具与进化策略不变。 |

## 验证与运行边界

复用带版本的已有原生DSH、HTTP迁移、配置、Web/iOS契约测试；审查发现的两项恢复问题先红后绿并独立复现闭环。按当前CI运行build/typecheck/Vitest、Python/Ruff、docs-check和原生test/archive。Web完整tsc既有timer类型问题单独记录，不声称全绿；无真机验收。

若需真实进程复现，遵循 [worktree-runtime](../../development/worktree-runtime.md)，只在现有专属worktree用 `scripts/e2e-up.sh` / `scripts/e2e-down.sh`；临时端口、config、owner根、DSH home、身份和workspace均隔离，测试账号来自repo E2E config，不使用生产身份。主Agent负责起停和清理。用户已取消额外界面验收，不为本次内部机制变更继续搭建UI演示。
