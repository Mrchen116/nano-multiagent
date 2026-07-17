# bugfix-468: 工具链语义三缺口（设置页假象 / executor 无兜底 / 校验报错无字段名）

## Relations

- Closes: #203
- Related: #201（根因 unit，bugfix-467 已修）、bugfix-467

## 原始报告

> 为什么agent配置页看到的并不是空，是有工具的

> H2 不接受别名。报错列出实际 required 字段名的具体方式，参考CC。

> 空 = 零工具没问题啊，问题是为什么空吧

GitHub issue：https://github.com/Mrchen116/nano-multiagent/issues/203 （含三个缺口的完整机制分析与真栈证据）

## 澄清记录

- Q1: 「空 allowlist = 零工具」语义是否保留？
  A(原话): 空 = 零工具没问题啊，问题是为什么空吧
  Agent 解读: 语义不动；要修的是各处对「空」的表达与防御不一致。

- Q2: edit validator 是否接受 CC 惯例别名（old_string/new_string）归一化？
  A(原话): H2 不接受别名。报错列出实际 required 字段名的具体方式，参考CC。
  Agent 解读: 不做别名兼容；报错按 CC 风格逐条列出字段名（缺/多/类型错分行），让模型能自我纠正。

- Q3: 对齐表 H1-H3 修复方向是否认可？
  A(原话): 好这个不错。现在所有问题都大致明确思路了。
  Agent 解读: 用户认可三缺口的修复方向：detail 页按存储值渲染（显式空可表达）、executor 兜底拦截、validator 报错列字段名。

## 现象与复现

三个独立缺口，同一事故现场（#201 零工具声明会话）暴露：

**缺口 1 — 设置 detail 页工具勾选是假的（UI/runtime 语义脱钩）**
agent 的存储 tool_allowlist 为空时，设置 detail 页按 capabilities `default_on` 渲染成「默认工具全开」；而 runtime（PR #195 后）语义是「空=零工具」。页面显示 11 个工具全亮，实际会话一个工具都没有。用户「显式清空所有工具」也无法表达：清空保存后刷新，页面又回弹成默认全开。skills 无此约定（skill 的 default_on 基本为 false），故 skills 显示全不亮——tools/skills 两个面板给出两个方向的假象。复现：任一 agent 打开 `/settings/agents/<id>`，其存储 allowlist 为空时工具面板必现。

**缺口 2 — 显式零工具会话 executor 无兜底拦截**
PA 会话路径从不传 `tool_execution_allowlist`（默认 None=全放行）。会话零工具声明（无论显式配置还是被 #201 抹空）时，模型按训练惯例自由发挥的工具调用（read/edit/bash...）executor 按名字照常执行——advertisement 是唯一的 allowlist 执行手段，执行层没有对应 enforcement。复现：#201 现场会话 31 个请求 tools=0，模型自由调 read 成功、调 edit 因参数名惯例不匹配失败——两类调用都不该发生。

**缺口 3 — 工具参数校验报错不含字段名，模型无法自我纠正**
`registry._validate_args` 在单个 required 字段缺失时报 `missing required argument: X`（有名字），但两个以上缺失时退化为 `missing required tool args`（无名字）。模型收到后不知道该补什么，原地用同样错误参数重试 3+ 次死循环。复现：#201 现场消息 [33]/[35]/[37] 连续三次 `edit(path, old_string, new_string)` 均收到同一句无信息报错。

## 影响范围

- 缺口 1：所有查看 agent 设置页的用户。空 allowlist 的 agent 工具面板显示与 runtime 行为直接矛盾（UI 说谎比不显示更糟）；且「显式清空」这一合法配置在 UI 上不存在。修复后空 allowlist 的 agent 工具面板从「默认全开」变「全不亮」——这是语义校正，反映真值。
- 缺口 2：显式零工具 / 受限工具的会话（如精简权限 agent、或被 #201 波及的会话）。模型自由发挥的调用会被执行，可能读写用户文件/执行命令——是安全问题不只是正确性问题。修复后这类调用被明确拒绝，是预期的行为收紧。
- 缺口 3：所有参数校验失败的场景。报错文本变化（模型可见；用户在工具错误卡上可见更具体的信息）。无数据损坏。

## 根因分析（RCA）

**缺口 1（设置页假象）**：feat-394 M9 时代 UI 约定「空 allowlist = 显示默认全开」（`useDefaultOn`），与当时 runtime「空→默认工具集 fallback」一致。PR #195（`69cf5c80b`）把 runtime 翻转为「空=零工具」时只改了 create 页（预选物化默认值），漏改 detail 页的 `useDefaultOn` 渲染——两处语义需要联动而只改了一处。为什么能进来：PR #195 的测试只覆盖 create 页与 load backfill，无 detail 页渲染回归测试；review 未发现联动面。回归引入点：`69cf5c80b`。

