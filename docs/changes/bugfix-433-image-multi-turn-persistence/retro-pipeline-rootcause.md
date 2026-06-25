# bugfix-433 全链路根因复盘

> 视角：把 SDD 全链路(spec → design → orchestrate → impl → review → verify)当审计对象，从用户每条反馈和日志倒推到真正引入问题的那个节点。
> 方法：每条结论用一手证据核实(session/subagent jsonl + 沉淀文档 + 代码)，不采信二手总结。
> 被复盘 session：`d9458ef5`（2026-06-24 10:30 → 06-25 06:08）。作者：审计 agent(独立于本 unit 实施链)。

## 0. 用户的核心期望 vs 实际

用户在一次 `/stop` 修复的 PR review 中顺手发现「下一轮图片没了」，确认是 bug，授权 **0 交互自主**走完 spec→design→orchestrator 把它修掉并提 PR。实际：unit **确实完成**（PR #148、CI 全绿、04:53 orchestrator 退出），但中途吃了 **3 轮 review/fix 级联**，其中**两轮是同一个 design 盲区**——而这个盲区的解法（CC 的 `normalizeMessagesForAPI` error-replay-strip）**早在立项第 1 小时(10:52)就被亲读 CC 源码后准确写出来了，却没进 incident.md、没进 design**。外加收尾时 **15 个后台 agent 没被回收**，用户 74 分钟后手动停掉。

一句话：这不是灾难，是一次「本可一轮过、实际三轮过」的 unit——多出的两轮全因一个**第 1 小时就掌握、却在 spec→design 边界丢失的关键机制**（P0）。围绕它还暴露了几个可机械根治的流程/机制硬伤：scope 决策靠 live 采样而非查证模型能力（P4）、verifier 报告三轮卡 detached worktree 没上 origin（P5）、入站校验欠规约 + design Changelog 空白（P1/P3）。（**P2「收尾留 15 个滞留 agent」已撤回**——见下文，那是 skill #14 有意保留 teammate 供 PR 反馈复用，非缺陷。）

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
| ~~P2~~ | 用户 06:08 手停 15 agent | orchestrator 宣告「后台 agent 会自然结束」，实际滞留 74 分钟 | **已撤回**：留 teammate 是 skill #14 有意为之（供 PR 反馈复用）；§7.5 只要求 sweep 服务 PID（已做）+ worktree remove，不要求 TaskStop teammate | ~~orchestrator 收尾~~ → 非缺陷（至多 harness 层是否自动回收 idle teammate） |
| P3 | 审计挖出（无对应反馈） | design.md `## Changelog` 空白，多轮修订无耐久追溯 | design 修订记在 design-review.md 闭环记录，design.md 自身 Changelog 未维护 | design 文档卫生 |
| P4 | scope B 04:01–04:23 拍B→撤B→保留B 三次翻转 | 一个决策事实（模型支不支持图片）靠 worker 单次 live 观察反复拍板，40 分钟拉锯 + 最终 inconclusive | orchestrator 把「查文档就能定死的外部能力事实」当「在真栈跑跑看的行为」，从不 WebSearch 核 | orchestrator 决策依据 |
| P5 | 审计挖出（lead 事后提出） | verifier 三轮报告全卡在 detached worktree 没上 origin，lead 手动捡回三次 | change-verifier §1 detached 签出 + §5.2 按本地分支名 push，commit 落点≠push 目标，且无落地校验 | change-verifier skill 机制 |

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

## ~~P2 — orchestrator 收尾未回收 15 个 in-process teammate~~ —— 已撤回

> **早期版本曾认为**：orchestrator 收尾未显式 TaskStop 15 个 teammate 是失误。**经核 change-orchestrator skill 证伪，已撤回。** 撤回理由如下，留作「未读 skill 就下判断」的反面记录。

### 当初的症状观察（事实仍成立）

主 session 04:54:06 orchestrator 原话「后台 worker/reviewer/verifier **会自然结束,不需要我显式回收**」；06:08:26 用户手停 **15 个 background agents**（M1 worker / verifier / reviewer / 7 个 code-review finder 等），它们 04:38 起 idle 滞留 74 分钟。这些观察没错——错的是把它归成 orchestrator 缺陷。

### 为什么撤回（读 skill 后）

