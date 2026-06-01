# bugfix-390 — 回归验证

> 对齐: incident.md
> Round: 1 — 2026-06-01

## Verdict

**fail**

---

## 澄清记录

无待澄清项，验收标准 Requirement/Scenario 结构清晰。

---

## User Journeys Exercised

| Journey | 覆盖 Scenario |
|---|---|
| J1: 从用户下拉菜单进入策略页 + 查看/保存全局策略 | Scenario: 从用户下拉菜单进入 / Scenario: 查看与保存全局策略 |
| J2: 查看带 total 的 agent 回复的 token 用量牌 | Scenario: 回复带 total |
| J3: 查看 pre-M17 旧回复（total=null）的 token 用量牌 | Scenario: 旧回复（pre-M17 持久化行）经历史加载 |

---

## 验收标准覆盖表

### Requirement: token 用量牌显示这一轮的总消耗

#### Scenario: 回复带 total

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md § 目标状态/验收标准 |
| WHEN/THEN | WHEN 用户查看带 total=2429 的 agent 回复 THEN 牌子主数字显示 "2.4k"，不是 output=1 |
| 验证方式 | 数据库插入 token_usage={output:1, context_used:2428, total:2429, context_window:200000, delivery_status:completed} 的 agent 消息，浏览器加载对话页截图核查 |
| 证据 | 截图 `/tmp/bugfix390-chat-token2.png`：牌子显示 `▸ 2.4k tok · ctx 1%`；展开后显示 output tokens=1，total tokens=2,429 |
| 结果 | **pass** |
| 备注 | total=2429 正确格式化为 2.4k；主数字取 total 而非 output=1 |

#### Scenario: 旧回复（pre-M17 持久化行）经历史加载

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md § 目标状态/验收标准 |
| WHEN/THEN | GIVEN 一条 total=null 的旧持久化行；WHEN 用户打开会话经 REST 历史加载；THEN 牌子主数字仍显示 total（后端兜底为 context_used+output），不报错、不显示空白 |
| 验证方式 | 数据库插入 token_usage={output:42, context_used:500, total:null} 旧消息，浏览器加载对话截图；同时 curl REST /messages 核查 token_usage.total 字段 |
| 证据 | curl 结果：`"token_usage": null`（整个 token_usage 对象为 null，total 不恒有值）；截图 `/tmp/bugfix390-pre-m17-token.png`：pre-M17 消息无 token 用量牌 |
| 结果 | **fail** |
| 备注 | 根因：`repositories.py:2563` `_decode_token_usage` 在 `"total": null` 时调用 `int(None)` 抛 TypeError，整个 decode 返回 None；messages.py 的 REST 兜底逻辑（159-167 行）因 `message.token_usage is None` 永远跳过，total 从未被计算；前端 token_usage 为 null，chip 不渲染 |

---

### Requirement: 全局策略页可从用户菜单进入并使用

#### Scenario: 从用户下拉菜单进入

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md § 目标状态/验收标准 |
| WHEN/THEN | WHEN 用户点开右上角头像下拉菜单 THEN 在「节点」下方看到「策略」入口，点击后打开全局策略页不再 404 |
| 验证方式 | 浏览器点击右上角头像展开下拉菜单截图，确认菜单项顺序；点击「Policies」观察跳转 URL |
| 证据 | 截图 `/tmp/bugfix390-user-menu.png`：菜单显示 Account → Nodes → Policies → Language → Sign out（顺序正确）；点击后 URL 变为 `/settings/policies`，页面正常渲染 |
| 结果 | **pass** |
| 备注 | Policies 入口位置：节点下方，与用户决定一致 |

#### Scenario: 查看与保存全局策略

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md § 目标状态/验收标准 |
| WHEN/THEN | GIVEN 用户已进入全局策略页；WHEN 编辑默认模型/审计级别/每轮最大轮次/每分钟限流并保存 THEN 保存成功，再次进入看到已保存的值 |
| 验证方式 | 浏览器策略页修改 Default Model→claude-sonnet-4-6，Audit Level→strict，Max Turn→20，Rate Limit→60，点击 Save Policies；导航离开再回来截图确认值持久化 |
| 证据 | 网络请求：`PATCH /im/v1/policies → 200`；截图 `/tmp/bugfix390-policies-saved.png`：修改后字段已更新；导航返回后 `/tmp/bugfix390-policies-page.png`（重载）快照显示 Default Model=claude-sonnet-4-6，Audit Level=strict，Max Turn=20，Rate Limit=60 |
| 结果 | **pass** |
| 备注 | 保存 PATCH 200，再次 GET 返回已保存值；四个字段均持久化 |

