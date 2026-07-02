# feat-446: 增加独立 skill_view 工具 + Curator 生命周期管理

## Relations

- Related: feat-392（kernel spec 契约层）

## 原始需求

> 加个需求，增加skill view工具，我觉得从逻辑上，skill view更合理，因为skill工具隐含了执行的意思，但是其实看了skill详细情况，或许不适合就不执行。引入的目的是我刚刚所说，为了可审计可监控skill，在压缩时可以带上，如CC的。以及自进化时能知道使用情况的统计。但没必要有file_path参数

> 我skill_manage是从hermes 抄过来的。他是什么样的？

> ok，那我现在用到skill_manage的地方，你都得去hermes agent审视一下，他是不是把skill view工具也加进去了。这样才能安全的删除

> 继续，所以我的选择是增加skill_view，并skill_manage移除view

> 对比，CC和hermes，我来思考下

> 按我现有的skill_manage(action="view") 返回

> 好（指 use_count + last_used_at only）

> 对（指 addInvokedSkill 压缩存活）

> 等下，我们有hermes 的Curator机制吗

> 那这次把curator机制也补上

> 我的意思就是纳入Per-skill Batch到本需求中。所以你统计use_count的同时，还要统计在哪个session用的，才能拿jsonl分析。

> 这要学习hermes的设计

> 对（指 hermes curator 触发方式：periodic + 7天门控 + 确定性扫描）



## 澄清记录

