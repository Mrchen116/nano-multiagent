# Design 评审:feat-430-im-slash-skill-picker

**结论**:Issues Found（2 CRITICAL + 2 WARNING）

评审对象:`docs/changes/feat-430-im-slash-skill-picker/design.md`（对齐 spec.md v2 + 三份 delta-spec）。

---

## 核实台账（逐条核过的承重原子;结论附证据）

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| capabilities skill option 带 `default_on`，可判"已启用" | 追 `_skills_from_kernel` 真实投影 | ✗ skills 项只投 `{name, description}`（`upstream_reporter.py:119-122`），**无 default_on**；default_on 是 tools 才有的字段（`agents.py:133` 默认 False）。skill 的 default_on 恒 False → 决策 2 前提不成立 |
| "已启用 skills" = 当前 agent 开启的 skills | 追 enable 判据真实落点 | ✗ 真实启用判据是 agent config 白名单 `agent.skills`（`inbound_pipeline.py:777-778` 写 session_metadata）；capabilities `list_skills(ws)` 返回 workspace 内**全部**发现的 skill，不按 allowlist 过滤 → 与 Q1「他开启了的那些 Skill」不等价 |
| `/skill:` 重写在 `rewrite_skill_command`，行首正则 `^\s*/skill:` | 读正则 + wiring | ✓ `skill_commands.py:5` `^\s*/skill:(?P<name>...)`；`runtime.py:451` 生产路径唯一调用点。`[Alice] /skill:doc` 因 `^\s*` 不吞 `[Alice] ` 而 miss——缺口真实 |
| 群聊 sender 前缀格式为 `[sender] ` | 追 format 函数 | ✓ `inbound_pipeline.py:1629` `return f"[{sender}] {text}"`；`_build_message_parts` `texts = buffered_texts + [current_text]`（每条都 `_format_sender_text`） |
| 群聊裸 `/stop` 被 MENTION 投递策略丢弃 | 追 `_should_process` vs `_is_stop_command` 执行顺序 | ✓ `handle_inbound` 先 `_should_process`（:258），MENTION 下裸 `/stop` 命中 `return f"@{agent_id}" in message.text`=False（:852）→ :280 return None，**永不到** `_is_stop_command`（:283）。缺口真实 |
| `_is_stop_command` 只 strip `@{agent_id}` 字面 | 读实现 | ✓ `:887-890` 仅 `text.replace(f"@{agent_id}", "")`，wire 形式 `@agent:{id}` strip 不净 → 匹配失败。缺口真实 |
| 契约 drift：gateway spec 已声明"控制命令触发"但代码丢弃 | 读 `docs/specs/gateway/spec.md` + 代码 | ✓ drift 成立；本 unit 让代码符合既有契约，方向对 |
| `SkillMetadata.location` 存在可取 | 读 registry | ✓ `registry.py:15` `location: Path`，`:77` `location=resolved_file` |
| `SkillInfo`(sdk) 现无 location | 读 dto | ✓ `dto.py:385` class SkillInfo 无 location 字段，本 unit 新增成立 |
| 前端 `@` 触发 `/@([^@\s]*)$/`、`/` 无处理 | 读 message-pane | ✓ `MENTION_RE = /@([^@\s]*)$/`（:50），群聊才取 mentionMatch（:144），无 `/` 分支。可照搬 |

### 决策

| 决策 | 四问 | 结论 + 证据 |
|---|---|---|
| 决策 1：slash-picker 照搬新建 | 拍死/自洽/有据 | ✓ 拍死、有 Q1/原型驱动；复用机制不共用组件，理由（wire XML vs 纯文本）成立 |
| 决策 2：skills 走 capabilities + 过滤 default_on | 有据/前提成立 | ✗ 前提塌（见现状栏）：skills 无 default_on，且 default_on≠Q1 的"已启用"。数据流缺 config allowlist 交集 → **CRITICAL #1** |
| 决策 3：location 五层只读透传 | 自洽/有据 | ✓ 沿用 description 既有通路，加可空字段，无行为变更，低风险 |
| 决策 4：群聊 /stop 缺口在 gateway 修 | 自洽/有据 | ⚠ ② 裸 /stop 绕 MENTION 成立；① "picker 补入的 wire mention 形式 /stop" 与决策 6"命令补 `/name `（纯文本）"对不上 → **WARNING #3** |
| 决策 5：群聊 /skill 靠内核 rewrite 容忍 sender 前缀 | 完整/有据 | ✗ 机制对单 part 成立，对群聊 buffered 多 part 路径不成立（join 破 `^` 锚 + len>1 重取末 part 绕过 rewrite）→ **CRITICAL #2** |
| 决策 6：补 `/skill:name `、命令 skill 一视同仁过滤 | 拍死/自洽 | ✓ 触发正则 `^/(skill:)?([^\s/]*)$` 覆盖编辑纠错（Q9/Q10），与现状一致；惟与决策 4① 的 /stop 形态冲突（见 #3） |

