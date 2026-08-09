# feat-519 Verification Report

## Verification metadata

- Unit: `feat-519-workspace-compat-skills`
- Review round: 1
- Mode: full
- Verdict: **FAIL**
- Validated at: `2026-08-10T01:40:21+08:00`
- Validated implementation commit: `85d9883f86334315da633e7a0ab81260c83b818e`
- Executed base: `1d0c2cb45`
- Requires full verification after fixes: `false`
- Findings: 1 CRITICAL, 2 WARNING, 0 SUGGESTION

## Executive result

The ordered workspace layouts, native write boundary, shared-only query,
`source_group`, three-state selector, legacy payload handling, SlashPicker,
Gateway/IM persistence fields, Feishu reconciliation, and `skill_created`
state transitions are present and their focused tests pass. The implementation
is nevertheless not shippable because a new Kernel session folds an explicit
empty Skill allowlist into default discovery. This directly widens a user's
saved zero-Skill selection to every discoverable Skill.

The same selection-mode design is also incomplete in Agent prompt preview, and
the required config-operation recovery behavior has no explicit-empty regression
test. The M1 exit criteria are therefore not met.

## Scorecards

### Completeness

- Requirement surfaces implemented: **16/16**
- Requirements fully satisfied: **14/16**
- Milestones fully satisfied: **0/1** (`feat-519-M1` is blocked by C1)

### Correctness

- Scenarios verified: **58**
- Passing scenarios: **56**
- Failing scenarios: **2**
  - Gateway: `用户显式清空全部 Skill 后下一轮不再发现 Skill`
  - IM: `显式空选择在配置页和后续回复中一致`

### Coherence

- Design decisions followed: **5/6**
- Decision 4 is only partially implemented: the intent survives the profile,
  YAML and projected runtime boundaries, but is lost by Kernel session creation;
  Agent prompt preview also ignores the mode.
- No package dependency or product-boundary violation was found.

## Requirement and scenario coverage ledger

### Unit `spec.md`

| Requirement / scenario | Result | Evidence |
|---|---|---|
| PA 与 Coding CLI 一致发现指定兼容根 / PA 配置页提供工作区与主目录兼容 Skill | PASS | PA layout wiring, shared resolver and Gateway capability projection; focused Python suites pass. |
| 同上 / Coding CLI 在同一项目中提供兼容 Skill 候选 | PASS | `CLI_WORKSPACE_SKILL_DIRNAMES` wiring and CLI product-layout test. |
| 同上 / 原生与既有兼容来源保持可用 | PASS | SDK fallback and ordered-root tests retain native plus existing `~/.codex` roots. |
| 同名 Skill 按统一优先级 / PA 选择最优先来源 | PASS | Registry first-root-wins is reached through the common root builder; PA exact layout is tested. |
| 同上 / Coding CLI 选择最优先来源 | PASS | Exact CLI layout and same-name resolver tests pass. |
| PA 显式选择后下一轮生效 / 新发现 Skill 不静默扩大显式保存范围 | PASS | Explicit non-empty mode remains an allowlist; `skill_created` and Feishu writers preserve mode. |
| 同上 / 选择兼容 Skill 后继续既有聊天 | PASS | Existing binding is retained and `reconfigure_session()` replaces future runtime without replacing session identity/history. |
| 分组批量选择 / 以分组为单位调整并继续单项调整 | PASS | Selector component tests cover group update followed by individual update. |
| 同上 / 分组状态如实反映单项选择 | PASS | None/mixed/all ARIA state and hidden-name preservation tests pass. |
| 同上 / 批量选择融入桌面与移动配置体验 | PASS | Control remains in the group-title row with wrapping layout; focused create/detail tests pass. |
| 可选目录缺失 / 工作区不含兼容目录 | PASS | Registry skips absent roots; resolver/product tests pass. |
| 同上 / 兼容目录没有有效 Skill | PASS | Existing registry behavior skips empty/invalid candidates without changing other roots. |

### CLI delta

| Scenario | Result | Evidence |
|---|---|---|
| CLI 装配保持在产品包 | PASS | `coding_cli.product` alone declares the product layout and calls `agent.sdk`. |
| CLI 在工作区发现 Claude/Codex Skill | PASS | Layout is `.nanocode → .claude → .codex`; product and resolver tests pass. |
| CLI 发现用户主目录 Claude Skill | PASS | Shared roots are `~/.nanocode → ~/.claude → ~/.codex`; first-root-wins remains intact. |
| workspace 与全局扩展目录被纳入 | PASS | Skill layout is extended while tool/hook namespaces remain native `.nanocode`. |
| 缺失可选兼容目录不影响 CLI 启动 | PASS | Root discovery tolerates absent directories and focused tests pass. |

