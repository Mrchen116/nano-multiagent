# feat-540: Agents 列表条目标注归属设备 — 技术方案

> 对齐: spec.md v2

> Unit branch: `unit/feat-540` (will be created by orchestrator)

- 2026-08-18 (M1): 决策 3 移动端显示名字色以现状 `oklch(0.18 0.01 240)` 为准(design 表与 prototype 误写 `0.14`,与决策 4「移动端不动」自相矛盾;实现与本文档已按现状值统一)。
- 2026-08-18 (M1): Scenario「无归属信息的条目右缘留空」从 spec/delta-spec/退出标准/原型删除——真栈验证发现列表接口强制 `JOIN nodes` + `node_id IS NOT NULL`(src/IM/infra/repositories/agents.py:88-90),无归属 agent 不进列表,前提不可达;用户裁决「这种压根不会出现的场景就不应该写,改干净」(spec Q8)。组件层防御性渲染保留,单测锁定。

## 现状分析

### 涉及范围

- `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx` — Agents 设置首页侧栏(桌面 240px 深底 / 移动端全宽浅底)。内含 `AgentRow`:头像用共享 `Avatar`(带状态角标),右缘有独立状态圆点;桌面端非选中行文字色 `oklch(0.18)` 配深底 `oklch(0.24)`(深底深字 bug)。
- `src/IM/frontend/src/features/settings/agents/agents-rail-desktop.tsx` — agent 详情页 / 新建页的同款桌面侧栏(`hidden lg:flex`,仅桌面)。内含一份独立实现的行:头像是裸 `<span>`(无状态角标),右缘独立圆点是唯一状态表达;行文字色正确(`0.86`/`0.64`)。
- `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts` — 只读。`AgentSummary` 带 `node_id` / `node_status`;后端 `/im/v1/agents` 的 `AgentSummaryResponse` **不含 `node_name`**(已核实 `src/IM/api/routes/agents.py:117-135`)。`/im/v1/nodes` 返回 `NodeSummary`(`node_name` + 可选 `alias`),首页侧栏已在查询, rail 未查询。Account 页展示设备名的优先级是 `alias || node_name`(`account-page.tsx:215`、`:250`),本 unit 的设备名取值必须同优先级(spec Scenario「与 Account 页显示的设备名一致」)。
- `src/IM/frontend/src/features/chat/components/avatar.tsx` — 共享 `Avatar` 组件(可选 status 角标)+ `colorForAgent` 颜色算法,只读复用。
- 对应测试:`agents-list-page.test.tsx`、`agents-rail-desktop.test.tsx`。

### 既有约束

- 前端只经 `/im/v1/*` HTTP 与用户维 WS 取数;本 unit 不动后端(spec 非目标),设备名只能由前端现有两个接口拼出。
- 该目录样式习惯:Tailwind arbitrary values + 少量 inline style;文案走 `useTranslation`——设备名是接口数据,不引入新文案,无 i18n 改动。
- 行高 `min-h-[52px]`、圆角 12px、active/hover 底色体系源自 feat-340 原型,非本 unit 改动对象。

### 可复用能力

- 共享 `Avatar` 组件(含 status 角标) — **用**。首页侧栏已用;rail 换用它,状态角标才有落点。
- `listNodes`(`/im/v1/nodes`)— **用**。首页侧栏已查;rail 补同一 query,设备名 join 与状态回退共用。
- `statusOf(agent, nodes)` 语义(先信 `agent.node_status`,缺了查 nodes 表)— **统一**。目前只存在于首页侧栏,rail 只看 `agent.node_status`,共享后两处一致。
- `NodeChip`(chat 头部设备 chip,圆点+名字)— **不用**。形态不符:右缘是纯文字标注,且圆点会与头像角标双重编码。

### 相关历史

