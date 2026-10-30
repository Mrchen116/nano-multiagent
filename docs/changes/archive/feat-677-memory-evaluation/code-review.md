# Code Review: feat-677

## Round 1

- review_mode: `full`
- executed_base: `51b23e42b`
- validated_at: `97a8b168339fd6dc454537744db152597a3cf0cf`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**
- 范围：上述完整实现 diff 及其受影响的 MemorySources、Dreaming、DocumentMemory、Global 工具和 RuntimeClient 消费链。审查者未参与实现，未修改源码、测试、配置或设计。

## Findings

```json
[]
```

未发现具有具体触发场景及直接证据的存活缺陷。此结论覆盖机制与接口，不表示真实候选模型或 judge 已验证。

## Coverage

- `evals/memory/dataset.ts:53` 白名单拆开 history/question/gold，保留全部双方回合、日期和同日顺序；原题 ID 及 `_abs` 等标注不进入候选输入。`evaluation/history.ts:20` 经公开 persistence 导入合法配对事件，空来源 baseline 先于导入；user 使用 Inbox，assistant 使用 send_message，imported provenance 不冒充本轮网络送达。
- `evaluation/runtime.ts:70` 由真实 Dreaming status/start 处理当前候选准备完成度，不以文件存在或一次维护成功替代全部完成；未完成、阻塞与预算耗尽均有独立状态。框架只依赖 product-contracts 的 prepare/answer/close，未读取 Dreaming 状态或记忆布局。
- `evaluation.ts:91` 每次 answer 启动独立 runtime/workspace/session，复制封存记忆及必要状态后走正常 DocumentMemory 装配。`runtime.ts:45` 在宿主工具入口拒绝旁路；`evaluation.ts:183` 的本地产品服务只提供本题 question 与本地投递，不连接历史 Inbox 或生产 IM。即使 Global 固定基础工具仍出现在 schema，其他操作也被该 guard 拒绝。
- `runtime.ts:24` 在 agent/request 施加输出上限，并在 llm/stream 验证和限制请求数；`evaluation.ts:58,97,120,152` 的阶段定时器、取消与进程组终止负责回收。Runner 的超时清理失败会停止后续题，不把后台环境泄漏隐藏成成功。
- `plan.ts:50` 分别冻结数据/题集/评分协议与产品/实际构建/锁文件/模型及限额身份；`runner.ts:44,78,127` 保留全部计划分母、原回答和历次 judge 尝试。CLI 默认计划零模型调用，run/score 明确 opt-in；score 不重启候选。
- 未修改生产接线或 current 产品行为。suite README 是新增评测协议权威，`docs/README.md` 与 `evals/README.md` 已更新导航；Gateway/PA 的 no spec delta 成立。

## Agent Context Implementation Review — Mode B

触发面：历史物化、时间/身份/来源、准备材料、记忆恢复、答题工具及问题、独立 judge。沿来源→物化→真实来源选择→Dreaming 文件读取→记忆封存→冷上下文→本地公开交付检查。

复用 `progress.md` 在受审实现上的 5 files / 13 tests、相关 package build 和 eval tsc 证据；阅读了全部新增测试及相关现有产品限制。另执行 `pnpm exec tsx /tmp/feat677-review-probe.ts`，使用真实锁定 DSH 与现有确定性 provider fixture，新增 assistant-only 会话、连续 user、中文/emoji/换行，共 3 sessions / 6 messages：prepare=ready、answer=completed。准备阶段 12 次实际 llm/stream 请求包含新增双方原文、长消息尾部与原日期；首请求是 Dreaming 的受限 system/user，工具为 edit/finish/glob/grep/read/write。冷答题 7 次请求未包含这些原历史；问题只在 answer 出现；旧 runtime read 与越界 glob 均被拒绝（deniedTools=2）。最终答案来自实际本地 send_message 回执。