### Gateway delta

| Scenario | Result | Evidence |
|---|---|---|
| 新安装发现产品说明书与完整 Lark bundle | PASS | Existing bootstrap path remains intact; bootstrap suite passes. |
| 升级刷新全部随包内置 skills | PASS | Existing atomic bootstrap behavior is unchanged; bootstrap suite passes. |
| 非内置用户 skill 保持不变 | PASS | Bootstrap restricts replacement to managed names; bootstrap suite passes. |
| 刷新失败保留旧完整目录并继续启动 | PASS | Existing staged replacement/fallback tests pass. |
| backup 清理失败不遮蔽已切换的新版本 | PASS | Existing cleanup failure behavior remains covered by bootstrap tests. |
| 共享全局 root 的并发 Gateway 刷新保持完整版本 | PASS | Existing concurrency bootstrap tests pass. |
| 显式 skill allowlist 不因资源刷新改变 | PASS | Bootstrap does not mutate profile selections. |
| 显式非空 allowlist 的飞书 Agent 获得完整 bundle | PASS | Static and managed Feishu reconciliation tests pass. |
| 默认发现的飞书 Agent 不物化 bundle | PASS | `default_discovery` reconciliation remains name-free; focused Gateway tests pass. |
| 显式空 allowlist 不因飞书 channel 调和扩宽 | PASS | Both static YAML and managed channel tests retain explicit empty. |
| 静态 Feishu Agent 的 IM profile ingress 保留完整 bundle | PASS | Registration and static reconciliation payloads retain names and mode. |
| 用户明确请求独立 Lark 事件监听 | PASS | Existing external-channel behavior is not changed by this unit. |
| 工作区 Claude/Codex Skill 出现在 Agent capability 中 | PASS | Agent capability uses the real workspace plus the PA layout. |
| PA 新回复与 capability 使用同一同名覆盖结果 | PASS | Capability, runtime resolver and `skill_view` share the ordered roots for non-empty/default selections. |
| 缺失兼容目录不阻断 PA Agent | PASS | Registry skip behavior and product tests pass. |
| 新建页只取得全局 Skill candidates | PASS | Node capability calls `Kernel.list_shared_skills()` and excludes repo workspace roots. |
| 用户显式清空全部 Skill 后下一轮不再发现 Skill | **FAIL** | C1: a newly bound Kernel session turns `[]` into `None`, restoring default discovery. |
| 旧空配置升级后保持历史行为 | PASS | Absent mode plus empty names projects to `None`, with no eager migration. |
| 自动 Skill 写回保留 selection mode | PASS | Gateway apply/local YAML mutation paths carry the mode; Feishu-focused tests pass. |
| 成功创建 Skill 后按当前 mode 变为可用 | PASS | Default remains default; explicit non-empty and explicit empty append the new name while remaining explicit. |

### IM delta

| Scenario | Result | Evidence |
|---|---|---|
| 节点能力含 features 列表供创建页渲染 | PASS | Existing IM contract test passes. |
| agent 能力透传 features 五元字段 | PASS | Existing feature projection contract remains intact. |
| 可选模型列表每项携带其注册的 provider | PASS | Existing model capability tests pass. |
| 用户按有效模型能力选择推理设置 | PASS | Existing effective-model handling is unchanged. |
| 可选模型列表每项携带安全的推理能力 | PASS | Existing safe descriptor projection tests pass. |
| agent skills 携带 location 与来源分组 | PASS | Gateway emits structured `source_group`; IM validates and forwards it. |
| 旧节点未提供来源分组时安全降级 | PASS | Field is optional and selector fallback test passes. |
| 批量选择分组后继续逐项调整 | PASS | Selector tests cover group and pill composition. |
| 批量取消部分已选分组 | PASS | Mixed/all/none state and visible-group-only changes are tested. |
| 窄屏配置仍保持清晰分组操作 | PASS | Inline wrapping control reuses the responsive create/detail layout. |
| 显式空选择在配置页和后续回复中一致 | **FAIL** | UI persists and re-renders empty correctly, but C1 makes a newly created runtime session discover all Skills. |