- feat-340 原型 `im-settings-page.jsx` 的 `AgentListView` 定义了行的全部视觉(含把桌面非选中文字误写为 `oklch(0.18)`);feat-340-M23 照抄实现出首页侧栏,深底深字 bug 由此带入。
- 后续"桌面 Agent 页面提供连续导航"需求新增 rail 时修正了文字色(`0.86`/`0.64`),但与首页侧栏形成两份漂移的行实现——本 unit 的共享组件决策正是针对这个根因。
- `0a7e06282` 统一过聊天页与配置页头像颜色算法(`colorForAgent` seed = display_name),本 unit 沿用,不动颜色算法。

## 架构总览

两份漂移的行实现收敛为一份共享行组件,设备名与颜色修复只落一处:

```
before(两份行实现,已漂移)                after(单一共享行组件)
┌ agents-list-page.tsx ────────┐        ┌ agents-list-page.tsx ──┐
│  AgentRow(深底深字 bug)      │        │  错误/空态/头部          │
│  Avatar(有角标)+右缘圆点     │        └─────────┬──────────────┘
├ agents-rail-desktop.tsx ─────┤   →    ┌ agents-rail-desktop.tsx ┐
│  inline row(文字色正确)      │        │  头部                    │
│  裸 span 头像(无角标)+圆点   │        └─────────┬──────────────┘
└──────────────────────────────┘                  ▼
                                   ┌── agent-row.tsx(新增,共享)──┐
                                   │ Avatar(带角标) + 名字两行    │
                                   │ + 右缘设备名(圆点删除)       │
                                   └─────────────────────────────┘
```

本需求最易迷路处在**视觉**而非流程,图以 before/after 结构 + [prototype.html](prototype.html) 的逐状态视觉为准;跨模块时序图略(纯展示层,数据已在行内,无新调用链)。

## 关键决策

### 决策 1: 抽出共享行组件 `agent-row.tsx`,两份行实现合一

**首页侧栏与 rail 改用同一份 `AgentRow` 实现,颜色修复、设备名、头像角标只写一次。**

- **理由**:深底深字 bug 的根因就是两份行实现漂移(原型错→首页照抄,rail 修正过但没回灌)。"三处同款列表一致"靠纪律守不住,靠结构才能守住;本 unit 两个改动面(设备名、颜色修复)恰好都要落在这两份实现上,合并的边际成本最低。
- **统一项**(两实现现存微差,合并时定死):active 样式取 feat-340 原型值(桌面 `outline 1px oklch(0.40 0.08 180)` + 底 `oklch(0.31 0.015 240)`;移动浅青底);状态语义统一 `statusOf(agent, nodes)`;rail 的裸 span 头像换成共享 `Avatar`(获得状态角标);右缘独立圆点删除(spec 已定:状态只由头像角标表达)。
- **拒绝**:各改各的(漂移根因留存,下一个改动还会双写);整页合并(头部/空态/错误态各不同,合并等于重写两页,范围爆炸)。
- **风险**:统一 active/hover 样式会微调 rail 现状视觉(ring-inset → outline,肉眼近无差),由 reviewer 截图对照原型兜底。

### 决策 2: 设备名 = 前端按 `node_id` join `/im/v1/nodes`,零后端改动

**设备名与 Account 页同优先级取 `alias || node_name`:节点表查到时取 `node.alias || node.node_name`;查不到回退 `agent.node_id`;`node_id` 为空则不渲染;rail 新增 `listNodes` query。**

- **理由**:`/im/v1/nodes` 已提供全部所需信息,首页侧栏本就在查;后端加字段违反 spec 非目标且无任何新信息。取值优先级必须与 Account 页相同(`alias || node_name`),否则设置了别名的设备在两页显示不一致,直接打破 spec Scenario「与 Account 页显示的设备名一致」。回退规则保证节点表暂时缺该节点时仍有合理显示。
- **失败态**:`listNodes` 查询失败不阻塞列表——设备名回退为 `node_id`(仍符合"标出归属"),状态回退 `agent.node_status`。
- **拒绝**:后端 `AgentSummaryResponse` 加 `node_name`(非目标+冗余);直接用 `node_id` 或裸 `node_name` 当显示名(皆与 Account 页可能不一致)。
- **风险**:`node_name`/`alias`/`node_id` 在用户当前环境相同(mac-mini/macbook-air 且未设别名),别名与回退路径靠单测覆盖;reviewer 旅程含别名场景(见 Milestone 退出标准 1)。