### spec 约束 / delta-spec / milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Q1：候选=当前 agent 已启用 skills | design 落点 | ✗ 决策 2 用 capabilities default_on，未取 config allowlist 交集 → 见 #1 |
| Q6/Q12：群聊 /stop 广播+幂等、裸 /stop 无视 @ 设置 | 覆盖 | ✓ 决策 4 + gateway delta 覆盖，幂等由既有 interrupt 保证 |
| Q7：同名 skill 按 location 区分、标来源 | 覆盖 | ✓ 决策 3 + §前端数据组装"按 location 去重合并/分行"覆盖（前提是 location 真到位 + 已启用集正确，依赖 #1 修） |
| Q9/Q10：补 `/skill:name `、命令参与前缀过滤 | 覆盖 | ✓ 决策 6 覆盖 |
| 非目标：不新增其他本地命令 / 不动中断机制 / 不引入新 wire 格式 | 不越界 | ✓ 范围内只 `/stop`+skills，未越界 |
| kernel delta（list_skills 带 location / 群聊 /skill 重写保留 sender） | 锚 canonical/用法/THEN | ✓ MODIFIED 锚既有 canonical 标题、加 Scenario；THEN 写消费者可观察重写文本，未点内部符号 |
| im delta（capabilities 返回 location） | 同上 | ✓ MODIFIED 锚"节点 runtime 能力按需解析"，加 Scenario，THEN 可观察 |
| gateway delta（/stop wire 识别 + 裸 /stop 绕门控） | 同上 | ✓ MODIFIED 锚"/stop 控制命令中断当前运行"，消解 drift，THEN 可观察。惟 Scenario 1"picker 补入的提及形式"承袭决策 4① 的存疑前提（见 #3） |
| cli：no spec delta | 注明 | ✓ 显式声明无 delta |
| 单 M1（前端+location 透传+群聊命令缺口） | 垂直 vs 横切 | ✓ 端到端单垂直切片，未横切拆分；退出标准两轨齐、`[reviewer]` 引 Scenario、`[worker]` 可验。无过度拆分 |

---

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 决策 5：把 `[sender] ` 前缀识别塞进内核 `rewrite_skill_command` | ⚠ `[sender] ` 是 gateway 群聊产品约定（`inbound_pipeline.py:1629`），让 core 内核正则认它，等于 core 反向编码 product 层消息格式——破坏"core 不知道产品"分层。长远代价:gateway 改 sender 格式须同步 core 正则 + core 单测须内嵌产品格式串;每次群聊格式演进多一处隐性耦合点。设计已自承耦合并提"共享约定"，但共享常量仍是 core 依赖 product 定义的格式 → **WARNING #4** |
| 该不该存在 | 决策 1：slash-picker 与 mention-picker 双组件 | ✓ 删除测试:合并需 mode 分支糅两套选中语义（wire XML vs 纯文本），复杂度真实分裂而非搬家；非假想接缝。重复代码风险已显式接受、留"稳定后抽 hook"。走完无存活发现 |
| 该不该存在 | 决策 3：location 五层透传字段 | ✓ 是数据到达前端的固有成本，沿用 description 既有管线，非多余封装。走完无存活发现 |
| 深还是浅 | 决策 4②：在共享 `_should_process` 上为 /stop 开特例口子 | ✓ /stop 本就是控制命令、契约（gateway spec:71）已要求它绕回复策略——修码符契约属治本非补丁;设计已点"严格限定只对 /stop"风险。走完无存活发现 |
| 治本还是补丁 | 决策 4① wire-mention 识别 | ⚠ 见 #3:若 picker 实际只补纯文本 `/stop `，则 4① 在解一个本设计前端不产生的输入形态 → 可能是无消费者的死需求。归入 #3 |

---

## Issues（按 CRITICAL > WARNING 排序）

- **[CRITICAL] [决策 2 / §接口与数据流·前端数据组装 / Q1]:「已启用 skills」判据塌台。** 决策 2 让前端拉 capabilities 后「过滤 `default_on==true`」，但 capabilities 的 skill 项**根本没有 default_on**（`upstream_reporter.py:119` 只投 `{name,description}`；default_on 是 tools 专属，skill 恒 False）——照此实现 picker **永远是空的**。退一步即便 worker 改成「显示全部 capabilities skills」，那也是 workspace 内**全部发现的 skill**，而非该 agent **已开启**的子集（真实启用判据是 config 白名单 `agent.skills`，`inbound_pipeline.py:777`），直接违反 Q1「指当前对话这个 Agent 他开启了的那些 Skill」。**不改→** worker 要么建出空 picker，要么把未启用 skill 也列出来。修法:数据流须**同时拉 `getAgentConfig`（拿 `skills: string[]` 白名单）+ capabilities（拿 description/location）并按 name 取交集**，design 的 §前端数据组装两段（单聊/群聊）都要补这一步并明确空白名单语义（empty=全部 还是 无）。

