# feat-628 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/pa_eval_design_review`（独立 reviewer）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；完整检查需求、当前真实组装、时间域、隔离、接口、delta 与 milestone。
- started_at: `2026-10-21T12:32:03+08:00`（本轮首次记录的审查时间）
- completed_at: `2026-10-21T12:35:13+08:00`
- duration: `190 seconds`（自首次记录时间计）
- baseline: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`，当前 `main`；其他 dirty/untracked 内容未修改。
- reviewed: `spec.md`、`design.md`、`M1-clock-calibration/.gitkeep`、`M2-baseline/.gitkeep`；仅新建本报告，不提交。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

总体方向可取：固定事件与有限反馈、真实连续 PA、结果证据、语义复核、先校准后基线都与需求吻合。但业务时间和候选可见边界还有会让实施者作出不同实质选择的空白，尚不足以放行整体实施。下列两项属于设计决定未闭合；DSH 公开 clock API 尚未发布则是设计已经诚实声明的外部实施依赖，不重复记为问题。

### Coverage 与证据

**需求与用户约束。** `spec.md:35–88` 的四组 Requirement 均有设计对应：连续七天及干净重跑由 episode/初态/manifest 支持；跟进、澄清、取消、沉默、权限由 E01–E08 覆盖；未处理、未送达、不可观察分为不同 verdict/failure_class；各维度分母、成本与完整失败轨迹保留，不以单一总分作优化结论。用户未指定模拟技术，固定分支是设计者的合理首版选择；无需强制改成开放 LLM 用户。E02–E08 的实际文本、窗口和 rubric 交 M2 seal 是明确的案例制作工作，不要求设计阶段预写完整数据集。当前没有实跑，不能报告基线成功。

**当前真实组装。** 实际产品入口是 `apps/node/src/main.ts:46,85–121,305,330–337`：这里创建 InboxStore、RuntimePartitions/RuntimeSupervisor、GlobalAgent 与 Heartbeat，并通过 integration/client 初始化 stdio 子进程。`bootstrap.ts` 是接入配置引导，不是 PA 组装入口；见 R1-R1。`global-agent.ts:149–157,177–193`、`inbox.ts:37–101`、`heartbeat.ts:32–75` 确认当前业务 due/timer 仍用系统时间，局部传入 now 不等于真实启动已接线。

**DSH 依赖。** 实际安装的 `@deepseek-ai/dsh-schedule@0.2.1-alpha.1/lib/types/index.d.ts:18–29` 的 Config 只有历史保留设置，无 clock 注入；分发代码 `lib/index.js:1566–1644,2087,2214` 仍以 Date.now/setTimeout 扫描、投递、创建及更新。`dsh-tool-schedule/lib/index.js:539,561,651` 的渲染也读取 Date.now。`cron-owners.ts:46–54` 由隔离 realm 装配原生 ScheduleService；`features/cron.ts:10–13` 把原生工具接到同一 realm。因此设计拒绝用手动 run 或本地 Cron 替代原生到期是必要的。公开 API 的具体版本和映射可作为 M1 外部前置；当前状态只能做缺口报告，不能宣称已具备七天加速。

**接口和证据链。** prepare/apply/drain/receipt、下一 timer 推进、幂等 epoch、忙碌工具屏障和离线恢复的语义足以给控制协议定方向；不要求现在规定每条 RPC 的线格式。drain 要覆盖持久输入、执行与投递，而不是只看 active model=0，符合 `apps/node/src/main.ts:342–349` 现有安全更新屏障也需要多个产品 owner busy 条件的事实。`tests/e2e/critical_paths/test_global_agent_inbox_critical_path.py:35–49,77–81` 已有 Work 分页与 inbox_read_committed/source_refs 证据范式。收件人消息查询作为交付终点，且不外推到 Feishu 推送，是正确边界。

**架构与职责判断。** 薄 Python harness 负责外界事件、推进与评分；PA 保持 Inbox/Heartbeat/路由职责；DSH 保持原生调度与 Agent loop；integration 独占上游接入。与另建调度器或 PA 工作账本相比，该复用能避免两套 catch-up/授权/状态语义。受保护 IPC 仅用于隔离环境是合理需求，不构成恢复内核 HTTP 服务。未发现为了假想边界新增复杂框架的必要性；但隔离仍须选定可执行机制，见 R1-W2。

**delta 与客户端。** 依据 `SPEC.md`、Gateway `personal-agent.md` / `heartbeat-cron.md` 和 `docs/specs/CONTRIBUTING.md`，默认 real clock 下不改变产品契约、评测控制不对产品用户开放时，`no spec delta` 合理；CLI/实验协议归 evals README 合理。若解决问题需要更改生产对外字段或语义，应按设计现有规则补最窄 delta。无前端/原生界面变化，不适用渲染原型与视觉验收。

**Milestones 与验收。** 两个 .gitkeep 目录存在且无实现内容。M1 先证明时钟、屏障、重启与 default real-clock 回归，M2 才 seal 8 条 episode 和跑 8×3，串行依赖与退出证据清楚。M1 缺公开上游能力时只交阻塞证据、不算完成，M2 不自动降级，符合需求。重启不得再次运行会重建状态的 e2e-up，设计已正确区分。M1 的全跨度推进成本建议见 R1-R2。

**研究证据边界。** 独立查看了 [LongMemEval](https://github.com/xiaowu0162/LongMemEval)、[QMSum](https://github.com/Yale-LILY/QMSum)、[ProactiveAgent](https://github.com/thunlp/ProactiveAgent) 与 [TheAgentCompany](https://github.com/TheAgentCompany/TheAgentCompany) 的官方说明：分别涉及长期记忆问答、会议摘要、基于活动的主动任务感知和办公执行评测。设计把它们当维度借鉴，没有声称现成真值可直接迁入 PA，这一使用方式合理。本轮未重跑用户 zip 或独立恢复私有 ChatGPT 对话，故不将设计所述 pilot 测试通过作为本轮验证结果。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 业务时间边界尚未覆盖真实消息时间与知识时间，不能只留待实施时发现

- **位置：** `design.md:119–126,138,239`。
- **证据：** 方案列出了“消息内容中的业务日期”，但真实模型还直接看到 `InboxStore.read` 提供的消息 `time`（`packages/personal-assistant/src/inbox.ts:192–196`）以及 conversations 的 `source_time`（`apps/im-server/src/work.ts:647–648,704`），它们来自 IM 的 `messages.created_at`，不是正文日期。该字段同时参与 IM watchdog 的 wall-time 比较（`apps/im-server/src/server.ts:312–318`）。此外，`packages/dsh-integration/src/knowledge/files.ts:57,100,107,123,160` 给候选可读记忆和 Skill 使用记录写入真实时间，`knowledge/runtime.ts:150–159` 按真实小时触发 curation；这些是本仓实现，不是只能由 DSH 上游解决的来源。
- **缺失决定：** 哪些模型可见时间/查询过滤必须采用 scenario_time，哪些仅作 wall-time 审计；IM 业务时间与运行健康时间共享字段时如何分离；本版是否启用已有自动知识维护、若启用采用哪种时间域。现有“必要的 IM 业务时间接线”和实施时做时间来源清单没有确定这些影响基线含义的选择。并非要求全面虚拟化所有时间 API，也不要求新增遗忘算法。
- **未修后果：** 同一 PA 可能看到七天推进的正文与集中在同一真实日的来源/记忆时间，跨日事实判断和日期查询出现评测制造的失败；直接把 created_at 改成模拟时间又可能让 wall-time watchdog 错判。只把 ScheduleService 接好无法证明所称连续七天保真。
- **收口要求：** 在设计补一张有限的时间域/责任表，至少覆盖上述真实消费面与真实组装入口，决定知识维护开启状态，并把来源时间查询与健康计时不互相污染列入 M1 校准。上游部分继续保留公开扩展前置，本仓部分由对应 owner 注入或在冻结能力中明确排除。

#### R1-W2 — 未选定候选工具与控制资产隔离的执行机制

- **位置：** `design.md:69,126,152,172,176–178,240`。
- **证据：** 设计承诺候选不能访问真值、未来事件或其他 run，且不能从 shell 获取真实时间，但只给了独立 workspace/run-dir 和“实际可控工具清单”。现有 E2E 配置 `config/e2e/gateway.yaml:27–31` 包含 read/write/edit/bash；`packages/dsh-integration/src/capabilities.ts:55–68` 是工具名选择，不是文件访问根边界。`workspace-tools.ts:76` 明确插件是可信本地代码而非 OS sandbox。当前读文件与插件能力不会因 cwd 独立就自动失去读取同用户其他目录的能力，子 Agent 也属于实际可执行面。
- **缺失决定：** baseline-v1 究竟提供哪些工具/Feature/插件与 Skill 根，以及通过何种具体边界拒绝读取控制目录、未来事件和跨 run 状态。保留一般 read/write 或可执行能力时，需要明确受控文件根/权限机制；删去这些能力时，也应明确保留哪种真实持久工作能力供 PA 自由使用。“不注册为 Agent 工具”只隐藏控制 IPC 名称，不能代替该决定。
- **未修后果：** 实施者可能直接复用现有 E2E allowlist，把路径不同当作信息隔离；候选可读私有真值，或工具读到 wall-time，成绩无法证明来自连续交互和记忆。M2 再做“隔离泄漏检查”才决定工具世界，会反过来改变 M1 要校准的时间面与评测基线。
- **收口要求：** 先冻结一个小而具体的候选能力集，并选定最简单可执行的资产访问边界，覆盖主 Agent/子 Agent 和 workspace 插件；把控制文件与未来事件的不可读验证移到 M1 能力准入。无需为首版建立通用沙箱平台。

### Recommendations（不阻断）

- **R1-R1：校正实际组装入口。** `design.md:19` 应指向 `apps/node/src/main.ts` 加 `runtime-partitions.ts`；bootstrap.ts 负责接入配置。范围已包含 apps/node，故这处定位错误本身不另计 WARNING。
- **R1-R2：M1 量一次无模型七天推进成本。** `Heartbeat.start` 默认每秒一个 timer（`heartbeat.ts:32–35`）。严格逐 timer/跨进程屏障推进七天可能产生约 604,800 次 tick/episode；这只是已知操作量，不是已证实超时。先以 stub 模型跑完整时间跨度并报告 epoch/tick 数及 wall-time，避免短窗口校准通过后才在 24 条轨迹上发现成本。若需优化空 tick，仍由原 owner 保证等价，不让 harness 复制 Heartbeat 规则；不要求在没有测量时预建跳跃算法。

### Author Resolutions

- **R1-W1 — accepted。** design §关键决策 3 新增实际消费面的时间域/owner 表：IM 业务来源时间采用 scenario，新增内部 received_at_wall 与 event 活动时间供 watchdog；日期过滤和 Inbox/历史来源一致；memory_curation 保留并接业务时间；baseline 关闭 Skill 创建/老化，使用记录采用 scenario。M1 增加日期查询、记忆时间与 watchdog/认证不互相污染的校准，memory review 纳入 drain。
- **R1-W2 — accepted。** design §关键决策 1 新增 baseline-v1 能力表与文件边界：固定原生工具、禁 bash/web/PTC 代码/动态插件、独立只读 skill root，公开 pre-execute hook 的确定性 guard 在所有后代/review agent 强制执行 realpath 根边界，生产无 guard；M1 先验 sentinel 隔离与正常工作能力。现有 tools/pre-execute 见 policy/approval.ts，现有路径归一思路见 policy/cc-workspace.ts；不把现有安全工具豁免误当隔离。
- **R1-R1 — accepted。** 校正 main.ts 为真实组装入口，保留 runtime-partitions。
- **R1-R2 — accepted。** M1 增加完整七天 stub 探针、tick/epoch 数与 wall-time；15 分钟探针预算，超出先解决推进成本，不先扩到真实 24 runs。没有引入未经测量的跳跃算法。

## Round 2

### Metadata

- reviewer_target: `/root/pa_eval_design_review`（同一独立 reviewer）
- review_mode: `full`
- mode_reason: 修订新增实际资产隔离边界、跨包时间域/内部收据字段，并扩充 M1 准入及退出标准。按核心边界与 milestone 变化执行 full；未变内容沿用本轮仍成立的 R1 证据。
- started_at: `2026-10-21T12:38:22+08:00`
- completed_at: `2026-10-21T12:39:56+08:00`
- duration: `94 seconds`
- baseline: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`；`main`，未修改设计、代码或其他文件，未提交。
- reviewed: 修订后的完整 `design.md`、R1 Author Resolutions；需求与两个 milestone 占位目录未变。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1、R1-W2 均已闭合。此结论确认设计决定和实施责任足够明确；不表示当前依赖已具备虚拟时钟、不表示 M1 校准或 M2 基线已完成。公开 DSH clock 扩展仍是硬前置；实际能力、隔离 sentinel、七天成本探针任一不满足时，按已设计的准入规则停止。