脱敏执行摘要对应现场：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-review-9cAoYH/`，准备请求 `prepare-iF5WJ2/requests.jsonl`，答题请求 `answer-gCbkoG/requests.jsonl`；完整请求仅留本机，不提交。所有候选子进程均经 close 结束。脚本与合成审计材料保留供本轮复查。

证据限制：llm/stream 捕获证明 DSH 组装后、provider 适配前的交付及确定性工具链，不能独立证明 OpenAI-compatible wire 序列化，也不能证明真实模型理解、工具选择或记忆质量。本轮授权禁止真实候选与真实 judge，未运行它们，未下载或跑正式 benchmark；这符合本 unit 明确的交付范围。独立审查未重复全量测试；调用方随后提供的全仓 build/typecheck 与 Python/docs/lint 结果作为补充门禁，不替代上述机制检查。

## Round 2 — 最新父分支适配

- review_mode: `patch`
- executed_base（main merge-base）: `082e72ec4becb37d4ba08c3e3a8e0d2bf45da087`
- effective stacked base: `3e9a46030939bfcce351b7df2e29e5f3c2439055`
- review_diff: `117873fd1..93c8e305bf30de6f0354510f3d9e8eee46b293c1`
- parent_upgrade: `80db8b9a6..3e9a46030`
- validated_at: `93c8e305bf30de6f0354510f3d9e8eee46b293c1`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**

### Findings

```json
[]
```

无确认缺陷。此次只审评测自有增量，并沿父升级影响到的 Dreaming、DocumentMemory、来源物化及上下文恢复检查适配是否完整；未重新审父 PR 全部实现。Round 1 的历史结论保留，涉及旧准备机制的描述以本轮证据为准。

### 增量覆盖

- `evals/memory/plan.ts:14,69` 移除已退役的 Dreaming `maxSteps/maxRunMs` 并更新 candidate adapter 标识为 v2；strict schema 拒绝静默忽略旧配置，README 明示迁移方法。prepare 的外部 timeoutMs/maxModelCalls/maxOutputTokens 不变，实际构建、锁文件、候选模型/记忆配置仍进入 candidate 身份；历史、问题、评分规则和 protocol 计算未改。
- `packages/dsh-integration/src/evaluation.ts:212` 只给 prepare 加入既有 contextTools。父实现 `knowledge/dreaming-agent.ts:35` 通过父工具资格开启维护自身 notes/history/new_context/get_context_remaining；独立业务来源恢复由 `dreaming-history.ts:63` 的 source_history 提供。两者有不同的描述及数据作用域。父级的 sourceDirectory/qualifiedEvents 按可信来源、冻结时间/序号范围过滤；评测仍只导入完整原对话，没有构造子任务。
- `evaluation/history.ts:20` 的公开原生导入和空来源 baseline 接线不变，仍适用于新版根会话连续原文选择；`evaluation/runtime.ts:70` 继续使用真实 start/status，只有最终 backlog=no_eligible_increment 才 ready。父 `dreaming.ts:159-211,330` 已在自身循环中处理连续批次；框架不需要理解新批次或 finish 私有格式。
- 父 DocumentMemory 改为业务 Agent 只读、Dreaming 写正式记忆，评测没有另加写入器或旧 checkpoint 调用。`evaluation.ts:224` 的复制集合仍只含 memory 及 documents.json；父 MemoryDocuments 状态布局在这次父升级没有变化。准备侧的 notes、维护 session、Dreaming 输入和 runtime 数据没有复制给 answer。answer 的工具 guard 与仅本题 Inbox/本地发送服务也未改。
- 新 fixture 在当前产品的 direct input 上执行 source_history、notes/new_context/history、正常文件维护和批次级 finish，不再解析旧逐单元 File list。输入容量降到 1000 使长消息走真实连续批次；扩展的既有主旅程检查成功工具结果和冷答题排除维护笔记。没有把这些实现细节移入稳定 Runner 测试。
- 评测没有独立 IM 服务。实际 Dreaming schema 仍可能包含父级 conversations，但本地产品桥没有 memory.conversations 接线，因而不会获得额外 IM 原文；suite README 明确说明该限制。此处不把工具名出现在 schema 当作已可用的服务证据。

### Agent Context Implementation Review — Mode B（delta）

复用 `/tmp/feat677-sync-before.log` 的兼容性红测：旧 fixture 在新版第一次维护后因 without finish 返回 failed，没有误报 ready。复用 `/tmp/feat677-sync-targeted.log`：`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts`，5 files / 13 tests 通过，包含现有请求上限与挂起 provider 清理。

独立执行 `pnpm exec tsx /tmp/feat677-sync-review-probe.mts`，仅复用本仓确定性 provider，保留可复查现场：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-sync-review-mtuKAl/`。2 sessions / 4 messages、maxInputTokens=1000，prepare=ready，6 个独立 Dreaming 批次合计 66 次 llm/stream 请求，全部 maxTokens=2048。每批实际工具结果均证明 source_history 查询成功返回原长消息尾部、notes 恢复 EVALUATION_RECOVERY、history 返回自身旧窗口。首批第 0 次请求含原批次输入，第 3 次请求在 new_context 后不再含原输入，第 4 次请求才通过 notes 成功读回维护笔记，随后 history 返回该维护 session 的 initial 窗口；这证明换窗与恢复真实执行，未仅核对工具列表。

