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


## Round 3

### Metadata

- reviewer target: `/root/design_review`（沿用独立 reviewer；未参与本次跨仓设计或实现）
- review_mode: full
- mode_reason: 派发建议 delta，但实际新增 LLM_PROXY 仓库、共享 provider 转换边界、incident 的真实链路要求及 M1 范围/退出条件；按 skill 对需求、核心边界或 milestone 变化采用 full。保留 R1/R2 未受影响的源码证据，同时完整核对新增边界与整体覆盖。
- started_at: 2026-09-20T18:07:05+08:00
- completed_at: 2026-09-20T18:09:43+08:00
- duration: 158 秒
- reviewed baseline: Nano `codex/bugfix-567` / `fbfa77dfef2c4c3b2eeb6667916ccace8ae3bbd6` 的冻结 incident/design 增量；LLM_PROXY `016f32eb7c44f58d8429d833f8973c8cc43ba337`。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

Responses 支持结构化图片工具输出的前提成立；跨仓职责划分与真实模型验收方向合理。但共享 Anthropic → Chat 转换器也用于真正的 Chat Completions 上游，设计尚未区分其 wire 契约与 Codex 中间形态，直接按当前决定实施会带来非 Codex 路径的协议回归。

### Coverage 与证据

1. **原范围与用户约束。** incident 保留普通文件仅描述、当前图片失败提示、历史失败隔离、成员保护与接收后消费，新增范围有用户“一并修了”的确认。决定 1–5 未修改，原模块职责、索引、snapshot/consume、steer fallback 及 current/global 消费差异继续沿用 R1/R2 的证据；本轮没有把 provider 修复下沉到 Nano 内核，也未新增文件解析能力。
2. **真实 provider 入口。** LLM_PROXY `proxy_converters.py:178–183` 对 tool_result 调用纯文本提取器；`:167–177` 已支持顶层 base64/URL 图片；`:639–643` 已把结构化 tool 内容交给 `_tool_content_to_function_output`。`tests/test_proxy_converters.py:100` 现有回归覆盖 image_url → function_call_output 的 input_image，支持复用而非新造转换协议。实际请求入口是 `src/handlers/messages.py:_build_openai_bridge_payload`，`:405` 共用 Anthropic converter 后再按 auth_type 分支，并非仅检查独立 bridge wrapper。
3. **官方能力前提。** 2026-09-20 核对 [OpenAI 官方 SDK Responses input schema](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/responses/response_input_param.py)：FunctionCallOutput.output 接受字符串或结构化内容列表，并明确包含 text/image/file；因此不能把本次丢图归因为 Responses 一律不支持工具图片。实际 Codex 上游和模型仍需设计要求的真栈识图验收，官方 schema 本身不替代该验收。
4. **消费者和 delta。** Gateway delta 继续表述文字/有效图片正常进入上下文、普通文件未读取、历史失败和接收后消费；无需让 Nano canonical 暴露代理专用 payload。incident 新增 provider 链路验证是该结果的实现闭环，独立 LLM_PROXY PR 和 Nano unit 联合关闭的安排合理。
5. **测试与验收。** M1 已纳入 base64/URL 嵌套工具图片、纯文本原形态和真实 Nano → 代理 → Codex global 识图。验收明确使用独立代理 worktree/端口、隔离 Gateway 指向该代理、真实视觉模型及创建者清理，不能单测代签。尚缺共享转换器非 Codex 分支的协议保护和对应回归，见 R3-W1。
6. **回退。** 两仓独立 revert、无迁移、任一侧回退会重现对应缺口的说明准确。跨仓版本和 PR 应按最终交付实际记录；本轮不把合并或设计通过当作部署/识图已通过。

### 架构判断

Nano 负责有效图片进入既有 Anthropic 工具结果，LLM_PROXY 负责 provider 适配，Codex converter 负责 Responses 输出，是正确分工。复用顶层图片转换与既有 `_tool_content_to_function_output` 足够，无需新增内核块、文件解析工具或通用多模态框架。

