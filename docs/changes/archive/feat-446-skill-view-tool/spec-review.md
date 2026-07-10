# Spec Review: feat-446-skill-view-tool

**结论**: Follow-up Edits Applied

本轮 spec 已补齐 review 中合理的用户旅程与边界合约。用户确认同名 skill 应按既有优先级静默命中，因此不采用“名称不唯一失败”方案。

## 已处理

| Review 点 | 当前合约 |
|---|---|
| `skill_view` name-only 解析 | 使用与 `<available_skills>` / `/skill:` 候选一致的 resolver；同名按 search root 优先级读取第一项，返回 `location` 供审计；无 `file_path` 参数。 |
| stale / archived 可见性 | stale 仍可见且读取后恢复 active；archived 默认退出 `<available_skills>` 和 `/skill:`，日常 `skill_view` 按找不到处理。 |
| 手工 skill 保护 | Curator 只管 F3/F4 自动 skill；F1/F2/manual/unknown 不被自动 stale/archive，历史缺 source 的按 unknown 保护。 |
| F4 自动 patch 边界 | 只有 F3/F4 自动 skill 可在 `uses_since_last_B` 越线后触发 batch；F1/F2/manual/unknown 不自动 patch。 |
| F4 触发时机 | `skill_view` 成功计数越线后即时 enqueue，不等待 7 天 Curator。 |
| 历史会话蒸馏 transcript 输入 | IM 预填完整 `source_jsonl_paths`；用户发送的是普通聊天消息；Gateway 不解析、不校验、不注入 transcript。agent 在蒸馏 skill 指导下读取 JSONL，任一 source 不可读则整体失败不部分生成。 |
| 历史会话蒸馏写入范围 | IM 弹窗选择 `target_scope` 并预填进普通消息；`conversation-skill-distiller` 指导 agent 读取该字段，并通过 `skill_manage(create, scope=...)` 写 agent 或 PA root。 |
| 使用统计幂等 | 同一次 `{session_id, tool_call_id}` 重放不重复增加 use_count / session_refs。 |
| compaction survival | 压缩时重新读取当前 SKILL.md，并以 `<system-reminder>` 注入；metadata 可在 resume 后恢复。 |

## 非目标

- 不做 pinned skill / pin-unpin。
- 不做 archived restore UI。
- 不做专门 SKILL.md 草稿预览/确认 UI；用户可在输入框要求先展示草稿。
- 不做 F4 自动 patch 手工 skill。
- 不做 `skill_view(file_path=...)` 或独立 `skills_list` 工具。