本次冷答题 completed，本地 send_message 交付成功；冷请求没有 LONG_MESSAGE_END、UNRELATED_HISTORY_ONLY 或 EVALUATION_RECOVERY；FUTURE_SYNC_REVIEW 未进入准备请求，旧 runtime read 和越界 glob 拒绝共 2 次。准备请求定位 `prepare-jZMNdU/requests.jsonl`，答题 `answer-J19mpw/requests.jsonl`；pid 26076 / 28086 已确认均不存在，所有子进程经 close 清理。

限制：捕获仍是 DSH 组装后、HTTP provider 适配前的 llm/stream，不证明最终 wire 或真实模型理解、恢复策略和记忆质量。LongMemEval 本次只有对话，未覆盖父产品的子任务提炼；未接真实 IM。真实候选/judge/正式 benchmark 均未启动。源码和上述受影响机制的证据充分后停止，不扩大复审未变的 dataset/Runner/judge 或重跑全量门禁。后者由调用方另行记录。

## Round 3 — 时间回放修订

- reviewer_target: `/root/timeline_static_review`，独立审查者，未参与受审实现。
- review_mode: `patch`
- review_diff: `a524e3b900cfd32a4dc30ef88969dec635540a2e..13fff74b2ccb3d82e62638108a96363adea82fee`
- effective stacked base: `3e9a46030939bfcce351b7df2e29e5f3c2439055`
- validated_at: `13fff74b2ccb3d82e62638108a96363adea82fee`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**

现场核实 HEAD 与指定 SHA 一致、a524e3b90 是直接父提交，指定 effective base 在本分支祖先链；开始时工作区 clean。范围为本轮 13 文件 patch 及其受影响的产品准入、来源冻结、恢复和冷答题链；不重审无关父实现。保留 Round 1/2 对不变 dataset、Runner、judge、来源映射与隔离的适用证据；旧轮“必须清空 backlog 才 ready”的结论已被本轮批准协议替换。设计 Round 2 Approved；本轮仅追加本报告和 verification.md，不改源码、测试、配置或设计。

### Findings

```json
[]
```

### 增量覆盖

- `knowledge/dreaming.ts:74-107,131-149`：宿主时钟在 owner 初始化前启用，关闭该实例 timer/step 回调准入；默认生产实例仍用 Date.now 和原 timer/step。nextAutomaticAt 与 tick 共用 automaticTiming，周期、静默和重试条件未复制到 adapter。tick 返回真实 start 结果；时间改变不触及全局 Date、HTTP 或进程定时器。
- `evaluation/history.ts:18-35` 与 `evaluation/runtime.ts:88-111`：所有空来源在 baseline 前注册，正文仅在对应到达点通过公开持久化追加；同刻 do/while 全量追加后才 recordActivity 和准入。每次 await tick 完成才推进逻辑时间，业务历史不广播到工具执行监听器，不重演业务动作。source_history 继续受真实冻结范围及来源资格约束。
- `evaluation/runtime.ts:79-86,113-120`：只有正常完成或无合格增量能继续回放；失败、partial、cancelled 和请求预算耗尽不能落入正常 backlog-ready。最后没有手动 start 或向未来跳转，whenIdle 不启动新周期；冻结后仅允许 pending/no_eligible_increment 且 active=false。
- `evaluation.ts:53-82,94-114,133-160,224-237`：收据按实际导入计数，失败不会预记尚未导入历史；真实阶段计时、请求限额、取消和进程组清理保留。冷答题仍仅复制正式 memory 和 documents.json，不复制维护输入、恢复笔记或 session；服务桥只接本题 Inbox 和本地发送。
- `plan.ts:15-21,67-77` 与 suite README：protocol v2 / adapter v3、有效 intervalMs/quietMs、会话原子到达、同刻顺序、维护期间时钟暂停和末尾冻结语义均进入身份/说明。旧 bulk 产物不能与新协议混用；通用 Runner/judge 未耦合产品调度。共享默认常量导出不增加产品能力或生产入口，Gateway/PA **no spec delta** 成立。

### Agent Context Implementation Review — Mode B（patch）

触发面为历史交付时机、Memory 累积、按需来源与自身恢复、冷答题。阅读了当前 agent-capabilities 的持续合格增量/冻结/失败契约以及实际 DreamingAgent、DreamingHistory 和答题守卫；核对最终 llm/stream 组装的 system 消息、工具 schema、来源目录、文件/工具结果与后续请求。system 继续将历史及 Memory 标为不可信依据，source_history 的 session_id 来自宿主来源目录；history 恢复维护自身，与业务原文回查范围分离。本轮没有新增模型必填身份参数或额外记忆写者。