### 决策 3: 三者视觉规范——明度阶梯 + 设备名右对齐同基线,截断只截自己

**显示名 / Agent ID 两行一字不动;设备名右对齐、与第二行同基线,明度低一档,自身超长才截断。**(完整状态样见 prototype.html)

| 元素 | 桌面 · 普通 | 桌面 · 选中 | 移动端 |
|---|---|---|---|
| 显示名 | 13px semibold sans · `oklch(0.86 0.01 240)` | `#fff` | 15px semibold · `oklch(0.18 0.01 240)` |
| Agent ID / description | 11px mono · `oklch(0.64 0.01 240)` | `oklch(0.70 0.01 240)` | 12.5px sans · `oklch(0.55 0.01 240)` |
| 设备名(新增) | 11px sans · `oklch(0.55 0.01 240)` | `oklch(0.64 0.01 240)` | 12px sans · `oklch(0.60 0.01 240)` |

- **理由**:深底上 0.86 > 0.64 > 0.55 的明度阶梯读出"名 > ID > 设备"主次;设备名用 sans 与 ID 的 mono 区分,不被误认成第二个 ID;离线不变灰——状态只由头像角标表达,避免双重编码。
- **排布**:桌面设备名右对齐、与第二行同基线(右列单元素 `align-self: flex-end`);移动端设备名占原圆点位(右列上层),「›」保持在其下。
- **截断**:显示名 / ID 的截断行为与今天完全一致;设备名 `flex-shrink: 0` + `max-width` + ellipsis,仅自身超长时截断自己,永不挤压名字两行(用户拍板的优先级)。
- **拒绝**:设备名 inline 跟在 ID 后(spec Q2 用户已否);独立第三行(spec Q4 用户已否,行高);用 `NodeChip` 圆点 chip(双重编码)。

### 决策 4: 颜色修复 = 首页侧栏统一到 rail 的正确值,移动端不动

**首页侧栏桌面端非选中行文字色 `0.18→0.86`(显示名)、`0.50→0.64`(ID),并为 ID 行补选中态 `0.70`;其余(空态/错误态卡片、移动端)不动。**

- **理由**:rail 的值是 feat-340 原型的本意(深色侧栏浅色字),且已在生产被用户长期看见、无抱怨;统一过去等于让两份实现在决策 1 的共享组件里天然一致。
- **拒绝**:另调一套新色(无依据的发明);只修显示名不修 ID 行(0.50 在深底上对比度同样不足,半截修复)。
- **风险**:无——当前值近乎不可见,任何浅色都是改善。

## 接口与数据流

无新增/变更接口。数据流(两个组件相同):

```
GET /im/v1/agents ──► AgentSummary[] (node_id, node_status)
GET /im/v1/nodes  ──► NodeSummary[]  (node_id → node_name, status)
         │
         ▼  前端 join(共享纯函数,单测覆盖)
nodeLabelOf(agent, nodes): string | null
  = (n = nodes.find(node_id = agent.node_id))
    ? (n.alias || n.node_name)   // 与 Account 页同优先级
    : (agent.node_id ?? null)    // 节点表暂未含该节点 → 回退;无归属 → 不渲染
statusOf(agent, nodes): "online" | "offline"   // 语义不变,两组件统一
         │
         ▼
<AgentRow agent nodes isActive isMobile onSelect />   // 共享组件
```

`AgentRow` props(共享组件的全部输入):

