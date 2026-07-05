# feat-446 Design Review

**结论**: Follow-up Edits Applied

本轮根据 review 意见回补了 design/spec 的接口闭合点。用户已明确决策：同名 skill 按现有 search root 优先级静默命中，不做 ambiguity error；该项不再作为问题。

## 处理结果

| Review 点 | 处理 |
|---|---|
| `skill_view` 同名查找 | 不采纳原 review。spec/design/kernel delta 已改为按既有 `<available_skills>` / `/skill:` 候选优先级读取第一项，并通过 `location` 审计实际命中路径。 |
| 历史会话蒸馏 `target_scope -> skill root` 未闭合 | 已采纳。design 规定 `skill_manage(create)` 增加 `scope: "agent"|"pa"`，默认 agent；弹窗选择出的 `target_scope` 放在输入框普通消息中，由 `conversation-skill-distiller` 指导 agent 调用 `skill_manage(create, scope=...)`；Gateway 不解析写入范围。kernel/IM delta 已补。 |
| Compaction 存活保存旧 content | 已采纳。design 改为 `skill_view` 注册 `{name, location, root_id, invoked_at}`，compaction 时按 location 重新读取当前 SKILL.md，并以 `<system-reminder>` synthetic user message 注入；写入与 load metadata 白名单都要求包含 `is_skill_reinjection` / `skill_reinjection_refs`。kernel delta 已补。 |
| F4 trigger 被 7 天 Curator 门控 | 已采纳。design 改为 `skill_view` 成功后 `bump_use()` 越线即时返回 `F4Trigger` 并由 runtime enqueue；Curator 只负责 stale/archive 生命周期扫描。kernel delta 和 M2 exit 已补。 |
| `.usage.json.source` 归因不可靠 | 已采纳。design 规定 source 不由模型传参，`skill_manage(create)` 只从受控 session/fork metadata 推导：默认 F1，F2 Gateway metadata，F3 self_improvement fork metadata，F4 batch fork metadata。 |
| 使用统计重放幂等 | 已采纳。usage 数据模型增加 `tool_call_id` 与 `recent_call_keys`，`bump_use()` 对 `{session_id}:{tool_call_id}` 幂等。kernel delta 和 M1 exit 已补。 |
| delta-spec 漏契约 | 已采纳。kernel delta 补 stale/archived 可见集合、create scope、F4 越线触发、幂等和 compaction 当前重读；IM `run_state` 改为 MODIFIED conversation list/sync 响应；Gateway delta 补 F2 metadata 注入。 |

## 当前剩余风险

- PA 产品级 skill root 的真实来源需要 worker 在实现时对齐现有 product config；design 已要求 root 不可用时失败不回退。
- F4 background enqueue 的运行队列/去重集合由 runtime 持有，worker 需要避免 core import platform；design 已要求 core 只返回 `F4Trigger` 数据。
- `skill_manage(create, scope=pa)` 会扩大写入面，测试需要覆盖权限/未配置 root/默认 scope 三类行为。
