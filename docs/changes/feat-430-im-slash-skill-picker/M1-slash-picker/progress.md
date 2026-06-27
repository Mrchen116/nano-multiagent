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
- 幂等 ack 抑制（design 未明写、据 spec Scenario「群聊里 /stop 对未在运行的 agent 幂等(无报错、无副作用)」补的实现，**orchestrator 已批准**，非新 design 决策）：群聊 /stop 经 IM 广播到每个成员（各自 relay），未运行的成员若仍发「当前没有正在执行的操作。」会产生 N-1 条噪声气泡 = spec 所禁的副作用。故仅在「群聊 + 无 active run」分支静默。三点边界（lead 确认）：① 单聊无运行时仍返回友好 ack「当前没有正在执行的操作。」（canonical 契约 Scenario，不动）；② 群聊中真被停的运行 agent 仍发「已停止当前操作。」；③ 群聊全员都没跑 → 全静默（可接受的无副作用）。
- Evidence:
  - Tests: 群聊裸 /stop（MENTION、有 active run）触发 interrupt；群聊裸 /stop（无 active run）不发 ack、不进群上下文 buffer；**群聊多 agent（部分在跑部分不在跑）→ 只有在跑的被停 + 无噪声 ack**（`test_bare_stop_in_group_multi_agent_stops_only_running_no_noise`）。`pytest tests/unit/personal_assistant/` 全 passed（无回归）。
  - Entry: gateway 行为，真实入口（真栈群聊发 /stop）见 R5（plato MENTION 运行中裸 /stop 中断、未运行 hume 无 no-op ack）。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: 落 `test_gateway_stop_command.py` 三新测；既有群聊 @stop / sender prefix 测全绿。
- Rollback: revert C2（inbound_pipeline 两处改动）回到群聊裸 /stop 被 MENTION 丢弃。
- Commits: C1=test R3, C2=fix R3, C3=docs；fix-followup：多 agent 幂等配对测试 + 记账（本次）

## R4 — 前端 slash-picker 组件 + message-pane 接入 + 数据获取

- Context: composer 现状只认 `@`（mention），`/` 无处理。需新建 slash picker（决策1 照搬 mention 交互、独立组件），数据 = config 白名单 ∩ capabilities（决策2），群聊按 location 去重并集（决策3/Q7）。
- Decision:
  - `slash-candidates.ts`（纯函数，可测）：`resolveEnabledSkills`（whitelist∩caps，空 whitelist=全量 runtime parity）、`buildSlashSkills`（按 location 去重合并 fromAgents，location 为 null 降级按 name）、`matchSlashTrigger`（`^/(skill:)?([^\s/]*)$`，仅行首触发、支持 `/skill:` 纠错）。
  - `slash-picker.tsx`：内部建 `/stop` 命令 + 前缀过滤（skillMode 只过滤 skills）；键盘 ↑↓ 循环/Enter Tab 确认/Esc onClose，highlight `scrollIntoView({block:nearest})`（jsdom 缺该 API 故可选链）；鼠标 mousedown+preventDefault 选中、mouseenter 仅切高亮；空态文案；群聊 `来自 X` 来源标注；description 单行 ellipsis（CSS）。
  - `message-pane.tsx`：`slashMatch` 仅 mentionQuery 为 null 且未 dismissed 时触发（与 @ 互斥）；选中补 `/skill:name `/`/stop `（尾随空格、rAF setSelectionRange 末尾、保焦）；Esc/点面板外 setSlashDismissed(保留 `/` 文本)、再输入重开（changeDraft reset）；单聊群聊都可用。
  - `chat-workspace-page.tsx`：`conversationAgents` → react-query（keyed by agent ids、staleTime 60s）并发拉每 agent config+capabilities，组装 slashSkills 传 MessagePane。
  - `im-agent-config-api.ts`：导出 `normalizeAllowlistOptions` 供 chat page 归一化 capabilities wire（含 location）。
- Rationale: 数据组装抽成纯函数单测覆盖交集/空白名单/location 去重三类（防 design-review #1 空 picker / 全量误列）；picker 交互照 design checklist + 原型逐条落（hover 不重建 DOM 防点不中）。
- Evidence:
  - Tests: `npx vitest run` 全绿（62 files / 528→ 现 +20 新测：slash-candidates 11、slash-picker 9、message-pane slash 5；message-pane 共 54）。`npm run build`（tsc -b + vite）通过。
  - Entry: 前端真实入口浏览器验收 → R5。
  - Frontend State Matrix: default（弹面板）/empty(`/xyz` 空态)/loading(skills 拉取中面板可仅 /stop)/error(capabilities 失败 react-query 降级 slashSkills=[]，picker 仍出 /stop)/long-content(desc 单行截断 CSS)/missing(location null 降级 name 去重)/mobile+desktop（面板锚 composer 上方 max-height min(50vh,320px) 内滚）已覆盖；disabled/submitting/permission/dark = N/A。
  - Browser QA: 留 R5。
  - E2E/Regression: 组件+数据+集成测试落库（critical-path）。
  - Visual/Interaction: 留 R5 截图（单聊/群聊/空态/截断/移动端）。
