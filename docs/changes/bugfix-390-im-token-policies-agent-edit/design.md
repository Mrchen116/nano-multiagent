# bugfix-390: IM 前端三处缺陷 — token 用量牌口径 / 全局策略页入口 / agent 编辑保存测试 — 技术方案

> 对齐: incident.md

> Unit branch: `unit/bugfix-390` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

- 2026-06-01 (round 1 fix): reviewer 发现 total 恒非 None 的真正单一收口点在 decode 层 `repositories.py:_decode_token_usage`(持久化行 → 领域对象的唯一入口),而非各消费方(WS event_types / REST messages)。`"total":null` 时 `int(None)` 抛错使整个 token_usage decode 失败、旧消息 chip 不渲染。修复落 decode 层;下游兜底保留为防御。同步删除 §既有约束 中残留的"主数字必须回退 output"矛盾句(决策 1 已否决回退)。

## 现状分析

三处缺陷主要落在 IM React 前端,互不耦合。缺陷 1 额外含一处后端 REST 序列化对齐(使 token `total` 成为契约必有字段,见下);策略页所需后端 endpoint 已现成,缺陷 2/3 无后端改动。

### 涉及范围

- `src/IM/frontend/src/features/chat/v2/components/token-chip.tsx` —— token 用量牌组件。第 29 行 `const displayed = usage.output;`(注释"原型只显示 output")决定牌子主数字取 output。**详情面板(展开后)已正确展示 total**(74-79 行 `usage.total`),只是主数字没用它。本 unit 把主数字改为直接取 `usage.total`(不做任何视图层回退)。
- `src/IM/api/ws/event_types.py`(第 67 行)—— 后端 WS 事件构造处**已在服务端把 total 兜底为 `usage.total or (context_used + output)`**:即实时聊天经 WS 送到前端的 token 事件里 `total` 恒有值。这是"total 恒有值"契约的现状基础。
- `src/IM/api/routes/messages.py`(第 159 行)—— REST 历史消息序列化处 `total=message.token_usage.total` 原样透传,对 pre-M17 旧持久化行可能为 `None`(契约缺口)。本 unit 对齐 WS 的同一兜底,使 REST 路径也恒返回 total。
- `src/IM/frontend/src/features/chat/v2/components/token-chip.test.tsx` —— 牌子测试。R8-3 用例断言带 total 时主数字显示 "2.4k";另有用例只给 output 无 total 断言显示原值。本 unit 不改测试(改 total-fallback 后两用例都满足),仅作回归确认。
- `src/IM/frontend/src/app/router.tsx` —— 路由表。settings 子路由(34-75 行)当前只有 `agents` / `nodes` / `account`,**无 `policies`**。本 unit 在 `nodes`(70 行)与 `account`(71 行)之间插入 `policies` 路由,并 import `PoliciesPage`。
- `src/IM/frontend/src/app/shell/user-menu.tsx` —— 用户头像下拉菜单。`nodes` 入口(140-149 行)与语言切换组(150 行)之间无策略入口。本 unit 在 `nodes` Link 之后插入「策略」Link。
- `src/IM/frontend/src/i18n/en.json` / `zh.json` —— `shell.userMenu` 段(37-40 行附近)有 `nodes` / `account` label,**无 `policies`**。本 unit 各加一个 `policies` key(EN "Policies" / ZH "策略")。
- `src/IM/frontend/src/features/settings/policies/policies-page.tsx` —— 全局策略页,导出 `PoliciesPage`(命名导出)。**组件 + 其前端 API + 后端 endpoint 全现成**,只是没接进路由/导航。本 unit 不改它,只接线。
- `src/IM/frontend/src/features/settings/policies/policies-page.test.tsx` —— 当前因 `/settings/policies` 无路由报 "No routes matched" 而 404 失败;接回路由后自动转绿。本 unit 不改测试。
- `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx` —— agent 编辑页测试。保存断言用精确 JSON body,未同步组件现已合理多带的 `"features":{}`(Behavior card 引入,feat-379-M3)。本 unit 仅更新该断言。

### 既有约束

- 纯 IM 前端改动,**不碰后端 / 内核 / 其它顶层包**。遵守 AGENTS.md 模块边界(`IM` 不调用 `agent`)。
- 沿用既有 `appRoutes` 嵌套结构、`user-menu` 的 `<Link>` + i18n `t("shell.userMenu.*")` 约定、i18n EN/ZH 双份 key 对齐约定——不引入新风格。
- `TokenUsage.total` 为可选字段(`chat-types.ts`):旧消息(total 引入前持久化)`total` 字段为 null。本 unit 在后端令 total 恒非 None(见决策 1),前端不做视图层回退,旧消息也不得报错/空白。

### 可复用能力