### Coverage 与证据

**需求、输入和评分。** 全文复核后，连续单 PA/主会话/持久状态、七天加速、相同初态重跑、适当主动和克制、身份授权、投递证据、故障分类和非优化范围均保持原方案。E01–E08、反馈分类器、Judge/人工盲审、coverage 分母、8×3 与 smoke 区分没有变化。`retained_from: Round 1`：R1 对 spec 四组 Requirement、研究使用边界及证据终点的核对仍适用。新增受控工具环境没有被宣称为全渠道或任意工具的长期能力。

**实际入口与时间域。** `design.md:19,140–156` 现在明确由 main.ts 组装时钟，IM 业务消息 created_at、Inbox/历史来源与日期过滤一致；watchdog 用独立内部 received_at_wall/event wall 时间；原生 schedule、工作状态和候选可读记忆时间使用 scenario；provider、认证、执行时长与审计仍真实。重新核对 `apps/im-server/src/messaging.ts:345–366,398–401`，消息创建和 conversation event 原本已有不同写入位置，按 owner 分离时间无需引入第二消息通路。`server.ts:312–318` 的混用位置已由新内部 fallback 设计覆盖。`knowledge/runtime.ts:145–165` 的小时 scan 仅属于 skills 订阅，关闭 skill_creation 可关闭该支线；`features/memory-curation.ts:10` 与 `knowledge/runtime.ts:195–223` 仍保留真实 memory review，设计又将 review/持久写入纳入 drain。时间域选择不再留给 worker 临场决定。

