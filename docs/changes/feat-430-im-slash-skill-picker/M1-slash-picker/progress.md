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

- Context: design-review 核实——群聊 MENTION 策略下 `_should_process`(:258) 先于 `_is_stop_command`(:283)，裸 /stop 不命中 mention → return None，永不到 stop 处理（drift：canonical gateway spec 已声明"控制命令触发"）。另：放行后每个群成员都进 stop 处理，未运行的会发 no-op ack 噪声（spec 幂等/无副作用）。
- Decision: ① `_should_process` 开头加 `if message.text.strip()=="/stop": return True`（仅裸 /stop，置于 is_group 分支前，单聊本就 True 无影响）；② `_handle_stop_command` 无 active run 分支：`if message.is_group` 时返回 reply_text="" / outbound=None（不发 ack），单聊保留"当前没有正在执行的操作"友好 ack。
- Rationale: 决策4——群聊 /stop 是纯文本广播、各 agent 幂等响应；裸 /stop 经放行后既有 `_is_stop_command`（strip @agent 后 =="/stop"）本就匹配，无需 wire-mention strip（design-review #3 已删 4①）。中断机制 `kernel.interrupt` 不动。群聊无副作用补全已 SendMessage 同步 orchestrator。
- Evidence:
  - Tests: 群聊裸 /stop（MENTION、有 active run）触发 interrupt；群聊裸 /stop（无 active run）不发 ack、不进群上下文 buffer。`pytest tests/unit/personal_assistant/` 637 passed（无回归）。
  - Entry: gateway 行为，真实入口（真栈群聊发 /stop）留 R5。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: 落 `test_gateway_stop_command.py` 两新测；既有群聊 @stop / sender prefix 测全绿。
- Rollback: revert C2（inbound_pipeline 两处改动）回到群聊裸 /stop 被 MENTION 丢弃。
- Commits: C1=test R3, C2=fix R3, C3=本次 docs

## R4 — 前端 slash-picker 组件 + message-pane 接入 + 数据获取

## R5 — live 真栈验收