- **全局策略页全套(前端组件 + 前端 API `getPolicies`/`updatePolicies` + 后端 `/im/v1/policies` + `settings_policies` 表 + repo)均已存在**——缺陷 2 是"做了一半被晾着"的孤儿页面,**用**:纯接线恢复可达性,不新建任何页面/接口。
- token 牌详情面板已展示 total,字段链路通——**用**:主数字直接复用 `usage.total`,无需新增数据流。
- 后端 `event_types.py:67` 已有的 total 服务端兜底(`total or context_used+output`)——**用 + 扩**:把同一兜底逻辑对齐到 REST 序列化(`messages.py`),让 total 在所有出口恒有值,前端遂无需任何回退。"总消耗"的定义收口在后端一处。

### 相关历史

- **refactor-387**:合并入 main 后跑前端全量测试才暴露这三处既有失败(它们早已烂在 main)。本 unit 是其善后。
- **feat-379-M3**(Behavior card):给 agent config 引入 `features` 字段,使保存 body 多出 `features:{}`,是缺陷 3(agent-edit 测试陈旧)的近因。
- **commit `f1cc8881`**(R4 "Chip 显示 total 而非 completion"):token 牌显示 total 是明确历史需求,后被按早期原型静默改回 output。缺陷 1 的修复是**恢复 R4 原意图**,不是新决策——这是硬约束:不能为消症状删 R8-3 测试。
- **feat-388**(convention-guardrails):本三类缺陷的共同根因(前端 vitest 不在 CI 门)之"防复发"归 feat-388 落地;本 unit 只修缺陷本身(见 incident.md 非目标)。

## 架构总览

三处独立的"接线/取值修正",无新增模块、无数据流变更。前端组件/路由现状与改后对照:

```
缺陷①  TokenChip:  主数字 = usage.output            →  主数字 = usage.total（不做视图层回退）
                   (详情面板已显示 total,不变)
        后端 total 兜底:  WS 路径已恒有值              +  REST 路径(messages.py)对齐同一兜底
        (event_types.py:67 已 total or ctx+out)        → total 成为契约必有字段,前端直接取

缺陷②  路由:  /settings → {agents, nodes, account}  →  {agents, nodes, policies, account}
        菜单:  [账号] [节点] ──(无策略)── [语言]      →  [账号] [节点] [策略] ── [语言]
        (PoliciesPage + /im/v1/policies 后端均现成,纯接线)

缺陷③  agent-edit.test:  期望 body 不含 features    →  期望 body 含 "features":{}
        (产品保存行为正常,不动;仅测试断言对齐现状)
```

## 关键决策

### 决策 1: token 牌主数字 = `usage.total`,total 由后端契约保证恒有值(无视图层回退)

- **选择**: 前端 `const displayed = usage.total;`(同步更新第 28 行注释为"显示这一轮总消耗"),**不做 `?? output` 之类视图层回退**。配套:把后端 `event_types.py:67` 已有的 total 服务端兜底(`usage.total or context_used+output`)对齐到 REST 序列化 `messages.py`,使 total 在 WS 与 REST 两个出口都恒有值——`total` 实质成为契约必有字段。
- **理由**: 恢复 R4(`f1cc8881`)原意图——主数字反映这一轮总消耗。"总消耗"只该有一处定义(后端),前端不该在视图层用 output 顶替——output 严重低估,是误导性退让;旧持久化行的缺口在数据源头(REST 序列化)用与 WS 同一公式补齐,而非前端用更差的值兜。
- **拒绝**: ❌ `usage.total ?? usage.output`(用户明确否决:output 是误导性退让,坚决不要这种回退);❌ 前端 `total ?? context_used+output`(把"总消耗"定义复制进视图层,双处定义易漂移);❌ 删 R8-3 测试了事(违背 incident RCA "不能为消症状砍功能")。
- **风险**: REST 兜底是 `messages.py` 一行、镜像既有 WS 逻辑,低风险;`fmtK` 已处理 ≥1000 转 "k",total 走同一格式化。

### 决策 2: 全局策略页 — 接回路由 + 用户菜单加入口(纯前端接线)

- **选择**: ① `router.tsx` settings 子路由在 `nodes` 与 `account` 之间加 `{ path: "policies", element: <PoliciesPage /> }` 并 import `PoliciesPage`;② `user-menu.tsx` 在 `nodes` Link 之后、语言组之前加一个 `<Link to="/settings/policies">`「策略」入口(图标 + `t("shell.userMenu.policies")`,样式沿用 nodes Link);③ `en.json`/`zh.json` 各加 `shell.userMenu.policies`(EN "Policies" / ZH "策略")。
- **理由**: 后端 endpoint + 页面组件 + 前端 API 全现成,缺的只有路由与导航入口(incident 缺陷 2);用户已定入口位置="账号、节点按钮下面"。
- **拒绝**: 删 policies-page(用户决定保留该能力);把策略页塞进 settings 侧栏而非用户菜单(违背用户明确决定的放置位置)。
- **风险**: 低;路由 path 与页面内 `getPolicies`/`updatePolicies` 调用的后端 endpoint 已验证存在,接回即可达。