- Q1: skill_view 和现有 skill_manage 的 view action 的关系——拆出来还是保留两处?
A(原话): 继续，所以我的选择是增加skill_view，并skill_manage移除view
Agent 解读: 明确选择拆分。skill_manage 去掉 view action，skill_view 成为独立只读工具。
- Q2: skill_view 返回格式——结构化 JSON 还是原始文本?
A(原话): 按我现有的skill_manage(action="view") 返回
Agent 解读: 沿用现有返回格式 `{success, name, content, location}`，不引入 hermes 的 linked_files/tags 等额外字段。
- Q3: 压缩存活机制——是否引入 CC 的 addInvokedSkill?
A(原话): 对。
Agent 解读: skill_view 调用成功后注册该 skill 的身份和位置。compaction 时重新读取该 skill 当前 SKILL.md 内容，将 name + 当前 content 作为 `<system-reminder>` 重新注入。
- Q4: 使用统计——追踪哪些字段?
A(原话): 好（指 use_count + last_used_at only）
Agent 解读: 追踪 use_count 和 last_used_at。不区分 view/use（hermes 自己也不区分），patch_count 由 skill_manage 写侧追踪。
后续补充（Q10）：F4 纳入后，skill_view 调用时记录 {session_id, timestamp}。timestamp 同步更新 last_used_at（给 Curator 用），session_id 存入 session 引用列表（给 F4 batch 分析找 JSONL 用）。一次记录两个用途。
- Q11: F2 蒸馏 skill 的触发方式?
A(原话): 用户主动发起。看skill-evolution中讲的。agent自己判断这是现在就支持的，主agent用skill_manage搞，或者Per-turn Review。
Agent 解读: F2 是用户主动入口（选 session + 写意图），和 F3/F4 的自动触发正交。agent 自动判断并创建 skill 已有 F3 覆盖。
- Q12: F2 的入口形态?
A(原话): 我觉得这个可以做成一个skill，然后IM上可以在左边右键或者某种交互，选择某个session或者某几个session，然后跳转到一个新的对话中，写意图说明，然后用这个session总结生成skill的skill来给用户生成skill。这个skill用户可以选择生成成PA产品级的，还是agent级的
Agent 解读: F2 两层实现——IM 前端做历史会话选择交互（多选 → 范围选择 → 跳转新对话），蒸馏 skill 本身是一个标准 SKILL.md（教 agent 读 transcript + 意图 → 生成 skill）。后续 Q20-Q22 收口为：跳转新对话时预填 `/skill:conversation-skill-distiller`、`source_jsonl_paths` 完整路径列表和弹窗选择出的 `target_scope`。
- Q13: 面板归哪?
A(原话): 本unit包含了IM的实现
Agent 解读: skill 使用统计面板（IM 前端）在本 unit 内实现，不只是数据层。
- Q14: Curator 管辖范围——所有 skill 还是只管自动创建的?
A(原话): F2生成的skill属于手工生成，也不进行curator。然后所有skill虽然不都进行curator，但是都要记录使用次数，使用的session。
Agent 解读: 使用统计对所有 skill 生效（不管来源）。Curator 只管自动创建的 skill（F3 Per-turn Review 输出 + F4 Per-skill Batch 输出），不管手工创建的（F1 从零 + F2 蒸馏）。F1/F2 的 skill 是用户显式创建的，生命周期由用户自己管理。
- Q5: /skill: 斜杠命令现在重写为 `Use the "<name>" skill for this request.`，模型随后用 `read` 读 SKILL.md。改完后这条路径也走 `skill_view` 吗？
我的推荐：是。斜杠命令重写后的文案改为引导模型调 `skill_view` 而非 `read`。这样无论用户手动 `/skill-name` 还是模型自动调用，都走同一条路径，统计和 compaction 注册都能覆盖到。
反方：斜杠命令是用户显式触发，语义上和模型主动 view 不同。但追踪的目的是知道"skill 被用了"，不管谁触发的都该算。
A(原话): （用户未单独回答此问题，但从上下文确认了 skill_view 替代 read 的方向，此问题作为逻辑推导写入 spec）
Agent 解读: 统一路径。formatter.py 的引导文案和斜杠命令重写都指向 skill_view。
- Q6: 你项目有 self_improvement.py（后台 review），但没有 hermes 的 Curator（定期扫描 skill 生命周期）。现在 use_count / last_used_at 写了之后没有消费者。是先追踪后补 Curator，还是这次一起补?
A(原话): 那这次把curator机制也补上
Agent 解读: scope 扩大，Curator 纳入本 unit。
- Q8: hermes Curator 是全局扫描（所有 agent 共享 `~/.hermes/skills/`），本项目多 agent per-workspace 隔离，Curator 怎么处理?
我的推荐：改为 per-workspace 扫描。理由：本项目 skill 天然按 agent workspace 隔离，`skill_manage` 写入路径是 per-session 的，self_improvement 创建的 skill 也在当前 agent 的 workspace 里。全局扫描会打破隔离。
A(原话): 对，我改成per-workspace的。
Agent 解读: Curator 只扫描当前 agent 的 `<workspace_root>/<config_dirname>/skills/`，不碰别的 agent。状态文件 `.curator_state` 也存在 workspace 内。
- Q7: Curator 的触发方式——hermes 是"agent 空闲 + 距上次超过 7 天"时触发。Curator 是独立定时触发（hermes 的方式），还是挂在 self_improvement 里一起跑?
我的推荐：独立。理由：Curator 是确定性扫描（检查时间戳，不需要 LLM），和 background review（LLM 审视）职责不同。混在一起会让 self_improvement 更复杂。
反方：独立意味着要加新的调度机制（cron 或 heartbeat 触发）。挂在 self_improvement 里可以复用现有触发链路。
A(原话): 这要学习hermes的设计
Agent 解读: 读了 hermes 源码确认触发方式——CLI 启动时 daemon 线程调 `maybe_run_curator(idle_for_seconds=inf)`，Gateway 挂在 housekeeping loop 每 N tick 调一次。两者都传 `idle_for_seconds=inf`（始终 eligible），真正门控在 Curator 内部的 `config.interval_hours`（默认 7 天）。Curator 本身是确定性扫描：遍历所有 skill 的 last_used_at，30 天 → stale，90 天 → archived（物理移到 .archive/）。hermes 有 pinned 跳过语义，但本 unit 不采纳（见 Q17）。和 per-turn 的 self_improvement（LLM review）完全独立。
- Q15: F2 历史 session 蒸馏，本 unit 是要交付完整 IM 多选/跳转/生成流程，还是只交付蒸馏 SKILL.md，IM 交互另开 unit?
我的推荐：本 unit 交付最小完整 F2 端到端旅程：session 多选入口、范围选择弹窗、跳转新对话、预填 `/skill:conversation-skill-distiller`、用户补意图、发送后由 agent 在普通对话里生成并写入 skill。
理由：否则用户旅程断在"有蒸馏 skill，但用户不知道怎么从历史 session 触发它"。
A(原话): 纳入
Agent 解读: F2 的 IM session 选择交互、范围选择弹窗、跳转新对话和意图编辑都纳入本 unit，不另开 unit；写入走现有对话与 tool call 展示，不新增专门的 SKILL.md 草稿预览/确认 UI。
- Q16: Curator 把自动 skill 标成 `stale` 或归档成 `archived` 后，用户在 IM 和 `/skill:` 里应该看到什么?
我的推荐：`stale` 仍可见、可用，并在统计面板/候选详情里标记为 stale；`archived` 默认不再出现在 `<available_skills>` 和 `/skill:` 候选里，只在统计面板的 archived 过滤视图里可见。restore 本期只做手动文件级恢复，不做 UI 入口。
理由：这样不会因为 stale 误伤仍可能有用的 skill，同时 archived 真正退出日常使用路径。
A(原话): 对。
Agent 解读: stale 是降级提醒而非禁用；archived 退出日常 skill 发现和调用路径，但统计面板保留可审计记录。恢复 archived skill 的 UI 不纳入本期。
- Q17: `pinned skill` 本期要不要做?
A(原话): 明白，暂时不做吧
Agent 解读: pinned 相关能力本期不做：不提供 pin/unpin UI，也不做 Curator pinned 豁免。手工 skill 已不归 Curator 管；自动 skill 本期只按 active/stale/archived 规则流转。