- **[CRITICAL] [决策 5 / kernel delta Scenario]:群聊 `/skill` 重写机制对 buffered 多 part 路径不成立，worker 照做会产出 false-fix。** 决策 5 只规定「改 rewrite 正则容忍前导 `[sender] `」。但群聊有别人未被 @ 的发言时,`_build_message_parts` 把 buffered 上下文与当前消息拼成**多个 text part**,`render_user_text` 用 `\n` join（`state.py:101`），`rewrite_skill_command` 在 `runtime.py:451` 对**整段 join** 跑 `^\s*` 锚——`/skill:` 落在 `[Bob] …\n[Alice] /skill:…` 的非首行,正则改了也 miss;更要命的是 `runtime.py:556-581` 的 `len(input_parts)>1` 分支会把 `effective_user_text` **重新取成末 part 的原始渲染**（`render_user_text(last_part)`，未经 rewrite），彻底绕过 451 的重写结果。**不改→** worker 只改正则,单条 `/skill:` 消息（无 buffered 上下文）测试通过、reviewer 放行,但群里一旦有人先发言,`/skill` 静默失效——spec「群聊 /skill 真生效」在常见路径未达成。修法:design 须指明 rewrite 应作用于**命令所在的那个 part / `effective_user_text`**（或逐 part 重写），而非仅依赖整段 join 的行首正则。

- **[WARNING] [决策 4① vs 决策 6 / gateway delta Scenario 1]:群聊 `/stop` 的「picker 补入形态」自相矛盾,worker 不知前端补什么、后端解什么。** 决策 6 明确「命令补 `/name `（纯文本）」⇒ 前端 picker 补 `/stop `;但决策 4① 与 gateway delta Scenario 1 又要 `_is_stop_command` 识别「picker 补入的 wire mention 形式 `@agent:{id}` /stop」——一个说纯文本、一个说提及形式,且 user 场景/Q6 明确群聊 /stop 是「普通文本广播」。**不改→** 前端 worker 不知群聊 /stop 该补 `/stop ` 还是 `@agent /stop`,gateway worker 不知 `_is_stop_command` 要不要做 wire-mention strip,两端可能建出 insert/parse 对不上的实现。请作者拍板:群聊 /stop = 裸纯文本（则 4① wire-mention 识别无消费者,应删或改挂到"既有手动 @agent /stop 的 wire 渲染"这一独立动机上,不要归因于 picker）。

- **[WARNING] [决策 5 归属 / 风险段]:`[sender] ` 群聊产品格式渗入 core 内核正则,反向跨层。** `[sender] ` 是 gateway 的群聊约定（`inbound_pipeline.py:1629`），决策 5 让 `agent.core` 的 `rewrite_skill_command` 认识它,使内核反向编码 product 层消息格式,违「core 不依赖产品」分层。**不改→** 日后 gateway 改 sender 格式须同步改 core 正则与 core 单测,多一处隐性跨层耦合。设计已自承并提"共享约定",但更顺的归属是**让 gateway 在喂给内核前处理前缀**（或前缀与命令分 part,内核只对命令 part 重写）——把产品格式留在产品层。请作者评估归属,至少把"共享约定"具体化为单一 owner。

---

## Recommendations（不阻断门禁,作者自行取舍）

- §接口与数据流 建议补一句:capabilities 的 skill 项现状**无 default_on**,本 unit 不要给 skill 引入 default_on（那会扩到工具语义之外）,启用判据统一走 config 白名单交集——避免 worker 误以为要给 skill 补 default_on。
- 决策 5 修好后,delta-spec kernel 建议补一条覆盖 buffered 多 part 群聊路径的 Scenario（当前唯一 Scenario 只覆盖单条 `[Alice] /skill:…`，会让 reviewer 漏测真正易碎的路径）。
- 整体上层「给人审方向」一层（架构总览图 + 决策一句话结论）清晰可扫,综述把"数据从哪来/命令到哪生效两条链路"串起来了,不报上层被淹没问题。

---

**给作者的回修建议**:回 `change-design-author` 优先修 #1（已启用判据,影响 picker 能否出 skill）与 #2（群聊 /skill 多 part 路径,影响是否 false-fix），并顺手拍板 #3（群聊 /stop 补入形态）、评估 #4（决策 5 归属）。这四点化解后方案可放心进 `change-orchestrator`;location 透传链路（决策 3）、群聊裸 /stop 绕门控（决策 4②）、单 M1 拆分均已核实成立,无需返工。