1. **§7.5 退出段不要求回收 teammate**。它只做三件事：打印 PR URL、kill **服务 PID**（`.im.pid/.gateway.pid/.vite.pid/.coding-cli.pid`）、`git worktree remove`。orchestrator 04:52「pid sweep done」+ worktree 清理**全做了**，§7.5 照做无遗漏。
2. **「PID sweep」≠「teammate 回收」**，我当初混为一谈。§0.16/§7.5 的 sweep 治的是 reviewer/worker 起的**真栈服务进程**（uvicorn 等崩溃残留），不是 in-process teammate agent。
3. **留 teammate 是 skill 硬规则 #14 有意为之**：给每个子 agent 稳定 `name`，正是为了「失败循环 / Fast-lane 复验 / **PR 反馈处理（§6.FL / §7.5）**用 SendMessage 唤醒续跑，保上下文」。PR 还没 merge，把 worker 留着可寻址、等 PR review 回来复用，**恰是设计意图**，不是没回收。

### 残留的真问题（降级，且不在 change-orchestrator）

唯一站得住的小尾巴：orchestrator「会自然结束」措辞不准（teammate 实际 idle 到被用户手停，并非自然结束）。但「长期 idle 的 in-process teammate 该不该被自动回收」是 **harness/平台层**问题，按 change-orchestrator skill，PR 未 merge 前留着是对的。**不构成 skill 缺陷，从改进清单移除。**

---

## P3 — design.md Changelog 空白，修订追溯散落

### 证据

design.md line 6-7：`## Changelog` 标题下**空白**。但本 unit design 经 3 轮 review 修订（design-review.md 闭环记录详列：round1 2 CRITICAL+1 WARNING、round2 1 CRITICAL+1 WARNING、round3 复核）。修订**有记**，但记在 design-review.md，design.md 自身的 Changelog 没维护。

### 根因落点 + 本该怎样

`change-design-author` / `change-design-reviewer` 收尾应把每轮 review 的实质修订**回写 design.md `## Changelog`**（每条：改了什么决策 + 为什么）。本例修订追溯完整度其实不差（design-review 闭环 + progress 都很详尽），属轻度卫生问题，但 Changelog 是 design 文档的标准字段，空着违背模板。

---

## P4 — scope B 三次翻转：一个「查文档就能定死的事实」被靠 live 采样反复拍板

> P4 是 P0 在 orchestrator 阶段的下游：正因 strip 机制不在 design（P0），它以「scope 决策」形式临场冒出来，逼 leader 在一个未核实的前提上拍板。这段 worker↔leader 对话质量很高（双方都按证据更新立场），但拉锯本身可避免。

### 经过还原（SendMessage 原文，04:01–04:27）

1. **03:46 worker 中立上报，不擅扩**：fix1 损坏图闭合后，真栈发现更广面（合法图发 K2.6→provider error→会话毒化），定性「非本 unit 引入的既有面」，列 A（留 issue）/B（做 strip）请 leader 拍板。
2. **03:48 leader 拍 B（限 image）**，前提：「本仓 default K2.6 是非 vision，用户给非 vision agent 发图很常见」。
3. **04:01→04:07 worker 自纠前提 → leader 撤 B**：worker 澄清「K2.6 其实支持 vision（live 答对红蓝），那次报错是 provider 瞬时 stream error」；leader 据此「收回 B……给图片单独贴 strip 是 bandaid，不如 #147 统一根治」。
4. **04:17 worker 带新证据自主做了 B**：用 **doubao-seed code（本仓真有的「非 vision」模型）** live 证「确定性毒化」，并亲读 CC `normalizeMessagesForAPI errorToBlockTypes` 证其本就 image-specific。
5. **04:21 leader 第一次 keep**；**04:21:42 worker 第二次坚持 scope 纪律、建议 revert**（按 §0.8「无对应 reviewer 缺陷该是 issue」）。
6. **04:23 leader 用 worker 自己挖的 CC 事实逐条反驳、最终留 B**；04:27 worker 服（「你用我自己挖的 CC 事实纠了我」）。

### 一手证据：拉锯全卡在一个没人去查的事实

三方都在**用 live 采样反推「模型支不支持图片」**，这恰是最不可靠的方法：

- worker 04:17 称 doubao code「**确定性**毒化、每次发图必踩」，以此说服 leader 留 B。
- **reviewer 04:28 切同一个 doubao code 发图 → 答对颜色、零 error**（reviewer 原话：「有趣！非 vision 模型实际上也能正确回答图片颜色……可能这个模型版本其实支持视觉，**或者**代理层做了处理」）；切 gpt-5.5 同样答对。
- 即 **worker 的「确定性」证据，reviewer 用同一模型复现失败**。那次 doubao 报错几乎可定性为偶发 stream 抽风——正是 leader 04:07 撤 B 时说的「偶发」。
- reviewer 自己也没核清是「模型支持视觉」还是「proxy 处理」，只能标 **B1 inconclusive**。

