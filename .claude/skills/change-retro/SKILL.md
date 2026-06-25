---
name: change-retro
description: 对一个走 change-* SDD 流程的变更单元(feat/bugfix/refactor)做取证式开发复盘:从用户每条反馈和日志倒推到真正引入问题的节点(哪个 skill 阶段 / 哪个 agent),证据落到 session/subagent jsonl 与沉淀文档,产出按 skill 的改进清单。用户说"复盘 feat-X / 这次开发哪里出了问题 / feat-X 为什么拖这么久、这么多反复 / 这次 SDD 开发是个灾难帮我深挖根因"等回看已发生开发、找根因的信号时触发。
---

# Change Retro — 取证式 SDD 开发复盘

回答一个问题:**这次开发为什么不顺(慢 / 反复 / 做错 / 处处是问题),根因到底在哪一步?**

被复盘的是一个走 change-* SDD 流程(spec-author → design-author → orchestrator → impl-worker →
reviewer / verifier)跑出来的变更单元。产物不是感想,是**一份带一手证据的事故调查报告**:从用户每条
反馈倒推到真正引入问题的那个节点,精确到"哪个 skill 的哪条流程缺口 / 哪个 agent 在哪一刻做了什么",
最后给出按-skill 的可执行改进清单。证据全在 session/subagent 的 jsonl、当时沉淀的文档、和代码里。

## 调查立场(这套复盘可信的根本)

这几条不是流程仪式,是"为什么这份复盘值得信"的来源。守不住,结论就不可信:

- **证据优先,绝不采信二手。** 每个结论落在一手证据上:jsonl、沉淀文档(spec/design/acceptance/
  verification/progress/design 的 Changelog)、代码 diff。被复盘对象自己写的 `retro.md`、worker 的
  DONE 报告、reviewer 的口径——全是**线索**,要拿 jsonl/代码核。当事人只看得见自己意识到的那层,且
  会美化/误判自己的根因(这次实战里,当事人 retro 把真根因归成了表层"非复用 worker",漏了更深的
  "假绿假 DONE 弹回")。
- **症状 → 根因节点,不准停在症状。** 用户反馈是症状("勾 cron 全灰""做了三天")。挖到一个根因要继续
  追"那它为什么会这样"再下一层,直到那个让症状成为必然的最早决策/动作(spec 错 → 为什么 spec 错 →
  因为读了现状坏代码当产品真值)。崩在表层、根在更下层是常态。
- **分层归因,别把锅笼统甩给"agent 不行"。** 判定每个问题属于哪一层:spec 没对齐需求 / design 没对齐
  现状或自造平行物 / 实现偏离 design / 验收只验符合性没验对错 / 编排没尽 leader 职责。**尤其分清
  "上游(spec·design)本身错了"还是"实现偏离了对的 design"**——这直接回答用户最关心的"对齐 design 后
  到底能不能托管给 agent"。
- **量化,别只叙述。** "worker 反复探索"要落成数字:worker 轮数峰值、自主空转小时、worker↔主 agent
  往返次数、派发包要求 vs 实际做了什么。量化能区分"问题真多"和"没真解决就报完成"。
- **协作 + 自我修正。** 逐个问题和用户过。**用户推翻你时,回去重挖 jsonl 核实,不嘴硬也不附和**;
  证据和旧判断冲突,在文档里**显式撤回**("早期版本曾认为 X,被证据 Y 证伪,已撤回")——这恰恰是可信度
  来源。**尊重用户已确立的约束边界**(例:用户说"我不要人工介入",就别把"该早点叫人"写成根因/改法)。
- **怀疑朝内:你自己的发现也是待核声明,复盘要证伪不只生成。** 上面几条都在教你怀疑被复盘对象;但一份
  只会"找问题"的复盘必然制造问题(实战:一次复盘 6 条发现 2 条假阳,全靠用户当场拦下)。所以**每写一条
  "这是缺陷 / 根因在 X",落盘前先证伪**:它会不会其实是 by-design(回去读对应 skill/spec 确认)?我引得出
  它违反的那条标尺原文吗?——**引不出条款 = 这不是缺陷,是你没读**(实战反例:把 orchestrator 有意保留
  teammate 供复用,当成"收尾漏回收"写进报告)。**砍 / 留发现时区分"例子专属"与"教训专属"**:去掉本 unit
  的具体名词后教训仍成立 → 通用(保留、写成通用语),只是例子恰好出自本 unit;别因例子专属就把通用教训
  一起砍了。

## 流程