| prop | 类型 | 说明 |
|---|---|---|
| `agent` | `AgentSummary` | 行数据 |
| `nodes` | `NodeSummary[]` | 设备名 join + 状态回退;允许为空数组(查询失败回退路径) |
| `isActive` | `boolean` | 选中态 |
| `isMobile` | `boolean` | 桌面/移动双形态(rail 恒 false) |
| `onSelect` | `(agentId: string) => void` | 点击行为由父组件注入(首页 navigate / rail onSelectAgent) |

## 前端原型

- 原型文件: [prototype.html](prototype.html)
- 覆盖范围:桌面深底侧栏(普通 / 选中 / hover / 归属设备离线 / 无归属 / 超长 ID 截断 / 超长设备名防御)+ 移动端浅底(含 › 排布)+ 颜色修复 before/after + 三者视觉规范表。

### 现有 UX grounding

| 当前产品入口 / 组件 | 必须继承的 UX 特征 | 本次增量如何嵌入 |
|---|---|---|
| Agents 首页侧栏(`agents-list-page.tsx`) | 行高 52px、圆角 12px、active outline + hover 底色、共享 `Avatar` 带角标、移动端全宽浅底 + › | 右缘圆点原位换成设备名;桌面文字色修正到 rail 值 |
| 详情/新建页 rail(`agents-rail-desktop.tsx`) | 同上结构(仅桌面)、文字色正确值 | 裸 span 头像换共享 `Avatar` 得角标;右缘圆点换设备名 |
| feat-340 原型 `AgentListView` | 行全部视觉 token 的出处,active/hover 以此为权威 | 共享组件统一项取它的值 |
| chat 头部 `NodeChip` | 设备名 = `node_name` 的既有展示先例 | 印证 join 取值,不借形态 |

### 原型对齐契约

| 原型区域 / 状态 | 对齐级别 | 产品入口 | 必验 viewport / 状态 | 下游验收投影 |
|---|---|---|---|---|
| 桌面行:右缘设备名(右对齐、与第二行同基线、明度阶梯) | must-match | `/settings/agents` 首页 + 详情页 + 新建页 | desktop:普通/选中/离线节点/超长 ID/别名设备 | feat-540-M1 退出标准 1-6 |
| 移动行:设备名占原圆点位 + 「›」在其下 | must-match | 同上(移动形态) | mobile <768px:普通/选中 | feat-540-M1 退出标准 4 |
| 首页行文字色修复(0.86/0.64 + 选中态) | must-match | `/settings/agents` 首页 | desktop 未选中/选中/hover | feat-540-M1 退出标准 7 |
| 头像状态角标两组件一致;右缘无独立圆点 | must-match | 三处列表 | desktop + mobile | feat-540-M1 退出标准 5 |
| hover 底色、圆角、行高 52px | may-adapt(沿用现有值,非本 unit 对象) | 三处列表 | desktop + mobile | N/A |
| 空态 / 错误态卡片、列表头部 AGENTS+New | out-of-scope(原型未改,产品保持现状) | 首页 | desktop + mobile | N/A |

## 契约层增量 (delta-spec)

- kernel: no spec delta
- im: [specs/im/agents-nodes.md](specs/im/agents-nodes.md)
- gateway: no spec delta
- cli: no spec delta

## 风险与回退