**能力边界与公开接口。** `design.md:81–100` 冻结工具、Feature、Skill 根和 native 表示层，并明确 root/child/review agent 一致的 run/cwd/文件边界，排除任意执行和动态插件；独立工作文件、memory、schedule 与 subagent 仍可用于完成任务。核对了锁定版本 `dsh-tools/lib/types/index.d.ts:47` 的公开 tools/pre-execute 声明和 `lib/index.js:3225–3245` 实际执行门；拒绝会成为工具错误，不进入工具体。本仓 `policy/approval.ts:100–106` 在 safe-tool/skip 分支前保留非 allow 的 downstream 决定，因此本设计能在现有公开调用链完成确定性拒绝，不必修改 DSH 私有实现。`policy/cc-workspace.ts:16–49` 已有实际 file_path、cwd 和 realpath/新文件父目录解析做法，但设计正确地没有把该审批优化当成新隔离已实现。`capabilities.ts:59–68,120–121` 说明 native 表示层、工具选择及 includeDefaultRoots=false 的公开接点存在；仍须按设计 M1 在实际 root/child/review schemas 上验证，而非仅检查配置文本。

**维护代价与依赖方向。** 有界工具集配确定性入口检查，在禁任意代码的前提下能满足首版资产不可读的要求，未引入通用 OS 沙箱。时钟由各现有 owner 处理，harness 不新增 Cron/Heartbeat 决策，integration 仍是唯一 DSH 接入点。workspace plugin 清单“为空且锁定”应按正文要求落实为实际不能动态启用的状态，不能只检查启动时为空；这已是明确的实施约束，不另增加设计 finding。DSH clock 发布与安装版本仍未满足，但能力契约和拒绝策略没有缺失决定。