- Q18: `skill_view` 在 IM 工具调用面板里应该怎么展示?
我的推荐：作为独立工具行显示真实工具名 `skill_view`，折叠态显示"查看 skill：<name>"；展开态显示 name、location、content 预览/可展开全文；失败时按现有 memory/skill_manage 失败态标红，展示错误原因。
理由：这个需求的动机之一是"可审计可监控 skill"，如果 UI 里看不清 agent 查看了哪个 skill，审计价值会打折。
A(原话): Q18，说的对
Agent 解读: 本期需要给 `skill_view` 做 IM 工具调用面板专属展示，不能只按通用工具 JSON 展示。
- Q19: 从会话做 skill 蒸馏时，是否新增专门的 SKILL.md 草稿预览/确认 UI?
A(原话): 从会话做skill 蒸馏的时候，你设计的，放到输入框中的prompt是啥？以及这个设计，现在我们会话没有这个能力啊，也不要为了这个skill蒸馏特意做这么一个预览的功能
Agent 解读: 不新增专门预览/确认产品能力。IM 只负责把选中的 conversation 对应 JSONL 路径和默认意图预填到现有输入框；用户编辑后按普通消息发送。agent 基于消息文本中的 `source_jsonl_paths` 自行读取 transcript，再调用 `skill_manage(create)` 写入，并通过现有工具调用展示/普通回复告知结果。
- Q20: F2 蒸馏输入应该传 conversation ID 还是完整 JSONL 路径?
A(原话): 我觉得不是给id，而是应该给完整的对应jsonl的路径列表。否则他拿到了id，如果是跨agent的，根本不知道jsonl在哪里。
Agent 解读: F2 输入改为 `source_jsonl_paths`。IM 仍从可见 conversation 列表发起，但跳转新对话时预填对应 transcript JSONL 的完整路径列表，而不是 conversation ID。这样跨 agent 蒸馏时 agent 不需要再猜 ID 到文件路径的映射。提交后这是一条普通聊天消息；Gateway/运行时不做专门解析、校验或 transcript 注入。agent 在 `conversation-skill-distiller` 指导下读取这些路径，读取失败按普通工具失败/assistant 回复处理。
- Q21: F2 的生成范围 scope 怎么让用户选择?
A(原话): 还有scope还是在勾选完会话之后，弹个窗让用户选择一下会好点。否则用户不明所以。
Agent 解读: 用户选完 conversation 并点击"生成 skill"后，先弹出范围选择弹窗，让用户在 agent 级 / PA 产品级之间二选一。确认后再跳转新对话，系统把选择结果写入预填 prompt 的 `target_scope` 字段。不要只把 `scope` 藏在输入框里让用户猜。
- Q22: F2 蒸馏 skill 的触发文案应该是什么形式?
A(原话): 而且skill调用是/skill:xxx吧，你预填的prompt不对
Agent 解读: 预填 prompt 必须使用现有 `/skill:<name>` 触发形式。本期新增的蒸馏 skill 名称固定为 `conversation-skill-distiller`，预填首行是 `/skill:conversation-skill-distiller`，后面追加 `source_jsonl_paths`、`target_scope` 和用户可编辑意图。



## 用户场景

用户（agent）在执行任务时，系统提示词里的 `<available_skills>` 列出了可用 skill 的名字和描述。agent 需要读取某个 skill 的完整内容来决定是否遵循其指令。

**当前做法**：formatter.py 引导模型用 `read` 工具读 SKILL.md 文件。问题是 `read` 是通用文件读取工具，没有 skill 语义——无法追踪"哪些 skill 被读过"，压缩时无法带上已读 skill 的内容（不像 CC 的 `addInvokedSkill` 机制），自进化体系也无法统计 skill 的使用频率。

**拆分后的工具职责**：

- `skill_view`（读侧）：读取 skill 完整内容，追踪使用统计，压缩时可带上。模型在判断"这个 skill 适不适合用"时调用，看了内容再决定是否执行。
- `skill_manage`（写侧）：只管 create / edit / patch / list / write_file / remove_file。去掉 view action。

**skill_view 名称解析与失败语义**：
`skill_view` 不提供 `file_path` 参数。它只允许按当前会话可见的 skill 名称读取，并且必须与 `<available_skills>` 和 `/skill:` 候选使用同一套可见集合：用户/agent 在候选里看到哪个 skill，`skill_view` 就只能读取这个可见集合里的 skill。

若 PA 产品级、agent 级或 workspace 级存在同名可见 skill，`skill_view(name=...)` 按当前既有 skill discovery / search root 优先级静默命中第一项，不返回名称不唯一失败。这个行为必须与 `<available_skills>` 和 `/skill:` 候选保持一致；返回结果中的 `location` 用于审计实际读取的是哪一个 skill，使用统计、session_refs、compaction 存活也都记录到这个被优先级命中的具体 skill。`stale` skill 仍属于可见集合，可以被读取；读取成功后恢复为 `active`。`archived` skill 默认不属于日常可见集合，不会出现在 `<available_skills>` 或 `/skill:` 候选里；若 agent 仍按名称请求一个已归档 skill，用户可见结果按找不到处理，不能通过日常读取路径复活。

`skill_view` 的用户可见失败原因主要是找不到。失败调用不会增加 use_count，不会更新 last_used_at，也不会注册压缩存活。IM 工具调用面板需要展示失败原因，避免用户只能看到一个泛化红色失败。

**IM 工具调用审计展示**：
当 agent 调用 `skill_view` 时，IM 工具调用面板必须让用户看清楚 agent 查看了哪个 skill。折叠态显示真实工具名 `skill_view` 和"查看 skill：<name>"摘要；展开态显示 name、location、content 预览，并支持展开全文。调用失败（例如 skill 不存在）时，该工具行按现有 memory/skill_manage 失败态标红，并展示错误原因。

**Curator 生命周期管理**：
Curator 只管自动创建的 skill（F3 Per-turn Review 输出 + F4 Per-skill Batch 输出），不管手工创建的（F1 从零 + F2 蒸馏）。手工 skill 的生命周期由用户自己管理。历史 skill 若没有明确来源信息，默认按手工/unknown 保护，不被 Curator 标 stale 或归档。

自动创建的 skill 随着使用或闲置，在三个状态间流转：

- `active` → `stale`（自动创建的 skill 30 天未被 skill_view 读取）
- `stale` → `archived`（自动创建的 skill 90 天未用，物理移到 `<skill_root>/.archive/` 目录）
- `stale` → `active`（被重新读取，复活）

