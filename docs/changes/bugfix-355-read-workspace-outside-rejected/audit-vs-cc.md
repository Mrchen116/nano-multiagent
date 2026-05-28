# refactor-353 ↔ CC 系统性对照(仅 auto + dangerously 两个 mode)

> 本表是 bugfix-355 的事实参考,产出于澄清阶段对源码的核实(2026-05-16)。
> Mode 范围按 Q4 答复:本仓只做 `auto` + `dangerously-skip-permissions`,其他 mode 不做。

## CC 源码版本

`~/Repos/opensource-hub/claude-code/` — 与本仓 AGENTS.md 声明的参考项目一致。
关键文件:
- `src/utils/permissions/permissions.ts` — 主流程 `hasPermissionsToUseTool` / `hasPermissionsToUseToolInner`
- `src/utils/permissions/filesystem.ts` — `checkReadPermissionForTool` / `checkWritePermissionForTool` / `checkPathSafetyForAutoEdit`
- `src/utils/permissions/classifierDecision.ts` — `SAFE_YOLO_ALLOWLISTED_TOOLS`
- `src/utils/permissions/permissionSetup.ts` — `initialPermissionModeFromCLI`(`dangerouslySkipPermissions` → `bypassPermissions`)
- `src/types/permissions.ts` — `PermissionMode` 枚举
- `src/tools/FileReadTool/FileReadTool.ts` — Read 工具自带 `checkPermissions` 路由

## 对照矩阵

