# bugfix-433 全链路根因复盘

> 视角：把 SDD 全链路(spec → design → orchestrate → impl → review → verify)当审计对象，从用户每条反馈和日志倒推到真正引入问题的那个节点。
> 方法：每条结论用一手证据核实(session/subagent jsonl + 沉淀文档 + 代码)，不采信二手总结。
> 被复盘 session：`d9458ef5`（2026-06-24 10:30 → 06-25 06:08）。作者：审计 agent(独立于本 unit 实施链)。

## 0. 用户的核心期望 vs 实际

用户在一次 `/stop` 修复的 PR review 中顺手发现「下一轮图片没了」，确认是 bug，授权 **0 交互自主**走完 spec→design→orchestrator 把它修掉并提 PR。实际：unit **确实完成**（PR #148、CI 全绿、04:53 orchestrator 退出），但中途吃了 **3 轮 review/fix 级联**，其中**两轮是同一个 design 盲区**——而这个盲区的解法（CC 的 `normalizeMessagesForAPI` error-replay-strip）**早在立项第 1 小时(10:52)就被亲读 CC 源码后准确写出来了，却没进 incident.md、没进 design**。外加收尾时 **15 个后台 agent 没被回收**，用户 74 分钟后手动停掉。

一句话：这不是灾难，是一次「本可一轮过、实际三轮过」的 unit——多出的两轮全因一个**第 1 小时就掌握、却在 spec→design 边界丢失的关键机制**。

---

## 时间线与 jsonl 索引

jsonl 根：`~/.claude/projects/-Users-czj-Repos-nano-multiagent/`。主 session = `d9458ef5.jsonl`，subagent 在 `d9458ef5/subagents/agent-a<role>-<hash>.jsonl`。

### A. 主 session 表

| session | 时间跨度 | 装的阶段 |
|---|---|---|
| `d9458ef5` | 06-24 10:30 → 06-25 06:08 | 全程：bug 发现 + spec + design + orchestrator + 收尾 |
| `1ca8f3e2` | 06-25 01:44 → 02:11 | （旁支，113 hit，design 复核期） |

### B. 阶段时间线