归档为 `shutil.move` 到 `<skill_root>/.archive/`。只有目录移动成功后，用户才会看到该 skill 进入 archived 状态并退出日常候选；如果 `.archive/` 中已有同名目录、文件权限不足或移动失败，skill 不得被隐藏，统计面板需要保留它的可见状态并展示归档失败原因。restore 纯手动，本期不提供恢复 UI。

用户可见行为上，`stale` skill 仍保留在 `<available_skills>` 和 `/skill:` 候选中，可以照常被读取和使用，只是在 IM 统计面板和候选详情中标记为 stale。`archived` skill 默认不再出现在 `<available_skills>` 和 `/skill:` 候选中，只在 IM 统计面板的 archived 过滤视图里可见，作为审计和历史回看。

**Curator 是 per-workspace 的**：hermes 是单 agent 全局架构（`~/.hermes/skills/`），所有 agent 共享一个 skill 目录，Curator 统一扫描。本项目是多 agent 架构，每个 agent 有自己的 workspace，skill 天然按 agent 隔离（`<workspace_root>/<config_dirname>/skills/`）。因此 Curator 改为 per-workspace 扫描——每个 agent 只管自己的 skill 目录，不碰别的 agent。

**使用统计**：
所有 skill 不管来源（F1/F2 手工 + F3/F4 自动）都记录使用统计（use_count + session 引用列表）。统计对所有 skill 生效，Curator 只对自动创建的 skill 生效。统计只在 `skill_view` 成功读取后发生；失败读取不计数。系统重放或工具事件重复上报时，同一次 tool call 只能计一次；同一 session 内用户/agent 主动发起的不同 tool call 可以各自计数。

**使用统计面板（初版）**：
IM 前端增加 skill 使用统计面板，初版三个视图，后续根据使用体验迭代：

1. **Skill 列表视图**（主视图）：每行一个 skill，列：名字、来源（F1/F2/F3/F4）、状态（active/stale/archived）、use_count、最近使用时间、趋势 sparkline。默认按最近使用时间降序。一眼能回答"哪些 skill 在用，哪些是死重"。
2. **Agent 维度视图**：选一个 agent，看它的 skill 使用热力图——哪些 skill 用得多、哪些少。下面列该 agent 自动创建的 skill 列表（F3/F4 输出），每个标注 use_count。能回答"这个 agent 的自进化有没有产出价值"。
3. **自进化健康度视图**：三个数字卡片——F3/F4 创建的 skill 总数 → 其中 still active 的数量 → 其中 use_count > 0 的数量（漏斗比 = 自进化存活率）。下面是一个时间线：每个 skill 的创建时间 → 首次使用时间 → 最后使用时间，用色块区分来源。

Curator 每 7 天跑一次确定性扫描（不调 LLM），CLI 启动时和 Gateway housekeeping loop 中触发。状态持久化到 workspace 内的 `.curator_state` JSON 文件。本期不做 pinned skill 语义，自动创建的 skill 只按 active/stale/archived 流转。

**Per-skill Batch 优化（F4）**：
skill_view 调用时记录 `{session_id, timestamp}`。当某个 skill 的 `uses_since_last_B` 达到阈值（默认 ~20），触发该 skill 的 batch 优化：收集这些已结束 session 的 JSONL transcript，用 LLM 分析跨 session 的系统性缺陷（用户纠正、工具报错、任务放弃等信号），找到 ≥2 个 session 反复出现的问题后，通过 `skill_manage(action="patch")` 修补 skill。

F4 只 patch 不创建。分析的是"这个 skill 哪里有问题"，不是"要不要建新 skill"。F4 自动写入只允许作用于自动创建的 skill（F3/F4 来源）。F1 从零创建、F2 手动蒸馏、manual/unknown 来源的 skill 达到阈值时，不得被 F4 自动 patch；若系统产生优化建议，也只能作为建议等待用户显式预览确认，本期不承诺手工 skill 的自动优化 UI。

同一个 skill 同一时间只允许有一个 F4 batch 在运行。若已有 batch 运行中，后续 skill_view 继续增加使用次数也不能启动第二个并发 batch。F4 使用该 skill 的 session 引用去收集已结束 session 的 JSONL transcript；session 尚未结束或 transcript 缺失时，该 session 不作为分析证据。具体分析流程（W: map-reduce 多 agent 并行 vs A: 单 agent 单轮）留 design 阶段选型。

**F2 手动蒸馏 skill**：
用户在 IM 左边栏右键进入"生成 skill"多选模式 → checkbox 出现；默认 conversation 列表不显示运行态标签，多选模式下 `run_state=idle` 的会话可选，`run_state="running"` 的会话禁选并显示"运行中" → 用户选择若干可选会话后点击"生成 skill" → IM 弹窗让用户选择写入范围（agent 级或 PA 产品级）→ 用户确认后跳转到新对话 → 系统把 `/skill:conversation-skill-distiller`、所选 conversation 对应的 `source_jsonl_paths` 完整路径列表、`target_scope` 和可编辑意图预填到现有输入框 → 用户编辑后按普通消息发送 → agent 在蒸馏 skill 指导下读取 JSONL、提取模式并调用 `skill_manage(create)` 写入对应 skill root → 对话里通过现有工具调用展示/普通回复展示写入结果。

F2 正常入口只允许用户从当前可见的 conversation 列表中选择 `run_state=idle` 的 conversation。用户也可以复制或手动调整预填命令里的 `source_jsonl_paths`。提交后，agent 按蒸馏 skill 的指令读取这些路径；若任一路径不存在、不是 JSONL 或不可读，蒸馏流程必须在用户可见错误处停止，不得部分读取、不得部分生成、不得写入新 skill。