- Rollback: revert C2（前端 8 文件）。
- Commits: C1=test R4, C2=feat R4, C3=本次 docs

## R5 — live 真栈验收

- Context: 本 unit 改了客户端面 + 群聊命令真生效，必须真栈端到端（IM+Gateway+真 LLM proxy）自证，不能只靠 pytest/stub。
- Setup: `scripts/e2e-up.sh` 起 ephemeral IM(57353)+Gateway(真 agents plato/hume/luban,带 skills) + Vite(57469) proxy 指向 ephemeral IM；真 LLM proxy :4000。playwright(chromium) 驱动浏览器，登录 nano/nano1234。
- Evidence（全部真栈、跑到用户可见结果）:
  - **Slash picker UI（单聊+群聊）**: 浏览器敲 `/` 弹面板，COMMANDS(`/stop`+描述)+SKILLS；`/skill:change` 前缀过滤只剩 change-* skills；选中 → composer 变 `/skill:autoplan `（尾随空格）；`/zzznope` → 空态「No matching slash items」；群聊每行「from plato, hume」来源标注；`console error = []`。截图 r5-direct-slash / r5-group-slash-* / r5-group-empty。
  - **交集过滤（防 design-review #1 空/全量）live**: PATCH plato 白名单=[autoplan,deep-research]，单聊敲 `/` → 只出 `/stop`+`autoplan`（autoplan 既启用又被发现；deep-research 启用但未在 workspace 发现故不出；**非全 52、非空**）。证明 config∩capabilities 真生效。
  - **location 透传 live**: `GET /im/v1/agents/plato/capabilities` 每个 skill 带真实 `location`，如 `/Users/czj/.gstack/repos/gstack/.agents/skills/gstack-autoplan/SKILL.md`，端到端非空。
  - **群聊 /skill 真生效**: 群里发纯 `/skill:autoplan ...` → plato 回复「我会先读取 autoplan skill 文件…」并就 autoplan 语义作答；LLM proxy req log 含 `Use the 'autoplan' skill for this request`，证明 kernel rewrite 文本真到达模型。
  - **群聊 buffered 多 part /skill 真生效（design-review #2 防 false-fix）**: plato+hume ALWAYS，先暖场制造群上下文，再发 `/skill:autoplan 简短说明`。proxy req log（sess c788bdd4）显示该轮**含多个 user part**（buffered hume 上下文 + 当前命令），命令 part 被重写为 `[Test User] Use the "autoplan" skill for this request.\nUser input:\n简短说明`——**多 part 下命令所在 part 仍重写、sender 前缀保留**。
  - **群聊裸 /stop 真生效（绕 MENTION）**: plato 设 `group_reply_policy=MENTION`（仅@才响应），`@plato` 起长任务（status=running），发**裸 `/stop`**（不 @）→ plato run 中断，回复「已停止当前操作。」。证明 `_should_process` 放行裸 /stop 绕过 @ 门控 + interrupt 生效。
  - **群聊 /stop 幂等无副作用**: 同次 /stop 后，未运行的 hume **未发**「当前没有正在执行的操作」ack（消息流中 no-op ack 计数=0）。
  - E2E/Regression: 所有上述行为有单测/组件测试/集成测试落库（R1-R4）；live 证据为一次性验收（截图在 scratchpad、proxy log 在 LLM_PROXY/logs，不入回归套件）。
  - 全测试树: `pytest -m "not e2e"` 3047 passed（含 im_service）；前端 `vitest` 全绿 + `npm run build` 通过；`ruff check`+`ruff format --check` 全绿。
- 服务清理: `scripts/e2e-down.sh` + kill vite，pid 全清。
- Rollback: N/A（验收，无代码改动）。
- Commits: 验收无新代码 commit（R1-R4 实现已提交）。

## Fix Round 2 — 验收三闸反馈（reviewer/code-review/verifier）

复用原 worker 上下文（同 milestone worktree）。改在 milestone 分支、集成交 orchestrator。所有代码改动配测试。