### Kernel SDK-boundary delta

| Scenario | Result | Evidence |
|---|---|---|
| 能力查询与运行时事实一致 | PASS | `list_models/tools/features/skills` focused contract tests pass. |
| 消费者可在工具目录中启用 `skill_view` | PASS | Existing tool-catalog test and `skill_view` suites pass. |
| 部署级共享 root 叠加在每 workspace layout 之后 | PASS | Common root builder and exact same-name precedence tests pass. |
| 无真实 workspace 时只查询共享 Skill | PASS | `list_shared_skills()` directly builds a registry from shared roots only; exclusion test passes. |

### Kernel skills delta

| Scenario | Result | Evidence |
|---|---|---|
| 多个有序工作区目录在各读取路径中一致 | PASS | `list_skills`, preview, runtime resolver and `skill_view` use the shared layout and focused tests pass. |
| 预览与运行时技能一致 | PASS | Non-empty selection regression covers compatible roots and selected names. W1 is a frontend mode-projection defect, not a root-resolution divergence. |
| 未提供额外 workspace layout 时保持单目录默认 | PASS | SDK fallback remains the effective `workspace_config_dirname`, including `.nano`. |
| `list_skills` 返回 `SKILL.md` 路径 | PASS | `SkillInfo.location` focused test passes. |
| 管理工具从兼容 root 读取但写入原生 root | PASS | `resolve_skill_roots()` shares read roots while `agent_writer` remains on native root; regression passes. |
| prospective Agent capability 不把 repo workspace Skill 当候选 | PASS | Shared-only capability exclusion test passes. |

## Design-decision coverage

| Decision | Result | Verification |
|---|---|---|
| D1: explicit ordered workspace layout | PASS | SDK input and PA/CLI exact directory orders are wired and tested. |
| D2: one root builder for readers, native writer | PASS | list/preview/runtime/view/manage-list share the builder; agent writer and curator remain native. |
| D3: structured `source_group` | PASS | Gateway projects it, IM forwards it optionally, and old payloads fall back safely. |
| D4: explicit selection intent across every boundary | **FAIL** | C1 loses explicit empty at Kernel creation; W1 omits mode from prompt preview; W2 leaves operation recovery unguarded. |
| D5: compact group-title tri-state interaction | PASS | Inline checkbox semantics, none/mixed/all, group/pill composition and hidden names are implemented. |
| D6: create page uses shared-only candidates | PASS | Node capability calls `list_shared_skills()`; Agent detail uses the real workspace. |

## M1 exit-criteria ledger

| Worker/reviewer exit criterion | Result |
|---|---|
| list/preview/runtime/`skill_view` share ordered layout | PASS |
| native writer root remains unchanged | PASS |
| legacy/default/explicit non-empty/explicit empty survive IM DB, Gateway YAML and session projection | **FAIL — C1** |
| config-operation recovery carries selection intent | PARTIAL — implementation present, required regression absent (W2) |
| Feishu reconciliation and `skill_created` preserve mode | PASS |
| create/detail/SlashPicker use truthful mode semantics | PASS for selectors and SlashPicker; prompt preview is inconsistent (W1) |
| group keyboard/focus/tri-state and hidden-name semantics | PASS |
| old and new capability payloads render safely | PASS |
| relevant automated checks green | PASS for executed suites, but insufficient to catch C1/W1/W2 |
| real PA/CLI/browser product journey | NOT ASSESSED — owned by `change-reviewer`; current implementation is already blocked by C1 |

## Findings

### CRITICAL C1 — Kernel session creation converts explicit empty Skill selection to default discovery

**Affected contract:** Design decision 4, Gateway explicit-empty scenario, IM
explicit-empty scenario, and the M1 worker/reviewer exit criteria.

The PA projection is correct: explicit mode returns `[]` from
`_session_skills()` and the binder passes the complete runtime into
`Kernel.create_session()` (`src/personal_assistant/gateway/session_composition.py:19-24`,
`src/personal_assistant/gateway/session_binder.py:441-445`). Kernel initially
retains this list (`src/agent/sdk/kernel.py:1143-1146`), but its durable
`NewSession` call uses `skills=tuple(skills) if skills else None`
(`src/agent/sdk/kernel.py:1198`). An empty list therefore becomes `None`.

Core runtime gives those values opposite meanings:
`config.skills is None` means every discovered Skill, while an empty tuple means
none (`src/agent/core/agent/runtime.py:1185-1196`). A user who explicitly clears
all Skills can therefore receive all Skills again whenever the Gateway needs to
create a new Kernel session/binding.