本 unit 交付最小完整端到端旅程：IM 前端 session 多选/范围选择弹窗/跳转/输入框预填入口 + `conversation-skill-distiller` 蒸馏 skill（SKILL.md）+ prompt 中的 `target_scope`/意图编辑 + 现有对话内写入结果展示。不新增专门的 SKILL.md 草稿预览/确认 UI。

**与 hermes 的对齐**：hermes 本来就是三工具拆分（skills_list / skill_view / skill_manage）+ Curator。用户抄代码时把 view 和 list 合进了 skill_manage，Curator 没抄。现在补上，并从全局改为 per-workspace。

**自进化体系总览**（五个正交机制）：


|               | F1 · 从零创建            | F2 · 从历史蒸馏                    | F3 · Per-turn Review                     | F4 · Per-skill Batch                   | F5 · Curator                 |
| ------------- | -------------------- | ----------------------------- | ---------------------------------------- | -------------------------------------- | ---------------------------- |
| **触发**        | 用户手动                 | 用户手动（选 session + 写意图）         | 自动：单 session 内 tool calls ≥ 10           | 自动：单 skill uses_since_last_B ≥ 阈值（~20） | 自动：idle ≥ 2h + 距上次 ≥ 7 天     |
| **输入**        | 用户口述                 | 用户选中 conversation 后解析出的 `source_jsonl_paths` + 意图文本 | 当前 session 的 hook 事件                     | 该 skill 被用过的 X 个已结束 session 的 JSONL    | 整个 skill 库（不读 transcript）    |
| **分析深度**      | 无（用户描述，agent 直接写）    | 中：从 transcript 提取模式，生成 skill  | 轻量：用户纠正、风格偏好、工作流改进                       | 重量：跨 session 统计挖掘，≥2 证据阈值              | 维护级：时间戳扫描，不调 LLM             |
| **能做什么**      | 创建 skill             | 创建 skill                      | 创建 + patch skill                         | 只自动 patch F3/F4 skill，不创建              | 只归档 F3/F4 skill + 复活 active |
| **写入方式**      | skill_manage(create) | skill_manage(create)          | skill_manage(create/patch)               | skill_manage(patch)                    | 直接改状态 + 物理移动目录               |
| **本 unit 现状** | 已有（skill-creator）    | 新增：蒸馏 skill + IM session 选择交互 | 已有（self_improvement.py），补 skill_view 白名单 | 新增：阈值触发 + session 引用追踪 + 分析流程          | 新增：per-workspace periodic 扫描 |


五个机制正交不冲突：F1/F2 是用户主动创建入口，F3 在 session 内实时响应，F4 在 skill 维度批量深挖，F5 在库级别定期维护。

## 验收标准



### Requirement: skill_view 作为独立只读工具可用



#### Scenario: agent 调用 skill_view 读取 skill 内容

- **WHEN** agent 调用 `skill_view(name="change-spec-author")`
- **THEN** 返回该 skill 的 SKILL.md 完整内容（JSON 结构，含 success、name、content、location 字段）



#### Scenario: agent 调用不存在的 skill

- **WHEN** agent 调用 `skill_view(name="nonexistent-skill")`
- **THEN** 返回错误信息（success=false），不抛异常



#### Scenario: 同名 skill 按既有优先级读取

- **GIVEN** 当前会话可见集合中存在两个同名 skill（例如 PA 产品级和 agent 级各一个）
- **WHEN** agent 调用 `skill_view(name="same-name")`
- **THEN** 系统按当前 skill discovery / search root 优先级读取第一项
- **AND** 返回结果中的 `location` 指向实际命中的 skill



### Requirement: IM 工具调用面板展示 skill_view 审计信息

#### Scenario: skill_view 成功调用的折叠态可审计

- **WHEN** agent 调用 `skill_view(name="change-spec-author")` 成功，用户在 IM 工具调用面板查看该工具行
- **THEN** 折叠态显示真实工具名 `skill_view`，并显示"查看 skill：change-spec-author"摘要

#### Scenario: skill_view 成功调用的展开态展示内容

- **WHEN** 用户展开成功的 `skill_view` 工具行
- **THEN** 展开态显示 skill name、location、content 预览，并提供展开全文入口

#### Scenario: skill_view 调用失败时展示失败态

- **WHEN** agent 调用不存在的 skill 导致 `skill_view` 返回 success=false
- **THEN** IM 工具调用面板中该工具行标红，并在展开态展示错误原因



#### Scenario: skill_view 失败原因可见

- **WHEN** `skill_view` 因找不到等原因返回 success=false
- **THEN** IM 工具调用面板中的失败态展示对应原因
- **AND** 用户能分辨应该修正 skill 名称还是检查 skill 可见性



### Requirement: skill_manage 不再包含 view action



#### Scenario: skill_manage 的 action 枚举不含 view

- **WHEN** 查看 skill_manage 工具的 input_schema
- **THEN** action 枚举为 create / edit / patch / list / write_file / remove_file，不含 view



### Requirement: 使用统计追踪



#### Scenario: agent 主动调用 skill_view 记录使用统计

- **WHEN** agent 调用 `skill_view(name="xxx")` 成功返回
- **THEN** 该 skill 的 use_count +1，last_used_at 更新为当前时间



#### Scenario: 用户通过 /skill: 斜杠命令触发时也记录使用统计

