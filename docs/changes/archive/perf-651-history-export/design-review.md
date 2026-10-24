# perf-651 History Export — Design Review

## Round 1

### Metadata

- reviewer target: independent Codex agent `/root/design_review`; 未参与本 unit 设计或实现。
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖首文档、所有设计决定、实际组装与消费者、delta 和单 milestone。
- reviewed HEAD: `af01637e41f5e6cadade25dd2760a1e0a2980022`
- base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
- checkout: `/Users/czj/.codex/worktrees/history-export/nano-multiagent`
- branch: `codex/perf-651-history-export`
- started_at: `2026-10-24T00:56:36+08:00`
- completed_at: `2026-10-24T00:57:18+08:00`
- duration: `PT42S`；上述时间记录报告汇总阶段，前置只读取证已先完成但未记录起始时钟，不作为全程耗时指标。
- 初始工作区仅有未跟踪的 `packages/dsh-integration/tests/export-benchmark.tmp.test.ts`；按派发视作临时基线测量脚本，未修改、未运行、未当作产品实现。
- 受审文档 SHA-256：
  - motivation.md: `7269ced76b6e617e643fe3f1f8e9599bedd2fd1680334ba0daffd6682bf1a398`
  - design.md: `c177f32befb3a92d027da13952c7b3cd1f4e6af5d253483fbc9c24c675619eba`
  - specs/gateway/routing-delivery.md: `79c634cb3e355abd2aef6b740f8171ca2e74c1c2086bf5eeb4f8f1ff13a6e97b`

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING.** Gate 2 尚未通过。增量导出本身的职责和恢复方案合理，但原始文件真实消费者的延迟读取边界未闭合；仅在返回路径前等待队列不能兑现实际提炼时的完整可读性。

### Coverage 与证据

1. **现状与真实接线。** `packages/dsh-integration/src/index.ts:121` 创建 NativeHistory，`:271` 在 accepting=true 前调用 recoverExports，`:355-358` 在 session.export 校验 binding 后调用 path，`:587-601` 停机先等待运行结束再等待导出。`history.ts:96-105,320-337` 在 nano turn/end 为每次请求串行全量 flush、snapshot、重写；`:268-318` 原始与可读文件各自临时写入再 rename。基线重复序列化/写盘原因成立。没有以仅测试调用的实现代替产品入口。
2. **消费者。** `packages/personal-assistant/src/history.ts:145-175` 对每个来源请求 session.export 后，只将路径写入 source_jsonl_paths；`docs/specs/im/web-chat-ux.md:375-393` 明确生成 prompt 后预填普通聊天，由用户随后发送；`packages/personal-assistant/assets/skills/conversation-skill-distiller/SKILL.md:12-18` 随后要求读取所有 JSONL，无法解析时不得部分创建 Skill。workspace 副本仍是直接文件消费面。设计已披露 workspace 热更新尾行边界，但把原始提炼消费者归为“经过 session.export 即完整”并不充分，见 R1-W1。
3. **持久上界、增量和 fork。** 锁定依赖 `@deepseek-ai/dsh-session` 的公开 README 与安装实现确认 `seq` 是包含继承前缀的日志长度，snapshotEvents 接受半开区间、事件只追加，flush 等待所有 durability listeners 并传播失败。设计复用既有同步读取调用而不扩张调用面；先捕获 to 再 flush，尾段读取受 to 限制，可避免 flush 等待期间的新事件越过持久边界。成功水位在两份文件均完成后推进；首次与 fork 从零保留全部继承前缀。未引入 DSH private import 或第二份事实源。
4. **恢复与队列。** `history.ts:338-355` 既有恢复通过 sessionQuery observation 重建；锁定 `dsh-session-query/README.md:110` 说明 observation 固定事件切面。设计在初始化阶段重建并建立内存水位，长度不符/缺失/写失败清除水位后完整重建，权限等错误传播，不以空文件替代。每会话一个任务加 dirty 标志比逐请求 Promise 链简单且适合当前范围；明确失败期间新请求仍须处理，跨会话可并行、失败不伪报成功，没有无界自动重试。实现时按既定测试矩阵检验，无需另增复杂调度层。
5. **架构判断与用户约束。** `SPEC.md:29-50` 把持久历史产品投影归于 dsh-integration，PA 依赖 RuntimePort；把优化放在 NativeHistory 内合理。复用 DSH 日志、flush、query 和现有文件重建能力优于永久索引或缓存正文。保留自动更新可满足 workspace 直接读取，顺序轮次收益也不能仅靠合并队列取得；主要选择有依据。独立 worktree、不合并/部署、不删除历史、不改运行时和不扩大到任务/ACK/UI 的约束均被设计保留。
6. **delta。** `specs/gateway/routing-delivery.md` 的 canonical target 正确，ADDED 未覆盖或删除原有 Scenario；版本头、来源、envelope 过滤、图片占位、fork 与恢复语义有明确消费者描述。设计指出既有 conversation-id 与当前 session-id 命名漂移并避免命名迁移，本轮不要求借此扩大优化。新增完成边界本身须随 R1-W1 修正，不能只增加“读取时可能遇到尾行”便宣称提炼兼容。
7. **milestone、验收与性能口径。** M1-export 单切片无并行冲突；95% 指标针对应用传给文件 API 的 payload 和原始事件序列化量，未冒充设备 I/O 或生产时延。临时 benchmark 的真实 NativeHistory、临时文件与计数方式匹配该口径，但本轮只核方法，未重复运行或背书数值。现有 `tests/history.test.ts` 有真实 RuntimeClient 的 fork、compaction、来源过滤和 restart 证据入口；runbook 用确定性 LLM 避免无关模型变量合理。该测试在请求导出后立即读取（`:188-200`），尚不能代替 R1-W1 的延迟并发读取验收。无前端视觉变更，不要求原型或启动 UI。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 返回可变追加文件路径不能保证提炼 Agent 稍后读取完整 JSONL