**delta、migration、前端与 milestones。** `no spec delta` 继续成立：received_at_wall 仅为内部健康收据，生产默认 real clock 下业务来源语义不变，新增字段旧行回填已写明；评测 CLI 留在 evals 权威位置。没有前端改动。M1 已包括 schema/内部收据迁移、root/child/review sentinel、日期查询/知识时间/健康时间校准与七天成本探针，M2 的评分和场景制作保持串行后置。`design.md:178,277–278` 的 15 分钟是冻结准入预算，不是未经验证的性能成绩；超预算后先测量再由原 owner 做等价优化，未授权提前构建新调度器。`retained_from: Round 1`：隔离服务生命周期、重启保状态、Work 分页与收件账号消息作为终点的证据仍有效。

### 历史问题闭环

| ID | Author Resolution | 本轮独立证据 | 状态 |
|---|---|---|---|
| R1-W1 | 新增时间域/owner 表，分离 IM 业务时间和 watchdog wall 收据，保留 memory review 并关闭 Skill 创建/老化 | design:140–156、277；IM 消息/event 分开写入，knowledge skills scan 与 memory review 可分别配置；校准覆盖真实消费者与 drain | **closed** |
| R1-W2 | 冻结能力集和文件边界，公开 pre-execute 确定性拒绝，所有后代/review 一致，M1 sentinel 准入 | design:81–100、277；公开 hook 与实际工具执行门存在，本仓审批保留 downstream deny；文件/Skill 接点可复用 | **closed** |
| R1-R1 | 实际入口改为 main.ts | design:19、148、277 与 apps/node/src/main.ts 组装一致 | **closed** |
| R1-R2 | M1 七天 stub 成本探针及 15 分钟预算 | design:178、277；保留先测量、不预建跳跃算法 | **closed** |

