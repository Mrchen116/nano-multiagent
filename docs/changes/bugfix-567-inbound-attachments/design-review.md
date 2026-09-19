# bugfix-567 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`（独立 reviewer，未参与受审设计编写）
- review_mode: full
- mode_reason: 首轮 Gate 2；完整核对 incident、设计、delta、milestone 与真实组装路径。
- started_at: 2026-09-19T13:09:04+08:00
- completed_at: 2026-09-19T13:10:29+08:00
- duration: 85 秒（工具时间可核实的审查记录区间；此前的文件阅读不计入，未推测总耗时）
- reviewed baseline: `main` / `6ebc3f6ba7ac5addc9cf6dc3d446379be4d46b02`；incident 已提交，冻结的 design、specs delta、M1-fix/.gitkeep 为未提交产物。其他 dirty/untracked 文件未修改。
- 用户约束补充：主会话在本轮审查期间传达用户确认“保留当前图片失败提示，隔离群历史失败（推荐）”，与受审决定 3 一致，不构成范围变化。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案在现有产品组装与模块职责中可实施，需求和失败/接收边界已收口。此结论仅为设计门禁，不代表实现完成或真实产品验收通过。

### Coverage 与证据

1. **现状与真实入口。** `channels/web_relay_adapter.py:345` 保留所有带 URL 附件的 URL、content_type、file_name；`gateway/composition.py:663` 为 IM 组装含当前节点凭据的图片 fetcher，`:886`、`:926` 分别向 SessionRunCoordinator 与 GlobalRunCoordinator 注入同一 resolver，`:953` 起组装实际 InboundPipeline。`inbound_pipeline.py:169` 按 work_mode 进入 global；`:192` 起在 single_thread 群消息未触发时持久 append。不是只存在于测试的替代实现。
2. **普通文件与混合消息。** `session_run_coordinator.py:2344` 当前向 resolver 传入整组附件，任何 resolution failure 返回空 projection；`image_attachments.py:67` 起采用 all-or-nothing 图片校验，未按普通 MIME 分流。因此 incident RCA 与当前代码一致。设计决定 1、2 用共享无状态分类 helper 先分类，文件仅描述、图片继续受保护校验，可以保留文字和有效图片，且不扩大文件读取权限。`global_run_coordinator.py:550` 已区分图片与 attachment，但使用未规范化的 MIME startswith；两处采用同一判断可消除基本分类差异。普通文件明确未读取是本次两种模式共同验收要求，而不能只凭存在 attachment block 判定完成。
3. **顺序与失败范围。** `_ordered_kernel_input_parts`（`session_run_coordinator.py:3867`）使用 attachment_index；Feishu adapter 构建该索引与 `image_resolution_failure`。设计明确保留原索引，历史逐项失败只留下未读取事实、文字和有效图片；当前失败继续本轮停止。实现必须落实这两类 metadata 入口，但无需改变渠道协议或新增内核类型。既有 `relay-protocol.md` 的当前异常图片契约保留；用户确认与 incident 的当前/历史区分一致。
4. **缓冲不会在 admission 前消失。** `group_context_store.py:21` 已有 AUTOINCREMENT id；`:117` 的 drain 当前在同事务读取后全删，`_build_message_parts` 在下载及 submit 前调用它。无损 snapshot 加按 buf_key/id 上界删除无需迁移，后来 append 的行不受旧 receipt 影响。`dispatch` 的准备和 try_steer（`:791`—`:838`）及 `_run_one` 的准备和同步 submit（`:1773`—`:1829`）均处于已有 session transition 临界区，方案把 consume 放在成功接收并确认身份之后，能覆盖解析失败、submit 异常和 steer 拒绝。拒绝 steer 的群 projection 出队重建，避免等待期间已被其他接收消费的背景重复注入。设计也准确排除了跨内核/SQLite 崩溃 exactly-once 承诺。
5. **global 消费保持原边界。** `global-agent.md` 的“Inbox 读取与聊天历史读取具有不同的消费语义”已有普通文件描述摄取与失败图片可重读契约；`global_inbox.py:963` 的图片重物化和 `tools/inbox.py:30` 的图文序列化是实际消费路径。设计只共享分类、保留 attachment 描述及其 Inbox receipt 协议，不把 single_thread 的历史失败消费规则套到 global；不需要重写 global canonical 的既有消费要求。
6. **delta 完整且归属正确。** `specs/gateway/relay-protocol.md` 以 ADDED Requirements 补充普通文件、历史失败隔离和接收后消费，目标为 `docs/specs/gateway/relay-protocol.md`；没有 MODIFIED 全量替换，因此原图片追问、异常恢复、成员凭据等场景仍保留。消费者结果可观察，不把 snapshot/row id 变成对外契约。incident 的普通文件、混合有效输入、当前失败恢复、历史失败、拒绝接收及后来消息均有对应决定与 delta 场景。
7. **milestone 与验收。** M1 单串行范围覆盖 helper、两个 coordinator、group store 与相关测试，避免并行共享文件冲突；目录仅 `.gitkeep` 符合设计阶段骨架要求。退出标准含类型参数化、原索引、当前/历史失败、拒绝提交、后到消息、steer/FIFO 不重复和 global 基本语义。Runbook 明确隔离 IM/Gateway、真实 LLM 与 API 同入口、两种模式、图片/文件/群历史/坏图后恢复；无界面变更，无需 prototype/must-match。真实代理不可达应记录产品验收 blocker，不能以单测代签，前置和责任已明确。

### 架构判断

附件的 MIME/URL 类型语义由 Gateway 的窄 helper 共享，单会话投影和接收仍由 SessionRunCoordinator 负责，全局输入与消费仍归 GlobalRunCoordinator/Inbox；下载、字节校验与身份保护留在既有 ImageAttachmentResolver/fetcher；SQLite snapshot 与范围删除由 GroupContextStore 承担。这些职责与实际组装一致，也不突破 PA 仅使用 agent.sdk 的边界。

相比新增附件服务、通用队列或租约，复用 resolver 与现有 transition 锁只需无状态分类和 store 两个窄操作，维护代价与本次故障匹配。保留旧 drain 给既有调用者、生产 admission 改用 snapshot 的安排不会产生新持久协议；群 steer fallback 重建虽可能再次下载，但直接处理现有重复上下文风险，取舍充分。无需为非目标崩溃场景增加分布式事务机制。

### 历史问题闭环

首轮，无历史问题或 Author Resolutions。

### Issues

无。

### Recommendations

无。实施与后续验收按已冻结的 M1 标准推进。

### Author Resolutions

2026-09-19：核实 R1 证据与结论，无 findings 或待处理建议；接受 Approved。首文档补录用户确认原话，与已审策略相同，无语义增量，R1 retained。