复用 `/tmp/feat677-timeline-targeted.log` 的 8 files / 19 tests passed：包括零到期零模型请求、正常回放/冷答题、预算 incomplete、挂起 provider 真实截止、产品 scheduling 与真实 Dreaming 回归。另独立执行 `pnpm exec tsx /tmp/feat677-timeline-static-review.mts`，日志 `/tmp/feat677-timeline-static-review.log`。仅用现有确定性 fixture 和真实锁定 DSH；独立现场 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-timeline-independent-T5JKXm/`：

| 探针 | 实际交付/行为 | 证据 locator |
|---|---|---|
| chronological | 4 sessions、82 次受控请求，仅在已导入 1/2 sessions 时发请求；两个逻辑时点为 1704153600000 / 1704240000000。早期有 Berlin 而无 Paris，后期读到 Paris；未来 history-three 的 source_history 返回 items=[]、through=-1。末段两段新事实不在准备请求中，冻结 pending，正式记忆仍为 Paris。 | `chronological/prepare-DTX2KM/{requests.jsonl,timeline.jsonl,receipt.json}` |
| same-time-zero-quiet | 将后两段设为同一周期边界、quietMs=0；全部 3 sessions 的到达记录先于唯一 automatic_start。72 次请求全部 importedSessions=3、逻辑时间固定；此时 history-three 回查返回已到达原文，最终 no_eligible_increment。 | `same-time-zero-quiet/prepare-nyPXBF/{requests.jsonl,timeline.jsonl,receipt.json}` |
| provider-failure | 仅在临时 fixture 抛出确定性 provider 错误；1 次请求/1 次自动尝试后 prepare=failed、importedSessions=1，没有继续后续历史或重试，也没有 frozen-ready。 | `provider-failure/prepare-uASp7X/{requests.jsonl,timeline.jsonl,receipt.json}` |

所有请求 maxTokens=2048；首请求 roles 为 system/user/user，工具包含正常受限文件操作、finish、source_history 及维护自身恢复工具。conversations 名称仍可见，但产品桥未接 IM 补查，沿用前轮限制。pid 94832 / 99367 / 1157 均在 close 后验证不存在；未启动常驻服务或自建 worktree。原请求和临时脚本仅留本机，不提交。

冷答题复用本轮已通过主旅程在 `evaluation-runtime.test.ts:34-75` 的实际工具结果、Paris 公开投递、问题日期、原历史/恢复笔记缺席、越界拒绝和两次独立运行证据。上述证明确定性 provider 下的实际交付与机制，不证明 HTTP wire、真实模型策略、记忆质量或正式 benchmark 效果；真实模型/judge 的一题运行由 owner 单独报告，不在本 reviewer 执行范围。无存活 Context finding。

## Round 4 — 同一 Global 原生多窗口

- reviewer_target: `/root/window_static_review`，独立审查者，未参与受审实现。
- review_mode: `patch`
- review_diff: `cb296e8affc78715a3013bb35c737fc2bfec41a3..8ced1ccd7da12a6437a90927f8b2d632c4bcd66c`
- validated_at: `8ced1ccd7da12a6437a90927f8b2d632c4bcd66c`
- parent_product_baseline: `efaa2bbae3e21f8835fea477b1085c8efb7f0c93`，经 `9e5cfd6cc6019a2767f612ce5dbd504e4b3a29d9` 合入；两者均已核实在受审提交祖先链。
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**

开始时 HEAD 等于冻结版本、工作区 clean。审查本轮 13 文件 patch 及其受影响的持久化/来源/恢复/冷答题消费链；读取 Gate 2 Round 4 Approved、spec、design 的单根多窗决定、M1、current Global/Memory 契约及 codex-execution-notes。保留 Round 3 对未变 dataset、Runner、judge、时间调度与预算边界的适用证据。父版本删除 input.md/finish 不在本次实现内；fixture 跟随父版本正常 turn/end 完成，没有恢复退役工具。

### Findings

```json
[]
```

### 增量覆盖

- `evaluation.ts:56,174,213`：只注册一个可信 root binding，来源许可只含唯一主人聊天目标 `evaluation-question`；原段 ID 保留于 provenance/source-map，不成为额外 root 或聊天目标。`history.ts:22-26` 在首次真实加载前持久化空根并初始化 baseline，后续加载未替换 Dreaming 实例或 owner。
- `evaluation/history.ts:52-118`：每段到达后才通过公开 persistence writer 和 detached Session 追加；seq/turn/callId 跨段延续。后段边界为完整 start/summary/replace/end，替换前一活动窗口及旧 checkpoint；原 append-origin 正文完整保留。结构提示明确 imported-history，不含业务摘要或 Notes。TokenMeter 和所有新增 DSH import 均使用已声明公开 exports，没有 private import 或第二套运行时。
- `evaluation/runtime.ts:78-110`：真实自动尝试前恢复同一 root，完成后等待维护/parent idle、flush、dispose；下一次导入才重新取得 persistence writer。`history.ts:29-38` 仅对交接中的公开 SessionAlreadyOwnedError 做 5 秒有界等待，其他错误直接失败。导入未广播业务工具事件；换窗不重新激活 owner，也不自行触发维护。
- `plan.ts:76`、suite README：candidate v4 及 single-global-session / dataset-session-as-native-window / one-owner-conversation 进入候选身份；protocol v2、时间/冷答题/评分口径未改。长期说明区分固定数据分段与产品 token-pressure 换窗；外部方法研究页和导航没有变成第二份执行协议。Gateway/PA **no spec delta**。
- 受影响测试在原 evaluation runtime 文件内 rewrite-merge，新增零到期多窗场景从公开 Session surface / History 验证真实替换与读回；主旅程从实际 source directory 取唯一根，并核验实际 source_history 工具结果和冷投递。没有靠窗口目录或私有状态快照代替消费结果。

### Agent Context Implementation Review — Mode B（patch）

触发面为单根窗口交付、来源许可/原文身份、冷/live 交接、History 恢复与冷答题。沿 imported-history → 公开持久化 → MemorySources 冻结 → 实际 Dreaming system/messages/tools → source_history 与自身恢复 → 正式记忆 → 新 answer runtime 检查。实际 system 将历史及 Memory 标成不可信证据，source_history 必填 session_id 来自宿主目录；业务 source_history 与维护自身 history/notes 的语义和范围仍分开。没有新增模型不可获得的身份参数或额外记忆写者。

复用 `/tmp/feat677-window-targeted.log` 的 `pnpm exec vitest run packages/dsh-integration/tests/evaluation-runtime.test.ts evals/memory`：5 files / 15 tests passed；红证据 `/tmp/feat677-window-red.log` 在旧实现实际得到 1 窗而非 4 窗。相关 package build 已由 owner 记录，本 reviewer 未重复全量检查。

独立执行 `pnpm exec tsx /tmp/feat677-window-static-review.mts`，日志 `/tmp/feat677-window-static-review.log`。只用本仓确定性 provider、真实锁定 DSH 和两个隔离合成现场；另在公开 agent/created 事件观察恢复后的活动 surface，没有改产品逻辑。证据根 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-window-static-review-awo4PT/`，脱敏结果 `summary.json`：