### Issues

无新增 CRITICAL/WARNING，无仍开放的历史问题。

### Recommendations（不阻断）

无新增。按既定 M1 准入收集真实证据即可；未发生实质设计变化时不因实施细节重复启动设计审查。

### Author Resolutions

- 接受 Round 2 的覆盖与闭环证据，无实质异议。受审 spec/design/milestone 骨架此后未变；本段仅记录 author 判定，不新增设计决定。Gate 2 通过，实施仍受公开 DSH clock 前置及 M1 准入约束。本次交付止于设计。

### Author Revision Notice — 用户要求取消上游前置

用户原话：“那就不要依赖上游还没有的能力，想个现在能落地的评测方案，把设计改一下”。据此修订 spec 的时间覆盖要求、重写 design，并将旧两个 milestone 空骨架替换为 `M1-replay-baseline/.gitkeep`。当前设计使用压缩故事与短时真实机制两轨，全部时间保持真实；删除 BusinessClock、时钟 IPC、消息时间/健康字段迁移及上游 clock 发布前置。保留受控工具边界、证据与评分约束，基线改为 A01–A08/R01–R05 首次完整小样本。Round 2 的批准只针对历史稿，不用于批准这次实质修订，交独立 reviewer 追加新 Round。

## Round 3

### Metadata