- **WHEN** 用户输入 `/skill:<name>`，系统重写后引导模型调用 skill_view，skill_view 成功返回
- **THEN** 该 skill 的 use_count +1，last_used_at 更新为当前时间（和 agent 主动调用走同一条路径）



#### Scenario: skill_view 失败调用不记录使用统计

- **WHEN** agent 调用 `skill_view` 因 skill 找不到等原因失败
- **THEN** 该 skill 不增加 use_count，不更新 last_used_at，不追加 session 引用



#### Scenario: 重放同一次 skill_view 不重复计数

- **GIVEN** 同一次 `skill_view` 成功调用已经记录过使用统计
- **WHEN** 系统因事件重放或恢复重试再次处理同一次调用
- **THEN** use_count 不再增加
- **AND** session 引用列表不出现重复记录



### Requirement: 压缩存活（compaction survival）



#### Scenario: 压缩后已读 skill 内容保留

- **GIVEN** agent 在对话中通过 skill_view 读取了 skill A 的内容
- **WHEN** 对话触发 compaction
- **THEN** skill A 的 name + content 在压缩后的上下文中以 `<system-reminder>` 形式重新注入



#### Scenario: 压缩存活对同一 skill 去重

- **GIVEN** agent 在同一对话中多次通过 skill_view 读取 skill A
- **WHEN** 对话触发 compaction
- **THEN** 压缩后的上下文只重新注入一份 skill A 内容
- **AND** 注入内容来自 compaction 发生时重新读取到的 skill A 当前内容



### Requirement: Curator 自动生命周期管理



#### Scenario: 30 天未用的 skill 标记为 stale

- **GIVEN** 自动创建的 skill A 的 last_used_at 距今超过 30 天
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 的状态从 active 变为 stale



#### Scenario: 90 天未用的 skill 归档

- **GIVEN** 自动创建的 skill A 的 last_used_at 距今超过 90 天
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 的状态变为 archived，其目录物理移到 `<skill_root>/.archive/`



#### Scenario: stale skill 被重新读取后复活

- **GIVEN** skill A 当前状态为 stale
- **WHEN** agent 调用 `skill_view(name="A")`
- **THEN** skill A 的状态恢复为 active



#### Scenario: stale skill 仍可被用户发现和使用

- **GIVEN** skill A 当前状态为 stale
- **WHEN** 用户查看 `/skill:` 候选或 agent 收到 `<available_skills>` 列表
- **THEN** skill A 仍然可见、可被 skill_view 读取，并在 IM 统计面板和候选详情中标记为 stale



#### Scenario: archived skill 退出日常使用路径但可审计

- **GIVEN** skill A 当前状态为 archived
- **WHEN** 用户查看 `/skill:` 候选或 agent 收到 `<available_skills>` 列表
- **THEN** skill A 默认不可见、不会被日常选择或自动读取
- **AND** 用户在 IM 统计面板切到 archived 过滤视图时仍能看到 skill A 的历史记录



#### Scenario: 手工或未知来源 skill 不被 Curator 归档

- **GIVEN** skill A 来源为 F1、F2、manual 或 unknown，且 last_used_at 距今超过 90 天
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 不变为 stale 或 archived
- **AND** skill A 仍出现在 `<available_skills>` 和 `/skill:` 候选中



#### Scenario: Curator 归档失败时不隐藏 skill

- **GIVEN** 自动创建的 skill A 满足归档条件，但归档目标冲突或目录移动失败
- **WHEN** Curator 执行定期扫描
- **THEN** skill A 不得从 `<available_skills>` 和 `/skill:` 候选中消失
- **AND** 用户在 IM 统计面板能看到归档失败原因



### Requirement: skill_view 记录 session 引用



#### Scenario: skill_view 调用记录 session_id 和 timestamp

- **WHEN** agent 在 session S 中调用 `skill_view(name="xxx")` 成功
- **THEN** 记录 `{session_id: S, timestamp: now}`，其中 timestamp 同步更新 last_used_at，session_id 存入该 skill 的 session 引用列表



### Requirement: 从历史 session 蒸馏 skill（F2）



#### Scenario: 用户从 IM 历史 conversation 入口发起蒸馏

- **GIVEN** IM 左边栏存在若干 conversation
- **WHEN** 用户右键 conversation 并进入"生成 skill"多选模式
- **THEN** IM 显示 checkbox；`run_state=idle` 的 conversation 可选，`run_state=running` 的 conversation 禁选并显示"运行中"



#### Scenario: 默认会话列表不显示运行态标签

- **GIVEN** 用户正常浏览 IM conversation 列表
- **WHEN** 用户未进入"生成 skill"多选模式
- **THEN** conversation 行不显示"已结束/运行中"这类运行态标签



#### Scenario: 用户选择可蒸馏 conversation 后选择写入范围并跳转

- **GIVEN** 用户已在多选模式中选择一个或多个 `run_state=idle` 的 conversation
- **WHEN** 用户点击"蒸馏为 skill"
- **THEN** IM 先弹窗让用户选择 agent 级或 PA 产品级写入范围
- **AND** 用户确认后跳转到一个新对话，并预填 `/skill:conversation-skill-distiller`、所选 conversation 对应的 `source_jsonl_paths` 完整路径列表与 `target_scope`
- **AND** 用户可以继续补充意图说明



#### Scenario: 用户通过弹窗指定生成级别后提交蒸馏

- **GIVEN** 用户已在范围选择弹窗中选择 agent 级或 PA 产品级，且新对话已预填所选 `source_jsonl_paths` 与对应 `target_scope`
- **WHEN** 用户补充意图说明并发送
- **THEN** agent 在蒸馏 skill 指导下按该级别决定目标 skill root，并开始读取消息中 `source_jsonl_paths` 对应的 JSONL transcript