### 决策 3: agent-edit 测试 — 更新陈旧断言,不动产品代码

- **选择**: 把 `agent-edit.test.tsx` 保存断言的期望 body 更新为包含 `"features":{}`,匹配组件当前(feat-379-M3 后)的正确保存行为。
- **理由**: 经验核实保存功能正常(PATCH 正常触发、URL/method 匹配,唯一差异是实际 body 多 `features:{}`),纯测试陈旧、无用户侧影响(incident Q4)。
- **拒绝**: 改产品代码去掉 `features:{}`(会回退 Behavior card 的合理演进,属砍功能);放宽断言为部分匹配(掩盖回归检测能力)。
- **风险**: 无产品行为变更。

## 接口与数据流

无对外接口形态变更、无数据结构变更:

- `TokenUsage`(`chat-types.ts`)结构不变(`total?` 字段已存在);**行为契约收紧**:total 由后端在 WS(已)与 REST(本 unit 对齐)两出口恒返回值——`event_types.py:67` 与 `messages.py` 用同一公式 `usage.total or context_used+output`。前端只读 `usage.total`。
- `/im/v1/policies`(GET/PATCH)契约不变,本 unit 只把已存在的前端调用方(PoliciesPage)接回可达路由。
- agent config PATCH(`/im/v1/agents/:id/config`)请求体不变,本 unit 只让测试断言追上现状。

## 风险与回退

- **风险**: 三处都是小范围前端改动,主要风险是 i18n EN/ZH key 不对齐(漏加一份会导致一种语言显示 key 原文)、或 policies 路由 path 与菜单 `to` 不一致(点击 404)。退出标准的 reviewer 轨(菜单点击打开策略页不再 404)直接覆盖后者。
- **降级**: 无需降级——三处互不依赖,任一处出问题不影响另两处。
- **回滚**: 全部为前端源码改动,`git revert` 对应 commit 即可,无数据迁移、无状态残留。

## Runbook for Reviewer

本 unit 改 IM 前端源码 + IM 后端一处 REST 序列化(`messages.py` total 兜底)。reviewer 需重启 IM 前端 dev server **和** IM 后端以加载改动后的代码;Gateway 不在本 unit 改动范围,无需重启。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM 前端 dev server | `kill "$(cat .vite.pid)" 2>/dev/null; rm -f .vite.pid` | `cd src/IM/frontend && npm run dev -- --port <VITE_PORT> --strictPort > .vite.log 2>&1 & echo $! > .vite.pid` | 浏览器开 `http://127.0.0.1:<VITE_PORT>/`,登录后进聊天看 token 牌、开用户菜单看「策略」入口 |
| IM 后端(本 unit 改 `messages.py`) | `kill "$(cat .im.pid)" 2>/dev/null; rm -f .im.pid` | `IM_JWT_SECRET=<secret> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port <IM_PORT> > .im.log 2>&1 & echo $! > .im.pid` | `curl http://127.0.0.1:<IM_PORT>/im/v1/policies`(带 token)返回策略 JSON;历史消息接口返回的 token_usage 含非空 `total` |

> 前端测试无需起服务:`cd src/IM/frontend && npm test` 直接跑 vitest。

## Milestones

单 M1——三处均为小范围前端修正(远 < 800 行 / 10 文件),互不耦合、一个 worker 一趟完成,无并行收益,不拆。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-390-M1 | fix-frontend-three-defects | — | A | `token-chip.tsx`、`api/ws/event_types.py`（确认/复用现有兜底）、`api/routes/messages.py`（REST total 兜底对齐）、`router.tsx`、`user-menu.tsx`、`i18n/{en,zh}.json`、`agent-edit.test.tsx`（其余涉及文件只读不改） | `[reviewer]` token 牌主数字显示这一轮总消耗 total（覆盖 Req-token 用量牌显示总消耗 / Scenario-回复带 total；旧回复经 REST 加载同样显示 total，不显示 output）<br>`[reviewer]` 用户菜单「节点」下出现「策略」入口、点击打开全局策略页不再 404、可查看/保存（覆盖 Req-全局策略页可从用户菜单进入并使用 / 两个 Scenario）<br>`[worker]` token 牌主数字取 `usage.total`，前端无 `?? output` 回退；REST(`messages.py`)与 WS(`event_types.py`) total 兜底口径一致，total 恒有值<br>`[worker]` `cd src/IM/frontend && npm test` 全绿（token-chip / policies-page / agent-edit 三处由失败转绿，且不新增失败）<br>`[worker]` `npm run build` tsc 类型检查通过 + 后端 `pytest -m "not e2e"` 涉 total 序列化的测试全绿<br>`[worker]` i18n EN/ZH 均补 `shell.userMenu.policies`，无缺失 key |
