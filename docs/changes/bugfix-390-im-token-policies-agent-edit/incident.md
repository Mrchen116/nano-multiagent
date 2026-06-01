# bugfix-390: IM 前端三处缺陷 — token 用量牌口径 / 全局策略页入口 / agent 编辑保存测试

## Relations

- Related: refactor-387（合并入 main 后跑前端全量测试时，发现这三处早已存在于 main 的失败测试）
- Related: feat-388-convention-guardrails（本 unit 的"防复发"——前端 vitest 接入 CI 门禁——归 388 实现，见 RCA / 非目标）

## 原始报告

合并 refactor-387 后在 main 上跑 `npm test`（前端 vitest 全量），3 个测试确定性失败（非 flaky，已在干净 main 上复现）：

```
FAIL  src/features/chat/v2/components/token-chip.test.tsx
  > TokenChip > R8-3: displays token_usage.total (real prompt+completion sum) when present
  AssertionError: expected '▸1 tok·ctx 1%' to match /2\.4k/

FAIL  src/features/settings/policies/policies-page.test.tsx
  > policies page > loads and saves policies through IM APIs
  No routes matched location "/settings/policies"  → 404 ErrorBoundary

FAIL  src/features/settings/agents/agent-edit.test.tsx
  > agent edit page > loads agent form, shows bound node status, and saves edited display name via IM config APIs
  expected "spy" to be called with [PATCH /im/v1/agents/agent-core-1/config, <body 不含 features>]
```

用户就这三处的处置原话（截图见 `~/.claude/image-cache/438c1419-5e40-46f1-a3e9-f85258e85460/1.png`，用户菜单下拉）：

> 1. 同意你说的，按总的显示。2. 放到这吧[截图]，账号、节点按钮下面加多一个
>
> agent-edit这个你也要处理上
>
> 放一个

## 澄清记录

- Q1: 范围 + 类型——三处放一个 unit，还是 token+policies 一个、agent-edit 单独修？
  A(原话): 放一个
  Agent 解读: 三处合并为一个 bugfix-full unit（bugfix-390）。共同根因是前端测试未进 CI，放一起 RCA 能一次说清。

- Q2: token 用量牌按钮上的主数字，显示 agent 写出来的量（output）还是这一轮总消耗（total，含读进去的上下文）？
  A(原话): 同意你说的，按总的显示。
  Agent 解读: 牌子主数字显示 total（prompt+completion 总和）。

- Q2b: total 缺失时（pre-M17 旧持久化行）牌子主数字怎么办——回退显示 output？
  A(原话): 无 total 自动回退 output。坚决不搞这种退回
  Agent 解读: 否决视图层回退。output 严重低估、是误导性退让，前端不得用它顶替。改为在数据源头保证 total 恒有值——后端 WS 路径已兜底（`event_types.py:67` = `total or context_used+output`），REST 序列化路径对齐同一公式，使 total 成为契约必有字段；前端直接取 `usage.total`，无任何回退。详见 design.md 决策 1。

- Q3: 进不去的「全局策略」页放哪？
  A(原话): 放到这吧[用户菜单下拉截图]，账号、节点按钮下面加多一个
  Agent 解读: 在用户头像下拉菜单里、「节点」入口下方新增一个「策略」入口，点进去打开全局策略页；同时把缺失的路由接回去让页面可达。

- Q4: agent-edit 的保存是真坏了还是测试问题？
  A(经验核实，非用户答): 实跑 agent-edit 测试看全部实际 fetch 调用——第 6 次调用 URL=`/im/v1/agents/agent-core-1/config`、method=`PATCH` 均匹配，**唯一差异是实际 body 多了 `"features":{}`**（组件现在随 Behavior card 带空 features 对象，测试期望不带）。即**保存功能正常**，用户改 agent 名能正常持久化；失败纯属测试断言陈旧，**无用户侧影响**。

## 现象与复现

### 缺陷 1 — token 用量牌显示口径错（用户可观察）
- **复现**：在 IM 聊天里看任一 agent 回复旁的 token 用量小徽章。
- **期望**：徽章主数字显示这一轮的**总消耗 total**（输入上下文 + 输出），让用户一眼看出"这轮烧了多少"。
- **实际**：徽章只显示 **output**（agent 写出来的量）。一条回复 output=1、total=2429 时，徽章显示 "1 tok"，严重低估、误导用户以为几乎不花钱。total 只藏在点开后的详情面板里。
- 历史：曾有明确需求（commit `f1cc8881` "test(R4): Chip 显示 total 而非 completion"）要求显示 total，后被按早期原型图静默改回 output。

### 缺陷 2 — 全局策略页进不去（用户可观察）
- **复现**：在 IM 设置区找「策略 / Policies」入口。
- **期望**：用户能进入全局策略页，查看/编辑全局开关（默认模型、审计级别、每轮最大轮次、每分钟限流）并保存。
- **实际**：设置区只有「Agents / Nodes / Account」，**没有任何入口或 URL 能打开策略页**。页面与其 API 在代码里存在但无路由、无导航，等于做了一半被晾着，用户完全看不到、用不上。

### 缺陷 3 — agent 编辑保存测试失败（无用户侧影响，测试陈旧）
- **复现**：跑 `agent-edit.test.tsx`。
- **期望（用户侧）**：在 agent 编辑页改显示名并保存，改动持久化——**此行为实测正常，无缺陷**。
- **实际（测试侧）**：测试用精确 JSON 字符串断言保存请求 body，但组件现在合理地多带了 `"features":{}`（Behavior card 引入），断言对不上而失败。属测试维护问题，非功能缺陷。