- **位置：** `design.md:31-41,49,59,67`；`specs/gateway/routing-delivery.md:7-11`。
- **证据：** 设计让原始导出在同一路径上 append，并把 session.export 等待队列当作完整读取的解决方案。真实 PA 链路只把路径写入 prompt，IM 允许用户稍后再发送；Skill 此后才读取文件，且明确拒绝不可解析来源。session.export 的队列等待覆盖不到这个后续读取时刻，也没有阻止来源会话重新活动。旧实现通过临时文件 rename 发布完整文件；将发布文件改为原地追加新增了可见半行窗口。
- **具体场景与后果：** 用户取得来源会话的 distill prompt 后，原会话继续一轮；提炼 Agent 读取该路径时，新轮次的大事件正在追加，或追加失败留下部分尾行。即使此前 session.export 成功，输入也可能无法解析，提炼因此失败。多来源逐个取得路径还扩大了先取得路径的等待窗口。此问题是现有异步消费者的正常并发路径，不是假设用户同长度篡改派生文件。
- **要求闭合：** 明确原始导出路径在实际延迟读取期间的完整性保障，例如在显式请求时发布可完整读取的稳定副本，或通过真实消费者可执行的完整切面读取契约闭合；选择简单方案即可，不要求新事实库或广泛文件事务。若选择改变消费者行为，必须同步调整影响范围与契约，不能仅声明调用过 session.export 即安全。
- **复审证据：** 更新设计、delta 和 M1 验收，使“取得路径 → 来源继续产生导出（含部分写入失败）→ 稍后读取此前给出的路径”仍得到合法完整 JSONL，并明确此读取的是哪个切面。无需真实模型或生产服务。

### Recommendations

无额外可选改进；先闭合上述一个消费者边界，不扩大为冷启动、磁盘清理或 UI 改造。

### 本轮执行边界

只读取受审文档、实际组装/消费者/现有测试及锁定 DSH 公开 API 证据，仅新增本报告；未修改设计或代码、未提交，未执行全量 CI、生产服务或额外子任务。本轮是设计可实现性审查，不是实现或产品验收。

### Author Resolutions

- R1-W1 — accepted。PA distill 的 source_jsonl_paths 是延迟读取引用，等待一次队列不能保护后续读取。修订 design 关键决策 1/3/5 与接口数据流：原始导出仅 session.export 显式完整原子发布；正常轮次只增量可读副本，不新增第二份原始缓存。delta 增补延迟读取 Scenario，M1 增补并发读取验证。
- 同次落实恢复共用队列及显式 path 重试，消除对 initialize 回调静默的假设；请求标志在合并及失败重试时保真。