| 阶段 | 时间区间 | subagent agentType（轮数峰值） |
|---|---|---|
| P0 bug 发现 + 立项 RCA | 06-24 10:30–10:53 | `Explore`(71)，亲读 CC，10:52 写出 strip-on-error，10:53 建 issue #146 |
| spec（自主） | 06-24 16:42 → | `/change-spec-author`，用户挂 Stop hook 离开，写 incident.md |
| design + 3 轮 design-review | 06-24 17 → 06-25 01:36 | 用户 01:20–02:10 回来挑战失败 UX(Q6) + 看 design-review + 整体自检×2 |
| orchestrator 实施 | 06-25 02:13–04:53 | `bugfix-433-M1`(**793**, 02:15–04:38, 全程复用) |
| ├ verify + review round1 | 02:54– | `verifier`(126)、`reviewer`(221) → round1 **fail**(Issue#1,#2) |
| ├ fix1（复用 worker） | ~03:12– | 损坏图结构校验 + 根因调查（#1/#2 同根） |
| ├ fix2 / scope B | ~04:17– | port CC `normalizeMessagesForAPI`（strip-on-error） |
| └ code review 3 轮 | 02:55–04:30 | `cr-A..G`+`cr-verify`、`cr2-A/B`、`cr3-A/B` |
| 收尾 / 孤儿 agent | 04:53–06:08 | orchestrator 宣告退出；15 后台 agent 滞留→用户 06:08 手停 |

> worker `bugfix-433-M1` 793 轮看着像失控，实为 **02:15→04:38 连续复用**（原 M1 + fix1 + fix2 + scope B + code-review 修复，dialogue 显示 11 次→lead / 13 次←lead），约 5.5 轮/分钟密集真实工作，**非空转**，符合「复用 worker 保上下文」良性模式。不计为问题。

## 主索引

| # | 发现时刻 | 表面症状 | 真正引入问题的节点 | 失效阶段 |
|---|---|---|---|---|
| P0 | reviewer round1 (03:xx) + live fix2 (04:17) | 损坏图/合法图触发 provider error 后，同会话后续文字**空回复**（会话被毒化） | design 缺「image turn 在 provider 报错后重放时 strip image」机制——而 10:52 探索已写出 CC 正是这么做 | **design 本身漏**（非实现偏离） |
| P1 | reviewer round1 Issue#1 | 41 字节损坏 PNG（合法头）未被入站拦截，透传 Anthropic→provider error 文案而非固化文案 | design 决策5 只说「解析失败→corrupt」，未钉死校验深度；worker 取 magic-bytes，被合法头骗过 | design 欠规约 + 实现 |
| P2 | 用户 06:08 手停 15 agent | orchestrator 宣告「后台 agent 会自然结束」，实际滞留 74 分钟 | orchestrator 收尾未显式回收 in-process teammate | orchestrator 收尾 |
| P3 | 审计挖出（无对应反馈） | design.md `## Changelog` 空白，多轮修订无耐久追溯 | design 修订记在 design-review.md 闭环记录，design.md 自身 Changelog 未维护 | design 文档卫生 |

---

## P0 — design 漏掉「provider 报错后重放 strip image」，而它第 1 小时就被写出来了

### 用户反馈 / 症状

reviewer round1 `regression.md` Issue #2（major）：发损坏图触发 provider error 后，**同一会话**继续发纯文字「1+2等于几？」→ **空回复(content='')**，1 分钟以上无更新；但无图错误历史的会话同时发文字正常。fix2 阶段 live 又暴露更广形态：合法图发**非 vision 模型**→provider error→同样毒化会话。

### 一手证据

1. **第 1 小时就掌握了解法**。`normalizeMessagesForAPI` 首次出现于 jsonl `2026-06-24T10:46:01`，`errorToBlockTypes` 于 `10:51:19`。10:52:14 主 session assistant 原话：
   > 「CC 抽验通过(`MessageContent = string | ContentBlockParam[] | ContentBlock[]`,单一 content 直接装 image block;**只有上轮 API 报 image-too-large 才 strip**)。证据链完整,本仓侧我已逐处亲读源码。」

   即 CC 的 error-replay-strip 机制在立项 RCA 阶段**被准确理解并写下**。

2. **这个洞见没进耐久文档**。`grep -in "strip\|normalize\|毒化\|留史\|provider.error" incident.md` = **0 命中**。incident.md 只编码了 3 断点（送达/持久化/mapper）+ 双轨 + 失败 UX「硬停」（Q6），**完全没有** strip-on-error。design.md 决策1-5 同样只覆盖「送达 + 持久化 + 入站拦截」，**没有 replay-strip**。

3. **design 自己制造了毒化面却不配套解药**。决策4（`Message.parts` 落盘 + 回放消费）让图片**首次真正持久化并每轮重放**——这正是毒化的物理前提：修复前图片被丢成占位符，永不重放、永不毒化；修复后失败图 turn 留史，**每轮重发→每轮 error→空回复**。progress.md fix1 根因段实证：「user_msg（含损坏 image parts）在进 loop **前**就 enqueue+flush 落盘…下轮重建历史→`_to_message` 还原 parts→`build_chat_messages` 再发损坏 image block→再 error→空回复。**损坏图确定性毒化会话历史**」。

4. **3 轮 design-review 全没拦住**。design-review.md 三轮 CRITICAL 全是「写出来的东西内部自洽吗」（is_provider_error 数据流闭合、M246 多图、delta-spec 归属），**无一问**「决策4 持久化了 image turn——它在 provider 报错后会怎样？」。reviewer 只能审写出来的，漏掉的机制天然在视野外。

5. **仓库已有同类已知账**。issue #82(CLOSED)：「中断的工具调用轮会永久污染会话历史,导致该会话之后所有消息失败」——**同一毒化类**（一个 error turn 留史毒化后续）。design 既没连 CC 的解法，也没连本仓 #82 的前车。

6. **fix2 才把第 1 小时的洞见 port 回来**。「strip image」首次出现 `2026-06-25T04:17:08`；progress.md fix2 段亲读 `messages.ts:2275-2420 normalizeMessagesForAPI` 后在 `build_chat_messages` 同构落点实现——**与 10:52 写下的完全是同一机制**，绕了一圈 ~5.5 小时回到原点。out-of-unit #147 记录更广面。

### 根因落点

**失效在 design 本身（不是实现偏离对的 design）**——这正回答用户最关心的「对齐 design 后能不能托管 agent」：本 unit 实现**高度忠实** design（verifier round1：5 决策 + 2 CRITICAL 全遵守、8/8 scenario 覆盖），可还是 fail 了两轮，因为 **design 缺了一块**。

更精确的根因是**知识在 spec→design 边界蒸发**：解法在 10:52（立项第 1 小时，`Explore` 完成回主线时）被准确articulate，但
- `change-spec-author`（16:42 自主起）写 incident.md 时，RCA 只搬运了「3 断点 + 双轨 + 失败硬停」这条**送达主线**，把「CC 在 error 重放时 strip image」这条**异常重放支线**漏在了对话里没沉淀；
- `change-design-author` 读的是 incident.md（已无此洞见）+ 源码，自然产不出 replay-strip 决策；
- 决策4 引入持久化时，**没人回头问**「持久化 image turn 后，失败重放的不变量是什么」。

### 这一步本该怎样

1. **spec-author**：RCA 写参考实现时，不止抄「正常路径怎么做」，必须同时抄**参考实现的异常/重放路径**。本例 incident.md 的「对照 CC」段只写了 content-blocks 送达模型，应强制追问并落一句：「CC 在 turn 于 provider 报错后重放时如何处理该 turn 的 image？」——答案 10:52 已有，落进去即可。可固化为 spec grounding checklist 一条：**「参考实现的 happy-path 抄了，error-path / replay-path 抄了吗」**。
2. **design-author**：任何「新增持久化字段 / 让某内容首次进历史并重放」的决策（本例决策4），必须配一条**重放不变量审查**：「这条内容若在某轮 provider 报错，下一轮重放会怎样？参考实现怎么防？」决策4 当时只审了「纯文本 golden 不漂移」，漏了「失败 image turn 重放」。
3. **design-reviewer**：进攻清单加一角度——**「本 design 让什么内容首次持久化/重放？这些内容的失败态重放有没有被任一决策覆盖？」** 这是「该存在的没存在」的反向检查，能在写出来的东西之外发现缺失的机制（本例三轮 review 全缺这一问）。

---

## P1 — 损坏图入站校验只取 magic-bytes，被「合法头 + 损坏体」骗过

### 用户反馈 / 症状

reviewer round1 Issue #1（major）：41 字节损坏 PNG（前 8 字节合法 magic + 损坏体）未被 gateway 入站拦截，被转 base64 发给 Anthropic，返回 `⚠️ 模型调用失败:anthropic: stream ended without terminal event`，而非 design 决策5 固化文案「这张图片我无法识别…」。

### 一手证据

- design.md 决策5/接口段对校验深度的措辞是松的：「图片的下载、大小校验、**解析**…在 gateway 入站完成」「解析失败（格式不支持/数据损坏）→corrupt」，但**没钉死「解析」要到什么深度**。
- progress.md R3：worker 实现 `_detect_image_mime` = 「PNG/JPEG/GIF/WEBP **magic bytes**，未知→corrupt」——只验头几个字节，合法头的损坏体直接过检。
- fix1 才补结构校验（PNG 验 IHDR 紧跟签名 + IEND、JPEG 验 EOI、GIF trailer、WEBP RIFF size），fix3 再修 PNG 最小长度 28→45。三次才把「损坏图判定」打磨到位。
- fix1 明确**不引 Pillow**（progress.md：本仓未声明该依赖，clean CI 缺失即红）——这约束本应在 design 决策5 就点明，worker 才不会先走弯路。

### 根因落点

design 欠规约 + worker 合理但不足的实现。Issue#1 与 P0 的 Issue#2 被 fix1 根因调查证为**同根**（损坏图过入站→submit→error→毒化），所以 P1 本质是 P0 毒化链的**入站触发口**；但「校验深度」是独立于「replay-strip」的第二个 design 欠规约点。

### 这一步本该怎样

design 决策5 应把「解析」具体化为可验收的判据：**「magic-bytes 不够——须做结构完整性校验（关键 chunk 存在性 / 文件尾标记），stdlib-only，禁止引入未声明依赖(Pillow)」**，并给最小长度等边界。worker 即可一次到位，省去 fix1+fix3 两轮打磨。

---

## P2 — orchestrator 收尾宣告「后台 agent 自然结束」，实际 15 个滞留 74 分钟

### 症状（审计挖出，有用户动作佐证）

主 session 04:54:06 orchestrator 原话：
> 「bugfix-433 已全部收尾…后台 worker/reviewer/verifier 任务完成后**会自然结束,不需要我显式回收**。无进一步动作。」

06:08:26 用户侧：「**15 background agents were stopped by the user**: "请使用 skill: change-impl-worker…", "…change-verifier…", "…change-reviewer…", "你是 code review 的 finder…"」。即原 M1 worker、verifier、reviewer、7 个 code-review finder 等 **15 个 in-process teammate 在 orchestrator 退出后仍滞留 idle**（04:38 worker 已发 `idle_notification`），直到用户手动停。

### 一手证据

- meta.json：`"taskKind":"in_process_teammate"`，这些是进程内常驻 teammate，不是发完即焚的一次性 Task——**不会自然消失**，需显式 stop。
- orchestrator 在 04:54 明确判断「不需要我显式回收」，与 in_process_teammate 的生命周期事实相悖。

### 这一步本该怎样

`change-orchestrator` §7.5 退出步骤应**显式 TaskStop / 回收所有派发过的 in-process teammate**（worker、verifier、reviewer、code-review finders），再宣告退出。判据：退出前 teammate 列表清零。这是 0 交互自主模式下尤其重要——没有用户兜底，滞留 agent 会一直占资源。

---

## P3 — design.md Changelog 空白，修订追溯散落

### 证据

design.md line 6-7：`## Changelog` 标题下**空白**。但本 unit design 经 3 轮 review 修订（design-review.md 闭环记录详列：round1 2 CRITICAL+1 WARNING、round2 1 CRITICAL+1 WARNING、round3 复核）。修订**有记**，但记在 design-review.md，design.md 自身的 Changelog 没维护。

### 根因落点 + 本该怎样

`change-design-author` / `change-design-reviewer` 收尾应把每轮 review 的实质修订**回写 design.md `## Changelog`**（每条：改了什么决策 + 为什么）。本例修订追溯完整度其实不差（design-review 闭环 + progress 都很详尽），属轻度卫生问题，但 Changelog 是 design 文档的标准字段，空着违背模板。

---

## 综述：对齐 design 后能托管给 agent 吗？——能，前提是 design 没漏机制

### A. 唯一的实质失效是一个「第 1 小时掌握、spec→design 边界蒸发」的机制缺失（P0，牵出 P1）

本 unit 最有说服力的数据点：**实现忠实度极高**（verifier 全绿、5 决策全遵守），**design 经 3 轮独立 review approved**，可产品仍 fail 两轮。原因不是 agent 不行、也不是实现走样，而是 **design 本身缺了一块——而这块在立项第 1 小时(10:52)就被亲读 CC 写得明明白白**。证明：
- 「对齐对的 design → 托管 agent 实现」这条链是**可靠的**（verifier + 实现忠实度背书）；
- 真正的脆弱点在**上游**：洞见从 `Explore`/RCA 回到主线后，没被 spec-author 沉进 incident.md，design 就再也看不见它。**0 交互自主放大了这个风险**——没有人在 design 评审时凭直觉问一句「图片失败重放会怎样」。

### B. design-review 的盲区：只审「写出来的对不对」，不审「该写的写了没」

3 轮 design-review 把写出来的部分审得很细（is_provider_error 数据流、M246、delta-spec 归属、is_provider_error 是否残留），却没有任何一角度做**缺失检测**：「这个 design 新持久化/重放了什么内容？它们的失败态有没有被覆盖？」缺失的机制天然在「逐条对照写出来的内容」的视野外。

### C. 收尾纪律：自主模式必须显式回收 in-process teammate（P2）

orchestrator 凭「会自然结束」的错误假设留下 15 个滞留 agent。0 交互下无用户兜底，收尾回收必须是硬步骤。

### 一句话

> **这次唯一值得改的，是让「参考实现的异常/重放路径」和「本 design 新增的持久化/重放内容的失败态」在 spec→design 阶段被强制问一遍**——做到这两件，10:52 就有的解法不会蒸发，三轮级联会塌成一轮。其余（实现、验收、worker 复用）都健康。

**两个最高杠杆改动**：① spec/design grounding checklist 各加一条「参考实现 error-path/replay-path 抄了吗 + 本 design 新持久化内容失败态覆盖了吗」（治 P0+P1 根，收益最大）；② design-reviewer 加「缺失机制」反向角度（在写出来的之外兜住 P0 类盲区）。

---

## 附：按 skill 的改进清单

> 每条标来源 P。尊重用户约束：0 交互自主（不引入「该叫人」类改法）。

### change-spec-author（来源 P0、P1）
1. RCA 写「对照参考实现」时，**happy-path 与 error-path/replay-path 都要抄**。固化 grounding checklist 一条：「参考实现的正常路径抄了；它的**异常 / 失败重放路径**抄了吗？」——本例 10:52 已写出 CC strip-on-error，却没进 incident.md。
2. 把「解析/校验」类要求**具体到可验收判据**（如「magic-bytes 不够，须结构完整性校验；stdlib-only 禁引未声明依赖」），别留「解析失败→corrupt」这种深度未定的措辞给 worker 自由发挥（省 fix1+fix3）。

### change-design-author（来源 P0、P3）
1. 任何「新增持久化字段 / 让某内容首次进历史并重放」的决策，**必须配一条重放不变量**：「这条内容若某轮 provider 报错，下一轮重放会怎样？参考实现如何防？」——决策4 当时只审「纯文本 golden 不漂移」，漏了「失败 image turn 重放毒化」。
2. 收尾把每轮 review 实质修订**回写 design.md `## Changelog`**（本例空白）。

### change-design-reviewer（来源 P0）
1. 进攻清单加**「缺失机制」反向角度**：「本 design 让什么内容首次持久化 / 重放？这些内容的**失败态重放**有没有被任一决策覆盖？仓库有无同类已知账（如 #82 毒化类）可连？」——三轮 review 全缺这一问。

### change-orchestrator（来源 P2）
1. §7.5 退出前**显式回收所有派发过的 in-process teammate**（worker / verifier / reviewer / code-review finders 全部 TaskStop），判据「teammate 列表清零」再宣告退出。删除「任务完成会自然结束、不需显式回收」的错误假设（in_process_teammate 不会自然消失）。

### change-impl-worker（无新增）
- 实现忠实度本 unit 是正面样本（verifier 全绿）。worker 复用（793 轮跨 4 个 fix 周期保上下文）是良性，无需改。

### change-reviewer / change-verifier（来源 P0，正面）
- reviewer round1 真栈跑出 Issue#1/#2、fix1 live 又抓出非-vision 毒化——**验收链是有效的**，是它把 design 盲区逼了出来。无需改；唯一注记：design 盲区不该靠验收兜底，应在 P0 改动后于上游消除。

### 跨 skill（结构性）
- **spec→design 知识传递**是本 unit 唯一结构性裂缝：`Explore`/RCA 阶段的洞见若不进 incident.md，design 就丢失它。除上面 checklist 外，可考虑 spec-author 收尾自检「本次 RCA 在对话里出现过、但没进 incident.md 的关键技术结论有哪些」，强制回收。