---

## 复现验证（修前→修后）

### 缺陷 1: token 牌显示 output 而非 total

- **修前**: 组件取 `usage.output`（值=1），牌子显示 "1 tok"，严重低估
- **修后（带 total 场景）**: 组件取 `usage.total`，牌子显示 "2.4k tok" — **已修复**
- **修后（pre-M17 旧消息场景）**: 后端 decode 在 `total=null` 时整个返回 None，前端 token_usage=null，chip 不渲染 — **未修复（见 Issue #1）**

### 缺陷 2: 策略页无入口，导航 404

- **修前**: 设置区无策略入口，直接访问 `/settings/policies` 报 404
- **修后**: 用户菜单「节点」下方有「策略」入口；点击成功打开策略页；GET/PATCH 策略 API 均正常 — **已修复**

### 缺陷 3: agent-edit 测试陈旧

- 测试修复通过 `npm test` 验证：54 文件，345 测试，全绿（agent-edit.test.tsx 在内）
- 保存行为正常，无用户侧影响 — **已修复**

---

## 自动化测试增量

- **前端 vitest（`npm test`）**：54 文件，345 个测试，全绿
  - `token-chip.test.tsx > R8-3`: displays token_usage.total when present — **pass**（原失败，现绿）
  - `policies-page.test.tsx > loads and saves policies through IM APIs` — **pass**（原 404，现绿）
  - `agent-edit.test.tsx > loads agent form, shows bound node status, and saves` — **pass**（原失败，现绿）
- **后端测试（`pytest -m "not e2e"`）**: 未在本次旅程中显式运行；token REST 兜底的实际效果已通过产品旅程发现问题（see Issue #1）

---

## Issues

### Issue #1（blocking）: pre-M17 旧消息经 REST 历史加载时 token chip 完全不渲染

- **Severity**: major（主路径：查看旧对话历史时 token 用量信息丢失；不是 blocking 主路径，但是验收标准明确要求的用户可观察行为）
- **Recommended Action**: fix-implementation
- **Action Rationale**: 后端 `_decode_token_usage`（repositories.py:2563）对 `"total": null` 的 JSON 调用 `int(None)` 抛 TypeError 后返回 None，messages.py 的 REST 兜底逻辑（159-167 行）因 `message.token_usage is None` 始终跳过；design.md § 决策 1 和 incident.md § Scenario「旧回复」明确要求 REST 兜底使 total 恒有值，但实现在 decode 阶段就失败了。

**期望**：pre-M17 消息（`total=null`）经 REST 加载后 token_usage.total = context_used + output = 542，前端渲染 token chip 显示 "542 tok"

**实际**：REST 返回 `"token_usage": null`，前端无 chip

**复现步骤**：
1. 向数据库插入消息（sender_type=agent, delivery_status=completed, token_usage_json=`{"output":42,"context_used":500,"total":null,"context_window":100000}`）
2. 前端加载该对话
3. 观察：消息无 token chip

**根因位置（用户语言描述）**：后端读取旧消息时，`total` 字段为空（null），触发了一个内部处理错误，导致整个 token 用量信息被丢弃而非用 output+context 计算出总量。

---

## Side Findings

- WebSocket 连接警告（console 中可见）：`ws://127.0.0.1:61525/im/ws/user` 的 WS 连接失败，属于 worktree 环境下 Vite dev proxy 未转发 WebSocket 的已知现象，不影响 REST 旅程验收，也不在本 unit 范围内。
- pre-M17 消息在前端渲染时头像显示为用户头像（TE）而非 agent 头像，因为 `sender_user_id` 是用户自身 ID——这是测试数据构造的局限，不影响验收结论。

---

## 上层文档同步

- [x] `SPEC.md`：无需更新（三处均为前端接线/取值修正，不涉及架构变化）
- [x] `docs/内核设计SPEC.md`：无需更新（IM 前端修改，不涉及内核设计）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] 相关产品 SPEC（`docs/IM-SPEC.md`）：无需更新（policies 路由和菜单入口是修复可达性，不是新增能力；SPEC 原本就描述了策略页的存在）

---

## Highest Required Action

**fix-implementation**

主要验收失败项（Issue #1）属于实现层 bug：`_decode_token_usage` 对 `total=null` 的处理有缺陷，导致 REST 兜底逻辑从未执行。需要 fix worker 修复 `repositories.py:_decode_token_usage` 对 null total 的处理。
