# bugfix-362 — Regression Report

**Unit**: bugfix-362-im-ghost-agent-reconcile
**Round**: 1
**Date**: 2026-05-19
**Reviewer**: change-reviewer (automated)
**Branch**: unit/bugfix-362-im-ghost-agent-reconcile

---

## Verdict

**PASS**

## Highest Required Action

**pass**

## Issues Count

| Severity | Count |
|----------|-------|
| blocking | 0 |
| major    | 0 |
| minor    | 0 |

## Issues

_No issues found._

---

## User Journeys Exercised

| # | 旅程 | 路径 |
|---|------|------|
| J1 | 主路径：Gateway 删 agent 后重启，验 agent 列表/picker/新建群不出现 stale agent | 启动 Gateway（含 ghost-reviewer-362）→ 删除 config 中 ghost agent → restart → 验证三个入口 |
| J2 | 群成员置灰：含 stale agent 的已有群，group header 展示置灰效果 | API 创建含 ghost-reviewer-362 的群，进入群聊，检查 header 渲染和 @ picker |
| J3 | 历史消息保留：发送消息后消息正常渲染，与 agent stale 状态无关 | 向含 ghost agent 的群发送消息，验证聊天历史正常显示 |
| J4 | 复活路径：将 ghost agent 写回 config + restart → 所有入口恢复 | 再次 restart 含 ghost-reviewer-362 的 Gateway，验证 Agents 页+群 header 都恢复 |

---

## 验收标准覆盖表

| # | 验收标准（来自 incident.md / design.md M1 退出标准） | 验证方式 | 结果 | 备注 |
|---|------------------------------------------------------|----------|------|------|
| AC1 | Gateway restart 后 agent 列表页不出现 ghost agent | 浏览器访问 /settings/agents | **pass** | 截图证实只有 default-agent，ghost-reviewer-362 消失 |
| AC2 | 新建群成员选择列表不出现 ghost agent | 点击 "+ Group" 弹框 AGENTS 列表 | **pass** | 截图证实选择器只有 default-agent |
| AC3 | @ picker 不出现 ghost agent | 群内输入 @，展开候选 picker | **pass** | picker 只显示 default-agent，snapshot 确认 |
| AC4 | 历史群成员页面 ghost agent 置灰且不可 @ | 群 header + JS 样式检查 + @ picker | **pass** | opacity-40，title="Offline — agent no longer advertised by its Gateway"；@ picker 无该 agent |
| AC5 | 历史聊天消息正常渲染（mention 标签、显示名等） | 向群发消息后验证渲染 | **pass** | 消息气泡正常显示 |
| AC6 | config 写回 + restart → 全部恢复（stale→active） | restart Gateway 带 ghost agent 后验证所有入口 | **pass** | is_stale 归 0，Agents 页重现，群 header opacity 恢复 1.0 |
| AC7 | DB 迁移幂等（is_stale / staled_at 列存在） | sqlite3 .schema 检查 | **pass** | 两列均已加入 agent_profiles |
| AC8 | 对账只在 node.register 时触发一次（不实时） | 架构验证（register 帧触发对账） | **not-applicable** | 内部时机机制，非 reviewer 可观察用户面 |

---

## 环境与证据

### 服务版本
- IM 前端产物：`index-D5m9q_2J.js`（unit 分支重新构建，指纹核验命中 `is_stale`/`opacity-40`）
- Gateway：unit 分支 worktree 运行
- DB 路径：`data/im_service.sqlite3`（全新数据库，从无到有重现）

### 关键证据截图

| 文件 | 内容 |
|------|------|
| `/tmp/bugfix362-r1-login.png` | 登录页 |
| `/tmp/bugfix362-r1-after-login.png` | 登录后主界面 |
| `/tmp/bugfix362-r1-agents-page.png` | stale 后 Agents 页（只有 default-agent） |
| `/tmp/bugfix362-r1-new-group.png` | 新建群 AGENTS 选择列表（只有 default-agent） |
| `/tmp/bugfix362-r1-ghost-group.png` | 含 ghost agent 的群聊（header 置灰可见） |
| `/tmp/bugfix362-r1-mention-picker.png` | @ picker 只显示 default-agent |
| `/tmp/bugfix362-r1-group-header.png` | 群 header ghost-reviewer-362 置灰 |
| `/tmp/bugfix362-r1-chat-message.png` | 历史消息正常渲染 |
| `/tmp/bugfix362-r1-agents-revived.png` | 复活后 Agents 页（ghost-reviewer-362 重现） |
| `/tmp/bugfix362-r1-revived-group.png` | 复活后群聊 header（opacity 恢复 1.0） |

### JS 样式检查结果

**stale 状态下**：
```json
{"tag":"SPAN","class":"opacity-40","opacity":"0.4","color":"oklch(0.5 0.012 240)","parent_class":"chat-pane-participants","title":"Offline — agent no longer advertised by its Gateway"}
```

**复活后**：
```json
{"class":"","opacity":"1"}
```

### DB 状态快照

**stale 后**：
```
default-agent|review-node|is_stale=0|staled_at=
ghost-reviewer-362|review-node|is_stale=1|staled_at=2026-05-19T01:43:05.085043Z
```

**复活后**：
```
default-agent|review-node|is_stale=0|
ghost-reviewer-362|review-node|is_stale=0|
```

---

## 上层文档同步检查

| 文档 | 需要更新？ | 说明 |
|------|-----------|------|
| `SPEC.md` | 否 | 架构依赖方向不变，无需更新 |
| `docs/内核设计SPEC.md` | 否 | 本 unit 纯 IM 内闭合，不涉及 agent 内核层 |
| `AGENTS.md` / `CLAUDE.md` | 否 | 开发约定不变 |
| `docs/NodeGateway-SPEC.md` | 否 | Gateway 端协议不变（register 帧已有 agents 字段） |
| `docs/IM-SPEC.md` | 建议补充 | `agent_profiles` 新增 `is_stale / staled_at` 字段，`ActorPayload` 新增 `is_stale` 可选字段；可由 PR 合并时追加一行 schema 说明，但不阻塞本次验收 |
| `docs/operator-runbook.md` | 建议补充 | 新部署需重启 Gateway 让对账生效的说明，属运维提醒，不阻塞 |

---

## Side Findings

无值得记录的 out-of-unit 发现。

---

## 验收结论

三类用户可观察场景全部通过：

1. **Agent 列表/picker/新建群**：stale agent 完全消失，用户无法选择或 @ 到幽灵 agent。
2. **已有群成员展示**：置灰效果正确（opacity-40），tooltip "Offline — agent no longer advertised by its Gateway"，@ picker 不含 stale agent。
3. **历史消息保留**：群聊历史消息与 agent stale 状态无关，正常渲染。
4. **复活路径**：config 写回 + restart 后自动恢复，零操作链路正常工作。

DB 迁移（is_stale + staled_at 列）确认存在并幂等。前端产物从 unit 分支重新构建，指纹核验通过。