- reviewer_target: `/root/pa_eval_design_review`（同一独立 reviewer）
- review_mode: `full`
- mode_reason: 用户明确改变时间覆盖要求，spec/design 与 milestone 实质重写；本轮重新审查整套方案，不用 Round 2 的 Approved 直接放行。
- started_at: `2026-10-21T14:22:05+08:00`
- completed_at: `2026-10-21T14:22:44+08:00`
- duration: `39 seconds`（独立核对阶段；报告写入随后完成）
- baseline: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`，`main`；本轮仅追加本报告，未修改 spec/design/代码，不提交。
- reviewed: 当前完整 spec/design、Author Revision Notice、`M1-replay-baseline/.gitkeep`；已确认旧两个 milestone 目录不再作为本稿骨架。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

新方案可基于当前锁定能力实施，不再等待上游时钟 API。批准的是“压缩故事的连续行为 + 短时真实机制”评测设计，不是七天实际流逝的等价证明，也不是已实现或已跑通基线。新增 runner、隔离 guard、场景与评分仍属于 M1 待实施工作。

### Coverage 与证据

**用户新约束和需求范围。** spec 原话及澄清记录保留了用户取消未知上游依赖的要求，验收改为连续故事回放、短时真实定时和相同相对协议重跑。design §关键决策 1–2 分开说明 A/R 的可证与不可证范围：story_day 只留控制侧，候选接收真实消息时间与按当次起点渲染的短期限；保存原故事与 executable variant，报告真实观察长度。改变紧迫度与并发密度的影响在风险段明确，不把故事“D7”包装为经过七天。无需重新引入 clock 满足已被用户修改的旧范围。

**当前能力与实际运行链。** 本轮读取了当前 `cron-owners.ts`、`features/cron.ts` 相关装配及 `schedule-evidence.ts`。锁定 alpha.1 的 `dsh-schedule/lib/types/domain.d.ts:11` 与分发 `lib/index.js:21` 均给出 `MIN_EVERY_INTERVAL_SECONDS=60`；原生工具分发明确支持 after_seconds、every_seconds 和 schedule_create/list/update/delete，180 秒 once 与 120 秒 every 在当前能力内。`schedule-evidence.ts` 从真实 schedule source 和 reminder framing 关联 schedule ID、occurrence、input evidence，并单独处理 manual，因此方案所需证据有当前接点。原生 `lib/index.js:1566–1620` 在恢复时按真实 now 解析 recurring 最近 occurrence、持久化 admission；R03 测的是该已有恢复机制，不是 runner 模拟触发。

`heartbeat-policy.ts:5–9` 接受 s/m/h/d，`heartbeatDue` 和 `withinActiveHours` 由真实 now/用户时区判断；2m 是现有配置而不是加速系统时钟。`inbox.ts` 的十分钟当前规则保持不动。R04 的阻塞工具是待新增的局部 fixture，利用已有工具注册/执行接口保持真实 running，既不伪造 busy，也不要求上游新增服务。真实组装入口仍是 main.ts/RuntimePartitions/RuntimeSupervisor。旧 `test_cron_push_critical_path.py:55` 仍含 schedule_cancel，设计已明确不能直接照搬旧测试或把普通 Agent 结果当 PA 验收；M1 实际 schemas 和 PA owner 绑定验证足以防止沿用过时名称。

**时间、反馈与停止协议。** A01 的 +1、+16、+32 分钟后台输入分别留出真实批处理和固定处理余量；A 轨允许其他合法入口提早读取，R01 则关 Heartbeat、排除 owner 催问独立测十分钟。+48 分钟的请求按消息时间确定 +51 分钟目标，固定 90 秒容差与 +54 分钟完成事件分开；最终观察覆盖原/新截止及后续周期，不以注册确认代替提醒。候选处理慢不顺延外部事件，属于冻结协议内的真实行为结果；runner 迟投递则用默认 5 秒容差归 harness-invalid，未把两者混为一谈。

R02 的更新/删除覆盖原、新到期点，R03 等安排已持久化后才停机，R04 验 actual running，R05 区分已入队工作与取消后的新催促。具体子场景文本、停止/恢复偏移和周期观察长度交 M1 seal，是已明确的 fixture 制作工作；设计已经决定必须观察哪些边界，不需要在本轮补出全部测试脚本。有限反馈按当时可知事实和固定延迟分支回复，unsupported 不临场补答案；它是唯一允许依候选输出改变输入的显式例外，不修改独立事件时间。

**取证、评分和沉默。** 不再要求跨进程全局 drain，而是对已知输入收集完整分页、source ref、admission、终态与目标账号消息；收集缺口为 unknown，可观察但未消费为 fail。窗口关门后固定 30 秒只补采已经发生的投影，以事件实际时间归窗，不把晚回复当按时。timed/manual、业务停止/已入队、stub/真实模型分别保留。A/R 指标分列且保留全部冻结机会分母，未观察到的未来 due 只记创建，不推算触发。基础设施完成允许 PA 有行为失败，但无效环境、缺证或漏跑不能包装成完整基线。首次 A01–A08 加 R01–R05 全子场景各一次和可选三次重跑的含义清楚，没有沿用旧 8×3 或 15 分钟全栈七天要求。

**隔离、架构与维护成本。** `retained_from: Round 2`：工具白名单、native 表示层、受控文件根、锁定 workspace 插件和 root/child/review guard 的机制未改变；公开 tools/pre-execute 接口及现有审批保留拒绝的核对仍有效。当前候选全用真实时间，关闭 bash/web 现在主要服务于资产隔离，不依赖时间伪装。方案删除 BusinessClock、跨进程时钟协议和 IM 时间迁移，harness 只负责输入/观察/生命周期，原 PA/DSH 保持业务决策和原生调度；比上一稿少一个外部能力与一套时间控制机制，职责边界成立。

**Runbook、delta 与 milestone。** `apps/node/src/cli.ts:27–48,138–143` 当前支持 stop/start --config；design:237–240 区分物化源配置和 e2e-up 生成的有效配置，保状态重启只用后者并保留 IM，避免重建工作状态。清理以本 run receipt 作用域执行。生产时钟、调度、Inbox、权限均不改，隔离 guard 仅在测试配置生效，因此 no spec delta 合理；新长期协议仍归 evals README，并更新索引。无前端变化。单 M1 同时交付 runner、场景、取证与真实小样本报告是完整的纵向交付，退出条件覆盖 spec 所有 Scenario，空骨架实际存在。

**取证限度。** 本轮没有启动服务、运行模型或执行任一新场景；当前可落地判断来自已安装 alpha.1 的公开类型/分发实现和仓库真实装配。design 所述其他 npm 版本调查未在本轮重跑，也不是本结论的前提。外部研究的方法借鉴未变，沿用 Round 1 的独立来源核对，不将其当成此方案已有效的实验证明。

### 历史问题闭环

| ID | Author Revision / Resolution | 本轮判断与证据 | 状态 |
|---|---|---|---|
| R1-W1 | 用户要求后删除双时钟；全部实际来源、记忆、调度和健康时间保持真实 | 原时间域冲突前提已不存在；新 spec 与 design §决策 1–2 明示压缩故事而非时间等价 | **closed — superseded by new scope** |
| R1-W2 | 保留 R2 的固定能力集与确定性资产边界 | design §决策 3 和 M1 sentinel 准入未退回“仅不同目录”；沿用 R2 公共接口证据 | **closed — retained** |
| R1-R1 | main.ts 保持为实际入口 | 当前 design 现状与运行链一致 | **closed — retained** |
| R1-R2 | 删除虚拟 timer 推进和七天 stub 成本门槛 | 不再有 604,800 次虚拟 tick；实际 A01 90 分钟计划及每 case 预算替代 | **closed — superseded by new scope** |

### Issues

无新增 CRITICAL/WARNING，无仍开放的历史问题。

### Recommendations（不阻断）

无新增。按冻结的相对协议制作并 seal 具体 case，实施后再用真实证据判断结果，不为旧七天全保真目标增加上游依赖。

### Author Resolutions

- 接受 Round 3 的覆盖与结论，无实质异议。当前 spec/design/单 M1 骨架在受审后未改动；本段仅记录判定。旧上游 clock 依赖已经移出本 unit，设计门禁按本轮通过；尚未实施或实跑。