| 探针 | 直接结果 | Locator |
|---|---|---|
| chronological | 4 segments / 6 turns、同一 root、4 个原生 History 窗、两次真实 root 加载；第二次活动 surface 含 Paris，不含 Berlin 长原文。84 次准备请求仅在已导入 1/2 段时发生；早期 source_history 只列 1 窗，后期列 2 窗并按返回的 window/item 读回 LONG_MESSAGE_END。 | `chronological/{live-roots.jsonl,imported-root.json}`；`chronological/prepare-xzdQ3z/{receipt.json,requests.jsonl,timeline.jsonl,source-map.json}` |
| cursor / recovery | 每批来源目录只有同一个 root、baseline=-1；允许 through 随实际批次从 6、13 到 36。冻结 backlog 的 start=36、through=61，证明后续窗口没有重置已消费进度。首维护 session 的请求索引 5 在 new_context 后不含长原文/维护笔记，索引 6 通过 notes 成功读回 EVALUATION_RECOVERY，索引 7 含成功的自身 history 列窗结果。 | 同上 `requests.jsonl`、`timeline.jsonl`；索引均从 0 起，限定首维护 session |
| cold answer | 新 runtime 7 次实际请求；本地 send_message 回执交付 `You live in Paris.`。请求含原问题日期，不含准备长原文、干扰原文或维护笔记；旧 runtime read 与越界 glob 均拒绝，deniedTools=2。未来问题标记未进入任何准备请求。 | `chronological/answer-fLVdd7/{answer.json,requests.jsonl,denied-tools.jsonl,deliveries.json}` |
| no-due | 四段都在三分钟内到达，真实持久化形成 4 窗；0 次 root 加载、0 次模型请求，ready 并保留 pending。最后活动 surface 仅最后原段及结构 checkpoint，旧正文仍可由公开 History 读取。 | `no-due/imported-root.json`；`no-due/prepare-CYx28T/{receipt.json,timeline.jsonl,source-map.json}` |