但该 converter 是共享 wire 边界。内部暂存 `role=tool/content=image_url` 可以服务 Responses 转换，不能据此宣称其为 OpenAI Chat API 可接受的工具消息；能力选择应在已知目标的代理组装边界明确收口，而不是由 Nano 感知 auth_type。这里有实际既有消费者，属于必须处理的协议边界，不是假想兼容需求。

### 历史问题闭环

R1/R2 无未关闭设计 finding。R2 Author Resolutions 已记录接受；其实现缺口是否通过代码/产品门禁不由本轮设计报告重签。R3 是新增跨仓范围审查。

### Issues

#### R3-W1 — 区分 Codex 中间图片工具消息与真正 Chat Completions wire 输出

- 位置：`design.md` 决定 6、接口与数据流最后一项、M1 provider 回归范围。
- 证据：LLM_PROXY `src/handlers/messages.py:405` 无条件调用同一 converter，`:435–436` 在 `auth_type != "codex_oauth"` 时直接返回该 Chat payload；Codex 分支才继续转换成 Responses。设计目前统一要求工具 content 转 text/image_url blocks，未限定这只是 Codex 的内部中间形态。[OpenAI Chat Completions 官方 schema](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 的 ChatCompletionToolMessageParam.content 只接受 string 或 text blocks，不接受 image_url。Responses 支持图片不能证明 Chat 工具消息也支持。
- 未修后果：普通 OpenAI Chat 目标收到同样的 Anthropic 含图 tool_result 时，原本合法的文字工具消息会变成非法多模态工具消息并被上游拒绝；“不扩大其他消息协议”无法兑现。
- 收口要求：明确目标能力分流和非 Codex 行为。最小范围可让嵌套工具图片保真仅在现有 Codex/Responses 转换链启用，普通 Chat 保持原有效 wire 行为；无需本 unit 额外开发普通 Chat 工具图片能力。增加实际 `_build_openai_bridge_payload` seam 的双分支回归，断言 Codex 最终 function_call_output 含有序 input_text/input_image、普通 Chat 不收到非法 image_url tool blocks，同时保留纯文本形态与 call_id。

### Recommendations

无。


## Round 4

### Metadata

- reviewer target: `/root/design_review`（原独立 reviewer）
- review_mode: delta
- mode_reason: 派发建议 closure，但除 R3-W1 的目标能力隔离外，还新增 Codex 将工具图片移到紧随其后的 user input_image 这一有界适配决定，故扩大为 delta 检查；未改变 Nano 消费协议或跨仓范围。
- started_at: 2026-09-20T18:12:06+08:00
- completed_at: 2026-09-20T18:13:32+08:00
- duration: 86 秒
- reviewed baseline: Nano worktree 冻结的 incident/design 决定 6 和接口增量；LLM_PROXY `.worktrees/bugfix-tool-result-images` 基于 `016f32eb7c44f58d8429d833f8973c8cc43ba337` 的 converter/bridge/tests 工作区 diff。
- retained_from: Round 3；原附件分类、snapshot/admission、群失败范围、权限、M1 其他验收及跨仓回退要求不变。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING（设计门禁）。**

R3-W1 的设计问题关闭。新 Codex 图片投影在 Responses schema 中合法，职责仍在代理内；但实际 handler 接线与 handler 双分支回归在本次读取的实现中尚未闭环，本结论不批准实现或产品验收。具体事实已发送主会话，见下述验证边界。

### Coverage 与证据

1. **普通 Chat 隔离已在设计中明确。** 决定 6 和接口段规定共享 converter 默认仅提取文字、仅 Anthropic→Codex 显式开启图片内部结构；M1 增加普通 Chat 保持字符串。工作区 `anthropic_messages_to_openai(..., preserve_tool_result_images=False)`、`anthropic_request_to_openai_chat_body` 默认 false 与 `anthropic_request_to_codex_payload` 显式 true，证明该窄能力参数可以落实，无需新增通用路由体系。
2. **Responses 合法性。** [官方 Responses Message schema](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/responses/response_input_param.py) 允许 user message，[其 content union](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/responses/response_input_message_content_list_param.py) 包含 input image。保留 call_id 对应的文字 function_call_output，再放紧随其后的 user image message，未把 image_url tool blocks 发到真正 Chat endpoint。公共 schema 允许图片工具输出，与特定 Codex OAuth 模型链路实测看不到该图并不矛盾；后者是本次兼容处理依据，不能泛化成所有 Responses 模型的限制。
3. **语义与职责。** 文字及来源元数据留在原工具结果，call_id 不变，仅图片以 provider 可见通道紧随该结果，每个工具结果的图片次序应保持；不是把工具文字转成真人指令。Nano 持久上下文、Inbox receipt 和用户权限协议不变。图文交错在 provider 层拆为文字结果和图片序列，是为实际可见性作出的显式取舍；现有 Inbox 输出本身采用文本元数据/image_index 与图片块对应，应在多图回归中保持该对应关系。
4. **回归覆盖与真实验收。** 已读新增 tests 的 base64/URL 双路径断言，普通 Chat wrapper 保持文字、Codex wrapper 保留 call_id 并输出后续 user image；纯文本原形态有回归。设计继续要求隔离代理真实 global 识图，故不将 schema 合法或 wrapper 测试通过当作真实请求成功。本轮未重跑产品旅程，也未独立重放主会话报告的同图对照实验。
5. **验证边界：真实 handler 尚需实现复验。** 本轮读取时 `src/handlers/messages.py:_build_openai_bridge_payload` 仍无参数调用共享 converter，之后直接调用 `openai_chat_body_to_codex_payload`，不经过已开启 opt-in 的 `anthropic_request_to_codex_payload`；新增测试只测 wrapper。故仅有 wrapper 修改不能证明真实 `/v1/messages` 已修复。实现者必须在真实 handler 的 Codex 分支落实设计规定的显式开启，并按 R3-W1 验收要求增加 handler 双分支测试；普通 Chat 同一输入仍须为合法文字工具消息。这是当前实现与已收口设计的差距，交代码/一致性门禁关闭，不因本轮设计 Approved 消失。

### 历史问题闭环

- **R3-W1：closed（设计）。** Author Resolution 由本轮派发说明及 design 决定 6/接口/M1 的修订提供；已明确普通 Chat 默认文字、Codex 显式启用。R3 所建议的最终 input_image 位于 function_call_output 的测试形态，被本轮审过的后续 user image 形态替代，call_id 和普通 Chat 隔离要求保留。
- R1/R2 未受影响判断 retained。本轮不关闭任何未完成的实现或真实验收 finding。

### Issues

无未解决设计 issue。

### Recommendations

无。


## Round 5

### Metadata

- reviewer target: `/root/design_review`（原独立 reviewer，未修改产品或受审设计）
- review_mode: delta
- mode_reason: provider 输出恢复为原生 function_call_output 内容数组，撤销 R4 的后续 user 图片方案；范围为决定 6、跨仓接口及对应证据，不改变其他需求、模块边界或 M1。
- started_at: 2026-09-21T09:14:40+08:00
- completed_at: 2026-09-21T09:16:12+08:00
- duration: 92 秒
- reviewed baseline: Nano `codex/bugfix-567` / `51f10e4e3` 工作区归档设计增量；LLM_PROXY `dc39109`；本地 Codex `968835997714baaff199cfed5f89a2c65d8ca77d`。
- retained_from: Round 3/4 中普通 Chat 隔离及 R1/2 的 Nano 附件、缓冲、索引、权限结论；R4 关于 Codex OAuth 需要后续 user 图片的判断不保留。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本地 Codex 对 API-key 与 ChatGPT OAuth 共用 Responses 请求/工具输出模型；原生图片形态为 `function_call_output.output` 数组中的 `input_image`。最新设计和 LLM_PROXY `dc39109` 已撤销额外 user 图片投影，恢复工具结果归因和文字/图片顺序。此判断针对受审源码基线，不把源码契约扩大为所有远端模型识图结果的保证。

### Coverage 与证据

1. **原生输出类型与序列化。** Codex `protocol/src/models.rs:1096` 明确 function_call_output.output 可为字符串或结构化数组；`:2074` 的 FunctionCallOutputContentItem 同时含 InputText 与 InputImage，后者字段为 image_url 和可选 detail；`:2162` 定义 ContentItems，`:2228` 的 Serialize 实现直接把 items 序列化为数组。这里没有按 auth 类型改变图片表示的分支。
2. **实际工具输出。** `core/src/tools/handlers/view_image.rs:238` 的 ViewImageOutput::to_response_item 直接生成 ContentItems(InputImage)，`:249` 返回带原 call_id 的 FunctionCallOutput。并未创建后续 user message，支持把图片留在其工具身份内。
3. **客户端与认证边界。** `core/src/client.rs:784` 的 build_responses_request 从同一 prompt 构造 ResponsesApiRequest；`:946` 附近的认证解析承担 API auth/identity，不在工具输出内容中搬动图片。`core/tests/suite/client.rs:1214` 起构造含图片的历史 FunctionCallOutput，`:1285` 起断言实际请求 output 为 input_image 数组；`:1622` 的 API-key 与 `:1654` 的 ChatGPT-auth 请求测试说明两类身份使用同一 Responses 客户端路径，OAuth 差异体现在端点和认证头。这些证据合起来支持“共享图片请求形态”；并不声称这些测试单独运行了每一种远端身份/模型的真实识图矩阵。
4. **最新代理与实际 handler。** LLM_PROXY `proxy_converters.py:674` 起对 tool content 使用 `_tool_content_to_function_output`，直接形成原 call_id 的 function_call_output，不再拆出 user image；`src/handlers/messages.py:408` 已按 codex_oauth 显式开启 preserve_tool_result_images，普通 Chat 默认 false。R4 记录的真实 handler 未接入问题在所读版本中已修正。`tests/test_messages_routes.py:55` 的 bearer/codex_oauth 双分支测试断言普通 Chat 字符串、Codex 同一 output 中 input_text/input_image，且 input 仅两项，排除合成后续 user 图片。converter 回归继续覆盖 base64/URL 和纯文本工具结果。
5. **设计与证据校正。** design Changelog、决定 6、接口段均明确撤销后续 user 方案；incident 与 `M1-fix/evidence/proxy-image-boundary.md` 区分了两个事实：最初转换器确实丢图，但后续失败轮次仍指向旧代理 :4000，因此不足以证明 OAuth 原生工具图片不可见。`evidence/validation.md` 记录正确 :4010 下的原生 output payload 及红色长方形识别。这些运行记录为已读的主流程证据；本轮没有自行重放真实请求，也未用其替代对源码契约的独立检查。
6. **语义、验收与回退。** 恢复同一工具结果的有序内容可保留 call_id、图片与文字的对应及工具来源，省去额外用户消息机制；普通 Chat wire 契约继续受隔离。原 M1 的双路径回归、真实 global 识图、隔离代理版本/端口和分别 revert 两仓要求仍适用。没有新增存储或内核协议，既有 canonical delta 不需因 provider 内部表示变化扩写。

### 历史问题闭环与纠错

- **R3-W1：保持 closed。** 普通 Chat 与 Codex 内部结构的能力分流在设计、handler 和双分支测试中一致。
- **Round 4 判断纠正：撤销其将“OAuth 图片不可见”视为已建立兼容性依据的结论。** R4 虽正确指出 schema 允许 user 图片，但这不足以证明需改写工具身份；当时没有独立确认失败请求使用修复后的代理。当前源码和校正运行证据支持直接使用原生 function_call_output 图片数组。保留 R4 历史原文，仅由本轮追加纠正。
- **R4 handler 实现差距：本轮源码证据确认已接线。** 不再只依赖独立 wrapper，仍由最终代码/产品门禁负责完整实施结论。

### Issues

无。

### Recommendations

无。