### 1. 建标尺 + 摊证据
- 锚定 `unit_id` / unit_dir / PR;问清复盘范围(整单 / 某阶段 / 某个具体反馈)。
- **读 `.claude/skills/change-*/SKILL.md`**——建立"这套流程每步本该怎样"的标尺。没标尺就看不出实际哪里偏
  (不知道 impl-worker 要求"真实入口验证",就发现不了 worker 用 stub 顶替算违规)。
- 定位 session(主 + subagent)和沉淀文档:

```bash
S=.claude/skills/change-retro/scripts/mine_jsonl.py
PROJ=~/.claude/projects/<proj-slug>                 # cwd 路径转 -Users-... 的那个目录
python3 $S sessions "$PROJ" <unit_id>               # 哪些主 session 涉及该 unit(按命中排)
git show origin/unit/<unit_id>:docs/changes/<unit_dir>/design.md     # 尤其 ## Changelog 段——金矿
git ls-tree -r --name-only origin/unit/<unit_id> | grep <unit_dir>  # 列全部 M*/acceptance/verification
```

> 沉淀文档一定从 **unit 集成分支**读(主仓 main 常看不到 fix 轮 M3-M13)。`design.md` 的 `## Changelog`
> 往往逐条记了每次 post-acceptance 决策修订与真根因,比任何 retro.md 详尽。

### 2. 先建时间线 + jsonl 索引(写任何问题之前)
这是后续定位的地基,也是用户复用你成果的入口。

```bash
python3 $S humans    <session>.jsonl ...    # 人类真输入时间线(已滤 teammate/task/idle 噪声)
python3 $S subagents <session_dir>          # 每个 subagent: 角色/起止/时长/assistant 轮数峰值
```

产出两张表(见 `references/output-template.md`):主 session 表 + 阶段时间线(`阶段 → 时间区间 →
session → subagent agentType`)。阶段边界:`humans` 里的 `/change-*` 命令时间戳是天然分界。

### 3. 抽问题(两个来源)
- **用户反馈**:`humans` 时间线里每条抱怨/纠错/质疑都是入口,留原话 + 时间戳。
- **自主异常**(用户没反馈也存在,最隐蔽):`python3 $S churn <session>.jsonl`——找"没人干扰也连续空转"
  的段;末尾闲置小(2-5min)= 用户撞见它正在跑 = 真空转,是问题,也要列。

### 4. 逐问题深挖(核心)
每个问题四段(模板见 references),**一个一个来,别赶**:
1. **症状**:原话 + 时间戳(自主异常类写"从日志挖,无对应反馈")。
2. **一手证据**:贴具体的——哪条 transcript 引文、哪行代码、哪个 commit、哪个数字。区分一手 vs 推断。
3. **根因落点**:落到具体 skill 的具体条款 / 某次 agent 动作;分清哪一层失效(见调查立场第 3 条)。
4. **本该怎样**:可执行改法,尊重用户约束。

取证时用下面的"追问反射"把表面声明戳穿到根因。

### 5. 综述 + 按 skill 改进清单
把散落根因归并成几个结构性主题,直接回答用户的核心困惑;然后对每个 change-* skill 列该改哪几条,
**每条标来源问题编号**。这是最终交付物——用户拿它去改 skill。

### 6. 落盘
写进 `docs/changes/<unit_dir>/` 下一个新 md(如 `retro-pipeline-rootcause.md`),结构照
`references/output-template.md`。按用户指示 commit/push 到 PR 分支(commit 格式见 AGENTS.md,别擅自合并)。
不覆盖已有 retro.md;必要时在文中指出当事人 retro 的盲区/误判并给 jsonl 证据。

## 追问反射:把表面声明戳穿到根因

复盘的核心动作不是过清单,是**顺着这一次的实际线索挖这一次的实际问题**。但有一个可泛化的反射贯穿始终:

> **trail 里每一个听起来确定的声明,都是待核线索,不是事实。** "DONE""全绿""pass""已修""blocked,
> 需更底层支持""race""这部分接受"——agent(和当事人 retro)会用这些把问题盖过去。你的工作就是对**当下
> 线索指向的那个声明**追问"它背后到底是什么",拿 jsonl/代码/真环境证据核到底。根因几乎总藏在某个被
> 当成事实接受了的声明背后。

**这把怀疑同样朝内——你自己写下的每条结论也是待核声明,落盘前过同一道闸:**