所有准备请求 maxTokens=2048；实际 system/message/tool schema 与成功工具结果已读取，未将 fixture 固定结论当作真实模型能力。pid 66811 / 69064 / 69395 均在 close 后以 process.kill(pid,0) 确认不存在；脚本自身已退出，未启动常驻服务或自建 worktree。原请求与临时脚本仅留本机，不提交。

限制：上述 llm/stream 是 DSH 最终组装后、HTTP provider 适配前的请求，证明本地确定性链路的交付/恢复/投递，不证明最终 HTTP wire、真实模型策略、记忆质量或正式分数。未调用真实模型/judge、生产 IM 或外部业务。只追加本报告与 verification.md，由 owner 提交。

## Round 5 — 常驻 PA 关系与冷答题产品接线

- reviewer_target: `/root/pa_context_static_review`，独立审查者，未参与受审实现。
- review_mode: `patch`
- review_diff: `75f4794d38cfcd33efbd49d259f7e5289ea9e763..a992a059d043fb118e98adb540304ed329e1b036`（12 files）
- validated_at: `a992a059d043fb118e98adb540304ed329e1b036`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **changes required**

开工时 HEAD 与冻结版本一致、工作区 clean；本轮只审上述 patch 和受影响消费链，不重审父分支或历史整个 PR。读取本仓 AGENTS、code-review / verifier / agent-context-review skills、Context / testing 规范、current Global/PA/Memory 契约、unit spec、设计新增冷答题修正和 M1。Gateway / PA 为 **no spec delta**；评测 adapter v5 的长期差异由 suite README 维护。后续其他角色修改 acceptance.md 未纳入本 reviewer 修改。

### Findings

```json
[
  {
    "file": "packages/dsh-integration/src/evaluation/runtime.ts",
    "line": 57,
    "summary": "[P2] 等待后台子 Agent 与后续根唤醒收口后再结束答题",
    "failure_scenario": "本 patch 放行并向答题模型正常提供 subagent，且其默认是后台执行。根 PA 在成功启动后台 child 后先结束当前轮等待结果时，idle RPC 仅等待 root.whenIdle（runtime.ts:128-130）；answerQuestion 随即读取 audit/deliveries、把根轮 completed 当成整题完成，并在 finally 关闭 runtime（evaluation.ts:113-126）。child 尚在运行就会被停止，正常委派的答题被记为 no public answer；若根已发送了进度，尚未完成的进度还可能直接成为评分文本。",
    "review_mode": "patch",
    "status": "CONFIRMED",
    "surface": "工具 schema / 默认后台委派 / 冷答题执行生命周期",
    "expected": "模型依照实际工具说明启动默认后台 child 后，可等待其完成通知，在同一 PA 常驻 session 继续处理并通过产品 send_message 交付；阶段仍受现有真实时间与全树模型请求限额约束。",
    "observed": "真实 DSH seam 返回 started subagent 成功；child 已进入 provider 请求。根首轮 completed 时评测在 803ms 就返回 failed/Agent delivered no public answer，child 的计划回传在 1200ms 后，尚未来得及送达；answer audit 当时只记录 4 calls，而退出前请求文件已有含 child 的第 5 次请求。",
    "impact": "工具可见性与可执行生命周期不一致，评测会因正常产品委派路径产生假失败或提前评分，README 所称原生内部委派未完整兑现。",
    "recommendation": "在现有阶段限额内等答题执行树及其引发的根后续工作真正收口，再采集 audit/terminal/deliveries；在现有 evaluation-runtime 旅程中覆盖默认后台 child 延后回传、根恢复并实际交付的场景。不要以拒绝模型已可见的默认委派工具规避。",
    "severity": "WARNING",
    "evidence": "/tmp/feat677-pa-delegation-probe.mts；/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-pa-delegation-zVj084/answer-XO15ZN/{answer.json,requests.jsonl,runtime.log}。仅使用既有封存合成记忆、锁定 DSH 与本地确定性 provider；确认的是机制，不声称真实模型必然选择委派。"
  }
]
```

### 增量覆盖