而「doubao-seed code / gpt-5.5 是否支持图片输入」是**厂商文档里确定、一次 WebSearch 就能定死的外部事实**；本仓 `docs/可用LLM_API与联调说明.md` 只记端点、**无任何模型的 vision 能力**（已核）。orchestrator 手握 WebSearch 工具，全程没搜。

### 根因落点

**orchestrator 把「该查的事实」当「该跑的行为」。** scope B 整场争的不是「怎么修」（摘图，照抄 CC，没争议），是「这 bug 够不够常见、该不该现在修」——而「够不够常见」=「看不了图的模型常不常见」=一个能力事实。leader 作为决策人，把它锚在 worker 的**单次** live 观察上反复横跳，而不是用最可靠的 lookup 一锤定音。live 采样对能力事实天生不可靠：偶发错误会假阳、proxy 可能改写请求、纯色小图能蒙对。

### 这一步本该怎样

`change-orchestrator`：**做 scope / 严重性判断前，先分清依据是「行为」还是「事实」。** 模型能力、API 限额、协议字段、依赖是否声明这类**外部可查事实**，优先 WebSearch / 厂商文档 / 仓库 doc 核证，**不靠 worker 单次 live 观察拍板**。本例一句 `豆包 seed code 多模态 / doubao-seed vision support` 即可定死前提，40 分钟拉锯 + inconclusive 不会发生。

> 注：B 这个修复**方向对、代码对、对齐 CC、单测能守**——保留 B 没错。错的是支撑「确定性、必须现在修」的那块 live 证据从头到尾没在真环境稳定成立过，inconclusive 暴露的正是「该用 lookup 确立的事实，用 sampling 反推了」。

---

## P5 — change-verifier 报告三轮卡在 detached worktree，全没上 origin

### 症状（lead 事后提出，审计坐实）

lead 原话：「verifier 报告三次卡 detached verify worktree 没 push，我手动捡回三次——change-verifier skill 的报告 push 机制有缺陷，值得修。」**诊断成立**，且可精确到命令。

### 一手证据

三轮 verifier（R1 03:19 / R2 04:12 / R3 04:29）每轮 §1 启动 + §5.2 提交推送，push 结果**全是 `Everything up-to-date`**——报告一行没上 origin：

| 轮 | §1 启动（无 -b） | §5.2 commit | §5.2 `git push origin unit/bugfix-433` |
|---|---|---|---|
| R1 | `worktree add … origin/unit/bugfix-433` | round 1（detached HEAD） | **Everything up-to-date** |
| R2 | 同上 | `bf2cd70` round 2 | **Everything up-to-date** |
| R3 | 同上 | `0eb6d24` round 3 | **Everything up-to-date** |

- `git branch -a --contains bf2cd70 / 0eb6d24` = 只在 `*`（detached HEAD），**不在任何分支**——orphan commit。
- unit 分支上的 verification.md 由 **lead 手提**：`11fe0cb3`（捡 R1）、`672ce867`（捡 R2+3，commit message 写明「捡回 verifier 报告，detached worktree 未 push」）。

### 根因落点：skill 自己的 §1 与 §5.2 互相打架

1. **§1 `git worktree add <dir> origin/unit/<id>`（无 `-b`）→ detached HEAD**：`origin/unit/<id>` 是远程跟踪 ref，签出即游离。报告 commit 落在游离 HEAD，不属任何分支。
2. **§5.2 `git push origin unit/<id>`**：推的是**本地分支 `unit/<id>`**（worktree 间共享 ref store，它还停在 orchestrator 上次位置），**不含**游离 HEAD 的 commit → git 判定已一致 → `Everything up-to-date`。**commit 落点（detached HEAD）≠ push 目标（本地 unit/<id>）。**
3. **`Everything up-to-date` 被当成功**：verifier 期望「pushed N commits」，没把 up-to-date 当红灯，照常回报 pass。这是缺陷三轮重复无人当场发现的直接原因。

> 为什么 §1 用 detached 而非 checkout 本地 `unit/<id>`：本地 `unit/<id>` 已被 orchestrator 的 unit worktree 占用，同一本地分支不能被两 worktree 同时 checkout。skill 用 detached 避开冲突，**但 §5.2 的 push 命令没跟着改**——没接上的设计缝。

