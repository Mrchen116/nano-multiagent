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


## Round 2

### Metadata

- reviewer target: `/root/design_review`（沿用 R1 独立 reviewer，未参与实现或设计修订）
- review_mode: delta
- mode_reason: 决定 2 补齐 global 既有附件索引及图文顺序投影，决定 3 约束失败描述的内联 payload；变化有界，无需求、公共接口、持久协议、milestone 或依赖边界变化，因此核对这两项及其消费路径，不重开 full。
- started_at: 2026-09-19T13:21:01+08:00
- completed_at: 2026-09-19T13:21:45+08:00
- duration: 44 秒（工具时间可核实区间）
- reviewed baseline: `codex/bugfix-567` / `30dac3b37a5f8a4c28059f003299f119f661c859`；worktree `/Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-567`，受审为冻结的 design.md Changelog 与关键决定 2/3 增量。
- retained_from: Round 1；原需求和 delta 未变，snapshot/admission、steer/FIFO、下载凭据、current/global 失败语义、真实组装、M1 与真栈验收要求保持原判断。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

两项设计修订足以指导修复已确认的实现缺口。code-review / verification 的两项实现 finding 仍须修复后由相应门禁核实，不能据此设计 Approved 关闭。

### Coverage 与证据

1. **global 原附件索引投影。** 独立核对 `channels/feishu/adapter.py:670` 起把资源封装为 data URL 并记录原附件索引，`:682` 的 `_kernel_input_parts` 生成 text 与 `image attachment_index` 有序序列。当前 `global_run_coordinator.py:559` 把占位图片收进 images、跳过 resolver，而后仅处理 source/image_url，因此占位确会消失。修订决定 2 明确在 global 按原索引解析为 Inbox image source、保持 text/image 顺序，且无 ordered parts 才使用正文与附件顺序；既有自包含图片沿用并避免重复。这直接封闭缺口，没有把索引重新解释为分类后列表索引，也没有要求复用 single_thread 的 SDK block 格式。
2. **失败 data URL 描述。** `inbound_attachments.py:57` 当前从 descriptor 原样取 url 并 JSON 序列化；`session_run_coordinator.py:2403` 起把历史 resolution failure 交给该 helper。因此历史失败内联图片的 payload 确可进入模型文本。决定 3 现在明确 data URL 仅保留内联来源标记、绝不包含 Base64 payload，仍保留失败原因及未读取事实，能满足原历史失败隔离要求；不影响有效图片作为 image 内容进入模型，也不改变当前坏图本轮提示。
3. **消费与权限波及范围。** global 图片物化继续复用已有 image_resolver 和 agent_id，结果保留 Inbox 所需 source/失败 attachment 描述；global 的失败可重读与 durable 消费协议继续有效。文本来源脱离 Base64 payload 仅改变未读取说明，不删除 store 原始附件，既有身份和下载保护不变化。没有新增公共接口或要求修改内核。
4. **需求、delta 与 M1。** 修订只落实 incident 及 delta 中“两种模式有效图片进入上下文”“历史图片失败不阻断新请求”的既定结果，无新增用户行为要求，无需扩写 canonical delta。M1 原有索引保真、global 基本类型及历史错误回归足以容纳这两项；验收时应使用真实 Feishu-shaped attachment_index 输入和历史失败 data URL 样例，而不能只以 Web-shaped 附件通过代替。测试是否已经通过不属于本轮设计结论。

### 架构判断

原索引到 Inbox image source 的适配应由 GlobalRunCoordinator 的输入投影承担；单会话已有索引处理可作为语义参照，但不需要把两个不同消费协议抽象为通用新框架。内联来源文本省略 payload 由现有 `unread_attachment_text` 负责，复用现有描述 helper 即可，不需要存储迁移、图片缓存或新限流机制。修订与现有职责一致，复杂度与已复现故障匹配。

### 历史问题闭环

- Round 1 无设计 issue；其 Author Resolutions 接受 Approved 并补录用户原话，本轮核实与当前策略一致，retained。
- 本轮触发材料为 code-review.md 的两个 CONFIRMED finding 及 verification.md 的两个 WARNING，并非 R1 遗留设计 issue：修订设计已覆盖其纠正方向；实现状态仍 open，留待代码审查和一致性复验关闭。

### Issues

无。

### Recommendations

无。

### Author Resolutions (R2)

2026-09-19：接受 R2 Approved。两项修订均对应静态审查确认的实现缺口，未改变用户已确认的失败策略、文件读取范围或 Inbox 消费协议。无未决设计问题。
