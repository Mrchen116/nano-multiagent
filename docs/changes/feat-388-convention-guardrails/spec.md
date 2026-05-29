# feat-388: 把项目规范固化为机器执行的硬约束

## Relations

- Depends on: refactor-387
- Refs: #40

## 原始需求

> /Users/czj/Repos/nano-multiagent/.worktrees/refactor-387-M1/SPEC.md 我想保证后续写代码能只import `agent.sdk` 不打开内部，有什么方法能做到吗，lint？

> ruff还能干嘛，我现在用agent做编码，我想把规范固化下来而不是用文字软约束agent

Agent 解读：种子需求是"产品包只能 import `agent.sdk`、不许穿透内核内部"的边界守护；第二句把诉求拓宽为通用目标——把现在散落在 AGENTS.md / COMMENTING_GUIDE.md 里靠"请遵守"的文字软约束，固化成机器强制执行的硬约束，因为执行主体是编码 agent，散文规范它可能不遵守。

## 澄清记录

- Q1: 范围是只做 sdk import 边界,还是当成"把规范固化为硬约束"的第一块、本期搭通用执行底座 + 首批规则?
  A(原话): 对，是这个意思
  Agent 解读: 做通用规范执行底座 + 首批规则,sdk 边界是首批规则之一。

- Q2: 硬约束在哪个时刻拦人/agent?(a) 编码 agent Edit/Write 后当场检查并回喂 (b) git commit 时拦 (c) PR/CI 时拦。
  A(原话): Q2:a, c
  Agent 解读: 本期核心 = (a) 编码 agent 写完文件当场检查并回喂 + (c) 远端 CI 兜底防绕过;(b) 不纳入。

- Q3/Q4: 首批纳入哪些规则?(给出 R1-R5 + B 组候选,各贴文档原文)R4 是否按"只在公开面强制 docstring"纳入?
  A(原话): 这种复杂的先不搞
  Agent 解读: R4(public API docstring 强制)押后——需按公开面 scoped、会大面积误伤存量,属"复杂",不纳入首批。

- Q5: 首批锁定 R1(产品只能 import agent.sdk)+ R2(四顶层包横向零互相 import)+ R3(core 不依赖 platform/products)+ B-1(统一 formatter)+ B-2(通用 correctness),R5(TODO/FIXME 精确格式)与 R4 一起押后?
  A(原话): 好，就这几个

- Q6: 上线时仓里现有代码若已违规怎么办?(i) 零容忍,门绿前全修掉、不留 baseline/xfail (ii) baseline 豁免,只拦新增。
  A(原话): 存量要本unit修了
  Agent 解读: 采纳 (i) 零容忍——本 unit 内修掉全部存量违规,不留 baseline/xfail;R3 已知的 #40(core→platform 反向依赖)修绿挂靠 refactor-387。

## 用户场景

这里的"用户"是**在本仓写代码的开发者,以及承担编码的 agent**。可观察面:运行检查得到红/绿、编辑文件后被回喂违规、提交/合并被拦或放行。

今天这些规范散落在 `AGENTS.md` / `COMMENTING_GUIDE.md` / `SPEC.md` 里,靠"请遵守"的文字生效。对人尚可,对编码 agent 是软约束——它可能读不到、读到也未必照做,违规要等人 review 才发现,甚至漏进主干。典型场景:agent 为图省事在 `personal_assistant` 里直接 `import agent.core.xxx` 穿透内核内部;或写出反向依赖 `core` import `platform`;或留下一堆未用 import、可变默认参数。这些都违反已写明的规范,却没有任何机器关口拦住。

本 feat 把其中**可机检的几条**从"文字软约束"升级为"机器硬约束",落在两个用户能直接感知的触点:

- **触点 (a) 编码循环内**:编码 agent 每写完一个 `.py` 文件,检查当场跑;可自动修的(格式、部分 correctness)被自动修好,agent 无需操心;不可自动修的违规(如反向 import、裸 `except`)被回喂给 agent,要求改正后才继续。约束的执行从"求 agent 自觉"变成"harness 强制 + 错误回灌",agent 绕不过去。
- **触点 (c) 远端兜底**:任何绕过编码循环的路径(人手改、别的机器、别的工具)推代码到远端时,CI 跑同一套检查,违规则红、阻止合并。

首批固化 5 条规则:产品包(`coding_cli` / `personal_assistant`)对内核只能走 `agent.sdk` 这一对外面、禁止穿透 `core`/`platform`/`products`(R1);四个顶层包之间横向零互相 import(R2);内核 `core` 不反向依赖 `platform`/`products`(R3);全仓统一 formatter、消除风格类口头约定(B-1);通用 correctness——未用 import/变量、可变默认参数、裸 `except`(B-2)。

