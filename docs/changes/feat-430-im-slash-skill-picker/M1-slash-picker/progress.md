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

- Context: design-review #2——群聊有人先发言时本轮是多 part，`runtime.py:556` 多 part 分支把 `effective_user_text` 重取末 part 原始渲染，绕过 :451 的 rewrite；且 `^\s*/skill:` 锚对带 `[sender] ` 前缀的命令不匹配。只改正则不改 part 选取 = false-fix（单条 /skill 测过、群里有 buffered 就静默失效）。
- Decision: ① `_SKILL_COMMAND_PATTERN` 加可选 `(?P<prefix>\[[^\]]*\]\s*)?`，命中时把 prefix 原样拼回重写结果前；② `runtime.py` 多 part 分支 `effective_user_text = rewrite_skill_command(render_user_text(last_part))`，命令总在末 part（当前消息）故对末 part 重写即命中。
- Rationale: 正则只认"可选前导 `[..]` 标注段"、不解析其内容（决策5：内核命令解析的产品无关约定，kernel 不知道里面是 sender）。文本-only 多 part 走 `user_text` 通路（`render_user_content_parts` 对纯文本返 None），故对 `effective_user_text` 重写即作用于喂给 LLM 的消息。修的是内核多 part 通用缺陷（非群聊特殊对待）。
- Evidence:
  - Tests: contract 4 新测（保留 `[Alice]` 前缀、无 args、非命令不动）+ runtime 多 part 末 part /skill 重写测（断言 buffered part 不动、命令 part 被重写、原始命令不达 provider）；`pytest` 33 passed。
  - Entry: kernel 行为，真实入口（群聊真发 /skill）留 R5。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: 多 part 测即 design-review #2 的防 false-fix 回归。
- Rollback: revert C2（skill_commands + runtime 两文件改动）。
- Commits: C1=test R2, C2=fix R2, C3=本次 docs

## R3 — gateway 群聊裸 /stop 放行 + 幂等无副作用

## R4 — 前端 slash-picker 组件 + message-pane 接入 + 数据获取

## R5 — live 真栈验收