## Round 2

### Metadata

- reviewer target: independent Codex agent `/root/design_review`，沿用 Round 1 reviewer；未参与设计修订或实现。
- review_mode: `full`
- mode_reason: 原始导出从自动追加改为显式完整发布，path 改变执行语义，冷读/实时读取与恢复并入队列，核心数据流和 milestone 验收发生变化；不能仅用旧问题 closure 放行。
- reviewed HEAD: `c88ade620a1b5d754f891c508d5bf18cb2d9dbc6`
- compared design baseline: `af01637e41f5e6cadade25dd2760a1e0a2980022`
- checkout / branch: 同 Round 1；本轮开始只有临时 benchmark 脚本未跟踪，未修改它。
- started_at: `2026-10-24T01:00:26+08:00`
- completed_at: `2026-10-24T01:01:52+08:00`
- duration: `PT1M26S`
- 文档 SHA-256：motivation.md 与 Round 1 相同；design.md 为 `d587675639af2e835c8de51caa1a2bdda43426a7c930b158c43d4fa20d464b5a`；delta 为 `58b2fe9e850987ed27da244357e193620cff4e4b901cf532c6e3f4c6f4c123d6`。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING.** R1-W1 已关闭。新引入的运行期冷读入口需要明确识别 query 转为 live observation 后的持久屏障，见 R2-W1；其余修订无阻断问题。

### Coverage 与证据

1. **首文档与用户约束。** 重新读取 motivation.md；用户允许在确认消费者后选择按需生成，要求完整性、fork、恢复与限定范围。显式原始导出改变文件刷新时机已有真实 PA 路径依据并进入 delta，未扩张 RPC 签名、产品范围或生产操作。核心性能目标仍是正常新增轮次按增量处理，完整显式请求成本已明确保留。
2. **现状和组装。** 比较 af01637e4..c88ade620，只有 unit 文档和 baseline evidence 改变，产品及依赖未变。复核 `history.ts:338-362` 与 `index.ts:349-358`，既有恢复、binding 校验与 path 入口可承接本方案。Round 1 的 PA distill、IM 预填 prompt、Skill 必须读所有 JSONL 的消费者证据仍适用；不存在前端布局变更。
3. **架构、数据流和职责。** `design.md:27-43` 把高频可读投影与低频原始快照分开，同在 NativeHistory 内复用 DSH facts，符合 `SPEC.md` 的 integration 投影职责。每次显式请求重用原始命名并临时写入/rename，比另存 append 原始缓存再复制快照减少一份大文件和水位状态；已发布文件保持完整，后续显式请求可发布更新完整切面，不承诺路径内容永久固定。原始文件不会再因正常续聊暴露半行。live 路径的先捕获上界再 flush 正确；冷读的来源识别仍缺一处闭合，见 R2-W1。
4. **队列与失败恢复。** pending/raw/rebuild 分离并要求合并保真，自动请求不能覆盖显式/重建意图；失败清水位，期间有新请求才继续，无新请求报错，避免无限重试。path 主动请求允许用户再次请求恢复；启动也经过同队列，移除了依赖 initialize 完全静默的假设。文件缺失/长度不符完整重建、其他错误传播、原始写失败保留前一完整文件且 RPC 不报成功均合理；无须引入磁盘游标或新后台任务。
5. **fork 与增量完整性。** 完整原始请求读取从零到持久上界的切面，可读增量只处理水位后的消息，均保留 DSH 继承前缀。fork 返回前等待可读副本，原始副本首次显式生成；继承到消息点和父子独立增长依旧由未改变的 DSH fork 管理。版本头、来源、envelope 过滤与图片占位要求均保留。
6. **delta 和验收。** canonical target 仍为 gateway/routing-delivery；ADDED 原有 Scenario 保留，新增延迟提炼读取覆盖原始发布变化，恢复条款区分可读启动恢复与原始请求生成。M1 增加延迟读取，隔离 RuntimeClient + fixture 的产品路径足够检验本次机制，不要求真实模型/UI。仍需实现期兑现队列意图保真、部分写失败和同会话并发矩阵；R2-W1 应纳入该矩阵。
7. **性能证据边界。** 新增 `M1-export/evidence/benchmark.md` 与临时脚本的 fixture、计数、阶段和限制吻合，本轮只读检查方法，未重跑或声称优化已实现。热路径不再序列化原始全文是合理优化，显式 O(总历史) 请求成本已在风险中披露；最终 evidence 宜分别列出正常 20 轮与显式导出开销，见可选建议。