本 unit 完成时,仓里现有代码必须**已全部满足**这 5 条(零容忍,不留 baseline / xfail 永久豁免);其中 `core` 现存的一处反向依赖 `platform`(#40)随 refactor-387 一起消除,R3 的检查才得以真正修绿。合法写法(产品 import `agent.sdk`、`core` 内部互 import 等)必须照常通过,不能误报——否则会逼人加 `noqa` 反而架空约束。

押后不做的:需要按"公开面"界定范围、且会大面积误伤存量的 public docstring 强制(R4);需要自定义检查的 TODO/FIXME 精确格式(R5);以及命名、注释"为什么 vs 做什么"等语义级规范——这些没有机器执行手段,继续靠 review。

## 验收标准

### Requirement: 产品包与内核之间只能走 agent.sdk 这一对外面(R1)

#### Scenario: 产品包穿透内核内部被拦(编码循环内)
- **WHEN** 编码 agent 在 `coding_cli` 或 `personal_assistant` 的文件里写入 `import agent.core`(或 `agent.platform` / `agent.products`)
- **THEN** 该编辑完成时,agent 当场收到这一违规
- **AND** 必须改正(改回 `agent.sdk` 或移除)后才能继续,违规代码进不了下一步

#### Scenario: 产品包穿透内核内部被拦(远端兜底)
- **GIVEN** 一处产品包穿透内核内部的 import 绕过了编码循环
- **WHEN** 该代码被推到远端 / 开 PR
- **THEN** CI 红,阻止合并

#### Scenario: 合法走 agent.sdk 不误报
- **WHEN** 产品包文件 `import agent.sdk`(或 `from agent.sdk import ...`)
- **THEN** 检查通过,不报任何违规

### Requirement: 四个顶层包之间横向零互相 import(R2)

#### Scenario: 顶层包横向互相 import 被拦
- **WHEN** 提交一处 `coding_cli` / `personal_assistant` / `IM` 之间的互相 import(例:`IM` 里 `import personal_assistant`)
- **THEN** 检查不通过(编码循环内当场回喂,远端 CI 红)

### Requirement: 内核 core 不反向依赖 platform / products(R3)

#### Scenario: core 反向 import 被拦
- **WHEN** 提交一处 `agent/core/**` 文件 `import agent.platform`(或 `agent.products`)
- **THEN** 检查不通过

#### Scenario: 现存反向依赖已消除
- **GIVEN** 本 unit 已完成、refactor-387 已落地
- **WHEN** 对 `agent/core/**` 全量跑该检查
- **THEN** 零违规(原 #40 的 `core.llm.factory → platform` 反向依赖不再存在),且检查处于真正生效状态(无 xfail / baseline 豁免)

### Requirement: 全仓统一代码格式(B-1)

#### Scenario: 格式不规范被自动规整
- **WHEN** 编码 agent 写出格式不符统一风格的 `.py` 代码
- **THEN** 该编辑完成后格式被自动规整,agent 无需手动处理风格

#### Scenario: 格式违规进不了远端
- **GIVEN** 一处格式不符的代码绕过了编码循环
- **WHEN** 推到远端 / 开 PR
- **THEN** CI 红,阻止合并

### Requirement: 通用 correctness 卫生(B-2)

#### Scenario: 可自动修的卫生问题被自动修
- **WHEN** 编码 agent 写出未用的 import 或未用局部变量
- **THEN** 该编辑完成后这些可自动修的问题被自动清除

#### Scenario: 不可自动修的卫生问题被回喂/拦截
- **WHEN** 编码 agent 写出可变默认参数(如 `def f(x=[])`)或裸 `except:`
- **THEN** 编码循环内当场收到违规并需改正;若绕过则远端 CI 红

### Requirement: 现有代码零违规上线(零容忍)

#### Scenario: 本 unit 完成后全仓干净
- **WHEN** 本 unit 完成后,对整个仓库现有代码跑这 5 条规则的检查
- **THEN** 零违规,且无任何 baseline / xfail 永久豁免残留

## 范围与非目标

- 在范围:
  - 首批 5 条规则:R1 产品包只能 import `agent.sdk`;R2 四顶层包横向零互相 import;R3 `core` 不依赖 `platform`/`products`;B-1 统一 formatter;B-2 通用 correctness(未用 import/变量、可变默认参、裸 `except`)
  - 两个执行触点:(a) 编码 agent Edit/Write 后当场检查、可自动修的自动修、其余回喂;(c) PR/CI 兜底
  - 存量违规在本 unit 内全部修掉(零容忍,含 #40 的 `core→platform` 反向依赖,挂靠 refactor-387)
  - 同步改写 `AGENTS.md` 中因 refactor-387 失效的 import 边界表述(产品现在要 import `agent.sdk`,旧文写的是"禁止 import agent")
- 非目标:
  - R4 public API docstring 强制(需按公开面 scoped、会误伤存量,押后)
  - R5 TODO/FIXME 精确格式校验(需自定义检查,押后)
  - 私有成员跨边界访问(`_foo`)等无文档背书的封装规则(先成文再固化)
  - 注释"为什么 vs 做什么"、命名、抽象合理性等语义级规范(无机器执行手段,仍靠 review)
  - git commit 本地拦截(触点 b)
  - 类型检查(mypy/pyright)、密钥扫描、覆盖率门等其它固化轴