## 影响范围

| 缺陷 | 受影响用户 | 严重度 | 数据损坏 |
|---|---|---|---|
| token 牌显示 output | 所有看 token 用量的用户 | 中——误导性低估真实消耗，但不影响功能 | 无 |
| 策略页无入口 | 需要配置全局策略的用户/运营 | 中——一项已实现的能力完全不可达 | 无 |
| agent-edit 测试 | 无用户影响（仅 CI/开发者） | 低——保存功能正常，仅测试红 | 无 |

三者均无数据损坏；token 与 policies 是真实用户可观察缺陷，agent-edit 纯测试维护。

## 根因分析（RCA）

**逐缺陷近因**：
1. **token 牌**：组件 `TokenChip` 把主数字写成 `displayed = usage.output`（注释"按原型只显示 output"），推翻了先前需求 R4「显示 total」。`TokenUsage.total` 字段存在但未被牌子主数字采用。
2. **策略页**：路由表的 settings 子路由只剩 `agents / nodes / account`，`/settings/policies` 被摘除（或从未接入），但 `policies-page.tsx` + 其 API + 测试仍保留 → 孤儿页面。
3. **agent-edit**：保存请求 body 随 Behavior card（feat-379-M3）演进加入 `features` 字段，测试的精确字符串断言未同步更新。

**共同根因（为什么这类错能进来且潜伏数周）**：
- **前端 vitest 未接入 CI**。仓库 PR 全程 `no checks reported`——前端测试不参与任何门禁。于是组件/路由/请求体随后续功能演进漂移时，对应测试早已变红却无人察觉，在 main 上烂了约 2–3 周直到 refactor-387 合并后手动跑全量才暴露。
- 三处都是"代码（或需求决策）演进了、对应测试/接线没跟上"的同一类漂移，只是没有任何自动闸门拦住。
- **防复发归 feat-388**：feat-388（convention-guardrails）正在建 CI 触点。但其现设计的 `ci.yml` 只跑 Python（`ruff` + `pytest -m "not e2e"`），**没有前端 vitest 步骤**——即 388 现状仍拦不住本 unit 这类前端腐烂。已建议 feat-388 在其 CI 触点补一个前端 job（`npm ci` + `npm test`），把门同时盖住 Python + 前端两半。本 unit 不自建 CI（见非目标）。

**原始设计意图追溯（防为消症状而砍功能）**：
- token 牌的 total 显示是 R4（`f1cc8881`）的明确需求，修复必须**恢复 total 语义**，而不是删掉 R8-3 测试了事。
- 策略页是一项已实现能力，修复应**恢复可达性**，而非删页面（除非确认该能力作废——本 unit 按用户决定保留并接入用户菜单）。

## 目标状态 / 验收标准

### Requirement: token 用量牌显示这一轮的总消耗
#### Scenario: 回复带 total
- **WHEN** 用户查看一条 agent 回复的 token 用量牌
- **THEN** 牌子主数字显示 total（例 total=2429 → "2.4k"），而非 output
#### Scenario: 旧回复（pre-M17 持久化行）经历史加载
- **GIVEN** 一条在 total 字段引入前持久化的旧回复，用户重新打开会话经 REST 历史加载它
- **WHEN** 用户查看其 token 用量牌
- **THEN** 牌子主数字仍显示 total（后端 REST 序列化按 `total or context_used+output` 兜底，恒有值），**不退回显示 output**、不报错、不显示空白

### Requirement: 全局策略页可从用户菜单进入并使用
#### Scenario: 从用户下拉菜单进入
- **WHEN** 用户点开右上角头像下拉菜单
- **THEN** 在「节点」入口下方看到一个「策略」入口
- **AND** 点击后打开全局策略页（不再 404）
#### Scenario: 查看与保存全局策略
- **GIVEN** 用户已进入全局策略页
- **WHEN** 用户编辑默认模型 / 审计级别 / 每轮最大轮次 / 每分钟限流并保存
- **THEN** 保存成功，再次进入页面时看到已保存的值

> agent-edit 不产生用户可观察的验收 Scenario——保存行为本就正常，仅需让其测试与当前正确行为对齐。归入下方修复方向与回归保障。

## 范围与非目标

**本期做**：
- token 牌主数字改为 total，前端不做视图层回退；total 由后端契约保证恒有值（REST 序列化对齐 WS 已有的 `total or context_used+output` 兜底）。
- 全局策略页：接回路由 + 在用户下拉菜单「节点」下方加「策略」入口。
- agent-edit：更新陈旧测试断言以匹配当前正确的保存行为（含 `features`）。

**非目标**：
- 不重新设计 token 牌的详情面板布局、不改 token 统计口径本身（只改牌子主数字取 total，并把 REST 序列化的 total 兜底对齐到 WS 既有口径，使其恒有值）。
- 不重做全局策略页的功能/字段（只恢复可达性 + 入口；页面既有能力保持）。
- 不改 agent 保存的实际行为（它正常）；不借机重构 agent 编辑表单。
- **不在本 unit 搭建 CI**。本仓目前无任何 CI（无 `.github/workflows`），CI 门禁由 **feat-388** 负责建设。RCA 已指出"前端测试无门禁"是共同根因，**防复发归 feat-388**（需在其 `ci.yml` 补前端 vitest job，已就此向 388 提补充）；本 unit 仅修三处缺陷本身。