| 面 | CC 行为(带源码引用) | 本仓现状(带源码引用) | 一致? |
|---|---|---|---|
| **dangerously / bypassPermissions 入口短路** | `permissions.ts:1268-1281` mode 维度 short-circuit allow,覆盖 tool checkPermissions | `auto_mode_gate.py:713-717` hook 返回 None / `{allow_unlisted:true}`,tool 自己的 safety 检查仍跑 | **部分对齐** |
| → write/edit 工作区外 + dangerously | bypass allow | `safety.py:269-282 resolve_path` 已移除硬错,只 normalize → hook 让路 → write 发生 | **对齐** |
| → **Read 工作区外 + dangerously** | bypass allow(`checkReadPermissionForTool` 返回 ask → mode 在 permissions.ts:1268 覆盖为 allow) | `safety.py:306-325 resolve_read_path` 仍硬 raise `path is outside repo sandbox` | **❌ 不对齐**(Gap-R1) |
| **auto 模式 safe-allowlist 概念** | `classifierDecision.ts:56-94 SAFE_YOLO_ALLOWLISTED_TOOLS` 名单 | `auto_mode_gate.py:163-179 SAFE_TOOL_ALLOWLIST` 名单 | **概念对齐**,清单有差异(详见 Gap-S1/S2/S3) |
| → Read 在 safe-allowlist | ✓ `FILE_READ_TOOL_NAME` 在 SAFE_YOLO_ALLOWLISTED_TOOLS | ✓ `read` 在 SAFE_TOOL_ALLOWLIST | **对齐** |
| → Task 系工具在 safe-allowlist | ✓ TASK_CREATE/GET/UPDATE/LIST/STOP/OUTPUT 都在 | ✓ task_create/get/update/list/stop/output 都在 | **对齐** |
| → SEND_MESSAGE 在 safe-allowlist | ✓ `SEND_MESSAGE_TOOL_NAME` 在 SAFE_YOLO_ALLOWLISTED_TOOLS | ✓ `send_message` 在 SAFE_TOOL_ALLOWLIST | **对齐** |
| → **WebFetch 在 safe-allowlist** | ❌ 不在;**走自己的 `checkPermissions`**(preapproved host + hostname rule,`WebFetchTool.ts:104-`) | ✓ `web_fetch` 在 SAFE_TOOL_ALLOWLIST(短路 classifier) | **❌ 不对齐**(Gap-S1) |
| → **WebSearch 在 safe-allowlist** | ❌ 不在;**走自己的 `checkPermissions`**(`WebSearchTool.ts:101-`) | ✓ `web_search` 在 SAFE_TOOL_ALLOWLIST | **❌ 不对齐**(Gap-S2) |
| → **AgentTool 在 safe-allowlist** | 外部用户:**所有 mode 都 allow**(`AgentTool.tsx:1708 return {behavior: 'allow'}`,`USER_TYPE === 'ant'` 分支被外部 build 的 DCE 移除);Ant 内部 + auto mode:走 classifier。`isReadOnly()=true` 注释明示"delegates permission checks to its underlying tools" | ✓ `agent` 在 SAFE_TOOL_ALLOWLIST,所有 mode 都 allow | **✓ 对齐 CC 外部用户行为**(D2 已决:不走 Ant 内部行为) |
| → 命中 safe-allowlist 的工具行为 | `permissions.ts:660-686` 直接 allow,skip classifier | `auto_mode_gate.py:735-736` hook return None(pass through hook,tool 自己的 safety check 仍跑) | **部分对齐** |
| → **auto 模式 Read 工作区外** | safe-allowlist 命中 → 直接 allow | hook return None → 但 `read.py:53` 调 `resolve_read_path` 硬 raise | **❌ 不对齐**(Gap-R1) |
| **auto 模式 write/edit 工作区外** | tool checkPermissions 返回 ask → 后处理 acceptEdits fast-path 失败 → write 不在 safe-allowlist → 跑 yolo classifier → allow/deny/ask | `auto_mode_gate.py:719-735 _detect_outside_workspace_path` 路由到 classifier 跑分类 | **对齐**(实现路径不同,效果等价) |
| **outside-workspace path hint 给 classifier** | `yoloClassifier.ts:1487-1495 formatActionForClassifier` 原样 tool_use,无 OUTSIDE 包装;由 system prompt 的 `BLOCK — File Write Outside CWD` 规则驱动 classifier 自判 | `auto_mode_gate.py:777-786` 显式塞 `NOTE: target path '...' is OUTSIDE...` | **❌ 不对齐**(Gap-W2,Q6 已确认要做 — 移除本仓 NOTE 包装) |
| **classifier 系统提示词 / 两阶段 XML** | CC `yoloClassifier.ts` + `buildYoloSystemPrompt` 两阶段 XML | `auto_mode_gate.py:46-157` pixel-perfect 复制,注释明示 | **对齐** |
| **classifier deny-limit** | `permissions.ts:990-1054 denialState` consecutive + total denials,超 limit fallback to prompt | `broker.is_deny_limit_exceeded` + `config.deny_limit`,超限直接 ask | **概念对齐**,语义略简(只有 consecutive,无 total) |
| **session-level allow** | `filesystem.ts:1267` session destination 的 alwaysAllowRules | `broker.is_session_allowed(session_id, tool_name)` | **对齐** |
| **ask 选项**(Allow once / session / Deny) | `permissions.ts` 卡片 + suggestions(Allow once / Allow session / Deny) | refactor-353 design 决策 5 复用 bash `_handle_ask` 选项构造 | **对齐** |
| **unattended_fallback**(heartbeat / background_task 无人值守时跳过 ask) | `shouldAvoidPermissionPrompts` headless 模式 deny 或 `throw AbortError` | `config.unattended_fallback = "allow" / "deny"`,heartbeat / background_task 自动决策 | **概念对齐**,本仓更细(可配置 allow/deny;CC headless 只能 deny+abort) |
| **危险目录保护**(write/edit) | `filesystem.ts:57-79 DANGEROUS_FILES`+`DANGEROUS_DIRECTORIES`(`.git/.vscode/.idea/.claude/.bashrc/.zshrc/.profile/.gitconfig/...`),write 在 bypass 下仍 ask | 无该机制 | **❌ 不对齐**(Gap-W1,本期已确认要做,Q5 答"和CC一致") |
| **Read 的危险目录保护** | CC 不做(`checkReadPermissionForTool` 不调 `checkPathSafetyForAutoEdit`) | 不做 | **对齐**(都不做) |

## 真实 Gap(可纳入本期)

### Gap-R1: Read 工作区外被 `safety.resolve_read_path` 硬 raise

- 跟 CC auto safe-allowlist 不对齐(应直接 allow)
- 跟 CC dangerously mode 短路不对齐(应 bypass allow)
- 修法:`resolve_read_path` 移除工作区边界检查(仅 normalize);Read 工作区外的决策权交给 `auto_mode_gate`(Read 已在 SAFE_TOOL_ALLOWLIST → hook 直接 pass through → 在 auto / dangerously 两种 mode 下都 allow)
- 文件触及:`src/agent/platform/tools/safety.py`、`src/agent/platform/tools/builtins/read.py`、相关单测

### Gap-R2: refactor-353 spec.md Q1 / design.md 决策 2 文档错误

- spec.md Q1 把"CC read 默认放行"作为 read 不动的依据,但没区分 mode,实际只在 auto mode 下因为 safe-allowlist 而 allow
- design.md 决策 2 把"workspace boundary check stays in safety.py as a guardrail" 当作对齐 CC,实际 CC 没有这个 guardrail
- 修法:在两份文档加 Changelog 行,标注被 bugfix-355 修正;在原决策旁附 corrigendum,解释 CC 实际行为