#### Scenario: source JSONL 路径不可用时不部分生成

- **GIVEN** 用户提交的 `source_jsonl_paths` 中包含不存在、不可读或不是 JSONL 的路径
- **WHEN** agent 按蒸馏 skill 指令读取 transcript
- **THEN** agent 停止本次蒸馏并告知用户哪些 source 不可用
- **AND** 不基于剩余 source 部分生成 skill



#### Scenario: 用户选 conversation + 意图生成 skill

- **GIVEN** 用户在 IM 左边栏选择若干 `run_state=idle` 的 conversation，跳转到新对话并写了一段意图说明
- **WHEN** 蒸馏 skill 被触发，读取这些 conversation 的 JSONL transcript
- **THEN** 系统从 transcript 中提取工作模式，生成新的 SKILL.md 内容，覆盖用户意图描述的工作流



#### Scenario: agent 写入 skill 后在普通对话里展示结果

- **GIVEN** 用户已发送预填后的蒸馏消息，且 source conversation 均可读取
- **WHEN** agent 从 transcript 中提取出稳定工作模式
- **THEN** 新 skill 写入用户选择的 PA 产品级 skill root 或 agent 级 skill root
- **AND** 对话里通过现有 `skill_manage(create)` 工具调用展示或普通 assistant 回复告知写入结果



#### Scenario: 本期不新增专门预览确认 UI

- **WHEN** 用户从历史 conversation 发起 skill 蒸馏
- **THEN** IM 不展示专门的 SKILL.md 草稿预览卡片
- **AND** IM 不新增"确认写入/取消"按钮或专门确认状态机
- **AND** 用户如需先审稿，可在输入框意图里要求 agent 先展示草稿而不是直接写入



#### Scenario: 蒸馏 skill 是一个普通 `SKILL.md`

- **WHEN** 查看蒸馏 skill 的实现
- **THEN** 它是名为 `conversation-skill-distiller` 的标准 SKILL.md 文件，教 agent 如何读 session transcript + 意图 → 生成 skill，使用 skill_manage(create) 写入



### Requirement: Per-skill Batch 优化触发



#### Scenario: 达到阈值后触发 batch 分析

- **GIVEN** 自动创建的 skill A 的 uses_since_last_B 达到阈值 X
- **WHEN** skill_view 调用完成且计数器越线
- **THEN** 触发 skill A 的 batch 优化任务：收集对应的已结束 session JSONL，分析跨 session 系统性缺陷



#### Scenario: batch 分析只 patch 不创建

- **WHEN** batch 分析发现 skill A 的缺陷
- **THEN** 通过 `skill_manage(action="patch")` 修补 skill A，不创建新 skill



#### Scenario: batch 分析要求 ≥2 session 的证据

- **WHEN** batch 分析某个问题模式
- **THEN** 只有在 ≥2 个不同 session 中出现的问题才被采纳，单 session 的问题被忽略



#### Scenario: 手工 skill 达到阈值也不自动 patch

- **GIVEN** skill A 来源为 F1、F2、manual 或 unknown，且 uses_since_last_B 达到阈值 X
- **WHEN** skill_view 调用完成且计数器越线
- **THEN** 系统不得自动 patch skill A
- **AND** 若产生优化建议，也必须等待用户预览确认后才可写入



#### Scenario: 同一 skill 不并发启动多个 batch

- **GIVEN** skill A 已有一个 batch 优化任务正在运行
- **WHEN** 新的 skill_view 调用让 skill A 的使用计数再次越线
- **THEN** 系统不启动第二个并发 batch 优化任务



#### Scenario: batch 有效证据不足时不 patch

- **GIVEN** skill A 达到 batch 阈值，但可收集的 session 引用中已结束且有 transcript 的 session 不足 2 个
- **WHEN** batch 优化任务收集输入
- **THEN** 系统不 patch skill A



### Requirement: 系统提示词引导模型使用 skill_view 而非 read



#### Scenario: formatter 引导用 skill_view 加载 skill

- **WHEN** 系统提示词生成 `<available_skills>` 块
- **THEN** 引导文案指示模型用 skill_view（而非 read 工具）加载 skill 内容



### Requirement: 使用统计面板（IM 前端，初版）



#### Scenario: Skill 列表视图

- **WHEN** 用户打开 skill 使用统计面板
- **THEN** 显示所有 skill 的列表，每行包含名字、来源（F1/F2/F3/F4）、状态（active/stale/archived）、use_count、最近使用时间、趋势 sparkline，默认按最近使用时间降序



#### Scenario: 使用统计面板空态

- **GIVEN** 当前 workspace 尚无任何 skill_view 成功记录
- **WHEN** 用户打开 skill 使用统计面板
- **THEN** 面板显示暂无 skill 使用记录的空态
- **AND** 不显示为加载失败



#### Scenario: 使用统计面板加载失败

- **WHEN** 用户打开 skill 使用统计面板但统计数据加载失败
- **THEN** 面板显示可理解的失败态和重试入口
- **AND** 不把失败态伪装成空数据



#### Scenario: Agent 维度视图

- **WHEN** 用户选择某个 agent
- **THEN** 显示该 agent 的 skill 使用热力图 + 自动创建的 skill 列表（F3/F4 输出）及各自 use_count



#### Scenario: 自进化健康度视图

