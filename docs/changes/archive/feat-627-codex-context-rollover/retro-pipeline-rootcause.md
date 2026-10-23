# feat-627 生产任务在换窗后丢失：设计与集成归因

记录日期：2026-10-21。调查会话：`c_8wedfh29`，原生 session `8d36509c-91d0-423d-97d4-2f6419162253`。本报告只记录取证与修复方向；未修改代码、配置或重启生产。

## 核心问题与结论

用户希望 PA 根据日记整理 todo，随后多次明确补充指令。PA 每次读到并发出确认，几步后却结束为“午后问候已送达，等待用户回复；本轮无新请求”。

主因是上下文策略的设计适配和集成未收口：Codex 风格的整窗移出与 Notes/History 恢复，叠加 DSH 的完整动态快照追加、Nano 的已用 Skill 全文恢复。动态引用每步改变，迫使整份快照反复入模；压力换窗又移走已读入但尚未完成的任务，而恢复入口没有区分当前任务与旧 Notes。

这不是两个 compaction 引擎同时执行的证据，也不是把本轮任务正确交付后正常安静等待。直接的模型请求证据表明：指令曾在输入中，换窗后消失，随后旧笔记进入输入并导致错误收尾。

## 范围、版本与证据位置

- 本调查 checkout：Nano `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`，保留原有 dirty/untracked。该 checkout 只有初始设计；未将它当作生产实现。
- 生产 Mini 及本机只读参考 checkout `/Users/czj/.codex/worktrees/prod-main/nano-multiagent`：Nano `be6c1271b00a9921a323e0da4e8385b1f61f2a86`（PR #376）。后续设计、审查、验收位于其 `docs/changes/archive/feat-627-codex-context-rollover/`。
- 固定插件：`dsh-agent-context@0.3.0-rc.1`，交付记录绑定源码 `7f0a2b78ec530075edd48452c2cf5499548ca99c`；关键路径同时核对了 Mini 实际安装的 `lib/`。
- 原始请求：Mini `~/Repos/LLM_Bridge/logs/session/2026-10-13_20-19-06_046_8d36509c-91d0-423d-97d4-2f6419162253/`。主要对照 `2026-10-21_15-09-17_613`、`15-09-32_768`、`15-09-45_675`、`15-09-59_928` 的 `req-anthropic_messages.json` 与 `downstream-res`。
- 原生事件：Mini `~/.nanoassistant/.dsh-runtime/mac-mini/pa/*/sessions/*/8d36509c-91d0-423d-97d4-2f6419162253/session.v4.jsonl.zstd`。可用 `/opt/homebrew/bin/zstd -dc` 只读解码；不要修改原件。
- IM 历史与投影：Mini `~/Repos/nano-multiagent/data/im_service.sqlite3`，以 SQLite `mode=ro` 读取 `messages`、`agent_work_events`、`agent_work_turns`。原始私人内容、凭据、数据库和完整请求均未复制到本报告。

## 已确认的因果链

### 1. 为什么带 Skill 原文：Nano 的既有恢复逻辑

Nano `packages/dsh-integration/src/knowledge/runtime.ts:63-74` 在每次 assembly 时检查 session 历史是否存在任意 `compaction/end`，随后获取该 session 用过的 Skill，将 `renderSkillContent(skill)` 全文放入动态 `nano-used-skills` context。它不是只在刚压缩后运行一次，也不按本轮任务选择 Skill。

`knowledge/files.ts:142-151` 从 `.usage.json` 的 session_refs 找出当前 session 曾使用的 Skill。因此本轮即使没有调用这些 Skill，它们仍可由宿主自动恢复。代码目的从 `Previously used Skills, restored after compaction` 可见：补回压缩移出的操作规程。这段行为早于 feat-627（git 历史定位到 `ef4d3dd2b`），不能把它单独说成本 feature 新写的代码。

本次最后一份快照中的 Skill 全文共 52,400 字符：