### 历史问题闭环

- **R1-W1 — closed。** Author Resolution 接受延迟读路径事实。`design.md:31,35,39-43` 明确原始文件不再原地 append，只在显式请求中完整临时写入并 rename；普通后续聊天只改变可读副本，即使可读追加失败也不会污染既有原始快照。其他显式请求的失败保留旧完整文件，成功发布另一个完整切面。delta `:13-15` 与 M1 对应补入延迟读取。原始文件读取保证不再依赖模型容忍半行，足以在设计层关闭原问题。

### Issues

#### R2-W1 — observeSession 的冷读入口可能返回 live 切面，不能跳过持久屏障

- **位置：** `design.md:34,39-41`。
- **证据：** 设计先用 ctx.sessions.get 区分实时和未加载会话，并把后者的 sessionQuery.observeSession 称为“冷读租约”。锁定 `@deepseek-ai/dsh-session-query/README.md:106-110` 明确 query live-first 且冷读中 session 激活后转为 live；其公开 `lib/types/observation.d.ts:7-23` 提供 `source: 'live' | 'prepared'`。安装的 `lib/index.js:348-365` 在 await stat/load 后重新 get，发现附着即返回 live；`:473-495` 只捕获 seq 并 snapshotEvents，没有 flush。单次入口 get 未命中不能证明返回 observation 来自持久冷记录。
- **具体场景与后果：** 对一个尚未加载的已绑定会话调用 session.export，query 等待读盘时同会话被 session.ensure/submit 激活并追加事件；query 返回 live observation。若按设计的“冷读”直接发布，则没有经过该切面的持久屏障，新导出可包含尚未持久或随后 flush 失败的事件，违背本 unit 的持久事实保证。单会话导出队列不能阻止产品正常激活/提交会话，因此序列化导出任务本身不能消除此窗口。
- **要求闭合：** 明确根据实际 observation 来源保证持久性；prepared 结果可依赖其持久来源，live 结果也必须遵守固定上界后成功 flush 再发布的约束。可以复用既有 flush 与 observation 的公开 source/cursor，不要求新增抽象、重试框架或私有 API；flush 缺失/失败不得返回成功路径。
- **复审证据：** 补充该来源判断及“初查未加载 → query 等待时激活 → 返回 live”并发验证，覆盖屏障成功与失败、等待中新增事件不越过固定上界。无需启动生产或全量 CI。

### Recommendations

- **R2-R1（可选）：** 最终 benchmark 分开报告顺序 20 轮自动维护成本和一次显式原始导出成本，注明最终完整性读取是否计入各阶段。按需化已是允许的行为改变，但不宜把移到显式请求的全量成本描述为所有工作负载均消失；不影响设计通过判据。

### 本轮执行边界

仅追加本 Round；未修改设计、代码或旧 Round，未提交，未运行全量 CI、服务或额外子任务。本轮仍是设计审查，不是实现测试或产品验收。

### Author Resolutions

- R2-W1 — accepted。锁定 DSH query 的公开 source 标记区分实际来源，不能以第一次 sessions.get 未命中推断持久性。design 接口与数据流已规定：observe 返回 live 时重新取得 Session，捕获上界再 flush；无法取得或 flush=false 失败，prepared 才使用持久 observation。M1 覆盖此并发边界。
- 水位明确绑定 live Session 生命周期（WeakMap），prepared 恢复不向未来 live 对象移交游标；这是对“可信水位”的具体收口，不新增持久缓存。

## Round 3

### Metadata