### P0 BLOCKING（reviewer）：白名单交集失效——picker 显示全部 52 skill
- 根因：前端 `getAgentConfig` 硬编码 `?source=mirror`；网关播种的 agent 经 node.register 只上报 agent_id，IM mirror 的 `profile.skills` 天然为空 → 触发「空白名单=全量」回退。R5 的 PATCH 自测绕过了前端实际调的 mirror endpoint 故未暴露。
- 架构正确层：agent「已启用 skills」的真源是**网关 live 配置**（`request_agent_config` → `_merge_live_agent_profile` 已携带 skills），不是 register 播种的空 mirror。修 mirror 同步需改 node.register 协议（跨包、大改、出本 unit 范围）。故选**前端用 `source=live`**（决策按纯架构最优）。
- 改动：`im-agent-config-api.ts` `getAgentConfig(agentId, source="mirror"|"live"="mirror")` 参数化；`chat-workspace-page` picker 拉取改 `getAgentConfig(a.agent_id, "live")`。
- live 真栈验证（前端实际 endpoint，非 PATCH/非绕 endpoint）：plato 网关配置 skills=[change-spec-author/change-design-author/change-orchestrator]。`config?source=mirror`→`[]`，`config?source=live`→那 3 个；浏览器单聊敲 `/` → picker 只出 `/stop`+那 3 个（**非全 52、非空**），`/skill:auto`→空。console error=0。

### P1 CRITICAL（code review）
1. **多 part `/skill` rewrite 混乱**（runtime.py 451 全文 + 586 last_part 两处打架）：① `/skill+image` 时 last_part=image，586 落空→skill 静默失效；② 451 全文 rewrite 把 `[image:placeholder]` 当 `[..]` 前缀/args 折入→污染 user_msg.content。改：新增 `_rewrite_skill_command_in_parts`——只对**含命令的那个 text part**做 rewrite；单 part 走原 451（保 hook 语义），多 part 走 part 级 rewrite 后再 split，清掉 586 的 last_part rewrite。测试：`test_skill_command_with_trailing_image_still_rewritten`（命令非末 part 仍生效+image 保留）、`test_multipart_skill_command_does_not_fold_image_into_user_input`（image 不被折进 User input）。live：群聊暖场制造多 part 后 `/skill:change-orchestrator`，proxy req log 含 `Use the "change-orchestrator" skill for this request` + agent 按 skill 行为。
2. **IME 误选**：slash-picker window keydown 加 `if (e.isComposing) return`。测试 `ignores Enter while IME is composing`。
3. **高亮越界/选错**：reset effect 改依赖候选**内容签名**（`kind:name` join）非长度；`onSelect` 前 `const choice=candidates[highlighted]; if(choice)` 守卫。测试 `resets the highlight when candidate content changes at the same length`。
4. **一个 agent 拖垮 picker**：`chat-workspace-page` slashSkillsQuery 外层 `Promise.all`→`Promise.allSettled`，过滤失败 agent。
5. **create_session 副作用**：群聊裸 /stop 的 no-active-run 短路移到 `_ensure_binding` 之前（idle 群成员不建空 session）。测试断言 `create_session_calls` 不含 idle agent。

### P2（cleanup）
6. display name 含 `]`：接受+注释约束（不用 greedy，结构化已被 design-review #4 否决）。
7. slash-picker `itemRefs.current=[]` 出 render 体：改 `useId`+元素 id（scrollIntoView 走 getElementById；同时落地 P2.11 `aria-activedescendant`）。
8. `getattr(s,'location',None)`→`str(s.location)`(kernel) / `skill.location`(reporter)（非空 Path 去过度防御）。
9. tasks.md 6 条退出标准勾 `[x]`。
10. e2e-critical-paths.md 「已知缺口」表登记群聊裸 /stop 绕 MENTION 一行（单测+手工 live 覆盖，无自动化 Gateway e2e）。
11. slash-picker listbox 补 `aria-activedescendant`（测试 `exposes aria-activedescendant pointing at the active option`）。
12. Tab 确认选中测试 `selects the highlighted candidate on Tab`。

### 补显式测试（reviewer inconclusive）
- R1-S3 输入框中间 `/` 不触发：`message-pane.test` `does not open the picker when '/' is in the middle of the text`（已有）。
- R5-S3 编辑 `/skill:doc`→`/skill:d` 重过滤纠错：`message-pane.test` `re-filters skills when editing a /skill: prefix for correction`。

### 门禁
后端 `pytest -m "not e2e"`（相关全跑）绿；前端 `vitest` 540 passed + `npm run build` 通过；`ruff check`+`ruff format --check` 全绿。env_caveats：none（P0/P1.1/stop 均真栈 live 复验通过）。