- **统一 active/hover 样式的视觉回归**:rail 现状 ring-inset 与原型 outline 肉眼近无差,但属既有行为变更 → reviewer 桌面截图逐入口对照原型;worker 补双入口渲染测试。
- **`listNodes` 失败 / 节点表滞后**:设备名回退 `node_id`、状态回退 `agent.node_status`,列表不阻塞、不报错;回退路径单测覆盖。
- **超长设备名或超长 ID 挤压**:截断规则(决策 3)+ 原型防御态;worker 以长字符串 fixture 测试。
- **共享组件回归面 = 三处入口全部行渲染**:两组件现有测试需随 props 变化更新;最窄测试命令见 Milestone 退出标准。
- **回滚**:纯前端展示层、无数据迁移,revert unit 分支即完全恢复。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM + Gateway(worktree 隔离栈) | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh`(退出码 0 即 IM readiness 通过) | `source .e2e-ports.env && curl -fsS "http://127.0.0.1:${IM_PORT}/im/v1/nodes"` 返回 200(需带登录态;或浏览器能登录 Agents 页即可) |
| IM 前端 dev server | `pkill -f "vite"`(worktree 内启动的进程) | `cd src/IM/frontend && npm ci && npm run dev` | 浏览器打开 `http://localhost:5173` 正常渲染 |

**Review 驱动方式**: 端到端真栈;本 unit **改了客户端面**,必须真驱动浏览器 UI(Playwright 或手工),关键界面:`/settings/agents` 首页、任一 agent 详情页、新建页,desktop 与 mobile(<768px)两种 viewport。

**验收前置**: 一个拥有 **≥2 台在线节点、各带若干 agent** 的账号(spec「多设备逐条标注」Scenario 的硬前置),另需 1 个归属设备离线的 agent 与 1 个无归属信息的 agent(边界 Scenario)。两条获取路径:
- (a) 用户生产双节点 fleet(mac-mini IM `:8011` + macbook-air gateway,即 spec 截图环境)部署 unit 分支——按 `prod-fleet-deploy` skill,**部署前必须与用户确认**;离线节点场景可临时停一台 gateway。
- (b) worktree `./scripts/e2e-up.sh` 起 IM + 第一台 gateway,再参照该脚本以不同 `NODE_ID` / 端口手工起第二台 gateway 连同一 IM。
- 移动端 viewport 用浏览器设备模拟即可,无需真机。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-540-M1 | impl | — | A | `src/IM/frontend/src/features/settings/agents/`:新增 `agent-row.tsx`(共享行组件)+ 改 `agents-list-page.tsx`、`agents-rail-desktop.tsx` 接入;测试 `agent-row.test.tsx`(新)、`agents-list-page.test.tsx`、`agents-rail-desktop.test.tsx` | 1. [reviewer] 多设备账号下,三处列表每个条目右缘右对齐显示归属设备名,与 Account 页设备名一致;设备设置了别名时与 Account 页一样显示别名(spec Scenario「多设备下逐条标注」+「设备设置别名时显示别名」)<br>2. [reviewer] 归属设备离线的 agent 右缘仍显示设备名(Scenario「设备离线仍显示归属」)<br>3. [worker] 设备名解析的防御路径(节点表暂未含该设备 → 回退显示设备 ID;agent 无 `node_id` → 不渲染设备名)有单测覆盖——该状态经 SQL 层核实不会出现在列表接口,不进产品契约,仅作组件鲁棒性<br>4. [reviewer] mobile viewport 下每条同样标注,› 保持可见(Scenario「移动端同样标注」+ 原型移动契约)<br>5. [reviewer] 名字两行与行高不被挤压;状态从头像角标辨认;右缘无独立圆点(Req「标注不牺牲条目既有信息与状态表达」两 Scenario + 原型角标契约)<br>6. [reviewer] 三处列表桌面行设备名呈现与原型 must-match 行一致(超长 ID 截断规则、别名设备含在内)<br>7. [reviewer] 桌面端首页未选中条目名字浅色可读,选中/hover 三处观感一致(Req「三处列表条目文字在深色侧栏上清晰可读」两 Scenario + 原型修复契约)<br>8. [worker] `cd src/IM/frontend && npm test -- src/features/settings/agents` 全绿<br>9. [worker] 真实浏览器截图(desktop 首页 / 详情页、mobile 首页)与 prototype.html 逐状态对照,结论与截图存 `docs/changes/feat-540-agent-list-node-label/M1-impl/` |