| Skill | 字符数（含 Skill 包裹） |
|---|---:|
| interview-record-index | 18,234 |
| daily-journal-write | 12,257 |
| inbox-reply-protocol | 6,620 |
| skill-library-maintenance | 5,240 |
| ongoing-work | 4,603 |
| playwright | 3,850 |
| lark-calendar | 1,596 |

### 2. 具体从哪里开始重复：变化的引用触发完整快照追加

[初始 design.md:96-98](design.md#history-与当前引用) 选择通过动态 `systemPrompt.context` 每步生成引用索引；插件 `src/index.ts:103-109` 实现这一选择。引用中排除快照本身，只能避免索引递归，不能避免其他 context 正文随整份快照一起重发。

DSH `agent-loop` 的 `RuntimeContextProjection.project` 比较整份快照文本；只要变化就生成一个完整的 runtime-context 消息。`preStep` 将该消息追加到本步输入，旧快照仍留在活动历史。插件的引用随新消息/工具结果变化，于是连同不变的 Skill、Memory 等一起再次入模。这是重复的直接组合机制，不是模型连续主动调用了七个 Skill。

原设计审查 `design-review.md:52-57` 已明确知道“引用索引每步变化”和“变化时生成完整 snapshot”，但只处理切窗时新旧窗口身份冲突，没有对照完整快照的累计成本。生产请求已证实相同 Skill 原文反复出现。

| 请求时间（北京时间） | 同一请求内快照份数 | 快照总字符数 | provider 输入 tokens，含缓存 |
|---|---:|---:|---:|
| 15:08:49.793 | 3 | 171,635 | 117,676 |
| 15:09:03.974 | 4 | 230,312 | 152,759 |
| 15:09:17.613 | 5 | 289,520 | 188,150 |
| 15:09:32.768 | 6 | 349,272 | 223,853 |

最后一行是一次请求内 `35,821 input_tokens + 188,032 cache_read_input_tokens`，不是把四次调用相加。字符数与 tokens 不作固定比例换算；单份五万字符不是二十万 tokens。相邻请求输入实际净增约 3.5 万 tokens，足以解释几步内达到窗口边界。

### 3. 为什么没有先保存新任务：正常快照增量能跳过 fallback 区间

生产实际 C=258,400，输出策略预留 O=32,768；H=225,632，B=16,384，W=209,248，R=6,144，提醒线为 203,104。无 workspace 用户预算覆盖。

[初始 design.md:115-122](design.md#预算状态机) 分 reminder、fallback、hard-cap，但没有保证本次增量跨越 W/H 时先完成任务交接。插件 `src/index.ts:152-174` 先判断 T≥H 并立即执行换窗，之后才判断是否发送 fallback。

本轮 15:09:32 请求含剩余 6,061 tokens 的 reminder；模型选择读取 vault 的 AGENTS.md，下一步即强制 pressure reset，没有写入新 checkpoint。单步约 3.5 万 tokens 的净增大于默认 16,384 的 fallback buffer。设计虽提到“突然超长工具结果来不及保存”的风险，但本次主要增量来自稳定复现的宿主完整快照，不是异常巨大的业务工具结果。

### 4. 为什么新指令消失：只保护未提交输入，没有保护未完成任务

[初始 design.md:53、104-108](design.md#新窗事务与有效状态重建) 明确移出 system head 之后的所有可配对消息，只保留本 step 已 claim、尚未入日志的新输入。此前通过 Inbox 读入、已持久化但仍未完成的请求，被当作普通旧 surface 一起移出。

插件 `src/checkpoint.ts:20-26` 生成的恢复提示含空的 context_references 和近期 Notes 路径；`src/index.ts:314-320` 没有携带当前 turn 的未完成目标/触发消息引用，也不检查 Notes 是否覆盖最后一次 Inbox 输入。原始记录仍在 History，属于退出活动上下文而非物理删除。

生产 turn 183：15:09:17、15:09:32 的真实请求包含最新用户原话及其消息 ID；15:09:45 的第一条新窗请求二者均不再出现。原生 compaction/summary seq 7031，替换范围 6985–7028，reason=pressure。随后模型只读 14:10 保存的旧 latest-checkpoint，没有查询 History 找回最新任务；15:10:10 以“本轮无新请求”结束。Inbox 已提交读取，执行又被标成 completed，调度侧没有以执行失败重新送入这条消息。

14:12、14:14、14:57、15:08 四轮都观察到对应重复失败。它们每轮均结束，不是已证明的无输入无限运行；重复来自新指令触发后再次进入相同的错误恢复路径。

## 与 Codex 基线及验收的关系

对照设计指定 Codex `464add49587a7cb6032d5ab04faa8a1585947853`，不能将“尽量沿用提示词”视为已经采用同样的上下文生命周期：

- `codex-rs/core/src/session/mod.rs:4920-4971`：首次完整注入建立 baseline，后续动态状态按差异更新。
- `codex-rs/ext/skills/src/world_state.rs:165-176`：相同的 Skill catalog section 不产生新的 fragment。
- `codex-rs/ext/skills/src/host_prompt.rs:60-96`：读取选中 Skill 的正文；`core/src/session/turn.rs:1228-1238` 对扩展已注入的 host Skill 做重复抑制。
- `start_new_context_window` 也会重建初始上下文，因此不能反过来说 Codex 永不携带 Skill 正文，或永不清空旧对话。这里证实的差异是持续动态更新和正文载荷的生命周期；不将固定源码观察推广为所有线上模型统一行为。

生产版本的 archived `acceptance.md:31,41,73-77` 记录了真实长任务的 13 次换窗，实际主要覆盖 Notes 保存后主动 new_context 的提醒/fallback 路径；测试将 B 调为 30,000，C=65,536、O=16,384、W=19,152。它证明该配置下可以恢复任务，不覆盖本次默认 buffer、持续变动的大快照、旧 Notes 宣称完成而新 Inbox 已读的组合。

R2 `acceptance.md:150-164` 的 PA/Global 等身份矩阵也明确安排“预算→保存 Notes→new_context→Notes/History 恢复”。插件 `tests/safety.spec.ts:21-61` 的 hard-cap 断言保护新任务在第一个换窗请求中存在及最后的有效环境，不验证之后再次强制切窗时，已入日志的当前任务仍可被正确接续；脚本预定最后返回 finished。

因此，设计风险和测试判据更偏重“合法配对、确实缩短、能读旧记录”，对“强制换窗后仍知道当前正在做什么”缺乏足够约束和端到端覆盖。产品 spec 已明确要求最新更正生效和未完成事项不能误报完成，问题不是缺少用户需求。

保留反证：R1 算错汇总、违背 bash 禁令的历史案例，原始输入当时包含正确数据/约束，不能据本次故障将它们一并改判为上下文丢失。当前案例有独立的“切窗前存在、切窗后消失”的输入证据。

## 修复方向与完成条件

1. 先统一动态状态与 Skill 恢复的生命周期：引用的变化不应每步复制历史已用 Skill 全文；在 DSH 公开 API 边界内解决，不 patch/fork runtime 或 private import。
2. 强制换窗也必须有当前未完成任务的明确恢复入口，覆盖已通过 Inbox 读入的消息。保留原始来源与授权语义，不需要恢复任意普通对话尾部，也不引入另一套长期任务数据库。
3. 校验保存机会与本次已知输入增量；旧 Notes 的“完成”不能无条件覆盖更新的已读任务。具体方案由修复者对照公开接口选择，不只提高窗口阈值或要求用户重述。
4. 用默认预算验证本次失败形态：先产生已完成旧事项的 Notes，再读入新 Inbox 请求；在写新 Notes 前跨越保存区间并强制切窗，最终完成新任务。动态引用连续变化时检查请求内 Skill 正文数量及总输入增长；保留先前的 Notes/History、无摘要、来源、配对、隔离与副作用不重复约束。

本次仅做设计、源码及既有真实日志对照，未重跑实现测试或修改实现；已有请求证据足以确认这条因果链。尚未选择修复方案、证明修复有效或完成生产恢复。
