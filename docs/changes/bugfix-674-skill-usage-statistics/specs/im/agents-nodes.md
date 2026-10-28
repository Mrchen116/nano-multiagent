# Delta: Skill 使用统计 API

Target: docs/specs/im/agents-nodes.md

## MODIFIED Requirements

### Requirement: Skill 使用统计 API

浏览器前端可按 Agent 查询 Skill 使用统计；IM 通过在线 Gateway 读取对应 Agent 的运行态使用数据，离线时以前端可处理的方式降级。使用统计独立于 Skill 自进化开关。

统计只计入新版统计逻辑启用后的新使用，并明确首次计数时间；旧版总数和调用样本不回填。按产品 Agent 归属持久累计和最近 30 个 UTC 日的趋势；最近调用引用仅为证据样本，截断不得改变累计/趋势或其他 Agent 的记录。窗口及统计起点之前的日期不显示为已确认零调用。

#### Scenario: 关闭自进化时统计正常使用
- WHEN Agent 关闭 Skill 自进化后使用同一 Skill 超过 60 次
- THEN 新累计和对应日期趋势完整计数并跨重启保留，仍遵循调用去重。

#### Scenario: 共享 Skill 分别计数
- WHEN 多个 Agent 使用共享 Skill，早期调用引用已被后续样本挤出
- THEN 每个 Agent 的新统计保持，仅展示自身新调用引用。

#### Scenario: 旧记录与新统计起点
- WHEN 旧 Skill 尚未产生新版计数
- THEN 显示尚无新调用，不把旧累计或截断样本当成新统计。
- WHEN 产生新使用
- THEN 从实际首次新使用起累计，明确展示统计起点与 UTC 日期窗口。

#### Scenario: 查询 agent 的 skill 使用统计
- WHEN 浏览器前端请求 GET /im/v1/agents/:agentId/skills/usage 或设置页的 usage section
- THEN 返回该 Agent 的 Skill 使用数据，包含 name、source、state、use_count、last_used_at、session_refs 以及新统计起点/日期窗口。
- AND source 至少支持用户创建、历史会话蒸馏、自动创建、自动批量优化与 unknown。

#### Scenario: agent 离线时查询 skill 统计
- WHEN Agent 不在线或 Gateway 无法到达
- THEN API 保留现有离线/缓存数据语义，前端明确数据来源和离线提示而非崩溃。