## Gap-W1: write/edit 在 dangerously 下的危险目录保护(本期是否做未定)

- CC `permissions.ts:1252-1260` 注释 "Safety checks (e.g. .git/, .claude/, .vscode/, shell configs) are bypass-immune — they must prompt even in bypassPermissions mode"
- 本仓 `auto_mode_gate.py:713-717` dangerously 下对 write/edit 直接 return None,无 safetyCheck 兜底
- 用户在 Q2 修订的"对齐 CC"答复**只覆盖 Read 方向**(用户答的就是 Read 上下文),write/edit 方向是否做这个保护未表态

## 不在本期(用户 Q4 明确)

- `default` / `acceptEdits` / `dontAsk` / `plan` / `bubble` mode — 本仓只做 auto + dangerously
- Read 的危险目录保护 — Q2 已确认对齐 CC(CC Read 不做,我们也不做)

## Gap-S1: WebFetch 错放进 SAFE_TOOL_ALLOWLIST

- CC `WebFetchTool.ts:98 isReadOnly()=true` 但**不在** `SAFE_YOLO_ALLOWLISTED_TOOLS`;`checkPermissions`(`WebFetchTool.ts:104+`)走 preapproved host 表 + hostname rule 引擎
- 本仓 `auto_mode_gate.py:167 web_fetch` 在 SAFE_TOOL_ALLOWLIST,短路 classifier
- Q7 已确认严格复刻:本期把 `web_fetch` 从 SAFE_TOOL_ALLOWLIST 移除,**新建** preapproved host 表 + hostname rule 子系统(基础设施级新增,本仓没有这套)

## Gap-S2: WebSearch 错放进 SAFE_TOOL_ALLOWLIST

- CC `WebSearchTool.ts:95 isReadOnly()=true` 但**不在** safe-allowlist;`checkPermissions`(`WebSearchTool.ts:101+`)独立逻辑
- 本仓 `auto_mode_gate.py:168 web_search` 在 SAFE_TOOL_ALLOWLIST
- Q7 已确认严格复刻:本期把 `web_search` 从 SAFE_TOOL_ALLOWLIST 移除,补独立 `checkPermissions`
- 注:本仓 `web_search` 是 **personal_assistant 产品级工具**(`src/agent/products/personal_assistant/tools/web_search.py:75 WebSearchTool`),不在 `platform/tools/builtins/`。design 阶段需决定 checkPermissions 落在哪一层(产品/平台)

## ~~Gap-S3~~(已撤销 — 对齐 CC 外部用户行为非 gap)

bugfix-355 design D2 阶段对照 CC 源码 `AgentTool.tsx:1692-1709` 后发现:

- CC AgentTool **外部用户默认就是无条件 allow**(`return { behavior: 'allow' }`)
- `USER_TYPE === 'ant' && mode === 'auto'` 才走 classifier — 这条分支由 `process.env.USER_TYPE === 'ant'` guard 控制,**外部 build 在编译期被 DCE 移除**,运行时连判断都没有
- CC 注释 `isReadOnly()=true // delegates permission checks to its underlying tools` 是设计哲学:派子 agent 这一步不检查,子 agent 自己跑 tool call 时再次过 gate
- 本仓 `agent` 放在 SAFE_TOOL_ALLOWLIST 直接 allow,**跟 CC 外部用户行为完全一致**,非 gap

spec-author Q7 + 本文档初版基于"AgentTool 走子 agent 权限继承"的杜撰描述判断为 gap,经 design 阶段 D2 重新对照 CC 源码后撤销。S3 不进本期范围。

## Gap-W2: classifier 输入显式 OUTSIDE 提示

- 本仓 `auto_mode_gate.py:777-786` 在工作区外 write/edit 时给 classifier prompt 前面塞 `NOTE: target path '...' is OUTSIDE the agent's workspace. Writing here affects user files outside the project — be conservative.`
- CC 不做这个加工,classifier 凭 system prompt 的 `BLOCK — File Write Outside CWD` 规则自判
- Q6 已确认本期移除,对齐 CC

## 不算 Gap 的差异(语义等价或本仓更细)

- unattended_fallback 比 CC headless 更可配置(本仓 `config.unattended_fallback="allow"|"deny"`;CC headless 只能 deny+abort)
- deny-limit 只 consecutive 没 total(本仓简化)
- safe-allowlist 清单"本仓没有 CC 的 Grep / Glob / LSP / TodoWrite / Sleep / TeamCreate / TeamDelete / EnterPlanMode / ExitPlanMode / AskUserQuestion / Workflow 等" — 本仓没有这些工具,自然不列;后续真引入这些工具时再决策是否进 safe-allowlist
