# feat-430-M1 — Progress

> 派发包补充：群聊「/stop 未运行 agent 幂等无副作用」为 spec 场景必要补全（design 决策 4 仅写 _should_process 放行）；已向 orchestrator 同步判断（在群聊 no-active-run 分支抑制 no-op ack，单聊不变）。

## R1 — 后端 location 四层只读透传 + 前端 type

- Context: 群聊按真实路径区分同名 skill（Q7）需 skill 的 SKILL.md 路径端到端可见；现状 `SkillInfo` 在 sdk 边界即丢 location。
- Decision: 五层各加只读可空 `location` 字段：`SkillMetadata.location`(已有,core) → `SkillInfo.location:str|None`(sdk dto) → kernel `list_skills` 用 `str(s.location)` 填充 → `_skills_from_kernel` 透传进 payload → IM `AllowlistOptionResponse.location` + `coerce_allowlist_options` 透传 → 前端 `AgentAllowlistOption.location` + `normalizeAllowlistOptions` 透传。
- Rationale: 沿用既有 description 通路，只加可空字段，无行为变更（决策 3）。`getattr(s,"location",None)` 容错。location 在 kernel sdk 层即转 str，跨包不传 Path。
- Evidence:
  - Tests: `pytest -m "not e2e"` R1 相关 33 passed（kernel list_skills location、reporter agent capabilities location、IM coerce location 透传/缺省 None、baseline golden）。
  - Entry: 后端字段透传层，真实入口验证留 R5 真栈（capabilities API 真返回 location）。
  - Frontend State Matrix: N/A（R1 仅类型字段）
  - Browser QA: N/A
  - E2E/Regression: 回归落 `test_capability_payload_baseline.py`——golden byte-identity 对 name/description 保持，location 因是易变绝对路径单独断言 `endswith("<name>/SKILL.md")`（避免烤死宿主路径）。
  - Visual/Interaction: N/A
- Rollback: revert C2 `900fde7d` 回到无 location 透传；测试 revert `fc749eea`。
- Commits: C1=fc749eea, C2=900fde7d, C3=(本次 docs)

## R2 — kernel `/skill` 多 part 重写 + 正则认前缀

## R3 — gateway 群聊裸 /stop 放行 + 幂等无副作用

## R4 — 前端 slash-picker 组件 + message-pane 接入 + 数据获取

## R5 — live 真栈验收