- reviewer target: independent Codex agent `/root/design_review`，沿用前两轮 reviewer；未参与修订或实现。
- review_mode: `delta`
- mode_reason: 变化限定为 R2-W1 的实际来源分支、同模块水位生命周期及对应并发验收补充；需求、消费者、原始文件发布方式、RPC、模块职责和 milestone 交付切片不变。包含 WeakMap 生命周期影响核对，因此不限于 closure。
- reviewed HEAD: `ac0df963be40eb9c5471c5391638bb8cab1476ae`
- compared baseline: `c88ade620a1b5d754f891c508d5bf18cb2d9dbc6`
- checkout / branch: 同 Round 1；仅临时 benchmark 脚本未跟踪，未修改它。
- started_at: `2026-10-24T01:03:58+08:00`
- completed_at: `2026-10-24T01:04:11+08:00`
- duration: `PT13S`
- design.md SHA-256: `a41b11f61454e655a68e2b45f004b21f448bd6bd6b254cbb425a937d67ce820f`。motivation.md 与 Round 1 相同；delta SHA-256 与 Round 2 相同。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING.** Gate 2 通过。R2-W1 的持久边界已在设计中闭合，水位生命周期收口未引入额外阻断问题。此结论只批准设计进入实施，不代表性能、实现或产品验收已通过。

### Coverage 与证据

- **持久来源与固定上界：** `design.md:39` 明确检查 observation.source，只有 prepared 直接使用持久 observation；返回 live 时重新取得实时 Session，统一执行捕获 seq → flush → 读取该上界。获取失败或没有持久屏障明确失败、不发布。重新核对锁定 DSH 的 `dsh-session-query/lib/types/observation.d.ts:7-23` 与 `README.md:106-110`，source 判别与其真实公开契约一致；无需新增读取 API、同步读取调用点或私有导入。
- **水位生命周期与恢复：** `design.md:32,39` 将水位绑定到 live Session 对象的 WeakMap；prepared 不创建供未来 live 接管的水位，新 live 首次完整重建，之后仅追加。锁定 query README 明确冷日志会在内存补 interruptedTurnClosers，且不修改持久源；因此不跨生命周期复用游标是对真实来源差异的直接处理。单会话队列仍按 session id 串行写文件；WeakMap 仅约束可复用的增量状态，没有第二份事实源、正文缓存或 Session 强引用。代价是新 live 生命周期首次重建，属于既定恢复成本，不改变正常连续轮次目标。
- **失败和并发：** 统一 live 路径继续要求 flush 成功后发布；既有“任何写入失败清水位、下次完整恢复、raw/rebuild 意图不得被合并丢失”条款未变。prepared 读取后即使后续会话激活，未来 live 没有继承游标，按同队列完整接管即可，不依赖冷切面与未来对象的事件前缀相同。
- **验收变化：** M1 `design.md:69` 新增 observe 查询期间转 live 的持久上界场景，覆盖 R2-W1 的真实入口。其成功/失败分支与等待期间新增事件的截面约束归于已规定的持久上界、失败恢复和并发矩阵；无需额外测试基础设施或扩大产品旅程。
- **retained_from: Round 2。** Git 对比只改 design.md 与 append-only review；motivation、delta、产品代码、锁定依赖未改。Round 2 对原始文件延迟读取与原子发布、PA/RPC 组装、fork 继承、自动可读副本、用户范围约束、canonical target、隔离验收与性能口径的覆盖继续有效。R2-R1 仍是可选的最终证据呈现建议，不阻断。

### 历史问题闭环

- **R2-W1 — closed。** Author Resolution 接受 query 来源可能变化；本轮按公开 source 判别并对 live 结果重新执行固定上界与 flush，消除了“初查无 Session 即当作持久冷读”的错误前提，且缺少 Session/屏障时不发布。设计和 M1 已对应补齐。
- **R1-W1 — closed，retained_from: Round 2。** 原始文件仍只完整原子发布，延迟消费者不会因正常聊天追加遇到原始半行；相关设计与 delta 本轮未变。

### Issues / Recommendations

无新增 issue 或建议；不继续扩大设计审查。

### 本轮执行边界

仅追加本 Round，未改旧报告、设计或代码，未提交；未运行 CI、服务或额外子任务。

### Author Resolutions

Round 3 Approved accepted: 0 CRITICAL / 0 WARNING. Implementation began only after this gate. No subsequent substantive design changes.