### 对照 change-impl-worker 为什么稳（正面范式）

worker 同步代码三轮零失手，纪律是：**永远在有名字的真分支上 commit，push 的 ref 必须可证明包含该 commit。**
- §1 `worktree add **-b** "$branch" <dir> origin/unit/<id>`：`-b` 建真分支 `milestone/<id>` 并 checkout，commit 有家；
- 开工即 `git push -u origin <branch>`（中途保险，代码先落 origin）；
- §6.1 集成在**持有 `unit/<id>` 的 unit worktree** 内 `git merge --no-ff "$branch"` 再 `git push origin unit/<id>`——push 的分支是刚被 merge 推进、本 worktree 真正持有的，**可证明包含 commit**；配 `pull --ff-only` + unit 锁处理并发。

verifier 三条全违反：无 `-b`（detached）、无中途 push、push 的是不含 commit 的旧 ref。

### 这一步本该怎样（修法精确到命令）

verifier 是只读、无 unit worktree 可 merge，detached 只读签出**应保留**；要改的是 §5.2 的 push + 加落地校验：

```bash
cd "$verify_worktree_dir"
git add docs/changes/<unit_dir>/verification.md
git commit -m "docs(<id>): round <N> verification — verdict <…>"

git fetch origin unit/<id>
git rebase origin/unit/<id>          # 只 rebase 报告 commit，避并发非快进
git push origin HEAD:unit/<id>       # ← 推 HEAD（含报告 commit），不是本地 unit/<id>

# 抄 worker「push 后证明落地」精神，别信 up-to-date
git fetch origin unit/<id>
git merge-base --is-ancestor HEAD origin/unit/<id> \
  && echo "✓ 报告已上 origin" || { echo "✗ 未落 origin"; exit 1; }
```

两处要点：① `HEAD:unit/<id>` = worker「推可证明含 commit 的 ref」原则在「无分支只读」场景的等价写法（光加 `-b` 不改 push 行仍会推错 ref，无用）；② **push 后 `merge-base --is-ancestor` 强校验** = worker 靠 merge 天然保证 containment，verifier 没 merge 就得显式断言，把「up-to-date 当成功」的静默陷阱炸出来。

> 关联面（值得顺手查）：change-reviewer 同样自建 `origin/unit/<id>` worktree 推报告，但本 session 它的 regression 报告 push **成功了**（04:31 `a3a48e3f..6af1f2fa` 真上 origin）。说明两 skill 推送范式不一致、reviewer 那套是对的——verifier 应对齐它/上面修法。

---

## 综述：对齐 design 后能托管给 agent 吗？——能，前提是 design 没漏机制

### A. 唯一的实质失效是一个「第 1 小时掌握、spec→design 边界蒸发」的机制缺失（P0，牵出 P1）

本 unit 最有说服力的数据点：**实现忠实度极高**（verifier 全绿、5 决策全遵守），**design 经 3 轮独立 review approved**，可产品仍 fail 两轮。原因不是 agent 不行、也不是实现走样，而是 **design 本身缺了一块——而这块在立项第 1 小时(10:52)就被亲读 CC 写得明明白白**。证明：
- 「对齐对的 design → 托管 agent 实现」这条链是**可靠的**（verifier + 实现忠实度背书）；
- 真正的脆弱点在**上游**：洞见从 `Explore`/RCA 回到主线后，没被 spec-author 沉进 incident.md，design 就再也看不见它。**0 交互自主放大了这个风险**——没有人在 design 评审时凭直觉问一句「图片失败重放会怎样」。

### B. design-review 的盲区：只审「写出来的对不对」，不审「该写的写了没」

3 轮 design-review 把写出来的部分审得很细（is_provider_error 数据流、M246、delta-spec 归属、is_provider_error 是否残留），却没有任何一角度做**缺失检测**：「这个 design 新持久化/重放了什么内容？它们的失败态有没有被覆盖？」缺失的机制天然在「逐条对照写出来的内容」的视野外。

### C. 决策依据：该「查」的事实，被用「跑」来反推（P4）