The focused test named `test_runtime_preserves_explicit_empty_allowlist` stops at
the PA projection (`tests/unit/personal_assistant/test_skill_selection_mode.py:25-31`),
so it cannot detect the loss at the Kernel boundary. Direct reproduction against
the validated commit produced:

```text
input_skills=[]
persisted_skills=None
```

**Required fix:** preserve the three states in `Kernel.create_session()`, using
`tuple(skills) if skills is not None else None`. Add a lowest-boundary regression
that creates a real session with `SessionRuntimeConfig(skills=[])`, reads it back
with `get_session_runtime()`, and verifies the resulting model turn and
`skill_view` exposure contain no Skills.

### WARNING W1 — Agent prompt preview ignores `skills_selection_mode`

**Affected contract:** Design decision 4, which explicitly requires the config
page, prompt preview, real session, and SlashPicker to derive effective Skills
from mode rather than `names.length`.

The selector renders `default_discovery` as all current capability options
selected (`skill-source-selector.tsx:57-59`). The detail page's preview request,
however, always sends `draft.skills ?? []` and does not read the mode
(`agent-detail-page.tsx:153-169`). A legacy/default profile with empty stored names
therefore shows every Skill selected in the form but previews no Skill listing,
because Kernel only resolves preview Skills when `skill_ids` is non-empty
(`src/agent/sdk/kernel.py:2234-2239`).

The current detail-page preview regression checks only `tool_ids`
(`agent-detail-page.test.tsx:748-767`), leaving this divergence unguarded.

**Required fix:** pass the effective Skill candidates to `BehaviorCard` and send
all current capability names for `default_discovery`, while continuing to send
the exact saved names for `explicit_allowlist`; alternatively, carry mode as a
first-class preview field across the whole API/Gateway/Kernel boundary. Add a
detail-page preview test for default, explicit non-empty, and explicit empty.

### WARNING W2 — Config-operation recovery has no selection-mode regression

**Affected contract:** Design decision 4 and the M1 worker exit criterion that
legacy/default/explicit states survive candidate/fingerprint/receipt recovery.

The implementation includes `skills_selection_mode` in the Gateway candidate
keys, candidate projection, result commit and profile persistence. The generic
pending-apply recovery test, however, seeds a legacy profile and sends an update
payload that omits the mode (`tests/im_service/integration/test_agent_config_operation_flow.py:15-47`);
it asserts only reasoning effort after recovery (`:50-101`). No test proves that
`skills=[]` plus `explicit_allowlist` is included in the candidate fingerprint,
survives a lost-ACK status recovery, and commits back as explicit empty.

**Required fix:** add an operation-flow regression whose pending candidate is
`skills=[]`, `skills_selection_mode="explicit_allowlist"`; assert the apply
payload and fingerprint, simulate recovered `applied`, and verify the committed
profile retains both the empty names and explicit mode. Cover compensation if
that path canonicalizes the same candidate shape.

## Command evidence

All commands ran in
`/Users/czj/Repos/nano-multiagent/.worktrees/verify-feat-519-r1` at the validated
commit unless noted.

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `85d9883f86334315da633e7a0ab81260c83b818e` |
| Focused resolver/SDK/Gateway/IM command from M1 progress, expanded by current tests | **117 passed**, 3 unrelated deprecation warnings |
| Runtime/view/Gateway selection command | **52 passed**, 2 unrelated deprecation warnings |
| Config-operation + schema command | **13 passed** |
| Bootstrap + PA/CLI product-layout + zero-tool integration command | **18 passed** |
| Frontend selector/edit/create/API/SlashPicker command | **48 passed**; existing user-stream 404 test noise only |
| Direct `SessionRuntimeConfig(skills=[])` create/read-back reproduction | **Failed contract:** input `[]`, persisted `None` |

Frontend dependencies were supplied by a temporary worktree-local symlink to the
main checkout's existing `node_modules`; the symlink was removed by the command
trap and did not alter the worktree.

## Final verdict

**FAIL.** C1 is a release blocker because it silently broadens an explicit user
allowlist. W1 must be corrected for the design's preview/runtime truthfulness,
and W2 must add the explicitly required recovery coverage before the next focused
verification round. A full verification rerun is not required after these scoped
fixes; round 2 may validate the three findings plus the affected focused suites.