- **二手包括 transcript 内部的事后 characterization。** 不只 retro.md / DONE 报告:leader、同侪在对话里
  对某个原始动作的转述定性("proxy 都能处理""那是偶发 race""已修复")同样是二手口径。**结论不能停在
  summary 上——去读它转述的那个原始动作**(实际命令 / 结果 / 代码)。收口前问自己:这结论我是读了原始动作
  得出的,还是停在某条 summary 上?停在 summary = 没核完,回去挖原文。(实战反例:停在 leader"proxy 都能
  处理"上,推出"模型默默忽略图片",没去读 reviewer 实测"切模型发图、答对颜色"的原始动作——结论反了。)
- **一手 vs 推断,且禁"推断伪装成事实"。** 报告与汇报对话里每个陈述句二选一:一手(带引文 / 代码 / 日志行)
  或**显式标注的推断**。没有第三类——读着像事实、实则脑补的。

怎么挖,由这次的线索决定——哪条用户反馈最痛、哪个阶段最反常、哪个数字最离谱,就往哪挖,一层层往下
追"那它为什么会这样",直到触到最早那个决策/动作。**不要拿下面的范例当必查清单逐条扫**:这次的真根因
很可能是个没列在下面的新模式;而下面某条若这次线索没指向它,就别硬套。

### 范例库(来自一次 feat-394 复盘——示意"追问长什么样",非清单)

这些是过去把表层戳穿到根因的真实追问,帮你认得出同类苗头。**当这次线索指向某条时**它可能有用:

- **"DONE" → 真做完没?** 读 subagent 收尾:跑了真实入口/真环境端到端,还是只 pytest/stub 就报 DONE?
  DONE 报告有没有**吞掉**自己撞的阻塞(env 坏了却不说)?(`dispatches` 看派发要求 vs 实际做了什么。)
- **"reviewer 才发现下一层" → worker 自己跑没跑到?** 真在通环境跑,当场就撞下一层崩点,轮不到 reviewer。
  所以这往往反证 worker 没真跑到那步(降级/没跑),而不是"串行链固有要多轮"。
- **"全绿" → 测的是真链路还是桩?** 跨进程 bug 多在集成缝,单测天然 mock 掉缝。stub 还会孵化错误根因:
  把确定性 bug 误判成"race/时序/需底层支持"——这类结论高度可疑,多半是"没真环境复现过"的遮羞布。
- **"pass" → 验的是符合还是对错?** reviewer/verifier 拿 spec/design 当真值,spec 错时越严谨越是给错东西
  盖章;reviewer 即使真机测,观察也常被"逐条对 Scenario"锁死,看不见同屏的明显副作用。
- **verifier 判"一致" → 对 design 一致还是对代码仓架构一致?** design 本身是不一致源头时(自造平行机制/
  破坏依赖方向),核"实现 vs design"会放行;看它有没有独立审"跟既有架构自洽"。
- **orchestrator 做了诊断 → 主动的还是被逼的?** 看它遇到反复失败是主动停下来诊断 systemic 根因/换打法/
  留 worker 在线协作,还是麻木"派→验→再派"、直到撞轮次 cap 或被用户质问才回头。
- **数字异常 → 背后是什么?** `subagents` 轮数失控(单 worker 上千轮)、`churn` 长时间自主空转、`dialogue`
  ≈2 的近一次性,都是"哪里值得读"的指针,不是结论本身——顺着去读原文。

## 取证工具 mine_jsonl.py

`scripts/mine_jsonl.py`,把反复要做的提取固化成子命令(脚本是起点:它告诉你"哪里值得读",证据来自
打开原文读):

| 想知道 | 命令 |
|---|---|
| 哪些 session 涉及这个 unit | `sessions <proj> <unit_id>` |
| 谁在什么时候说了什么(人类真输入) | `humans <s>.jsonl ...` |
| 每个 worker 干了多久/多少轮(失控信号) | `subagents <session_dir>` |
| 没人干扰时自己空转多久 | `churn <s>.jsonl [min_gap_min]` |
| 派发包到底要求了 worker 什么 | `dispatches <s>.jsonl` |
| worker 和主 agent 有没有真对话 | `dialogue <session_dir>` |
| worker 收尾真验了什么 / 是否吞阻塞 | 直接读 `<session_dir>/subagents/agent-*.jsonl` 尾部 |
| 每轮验收实际验了/判了什么 | 读 unit 分支 `acceptance.md` / `verification.md` 逐轮段 |
| 每次 design 修订的真根因 | 读 unit 分支 `design.md` 的 `## Changelog` |

`<session_dir>` = 去掉 `.jsonl` 的同名目录(`subagents/` 在其下)。