scope B 40 分钟拉锯 + inconclusive，根子是 orchestrator 把「模型支不支持图片」这个**外部可查事实**当成「在真栈跑跑看的行为」，靠 worker 单次 live 观察反复拍板。可泛化反模式：**做判断前先分清依据是「行为」（该跑）还是「事实」（该查）**——能力 / 限额 / 协议 / 依赖声明这类查文档/搜索一锤定音，别靠 live 采样（偶发错误假阳、proxy 改写请求、小图能蒙）。这条与 P0 同源——正因机制漏在 design（P0），它才以 scope 决策形式临场冒出来逼 leader 拍板。

### D. 机制纪律：verifier 报告 push 修复（P5）

一个真机制硬伤：change-verifier §1 detached 签出与 §5.2 按分支名 push 不匹配，报告三轮丢失靠 lead 手捡（P5）。不靠判断、靠改 skill 步骤即可根治；正解直接抄 change-impl-worker「在真分支 commit + 推可证明含该 commit 的 ref + push 后校验落地」的稳定范式。（原列此处的 P2「收尾留 teammate」已撤回——非缺陷，见上。）

### 一句话

> **这次唯一的实质失效（产品两轮 fail）是 P0：第 1 小时掌握的 strip 机制在 spec→design 边界蒸发。** 其余是可机械根治的流程/机制硬伤：P4（该查的事实没查）放大了 P0 的下游代价、P5 是 git 同步的步骤缺口、P1/P3 是 design 欠规约与文档卫生。实现忠实度、验收链、worker 复用、收尾回收——都健康（P2 撤回）。

**三个最高杠杆改动**：① spec/design grounding checklist 各加一条「参考实现 error-path/replay-path 抄了吗 + 本 design 新持久化内容失败态覆盖了吗」（治 P0+P1 根，收益最大）；② orchestrator 决策前分清「行为 vs 事实」、外部事实先查证（治 P4，最省力）；③ change-verifier push 抄 impl-worker 范式 + 落地校验（治 P5，一劳永逸）。

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

### change-orchestrator（来源 P4）
1. （P4）做 scope / 严重性判断前，**分清依据是「行为」还是「事实」**：模型能力、API 限额、协议字段、依赖是否声明等**外部可查事实**，优先 WebSearch / 厂商文档 / 仓库 doc 核证，**不靠 worker 单次 live 观察拍板**。本例一句 `doubao-seed vision support` 即可定死前提，免 40 分钟拉锯。

> （原列此处的 P2「§7.5 显式回收 teammate」已删——经核 §7.5 + 硬规则 #14，留 teammate 供 PR 反馈复用是设计意图，非缺陷。）

### change-impl-worker（无新增，作正面范式）
- 实现忠实度本 unit 是正面样本（verifier 全绿），worker 复用（793 轮跨 4 个 fix 周期保上下文）良性，无需改。
- 其 §1（`worktree add -b` 真分支）+ §6.1（持有 unit 分支的 worktree 内 merge 再 push + ff-only + 锁）是 **git 同步稳定范式**，被 P5 引为 change-verifier 的修复参照。

### change-verifier（来源 P5）
1. 修 §5.2 报告 push：detached 只读签出保留，但 commit 后改用 `git push origin HEAD:unit/<id>`（先 `fetch`+`rebase origin/unit/<id>`），**并 push 后 `git merge-base --is-ancestor HEAD origin/unit/<id>` 强校验落地**——别再把 `Everything up-to-date` 当成功。根因：§1 detached HEAD 与 §5.2 按本地分支名 push 不匹配，commit 落点≠push 目标（详见 P5）。
2. 对齐 change-reviewer 的报告推送范式（本 session reviewer push 成功、verifier 失败，两者应统一到「推可证明含 commit 的 ref + 校验落地」）。

### change-reviewer（来源 P0，正面）
- reviewer round1 真栈跑出 Issue#1/#2、fix1 live 又抓出非-vision 毒化——**验收链是有效的**，是它把 design 盲区逼了出来。无需改；唯一注记：design 盲区不该靠验收兜底，应在 P0 改动后于上游消除。
- P4 注记：reviewer B1 标 inconclusive 是**诚实的**（如实暴露「该用 lookup 确立的事实没法用 live 采样验」），非 reviewer 失误；根在 orchestrator 没先查证（见 P4）。

### 跨 skill（结构性）
- **spec→design 知识传递**是本 unit 唯一结构性裂缝：`Explore`/RCA 阶段的洞见若不进 incident.md，design 就丢失它。除上面 checklist 外，可考虑 spec-author 收尾自检「本次 RCA 在对话里出现过、但没进 incident.md 的关键技术结论有哪些」，强制回收。