- `evaluation.ts:64-86,174-191,206-217`：PA/owner/binding/conversation/rootSession 五项身份在准备/封存/答题间复用；新的 runtime/workspace 只恢复正式记忆与 documents 状态，未复制准备 sessions、Inbox 或维护笔记。prepare 的原生 Inbox 映射使用相同真实 owner、私聊/participant/web 字段。不是只改显示名。
- `nano-product.ts:19-22,43-88`：composition root 注入 product port，实际运行现有 GlobalAgent / InboxStore / NodeStore；问题正文从 receive 进入，生成随机消息/relay ID，题号没有作为用户消息身份。DSH 接入包不反向 import PA；PA 不 import DSH；无第二套 Agent Loop 或生产 RPC。
- `evaluation.ts:108-112`：在首轮 session 装配前同步来源资格；既有真实捕获的首请求有 personal-assistant role、有效 Paris 记忆入口、来源 generation=1 和 nano-memory 目录，无 source_eligibility_pending。答题自己的 Notes / History / new_context 实际成功；准备 History 原文查询为空，文件越界拒绝两次。
- `runtime.ts:51-70`：文件 read/glob/grep 对准备记忆和随包技能做 realpath 边界检查；控制区、旧 runtime 和其他题不能经该路径读取。上下文工具访问新 runtime 的自身会话；product transport 只保存本次问答，不存在连接原 IM 历史的后端。包内 Skill 可加载，但不能因此执行未开放文件写/插件工具。未发现原历史或 gold 旁路。
- `nano-product.ts:25-72`：本地 conversations 支持当前私聊 info/read/search、分页、时间/关键词过滤，public list 不返回私聊；不接受其他 target。来源修改和其他聊天/群创建明确不可用，与 README 差异矩阵一致。发送仍走 PA 私聊实际重核与回包。
- `plan.ts:18,63-83`：maxInputTokens 可选、周期/静默沿产品默认；candidate v5 加入实际 PA build、adapter 和技能 hash，protocol v2 / Runner / judge 未变。测试沿用原文件扩展，而不是新建平行框架；已有效的专项 5 files / 15 tests passed，但未覆盖本 finding 的后台委派收口。

### Agent Context Implementation Review — Mode B（patch）

触发面是常驻 PA 关系、首次入口来源资格、Inbox 实际字段、技能与上下文工具可用性、冷状态恢复及工具生命周期。组合检查 source/owner → configuration → GlobalAgent.receive → Inbox → 实际 llm/stream system/messages/tools → 工具结果/换窗 → PA 本地发送。除上述 finding 外，没有发现必填参数无来源、装配身份不一致或旧历史泄漏；首请求问题正文只在后续 Inbox.read 后出现，当前日期保留为原 question_date。

复用并亲自读取 owner 提供的 `/tmp/feat677-product-suite-final.log`（5 files / 15 tests passed）以及 `/Users/czj/.local/share/nano-evals/context-parity-20261030/result.json`。后者准备 84 次、答题 16 次真实 DSH 组装请求，answer 为 completed 且实际本地交付 Paris；定位 `prepare-mdO7ot/{prepared.json,receipt.json,requests.jsonl}` 与 `answer-Dw0Qug/{answer.json,requests.jsonl,denied-tools.jsonl}`。已读首请求与 fixture-0/1/5/6/7/9/10/11/12/13/14 的实际结果；同一 session、Inbox 读后消费、nano-memory 加载、答题恢复、原历史空结果与两个越界拒绝均可复查。prepare PID 9015 / answer PID 9614 均已退出。

关键缺口独立命令：`pnpm exec tsx /tmp/feat677-pa-delegation-probe.mts`。该临时脚本只替换隔离 provider fixture：根 check/read 后启动默认后台 child，结束当前轮等待；child 延后 1200ms 通过原生 send_message(agent_id=root) 回传 Paris，根下一步准备通过产品 send_message 回答。实际 tool probe-3 返回 started subagent，根先 completed、评测在 803ms 返回 failed；child 回传前 runtime 已收尾。结果在上述 finding locator；PID 18203 已退出。更早同类初探根目录 `feat677-pa-delegation-JGVyLW` 同样退出，PID 16781 已确认不存在。未启动常驻服务或自建 worktree；不修改源码/测试/设计、不提交报告。

限制：所有请求证据均是最终组装后的真实 DSH llm/stream seam 与本地确定性 provider，不证明 HTTP wire、真实模型选择/理解、记忆质量或正式 benchmark 分数。本轮没有真实模型、judge、生产或外部业务调用；不将旧单题结果改名为 v5 结果。

## Round 6 — 后台委派收口 closure

- reviewer_target: `/root/pa_context_static_review`
- review_mode: `closure`
- finding_origin_head / pre_fix_head: `a992a059d043fb118e98adb540304ed329e1b036`
- review_diff: `a992a059d043fb118e98adb540304ed329e1b036..de2b92942e5f4b03c9b6d86d2e13da510e3e3743`
- validated_at: `de2b92942e5f4b03c9b6d86d2e13da510e3e3743`
- branch: `codex/feat-677-memory-evaluation`
- focus_findings: Round 5 `[P2] 等待后台子 Agent 与后续根唤醒收口后再结束答题`
- focus_status: **closed**；无 still_open / superseded 项。
- retained: Round 5 其余 PA 身份、真实产品接线、来源资格/首入口、原历史与控制区隔离、Context 恢复、随包技能及文档差异结论；Round 4 无 diff 的时间回放/窗口/维护机制证据。
- verdict: **pass**

