# bugfix-611: As-built Design

> 本文在实现后根据实际 diff 与用户决定整理，不代表事前设计门禁。

## 实现范围

- Base: `9182699fca58d42fbf166f3de7445c635dcb3527`
- Branch: `codex/bugfix-611-global-empty-response`
- 本次文件：`packages/dsh-integration/src/index.ts`、`src/global-mode.ts`（同包）、`tests/communication-native.test.ts`（同包）及本 unit 文档。
- 主 checkout 的既有 dirty/untracked 内容不在范围内；独立 worktree 实施。

## 最终结构与调用链

删除 Nano 的空响应转换中间件和未使用的 EMPTY_RESPONSE_CODE import。模型请求返回 EMPTY_RESPONSE 后，DSH agent/request-error 交给既有 llm-retry，沿 provider 的原生策略恢复；耗尽或不可重试错误沿原路径失败。生产重试次数和退避配置不变。

全局 nano-global-mode 提示词要求每轮输出简短、非空的内部收尾。说明可以记录交付结果、已告知阻塞或无需公开回复的原因。公开交付仍只由 send_message 负责，内部收尾不自动发送到聊天。保留待交付请求不得以私有草稿结束的要求。

同一提示词新增过程沟通要求：读到真人任务后、深入调查或执行前，通过 send_message 向原会话简短确认及说明下一步；长任务在有必要的发现、阻塞或计划变化时发进度，一般一两句话。尊重明确不回复要求，避免重复状态、日志及空闲播报；确认和进度不能取代最终交付。不新增强制发送中间件或计时器。

## 关键决策

| 决策 | 原因与约束 |
|---|---|
| 复用原生重试，删除特殊豁免 | DSH 已有失败码、有限重试与失败终态，不需要第二套恢复循环 |
| 内部非空收尾与公开静默分离 | 后台无更新和已交付轮次也能满足运行时要求，不额外骚扰聊天 |
| 不将收尾文本视为送达证明 | 文本存在不能证明履行了用户请求，仍必须显式交付 |

## 失败路径、兼容性与回滚

持续空响应最终失败，不伪装 completed。AUTH 等不可重试错误保持失败。既有 session 无需迁移；提示词在使用新版本的配置作用域中生效。回滚这两个源码文件即可恢复旧行为，但也会恢复空响应被误判成功的风险。

原生请求重试不会自动重放已经完成的工具调用；本次 fixture 验证已发送后发生空响应的路径仅投递一次。模型后续主动再次调用工具的行为不属于运行时去重保证，提示词明确要求不重发已交付结果。

## 验证定位

- 既有 communication-native 测试 rewrite-merge：在真实锁定 DSH 子进程中，以模型流 fixture 覆盖发送后空响应、无公开更新、重试耗尽、AUTH 和单 Thread 失败。
- 测试 provider 设置一次重试和 1 ms 退避，仅用于快速验证；默认错误码列表来自 DSH。
- 旧代码上预期红：应有一次 llm/retry，实际零次；独立的 fixture 配置纠正不算产品红测。
- 修复后：该包 30 个测试文件、74 项测试通过；包 build/typecheck、13 项运行时依赖契约测试、git diff --check 通过。
- 一次性真实 profile 的 session.capabilities 检查确认：非空收尾要求和私有/显式交付边界已进入组装提示词，旧的允许空正文结束语句已移除。
- 全仓 docs-check 被基线既有 `docs/changes/feat-610-workspace-tool-install/specs/gateway/agent-capabilities.md:7` 的 `task-graphs.md` 断链阻塞；git show Base 核实该断链先于本次改动，未扩大本次范围。
- 真实模型场景验证：见 [regression.md](regression.md)，六个隔离用例通过；生产送达尚未验证，用户于 2026-10-15 确认快修验收通过，单次模型结果不等于行为稳定性保证。

## 后续增量验证

过程沟通增量仅修改提示词；保留原生重试与投递测试，不为特定措辞新增永久断言。增量重新构建通过；communication-native/capabilities 共 5 项回归通过；真实 profile 的 session.capabilities 组装检查确认先公开回应、深入执行前回应、必要进度、进度不等于最终交付和非空内部收尾要求全部存在。随后六个真实模型场景通过，详见 [regression.md](regression.md)；仍不代替生产送达或用户亲自体验。

## Canonical 文档影响

目标见 `specs/gateway/global-agent.md` delta。用户已于 2026-10-15 明确验收通过；按最终 delta 归并到 docs/specs/gateway/global-agent.md，同步包入口 Requirement 数量，然后整 unit 归档。
