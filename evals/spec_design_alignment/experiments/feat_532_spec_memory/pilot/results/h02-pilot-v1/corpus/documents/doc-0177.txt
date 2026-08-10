# refactor-403: orchestrator 退出时省掉批量 shutdown，避免 rate limit

## Relations

- Related: bugfix-402 (同 session 内发现的 rate limit 问题)
- Related: change-orchestrator skill

## 原始诉求

> 最后不要做 shutdown_request，不要做 team delete，不然太费 token 了。

对话中实测：unit-bugfix-402 退出阶段对 28 个子 agent 批量发 `shutdown_request` +
`TeamDelete`，后半批 14 个 agent 的 prompt cache 全冷，每个重建 ~639K tokens，
直接导致 rate limit（session 被截断）。

## 澄清记录

无交互澄清——本变更是对话中做实验后回顾性记录，结论已在实验中收敛。

## 现状痛点

**Claude Code 版本: 2.1.170**

`change-orchestrator` §0.14 原要求：

> unit 完成(§7.5 退出前)`TeamDelete` 清理。

实际成本：

| 指标 | 数值 |
|---|---|
| 子 agent 数 | 28 个 |
| 每 agent cache_create(冷启动) | ~639,127 tokens |
| 冷启动 agent 数 | 14 个(v-xxx / cr2-xxx 组) |
| 仅 shutdown 阶段消耗 | ~9M tokens(cache_create) |
| 结果 | rate limit，session 被截断 |

**数据来源**：session `c6067fb9-54b7-483a-9c13-1a050e188aa1`
(jsonl: `/Users/czj/.claude/projects/-Users-czj-Repos-nano-multiagent/c6067fb9-54b7-483a-9c13-1a050e188aa1.jsonl`)

**实验验证**（本 session 内完成，完整推理链）：

**方案 1：及时 `shutdown_request`**（agent 用完即关，省资源）

1. 建 `shutdown-test` team，spawn `test-agent`
2. 正常对话 → 通信 OK
3. 发 `shutdown_request` → agent 回 `shutdown_approved` → `teammate_terminated` → 从 team members 列表移除
4. **再发消息 → `SendMessage` 投递成功，但消息卡在 inbox（`read: false`），agent 已死，永无响应**

**结论：shutdown_request 后 agent 彻底关闭，后续无法复用。** 但 orchestrator 的 PR feedback 处理（§7.5）需要 `SendMessage` 唤醒已有 agent——关了就用不了。此方案不可行。

**方案 2：不 shutdown，直接 `TeamDelete`**（跳过逐个关，一键清 team）

`TeamDelete` 会检查 active members，有存活 agent 时直接拒绝：

> Cannot cleanup team with N active member(s). Use requestShutdown to gracefully terminate teammates first.

**joker-1 异常 case**：某 agent 收到 `shutdown_request` 后不响应（不发
`shutdown_response`），持续发 `idle_notification`，`TeamDelete` 永远删不掉，
只能手动 `rm -rf` 目录绕过。此方案也不可行。

**最终方案：不 shutdown，也不 TeamDelete**

- 子 agent 自然结束（完成工作后自行 idle → 最终被系统回收）
- team 文件留在 `~/.claude/teams/` 占用极小
- PR feedback 处理时 team 还在，可正常 `SendMessage` 复用 agent
- 用户手动 `rm -rf` 或下次 `TeamCreate` 覆盖同名 team

## 目标状态

orchestrator 退出时**不再**做以下动作：

1. 不发 `shutdown_request` 给子 agent
2. 不调用 `TeamDelete`

退出时只做：
- sweep 服务 PID（已有，§7.5 / §0.16）
- `git worktree remove` 清理 worktree（已有，§7.5）

team 文件残留策略：
- `~/.claude/teams/<team-name>/` 占用极小，不主动清理
- 用户手动 `rm -rf` 或下次启动 orchestrator 覆盖同名 team

## 用户侧验收标准（不变性）

无用户可观察变化——本变更只影响 orchestrator 内部退出流程，不改变任何产品
行为。验证点：

### Requirement: orchestrator 正常完成 unit

#### Scenario: 标准退出路径
- **WHEN** orchestrator 按流程完成所有 milestone、reviewer pass、CI 绿
- **THEN** 输出 PR URL 并退出，与变更前一致

#### Scenario: PR 反馈处理（复用 team）
- **WHEN** PR 被 request changes，用户调 orchestrator "address PR <url>"
- **THEN** orchestrator 能复用同一 team 的上下文继续处理，与变更前一致

### Requirement: 残留 team 不干扰后续工作

#### Scenario: 同名 team 复用
- **WHEN** 用户下次启动 orchestrator（同 unit 或不同 unit）
- **THEN** `TeamCreate` 覆盖同名 team 不报错，orchestrator 正常启动

## 影响范围

- `change-orchestrator` skill：§0.14 删除 `TeamDelete` 要求
- 退出流程：§7.5 删除 `TeamDelete` 调用（如有）
- 无代码变更——纯 skill 文档调整

## 迁移与回滚策略

- **行为不变**：orchestrator 的核心功能（派 worker、reviewer、提 PR）完全不变
- **回滚**：如需恢复旧行为，在 §0.14 加回 `TeamDelete` 要求即可
- **副作用**：`~/.claude/teams/` 下会累积已完成的 unit team 目录，需用户定期手动清理