HEAD 与冻结版本一致，开工 clean；只核上述修复与受影响的生命周期、计数、限额及文档措辞，不重审父分支或整个 PR，也不重复全量测试。独立读取红证据 `/tmp/feat677-pa-child-red.log`：旧实现第二次冷答题 failed/no public answer；复用最终 targeted `/tmp/feat677-pa-child-final.log`：5 files / 15 tests passed。源码改动只有专用评测 runtime、既有 fixture/旅程扩展；其余是本 unit 报告及文档。

### Findings

```json
[]
```

### Closure 与 Context Implementation Review — Mode B（targeted）

`evaluation/runtime.ts:27-33,135-146` 通过 DSH 已声明公开 `subagent/start` / `subagent/end` 事件记录所有活跃 residency/run；根 whenIdle 后如有 child，事件唤醒收口检查，再次等待根后续工作。候选进程隔离且同一时间只有一个 answer 操作，集合覆盖该候选全部子层级，不需要另复制执行调度。检查本机锁定上游实现可见 continuable settlement 先向父发送通知，再发布 end；新检查下一轮等待 root.whenIdle 可包含相应后续工作。无新增 private import、第二套 Agent Loop 或生产行为变更。

实际受影响消费链已验证，原 finding 的可成立条件被消除：

| Evidence | 直接观察 | Locator |
|---|---|---|
| 相同原失败探针重跑 | `pnpm exec tsx /tmp/feat677-pa-delegation-probe.mts`；根默认后台委派并结束当前轮，child 延后 1200ms 原生回传后，根公开发送 Paris。answer completed、8 次实际请求=usage.modelCalls 8；包含两个 child 请求、根消费回传、实际产品 send_message 和最终 settlement 通知后的根请求。 | `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-pa-delegation-tIyJpR/answer-lFAfzh/{answer.json,requests.jsonl,deliveries.json}` |
| 正式旅程回归 | 既有主旅程第二次 answer 默认后台 child 读取正式 city.md、延后回传；断言根实际请求消费 DELEGATED_RESULT、最终公开 Paris、完整请求数与全树 usage 一致。旧实现红、新实现 15 项通过。 | `/tmp/feat677-pa-child-{red,final}.log`；`evaluation-runtime.test.ts:153-163`；fixture 的 child 分支 |
| 全树请求预算 | `pnpm exec tsx /tmp/feat677-pa-closure-limits.mts budget`，maxModelCalls=5；实际 root/child 合计恰 5 请求，后续模型请求未进入 provider，未交付时 failed，进程退出。所有已进入请求 maxTokens=2048。 | `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-pa-closure-budget-dLTEAv/answer-oHETjs/{answer.json,requests.jsonl,usage.json}` |
| 等待 child 时仍受真实截止 | `pnpm exec tsx /tmp/feat677-pa-closure-limits.mts timeout`，child provider 延后 10000ms，阶段 timeoutMs=5000；child 已进入第 5 个请求时截止关闭连接、返回 failed 并回收 runtime，未等待 child 到 10 秒才结束。 | `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-pa-closure-timeout-mco4AG/answer-Sie6tK/{failure.json,requests.jsonl,usage.json}` |

外部 timeout / 模型次数 / 每请求 maxTokens 的 enforcement 未被新事件等待替换；llm/stream 全局拦截继续计入子树全部请求。provider fixture 不提供 token usage，inputTokens/outputTokens/costUsd 仍诚实为 null；没有从 modelCalls 外推实际 token 或成本。上述最终进程 PID 52379 / 60488 / 59583 已确认不存在；额外探针 PID 54850 / 54851 也已退出，未遗留服务。

README 与 design 改为直接引用当前产品按模型容量计算完整首轮输入的规则，正常评测不另设 maxInputTokens 材料上限；没有继续用旧固定值解释当前设计。现有公开可选配置仍可解析属保留产品能力，与正常评测配置指导不冲突。Gateway / PA **no spec delta**；候选 v5 / protocol v2 保持，未改旧真实评测结果。

本轮仅验证确定性真实 DSH seam、实际工具与本地产品交付；真实模型选择/理解、HTTP wire、记忆质量与正式分数继续未验证。没有真实模型/judge/生产调用。只追加本文件和 verification.md，不提交；修复充分覆盖，结束 closure，不扩大审查。