- **WHEN** 用户切换到健康度视图
- **THEN** 显示三个数字卡片（F3/F4 创建总数 → still active 数 → use_count > 0 数）+ 每个 skill 的创建→首次使用→最后使用时间线



### Requirement: 所有引用点正确迁移



#### Scenario: background review 白名单包含 skill_view

- **WHEN** self-improvement hook 启动后台 review
- **THEN** 工具白名单包含 skill_view（和 skill_manage）



#### Scenario: 产品层工具列表包含 skill_view

- **WHEN** coding_cli / personal_assistant 初始化工具集
- **THEN** skill_view 在可用工具列表中

#### Scenario: PA agent 默认启用但可取消 skill_view

- **GIVEN** PA agent 没有显式工具白名单
- **WHEN** Gateway 为该 agent 创建新 session，或 IM 展示该 agent 的工具配置
- **THEN** skill_view 默认启用 / 默认选中
- **AND** 用户在配置页取消 skill_view 并保存后，该 agent 的显式工具白名单不包含 skill_view，后续 session 不再启用 skill_view

#### Scenario: 已有显式工具白名单不被自动扩宽

- **GIVEN** PA agent 已持久化显式工具白名单，且其中不包含 skill_view
- **WHEN** 本功能上线后用户打开配置页或该 agent 创建新 session
- **THEN** skill_view 不被自动选回，也不被自动加入 session 工具集



## 范围与非目标

- 在范围：
  - 新建独立 `skill_view` 工具（platform 层）
  - `skill_view` 的 name-only 解析合约：只读当前会话可见集合中的唯一 skill，找不到或重名失败可审计
  - `skill_manage` 移除 view action
  - IM 工具调用面板为 `skill_view` 提供专属审计展示（折叠摘要、展开详情、失败态）
  - formatter.py 引导文案从 read 改为 skill_view
  - 使用统计追踪（use_count + last_used_at + session 引用列表 {session_id, timestamp}），对所有 skill 不管来源生效；成功读取才计数，失败和重放不重复计数
  - 压缩存活机制（addInvokedSkill + compaction 时 re-inject），同一 skill 去重，并在 compaction 时重新读取当前 SKILL.md 内容
  - Curator 生命周期管理（active/stale/archived，per-workspace，periodic 触发，7 天门控，只管 F3/F4 自动创建的 skill；F1/F2/manual/unknown 来源受保护）
  - Per-skill Batch 优化（F4）：uses_since_last_B 阈值触发，收集已结束 session JSONL，LLM 分析跨 session 系统性缺陷，≥2 证据阈值，只自动 patch F3/F4 自动 skill，不自动 patch F1/F2/manual/unknown skill
  - 手动蒸馏 skill（F2）：IM 前端 session 多选/范围选择弹窗/跳转/输入框预填入口 + `conversation-skill-distiller` 蒸馏 skill 本身（SKILL.md）+ prompt 中的 `target_scope` 与意图编辑 + 现有对话内写入结果展示；`source_jsonl_paths` 可复制/手动调整，但必须对应用户可见、已结束、已登记且 transcript 可用的 JSONL 文件
  - IM 前端 skill 使用统计面板（per-skill 使用情况 + per-agent skill 使用分布）
  - 所有引用点迁移（product.py、kernel.py、self_improvement.py、feature_registry、reporter 等）
- 非目标：
  - skill_view 的 file_path 参数（用户明确排除）
  - pinned skill / pin-unpin / Curator pinned 豁免
  - fork 子 agent 模式（CC 特有，本期不做）
  - contextModifier（权限/模型/effort 覆盖，CC 特有，本期不做）
  - 条件激活 paths 字段
  - skills_list 独立工具（list 留在 skill_manage 里）
  - Curator 的 LLM 合并 pass（hermes 的 consolidate 功能，本期不做）
  - archived skill 的 UI 恢复入口（本期只支持手动文件级恢复）
  - F4 自动 patch 手工 skill（F1/F2/manual/unknown 只允许产生建议，若要写入需另行设计用户确认 UI）
  - F4 的具体分析流程选型（W: map-reduce vs A: 单 agent，留 design 阶段）
  - Skills Hub 社区分发



## 后续候选清单

这些不是本 unit 的承诺范围，只是把本轮对齐中明确"暂时不做但后续可能要做"的项集中记录，避免后续跟丢。

- pinned skill 管理：为自动创建的 skill 增加 pin/unpin 入口，并让 Curator 尊重 pinned 豁免。
- archived skill 恢复入口：在 IM 统计面板的 archived 过滤视图中提供 restore 操作，把归档 skill 恢复到日常可见/可用路径。
- Curator LLM consolidate pass：学习 hermes 的 consolidate 能力，对 skill 库做更高层的合并/清理，而不只是时间戳扫描。
- 独立 skills_list 工具：如果后续发现 `skill_manage(action="list")` 仍让读/写职责混杂，再拆出只读列表工具。
- skill_view 支持读取 support files：当前 skill_view 只读 SKILL.md；后续若需要审计 references/templates/scripts/assets 的具体内容，再设计无 file_path 或受控 file_path 的读取方式。
- 条件激活 paths 字段：后续若 skill 数量太多、需要按路径/任务上下文减少候选噪音，再设计条件激活。
- contextModifier：如后续需要 skill 改变权限、模型或 effort，再单独设计，避免本期把 skill_view 和运行配置耦合。
- fork 子 agent 模式：如后续要学习 CC 的 skill 隔离执行/上下文隔离，再独立立项。