**缺口 2（executor 无兜底）**：`tool_execution_allowlist` 是内核为 fork sidechain 等内部场景设计的参数，PA 会话路径从未传（默认 None）。设计时隐含假设「模型只会调用声明过的工具」，对零声明/幻觉调用无防御——advertisement 是软引导不是硬约束。非回归，长期设计缺口，由 #201 的零声明会话首次大规模暴露。原始设计意图：tool allowlist（feat-379/394）让用户可显式禁用默认工具——**修复必须保住的不变量**：用户显式选择（含清空）被忠实执行；正常 agent 的工具调用不受影响（含 sub-agent fork、unattended 会话的既有工具通路）。

**缺口 3（报错无字段名）**：validator 实现时未考虑「模型需要靠报错自我纠正」的信息需求，多字段缺失走了笼统文案分支。对照 CC（`src/utils/toolErrors.ts`）：按缺/多/类型错逐条列出（`The required parameter \`X\` is missing` 等），组装多行错误。**不变量**：校验严格性不降低（不接受别名、不放松 required）；只是报错信息变具体。

## 用户场景（现状痛点）

用户在设置页打开 plato 的配置，看到 11 个工具全亮，以为 agent 装备齐全；去聊天让 agent 改文件，agent 却反复失败——页面说的和会话里真实发生的完全是两回事。用户想把一个 agent 的工具全部关掉做成「纯聊天」agent，在设置页取消所有勾选、保存、刷新，发现工具又全亮了——清空这个意图根本不存在于 UI 上。而在一个确实没有工具的会话里，agent 居然还能读出用户硬盘上的文件内容（模型自由发挥、executor 照跑）；它尝试编辑文件时，又因为一句没有任何字段名的 `missing required tool args`，用同样错误的参数原地重试到死。

修复后：设置页的每个勾选都反映存储真值（空就是全不亮），显式清空可以表达并被执行；零工具会话里任何工具调用都被明确拒绝；参数错了，报错告诉模型具体缺哪个字段，下一轮就能改对。

## 验收标准

### Requirement: 设置页工具/技能勾选态反映存储真值

#### Scenario: 存储非空的 agent 显示实际存储值
- **GIVEN** agent 的存储 tool_allowlist 为 11 个工具
- **WHEN** 用户打开该 agent 的设置 detail 页
- **THEN** 工具面板恰好这 11 个亮，其余不亮

#### Scenario: 存储为空的 agent 全不亮
- **GIVEN** agent 的存储 tool_allowlist 为空
- **WHEN** 用户打开该 agent 的设置 detail 页
- **THEN** 工具面板全部不亮，不再按 default_on 显示默认全开

#### Scenario: 显式清空可以表达并保持
- **GIVEN** agent 当前启用若干工具
- **WHEN** 用户在设置页取消全部工具勾选、保存、刷新页面
- **THEN** 工具面板保持全部不亮
- **AND** 该 agent 的新会话没有任何工具可用

#### Scenario: create 页预选默认行为不变
- **WHEN** 用户打开新建 agent 页
- **THEN** 默认工具仍预选，与变更前一致

### Requirement: 零工具/受限会话的非名单工具被明确拒绝

#### Scenario: 显式零工具会话中工具调用被拒
- **GIVEN** 一个 tool_allowlist 显式为空的 agent 的会话
- **WHEN** 模型尝试调用任何工具（如 read）
- **THEN** 工具不执行，目标文件/系统不被触碰，用户看到明确的工具不可用反馈（含「该会话未启用」语义）

#### Scenario: 正常 agent 工具通路不回归
- **GIVEN** tool_allowlist 非空的 agent 的会话
- **WHEN** 模型调用名单内工具
- **THEN** 工具正常执行，与变更前一致

### Requirement: 参数校验报错列出具体字段名

#### Scenario: 错参数名调用可自我纠正
- **WHEN** 模型用错误参数名调用 edit（如 `old_string`/`new_string`）
- **THEN** 返回的错误文本包含实际 required 字段名（`oldText`、`newText`）
- **AND** 模型下一轮用正确参数名调用成功，不再原地重试

#### Scenario: 多余参数与类型错误同样列名
- **WHEN** 模型调用时提供了 schema 外字段或字段类型错误
- **THEN** 错误文本逐条指出多余/类型错的字段名

## 修复方向

三个缺口独立修复，预计各一个 milestone（可并行）：

1. **设置 detail 页按存储值渲染**：移除/改造 `useDefaultOn` 在 detail 页的语义——存储空 = 全不亮；用户做任何勾选操作时把当前生效值物化为显式列表（沿用既有 allowlistUserTouched 物化路径）。create 页预选默认行为不动。
2. **executor 兜底拦截**：会话的 enabled_tools（空或非空）贯通为执行层 allowlist；非名单工具调用被拒并返回明确的 not-allowed 错误文本（含工具名与「该会话未启用」语义），模型可见、用户可见。正常 agent 会话行为不变。
3. **validator 报错列字段名**：多字段缺失/多字段多余/类型错误均按 CC 风格逐条列出字段名（缺：`The required parameter \`X\` is missing`；多：`An unexpected parameter \`Y\` was provided`；类型错：期望 vs 实际），组装多行错误。不接受别名归一化（用户明确否决）。
