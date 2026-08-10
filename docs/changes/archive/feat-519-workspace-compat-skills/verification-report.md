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

# Round 2

## Verification Report: feat-519-workspace-compat-skills

### Summary

- Mode: `targeted-closure`
- Delta range: `85d9883f86334315da633e7a0ab81260c83b818e..520cb5c371c9beb2b0f9b20a2d69665d35fc0d5e`
- Focus issues: C1, W1, W2
- Validated at: `2026-08-10T01:53:41+08:00`
- Validated implementation commit: `520cb5c371c9beb2b0f9b20a2d69665d35fc0d5e`
- Executed base: `1d0c2cb45`
- `requires_full_verification: false`

| Dimension | Result |
|---|---|
| Completeness | 3/3 focus issues closed |
| Correctness | 3/3 affected contracts and regressions pass |
| Coherence | Followed; fixes stay within existing Kernel, preview and config-operation mechanisms |

### Focus-issue closure

#### C1 — CLOSED: explicit empty survives a real Kernel session

`Kernel.create_session()` now distinguishes `None` from an empty list when it
builds the durable `NewSession` (`src/agent/sdk/kernel.py:1198`). The added
integration regression creates a discoverable `secret-skill`, opens a real
session with `SessionRuntimeConfig(skills=[])`, reads the persisted runtime,
executes a model turn, and makes the model attempt `skill_view`
(`tests/integration/test_empty_skill_allowlist_wiring.py:62-116`). It verifies:

- persisted `runtime.skills` remains `[]`;
- the first model request does not expose `<name>secret-skill</name>`;
- `skill_view` returns “not enabled for this session” even though the tool itself
  is enabled;
- the Skill body is never exposed to the model.

The test passes together with zero-tool wiring, real session coordinator,
`skill_view`, and PA selection-mode regressions. The Gateway/IM explicit-empty
scenarios that failed in Round 1 are therefore restored.

#### W1 — CLOSED: preview projects default, explicit non-empty and explicit empty

`BehaviorCard` now receives the current capability Skills and computes preview
IDs from the effective mode (`agent-detail-page.tsx:120-156`). Default discovery
materializes the current capability names for this preview request; explicit mode
uses the exact saved names, including an empty list. Fetch and debounce
dependencies use that effective list (`agent-detail-page.tsx:162-187`), and the
real detail page passes the live capability list into the card (`:1729-1735`).

The parameterized frontend regression covers all three required states:

| State | Expected `skill_ids` | Result |
|---|---|---|
| `default_discovery`, stored `[]` | all current capability names | PASS |
| `explicit_allowlist`, non-empty including a hidden name | exact saved names | PASS |
| `explicit_allowlist`, stored `[]` | `[]` | PASS |

Evidence: `agent-detail-page.test.tsx:741-812`; affected frontend suites report
39 passing tests and the production build succeeds.

#### W2 — CLOSED: explicit-empty operation recovery and compensation are guarded

The new lost-ACK regression persists and inspects the complete operation
candidate, verifies its canonical fingerprint matches the Gateway apply
fingerprint, recovers an `applied` status, and confirms the committed IM profile
and durable operation still contain `skills=[]` plus
`skills_selection_mode="explicit_allowlist"`
(`tests/im_service/integration/test_agent_config_operation_flow.py:108-176`).

The existing CAS-loss compensation scenario now uses explicit empty on both the
losing request and concurrent winner. It verifies the compensation apply payload,
candidate, fingerprint, recovered profile and terminal operation status retain
the same intent (`test_agent_config_operation_flow.py:351-451`). Both paths pass.

### Affected requirement and design coverage

| Contract | Round 2 result |
|---|---|
| Gateway: explicit clear means the next new session discovers no Skill | PASS |
| IM: explicit empty is consistent between configuration and later replies | PASS |
| Design decision 4: default vs explicit intent stays authoritative at session and preview boundaries | PASS |
| M1: config-operation lost-ACK recovery and compensation retain selection intent | PASS |

### Regression review

The fix delta changes one Kernel truthiness condition and adds mode-aware preview
projection; the remaining runtime/config implementation is untouched. The
operation changes are regression tests only. No new dependency direction,
cross-process boundary or parallel persistence mechanism was introduced.

Executed evidence:

| Command scope | Result |
|---|---|
| Explicit-empty session, zero-tool session, real session coordinator, config operations, `skill_view`, PA mode | **30 passed**, 2 unrelated dependency deprecation warnings |
| Agent detail/edit/API frontend suites | **39 passed**; pre-existing React `act(...)` and test user-stream warnings only |
| Frontend `npm run build` | PASS; existing large-chunk warning only |
| Ruff check and format-check on changed Python files | PASS |
| Fix-range `git diff --check` | PASS |

Frontend verification reused the main checkout's existing `node_modules` through
a temporary worktree-local symlink. The command trap removed it afterward; the
verification worktree remained clean.

### Verdict

All checks passed. Ready for PR.

# Round 3

## Verification Report: feat-519-workspace-compat-skills

### Metadata

- Verification mode: full independent implementation verification
- Validated at: `2026-08-10T03:22:59+08:00`
- Validated implementation commit: `7be956bc85bfb1f13ff1e02f11b2dd4e001ae0c0`
- Executed base: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9`
- Verification branch: `review/feat-519-verification-r3`
- Requires full verification: `false`
- Verdict: **PASS**
- Findings: 0 CRITICAL, 0 WARNING, 1 SUGGESTION

Round 3 re-read the unit source documents and verified the final implementation
without inheriting a result from Round 1 or Round 2. The verified document set is
`spec.md`, `design.md`, all five delta-specs, and M1 `tasks.md`/`progress.md`.
The implementation range, affected current code, relevant current specs and tests
were inspected independently.

### Executive result

The final implementation satisfies all **16 requirements and 58 scenarios**, all
six design decisions, and the single M1 worker exit criterion. In particular, the
five-state selection matrix now retains the same meaning at IM persistence,
Gateway YAML and operation boundaries, session composition, Kernel execution,
preview, SlashPicker and automatic-writer boundaries. IM and Gateway compute the
same canonical operation fingerprint for legacy-equivalent states, while explicit
empty remains distinguishable from default discovery.

No implementation defect or missing regression was found. The only finding is a
non-blocking process-document suggestion: the implemented test coverage is broad
and green, but the prose in M1 `tasks.md` does not use the repository's mandatory
structured test-strategy template.

### Completeness and coherence scorecards

| Dimension | Result | Evidence |
|---|---:|---|
| Requirements | 16/16 PASS | Unit spec plus CLI, Gateway, IM, SDK-boundary and kernel-skills deltas |
| Scenarios | 58/58 PASS | Per-scenario ledger below; source inspection and focused/full regressions |
| Design decisions | 6/6 PASS | Decision ledger below |
| M1 worker exit criteria | 1/1 PASS | Ordered readers/native writer, mode matrix, UI semantics and CI-equivalent validation |
| Worker checklist | 7/7 implementation items complete | M1 `tasks.md`; final unchecked item is explicitly orchestrator-owned |
| Architecture boundaries | PASS | Contract suite included in full Python run; no forbidden product/package dependency found |

### Requirement and scenario coverage ledger

Every scenario below was checked against final source and a matching focused or
full-suite regression. `PASS` means both the implementation path and its durable
test protection were present.

#### Unit `spec.md` — 5 requirements / 12 scenarios

| Requirement | Scenario | Result | Primary evidence |
|---|---|---:|---|
| PA 与 Coding CLI 一致发现指定的 Claude/Codex 兼容根目录 | PA 配置页提供工作区与用户主目录的兼容 Skill | PASS | `personal_assistant/product.py`, product-layout and reporter tests |
| same | Coding CLI 在同一项目中提供兼容 Skill 候选 | PASS | `coding_cli/product.py`, CLI product-layout tests |
| same | 原生与既有兼容来源保持可用 | PASS | exact ordered-root assertions in PA/CLI tests |
| 同名 Skill 按统一、可预测的来源优先级解析 | PA 中同名 Skill 选择最优先来源 | PASS | shared root builder/registry plus PA same-source runtime tests |
| same | Coding CLI 中同名 Skill 选择最优先来源 | PASS | CLI layout and core resolver first-root-wins tests |
| PA 配置显式选择兼容 Skill 后才在下一轮生效 | 新发现的兼容 Skill 不静默扩大已保存 Agent 的能力 | PASS | explicit mode session projection and writer-mode tests |
| same | 开发者选择兼容 Skill 后继续既有聊天 | PASS | session binder/composition and real Kernel session integration |
| PA 配置支持按已显示的 Skill 分组批量选择 | 开发者以一个分组为单位调整 Skill 选择 | PASS | `skill-source-selector` plus create/detail tests |
| same | 分组状态如实反映单项选择 | PASS | none/partial/all and pill-follow-up tests |
| same | 批量选择自然融入既有配置体验 | PASS | inline control, native keyboard/focus and wrapping semantics |
| 可选兼容目录缺失时保持正常使用 | 工作区不含某个兼容目录 | PASS | resolver and product missing-root tests |
| same | 兼容目录没有有效 Skill | PASS | registry skip/empty-root regressions |

#### CLI delta — 1 requirement / 5 scenarios

| Scenario | Result | Primary evidence |
|---|---:|---|
| CLI 装配保持在产品包 | PASS | `coding_cli/product.py`; architecture contract suite |
| CLI 在工作区发现 Claude/Codex Skill | PASS | `test_cli_product_workspace_layout.py` |
| CLI 发现用户主目录 Claude Skill | PASS | exact shared-root assertions |
| workspace 与全局扩展目录被纳入 | PASS | product layout passed to SDK ordered builder |
| 缺失可选兼容目录不影响 CLI 启动 | PASS | missing-root regression |

#### Gateway delta — 3 requirements / 20 scenarios

| Requirement | Scenario | Result | Primary evidence |
|---|---|---:|---|
| PA 内置 skill 启动自举 | 新安装发现产品说明书与完整 Lark bundle | PASS | builtin bootstrap tests |
| same | 升级刷新全部随包内置 skills | PASS | builtin refresh tests |
| same | 非内置用户 skill 保持不变 | PASS | bootstrap preservation regression |
| same | 刷新失败保留旧完整目录并继续启动 | PASS | atomic refresh failure regression |
| same | backup 清理失败不遮蔽已切换的新版本 | PASS | post-switch cleanup regression |
| same | 共享全局 root 的并发 Gateway 刷新保持完整版本 | PASS | concurrent bootstrap regression |
| same | 显式 skill allowlist 不因资源刷新改变 | PASS | bootstrap/local-store assertions |
| same | 显式非空 allowlist 的飞书 Agent 获得完整 bundle | PASS | static/managed Feishu reconciliation tests |
| same | 默认发现的飞书 Agent 不物化 bundle | PASS | mode-matrix channel tests |
| same | 显式空 allowlist 不因飞书 channel 调和扩宽 | PASS | explicit-empty channel regression |
| same | 静态 Feishu Agent 的 IM profile ingress 保留完整 bundle | PASS | Gateway/IM sync regression |
| same | 用户明确请求独立 Lark 事件监听 | PASS | bundled capability/bootstrap coverage |
| PA Agent 从有序的工作区与全局 Claude/Codex 兼容根发现 Skill | 工作区 Claude/Codex Skill 出现在 Agent capability 中 | PASS | PA layout and upstream reporter tests |
| same | PA 新回复与 capability 使用同一同名覆盖结果 | PASS | runtime same-source integration |
| same | 缺失兼容目录不阻断 PA Agent | PASS | product/resolver missing-root tests |
| same | 新建页只取得全局 Skill candidates | PASS | `Kernel.list_shared_skills` and shared-only capability tests |
| PA Agent 配置区分默认发现与显式空 Skill 选择 | 用户显式清空全部 Skill 后下一轮不再发现 Skill | PASS | real session integration; prompt and `skill_view` expose no hidden Skill |
| same | 旧空配置升级后保持历史行为 | PASS | legacy absent empty/nonempty matrix |
| same | 自动 Skill 写回保留 selection mode | PASS | Feishu/static/IM-ingress/`skill_created` writer matrix |
| same | 成功创建 Skill 后按当前 mode 变为可用 | PASS | default republish and explicit-list mutation tests |

#### IM delta — 3 requirements / 11 scenarios

| Requirement | Scenario | Result | Primary evidence |
|---|---|---:|---|
| 节点 runtime 能力按需向在线网关解析,不入库快照 | 节点能力含 features 列表供创建页渲染 | PASS | existing capability contract/full suite |
| same | agent 能力透传 features 五元字段 | PASS | agent capability contract/full suite |
| same | 可选模型列表每项携带其注册的 provider | PASS | capability contract/full suite |
| same | 用户按有效模型能力选择推理设置 | PASS | frontend/current capability regressions |
| same | 可选模型列表每项携带安全的推理能力 | PASS | capability schema tests |
| same | agent 能力的 skills 项携带 location 与来源分组 | PASS | reporter → IM optional field → frontend normalization tests |
| same | 旧节点未提供来源分组时安全降级 | PASS | legacy location/default-on fallback test |
| Agent 配置页可按 Skill 来源分组批量调整选择 | 用户批量选择一个来源分组后继续逐项调整 | PASS | group selector plus create/detail tests |
| same | 用户批量取消部分已选分组 | PASS | tri-state visible-group regression |
| same | 窄屏配置仍保持清晰的分组操作 | PASS | wrapping/compact selector assertions and build |
| 配置 API 表达默认 Skill discovery 与显式 allowlist 的不同意图 | 显式空选择在配置页和后续回复中一致 | PASS | API/repository/config-operation/real session/frontend tests |

#### Kernel SDK-boundary delta — 1 requirement / 4 scenarios

| Scenario | Result | Primary evidence |
|---|---:|---|
| 能力查询与运行时事实一致 | PASS | Kernel list/preview/runtime same-root tests |
| 消费者可在工具目录中启用 `skill_view` | PASS | `test_skill_view.py` and real session integration |
| 部署级共享 skill 根叠加在每 workspace 布局之后 | PASS | exact root-sequence unit tests |
| 无真实 workspace 时只查询共享 Skill | PASS | `list_shared_skills` shared-only test |

#### Kernel skills delta — 3 requirements / 6 scenarios

| Requirement | Scenario | Result | Primary evidence |
|---|---|---:|---|
| 同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致 | 多个有序工作区目录在各读取路径中一致 | PASS | common builder and focused 62-test root suite |
| same | 预览与运行时技能一致 | PASS | preview/runtime same-source tests |
| same | 未提供额外 workspace Skill layout 时保持既有单目录默认 | PASS | default-layout compatibility tests |
| same | list_skills 返回项携带 SKILL.md 路径 | PASS | Kernel list capability-query tests |
| Skill 管理写入不因兼容读取 root 改变目标目录 | 管理工具从兼容 root 读取但写入原生 root | PASS | `test_skill_manage_tool.py` native-writer regression |
| SDK 消费者可在没有真实 workspace 时只查询共享 Skill roots | prospective Agent capability 不把 repo workspace Skill 当候选 | PASS | shared-only query regression |

### Focused semantic matrices

#### Selection intent and persistence

| Stored state | Effective meaning | Session projection | Writer behavior | Result |
|---|---|---|---|---:|
| legacy mode absent, `skills=[]` | default discovery | `None` → discover | no eager migration | PASS |
| legacy mode absent, non-empty skills | explicit allowlist | exact tuple | materialize explicit only when an actual mutation is required | PASS |
| `default_discovery` | default discovery | `None` → discover | republish/no list widening | PASS |
| `explicit_allowlist`, non-empty | exact allowlist | exact tuple | retain mode; add only on explicit capability mutation | PASS |
| `explicit_allowlist`, empty | disable all Skill discovery | empty tuple | retain empty through Feishu/config/created paths | PASS |

The repository, API and wire representations retain raw legacy absence where no
mutation is required. Effective-mode helpers are used only at behavior and
canonical comparison boundaries. `Kernel.create_session` distinguishes
`skills is None` from `skills == []`; the real-session regression persists `[]`,
runs a model turn, verifies the model prompt does not advertise the hidden Skill,
and verifies `skill_view` cannot reveal it.

#### IM/Gateway fingerprint and operation lifecycle

| Boundary/path | Verified invariant | Result |
|---|---|---:|
| IM `gateway_candidate` vs Gateway `canonical_agent_operation_payload` | identical canonical projection for all five states | PASS |
| legacy absent empty vs explicit effective default | equal fingerprints | PASS |
| legacy absent non-empty vs explicit effective allowlist | equal fingerprints | PASS |
| default vs explicit empty | different fingerprints | PASS |
| invalid explicit mode | rejected on both sides | PASS |
| real apply | legacy/default local profile can apply explicit empty and persist it in YAML | PASS |
| lost-ACK recovery | candidate, fingerprint, applied payload and committed profile retain explicit empty | PASS |
| CAS-loss compensation | compensation payload and terminal recovery retain explicit empty | PASS |

Primary code evidence is IM `application/agent_config_operations.py:544-621`
and Gateway `gateway/agent_config_sync.py:91-142,1518-1524`; matrix, apply,
lost-ACK and compensation regressions are in
`test_agent_config_operations.py`,
`test_gateway_config_operation_validation.py` and
`test_agent_config_operation_flow.py`.

#### Ordered roots and consumers

| Surface | Uses shared ordered roots | Same-name first wins | Native writer unchanged | Result |
|---|---:|---:|---:|---:|
| Kernel `list_skills` / preview | yes | yes | N/A | PASS |
| Agent runtime prompt and compaction | yes | yes | N/A | PASS |
| `skill_view` | yes | yes | N/A | PASS |
| `skill_manage list` / reads | yes | yes | yes | PASS |
| PA capability and new session | yes | yes | N/A | PASS |
| Coding CLI | yes | yes | N/A | PASS |
| shared-only prospective query | shared roots only | yes | N/A | PASS |

The single builder is `agent/core/skills/discovery.py:18-48`. PA orders
`.nanoassistant`, `.claude`, `.codex` before its shared roots; Coding CLI orders
`.nanocode`, `.claude`, `.codex` before its shared roots. Every listed reader
receives the same sequence. `skill_manage` continues to write only beneath the
product-native workspace directory.

#### Automatic writers and user-facing consumers

| Surface | States/behavior independently checked | Result |
|---|---|---:|
| Static Feishu reconciliation | legacy empty, legacy non-empty, default, explicit non-empty, explicit empty | PASS |
| Managed Feishu reconciliation | effective mode respected; explicit empty not widened | PASS |
| Static IM profile ingress | only required non-empty explicit bundle repair | PASS |
| `skill_created` | default/legacy-empty republish; explicit lists mutate; legacy non-empty materializes | PASS |
| Agent detail preview | default = capabilities; explicit non-empty = exact names; explicit empty = `[]` | PASS |
| Runtime/SlashPicker | default discovers; explicit exact intersection; explicit empty none; old absent payload inferred | PASS |
| `source_group` | structured workspace/global/compatibility projection; old payload fallback | PASS |
| Create/detail selector | default → explicit on first edit; tri-state group control; hidden names preserved | PASS |

### Six design decisions

| Design decision | Final implementation result | Evidence |
|---|---:|---|
| 1. Explicit ordered workspace directory layout | PASS | SDK accepts ordered dirnames; PA/CLI provide exact product layouts |
| 2. One root-sequence builder for readers, native writer fixed | PASS | all seven reader/native-writer surfaces above |
| 3. Structured PA `source_group`, safe legacy fallback | PASS | reporter, IM optional schema, frontend fallback tests |
| 4. Explicit selection intent distinguishes clear-all from default | PASS | full five-state persistence/runtime/fingerprint matrix |
| 5. Inline tri-state group micro-interaction | PASS | checkbox semantics, count/state action, focus/keyboard and wrapping tests |
| 6. Create page uses shared/global Skills only | PASS | `list_shared_skills`, create flow and shared-only leakage regression |

The prototype's three must-match projections are represented in the production
component and regressions: default-to-explicit transition, none/partial/all group
state with compact count/action, and pill/group linkage at desktop/mobile layout.
Real browser product acceptance remains the downstream `change-reviewer` gate;
it is not substituted by this implementation verification.

### M1 worker exit-criteria ledger

| Worker exit clause | Result | Evidence |
|---|---:|---|
| list/preview/runtime/`skill_view` share one ordered layout | PASS | common builder plus 62 focused ordered-root tests |
| native writer root remains unchanged | PASS | `skill_manage` writer regression |
| legacy absent/default/explicit non-empty/empty remain coherent through IM DB and Gateway YAML | PASS | repository/API/local-store/mode tests |
| config operation recovery preserves intent | PASS | canonical matrix, real apply, lost-ACK and compensation tests |
| Feishu bundle, `skill_created` and session projection preserve intent | PASS | automatic-writer matrix and real session integration |
| group control has keyboard/focus/tri-state semantics | PASS | selector tests and production build |
| group changes only visible names and retains invisible names | PASS | hidden-name create/detail regression |
| old and new capability payloads render safely | PASS | API normalization and legacy source fallback tests |
| narrow-to-CI-equivalent related validation is green | PASS | command table below |

All seven worker implementation checklist items in `tasks.md` are complete. The
remaining unchecked checklist line combines real product journeys, independent
review gates, canonical-spec merge and archive; `tasks.md:24-25` explicitly owns
those final lifecycle actions to the orchestrator, so it is not an incomplete
worker implementation criterion.

### Findings

#### SUGGESTION S1 — M1 test strategy should use the mandatory structured template

**Evidence:** `M1-workspace-skills-selection/tasks.md:27-33` describes coverage in
five prose bullets. `docs/development/testing.md:95-113` says this section MUST
state the protected seam, existing-test disposition and de-duplication rationale,
layer/directory/marker rationale, file ownership, optional dependency policy,
one-off evidence, and an affected-existing-tests disposition table. Several of
those fields and the table are absent.

**Impact:** non-blocking process/documentation debt only. Source behavior is
protected by durable tests, the focused suites and CI-equivalent full suites pass,
and no implementation requirement is falsified.

**Precise fix routing:** M1 documentation owner should rewrite only the Test
strategy section using the template in `docs/development/testing.md`, naming the
existing files already used here and adding the affected-existing-tests table.
No production-code or test-code change is requested.

### Command evidence

| Command/scope | Result |
|---|---|
| `pytest -q -m 'not e2e'` | **3155 passed**, 25 deselected, 22 existing dependency/deprecation warnings; 153.78s |
| IM/Gateway selection, persistence, config-operation, session suite (11 files) | **101 passed**, 3 existing warnings; 8.76s |
| ordered roots/list/preview/runtime/`skill_view`/writer/product layouts (7 files) | **62 passed**; 0.40s |
| six focused frontend selector/create/edit/detail/API/SlashPicker files | **66 passed**; 3.15s |
| full frontend `npm test -- --reporter=dot` | **66 files, 638 tests passed**; 14.39s; existing `act(...)`, local-storage and mocked user-stream warnings only |
| frontend `npm run build` | PASS; 504 modules transformed; existing >500 kB chunk warning only |
| `ruff check src tests` | PASS |
| `ruff format --check src tests` | PASS; 853 files already formatted |
| `git diff --check 1d0c2cb45b887162912402b0fb489cdf3a1ad9c9..7be956bc85bfb1f13ff1e02f11b2dd4e001ae0c0` | PASS |
| `PYTHON=/Users/czj/miniforge3/bin/python ./scripts/docs-check` | PASS; 226 maintained Markdown sources and 67 required routes |

Frontend verification reused the main checkout's installed `node_modules`
through a temporary worktree-local symlink. It was removed after each command;
the only intended Round 3 worktree modification is this report.

### Verdict

**PASS.** Blocking findings: **0**. Non-blocking findings: **1 SUGGESTION**.
All implementation requirements, scenarios, design decisions and M1 worker exit
criteria pass at the validated commit. `requires_full_verification: false`.

All checks passed. Ready for PR.

# Round 4

## Verification Report: feat-519-workspace-compat-skills

### Summary

Mode: `targeted-closure`

Validated at: `2026-08-10T04:17:14+08:00`

Validated implementation commit: `fbdddd8812c47f687278758de1b5af51c6d032e0`

Executed base: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9`

Fix delta range: `7be956bc85bfb1f13ff1e02f11b2dd4e001ae0c0..fbdddd8812c47f687278758de1b5af51c6d032e0`

Implementation-fix commit: `05b5a777da4a47eebe8dbd15ef7e29fc0a57459d`

Focus issues:

1. `agent-config-v1`/`agent-config-v2` rolling protocol and legacy operation/receipt recovery.
2. Explicit-empty selection must not generate a distillation prompt.
3. Successful Agent save must invalidate the SlashPicker capability cache.
4. `source=mirror` must preserve raw legacy `skills_selection_mode=null` without eager migration.
5. Round 3 S1: M1 test strategy must use the structured repository template.

`requires_full_verification: false`

| Dimension | Result |
|---|---:|
| Completeness | 5/5 focus issues closed |
| Correctness | 5/5 focus contracts and regressions pass |
| Coherence | Followed; existing IM/Gateway operation, mirror and frontend query mechanisms were extended |

The delta is bounded to existing Agent config-operation negotiation/recovery,
distill readiness, mirror projection and frontend query invalidation seams. It
does not add a forbidden dependency direction, cross-machine filesystem access or
parallel persistence mechanism. Focused suites plus complete Python and frontend
regressions passed, so the Round 3 full-verification conclusion remains usable and
this round does not require another full requirement ledger.

### Focus-issue closure

#### 1. CLOSED — rolling fingerprint protocol and old operation/receipt recovery

The final implementation makes the fingerprint schema an operation-level durable
fact instead of inferring it again during recovery:

- Gateway registration advertises `agent-config-v2`; IM selects v2 only when the
  target connection advertises it and otherwise falls back to v1
  (`upstream_reporter.py:57-82`, `IM/ws/gateway/control.py:88-105`).
- IM v1 canonicalization retains the pre-feature names-only payload. V2 adds the
  effective selection mode. Explicit empty and default-with-names are rejected as
  `gateway_upgrade_required` before an old-Gateway RPC or IM operation row is
  created (`IM/application/agent_config_operations.py:141-225,604-717`).
- The selected schema is stored on IM operation rows, inherited by compensation,
  and reused for status recovery/resubmit and commit recognition
  (`IM/infra/db.py:189-208,386-399`,
  `IM/infra/repositories/agent_config_operations.py:44-100,199-249`,
  `IM/application/agent_config_operations.py:263-305,533-565,845-889`).
- Gateway request validation, receipt preparation, replay, status and terminal
  results all retain the schema. Missing schema remains v1 for old IM/Gateway
  interoperability (`gateway/agent_config_sync.py:60-192,519-716,827-910`,
  `gateway/config_apply_receipts.py:14-191`,
  `IM/ws/gateway/control.py:22-54,193-323,826-916`).
- Existing SQLite rows and JSON receipts without the field load as v1; legacy
  receipt candidates cannot acquire `skills_selection_mode` during read/replay.

Permanent regressions verify IM/Gateway v1 parity, v1 representability gates,
old/new Gateway WebSocket negotiation, an old IM request handled by a new Gateway,
legacy SQLite migration, a prepared legacy receipt resumed after Gateway upgrade,
lost-result status recovery, replay and v2 compensation. No old receipt is
re-fingerprinted under v2.

Result: **CLOSED**.

#### 2. CLOSED — explicit-empty distillation is rejected on both boundaries

Gateway readiness now computes the effective selection mode and requires the
distiller name whenever the mode is explicit
(`personal_assistant/gateway/distill_prompt.py:111-135`). Therefore explicit empty
returns `distiller_unavailable` before source resolution and never creates a
prompt. Web IM passes `config.skills_selection_mode` to the same SlashPicker
selection resolver before calling the distill API
(`chat-workspace-page.tsx:918-934`).

The Gateway regression asserts no `prompt` key for explicit empty
(`test_gateway_distill_prompt_resolver.py:164-195`); the frontend journey asserts
the unavailable message and absence of both the distill POST and prefilled command
(`chat-workspace.integration.test.tsx:620-638`). Default discovery remains able to
use a discovered distiller.

Result: **CLOSED**.

#### 3. CLOSED — Agent save invalidates the SlashPicker cache

The Agent detail save success handler invalidates the shared
`["chat", "slash-skills"]` query prefix
(`agent-detail-page.tsx:1352-1373`). The chat query key is that exact prefix plus
the sorted conversation Agent ids (`chat-workspace-page.tsx:381-423`), so every
cached conversation combination containing the changed Agent is marked stale
before the user returns to chat. The Agent detail regression spies on the shared
`QueryClient` and verifies the exact invalidation call
(`agent-detail-page.test.tsx:847-907`).

Result: **CLOSED**.

#### 4. CLOSED — mirror reads retain raw null without eager migration

The IM config serializer now distinguishes transport ownership from user-facing
effective projection. `source=mirror` returns the persisted raw mode, including
`null`; normal/live and write responses continue to expose the effective mode
(`IM/api/routes/agents.py:226-269,394-441`). Gateway mirror decoding stores that
raw value unchanged, while its behavior boundaries continue to use the effective
helper (`gateway/agent_config_sync.py:1300-1447`). Frontend wire normalization
accepts `null` and maps legacy empty/non-empty lists to default/explicit UI intent
(`im-agent-config-api.ts:517-563`).

Contract tests cover mirror raw null plus live effective projection for legacy
empty and non-empty rows. Reconnect reconciliation covers both list states and
asserts that neither in-memory nor persisted Gateway YAML eagerly gains a mode
(`test_agent_config_contract.py:68-103`,
`test_gateway_reconcile_on_connect.py:200-254`). Frontend normalization covers the
same two legacy forms.

Result: **CLOSED**.

#### 5. CLOSED — Round 3 S1 structured test strategy

`M1-workspace-skills-selection/tasks.md:27-43` now contains all six required
judgments from `docs/development/testing.md:95-113`: protected seam, existing-test
disposition/de-duplication rationale, layer and marker rationale, file ownership,
optional-dependency policy, one-off evidence, and the affected-existing-tests
disposition table. It also records the new rolling operation and post-save
SlashPicker risks.

Result: **CLOSED**. No Round 3 suggestion remains open.

### Related contract and design coverage

| Contract/decision | Round 4 result |
|---|---:|
| Gateway delta: old empty config keeps historical behavior | PASS |
| Gateway delta: explicit empty disables Skill discovery and automatic writers preserve mode | PASS |
| IM delta: explicit empty remains consistent between configuration and later behavior | PASS |
| Design decision 4: default discovery and explicit intent remain authoritative at every consumer | PASS |
| M1 worker criterion: operation recovery, SlashPicker and legacy/default/explicit states remain coherent | PASS |
| Existing architecture: IM owns durable operations; Gateway owns local YAML/receipts; WS remains the cross-process boundary | PASS |

### Regression and command evidence

| Command/scope | Result |
|---|---|
| 11 affected Python files covering schema negotiation, DB/receipt migration, create/apply/recovery, distill and mirror reconciliation | **93 passed**, 3 existing deprecation warnings; 11.16s |
| Focused frontend chat/SlashPicker/Agent-detail/config-API suites | **4 files, 98 tests passed**; existing React `act(...)` and local-storage warnings only; 4.67s |
| `pytest -q -m 'not e2e'` | **3169 passed**, 25 deselected, 22 existing dependency/deprecation/test-key warnings; 155.96s |
| Full frontend `npm test -- --reporter=dot` | **66 files, 640 tests passed**; existing test-runtime warnings only; 16.72s |
| Frontend `npm run build` | PASS; 504 modules transformed; existing >500 kB chunk warning only |
| `ruff check src tests` | PASS |
| `ruff format --check src tests` | PASS; 853 files already formatted |
| `git diff --check 7be956bc85bfb1f13ff1e02f11b2dd4e001ae0c0..fbdddd8812c47f687278758de1b5af51c6d032e0` | PASS |
| `git diff --check 1d0c2cb45b887162912402b0fb489cdf3a1ad9c9..fbdddd8812c47f687278758de1b5af51c6d032e0` | PASS |
| `PYTHON=/Users/czj/miniforge3/bin/python ./scripts/docs-check` | PASS; 226 maintained Markdown sources and 67 required routes |

Frontend commands reused the main checkout's installed `node_modules` through a
temporary worktree-local symlink. It was removed after each command.

### Findings

No CRITICAL, WARNING or SUGGESTION findings.

### Verdict

**PASS.** Blocking findings: **0**. Non-blocking findings: **0**.

Validated issues: rolling protocol/legacy recovery **closed**; explicit-empty
distill **closed**; SlashPicker cache invalidation **closed**; mirror raw-null
preservation **closed**; Round 3 S1 **closed**.

`requires_full_verification: false`.

All checks passed. Ready for PR.

# Corrected Delta Reconciliation

## Metadata

- Verification mode: `corrected-delta`
- Validated at: `2026-08-10T04:26:06+08:00`
- Validated unit commit: `6790ad5e9ab406d68981f21b41985bd58ebd21cf`
- Validated implementation commit: `fbdddd8812c47f687278758de1b5af51c6d032e0`
- Corrected delta commit/range: `fbdddd8812c47f687278758de1b5af51c6d032e0..c146cc555b054165bf5adea283f7c3f5aa077f01`
- Executed base: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9`
- Verification branch: `review/feat-519-corrected-delta`
- Outcome: **aligned**
- Issues: **0 delta-mismatch, 0 implementation-mismatch, 0 suggestion**

This pass re-read the original `spec.md`, final `design.md`, all five delta-specs,
their matching canonical current requirements, the final production diff and the
permanent tests. Round 4 already passed the implementation at `fbdddd881...`; only
unit documentation changed between that snapshot and the validated unit commit.

## Corrected items

| Contract correction | Implementation evidence | Test evidence | Outcome |
|---|---|---|---:|
| D4 negotiates durable `agent-config-v1`/`agent-config-v2`; v1 stays names-only, missing capability/schema means v1, and v1-unrepresentable intent is rejected before operation/write | `src/IM/application/agent_config_operations.py:24-43,141-225,604-717`; `src/IM/ws/gateway/control.py:18-40,88-105`; `src/personal_assistant/reporter/upstream_reporter.py:32-42,74`; `src/personal_assistant/gateway/agent_config_sync.py:60-187,539-712` | `tests/im_service/unit/test_agent_config_operations.py:45-210`; `tests/im_service/integration/test_agent_config_operation_flow.py:215-395`; `tests/unit/personal_assistant/test_gateway_config_operation_validation.py:175-263` | aligned |
| Selected schema survives IM persistence, retry/status recovery and compensation; new Gateway resumes old v1 prepared receipts | `src/IM/application/agent_config_operations.py:154-305,533-565,845-889`; `src/IM/infra/repositories/agent_config_operations.py:44-100,199-249`; `src/personal_assistant/gateway/config_apply_receipts.py:37-106,155-164` | lost-ACK/compensation tests in `test_agent_config_operation_flow.py:125-185,431-530`; legacy receipt tests in `test_gateway_config_operations.py:155-214` | aligned |
| Mirror read preserves raw legacy `skills_selection_mode=null`; live/write use effective intent; reconnect alone does not migrate YAML | `src/IM/api/routes/agents.py:226-269,394-441`; `src/personal_assistant/gateway/agent_config_sync.py:1300-1447`; `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts:517-563` | `tests/im_service/contract/test_agent_config_contract.py:68-103`; `tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py:200-254`; frontend API normalization tests | aligned |
| Explicit-empty selection has no Skill distillation readiness and produces no prompt | `src/personal_assistant/gateway/distill_prompt.py:111-135`; `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:918-934` | `test_gateway_distill_prompt_resolver.py:164-195`; `chat-workspace.integration.test.tsx:620-638` | aligned |
| Successful Agent save immediately invalidates cached SlashPicker candidates | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1352-1373`; query prefix at `chat-workspace-page.tsx:381-423` | `agent-detail-page.test.tsx:843-907` | aligned |

The D4 correction now distinguishes raw transport preservation from effective
behavior and records the rolling protocol required to keep pre-feature fingerprints
stable. It preserves the original acceptance: new discovery never widens an
explicit selection, successful saves govern the next new reply, and clear-all is
not reinterpreted as default discovery.

## Complete delta ledger

The five delta files contain **12 requirements / 54 scenarios**. Together with the
original unit spec, the final target is **17 requirements / 66 scenarios**. Every
delta scenario is explicitly accounted for below.

| Delta requirement | Scenarios reconciled | Evidence/result |
|---|---|---|
| CLI MODIFIED — CLI 自有装配定义产品 prompt、工具集合和扩展目录 | 装配保持在产品包; 工作区 Claude/Codex; 用户主目录 Claude; workspace 与全局目录; 缺失兼容目录 | CLI product-layout, resolver and architecture-contract tests — aligned |
| Gateway MODIFIED — PA 内置 skill 启动自举 | 新安装; 升级刷新; 非内置保留; 刷新失败; backup 清理失败; 并发刷新; 显式选择不因刷新改变; 显式非空 Feishu bundle; default 不物化; explicit-empty 不扩宽; 静态 Feishu IM ingress; 独立 Lark 监听 | bootstrap/atomic-refresh and complete Feishu mode matrix — aligned |
| Gateway MODIFIED — Gateway 配置 operation 可幂等恢复 | applied retry; status recovery; all persistent crash boundaries; operation-id reuse rejection; rolling old/new IM/Gateway | versioned canonicalization, stored schema, receipt replay/status and recovery tests cited above — aligned |
| Gateway ADDED — PA Agent 从有序工作区与全局兼容根发现 Skill | workspace capability; capability/runtime same source; missing roots; shared-only create candidates | PA layout/common resolver/reporter/runtime/shared-only tests — aligned |
| Gateway ADDED — PA Agent 配置区分默认发现与显式空选择 | explicit clear; legacy empty; automatic writers; `skill_created`; explicit-empty distill | five-state session/writer/distill matrix — aligned |
| IM MODIFIED — 节点 runtime 能力按需解析 | node features; agent feature fields; model provider; effective-model reasoning UX; safe reasoning descriptor; Skill location/source_group; old payload fallback | capability proxy/contracts and frontend normalization/fallback tests — aligned |
| IM ADDED — 配置页按 Skill 来源分组批量调整 | group select then item edit; group cancel/tri-state; narrow layout | selector/create/detail tests including keyboard, focus, wrapping and hidden names — aligned |
| IM ADDED — API 区分 default discovery 与 explicit allowlist | explicit-empty page/runtime; post-save SlashPicker refresh; mirror raw-null preservation | repository/API/session/cache/mirror tests — aligned |
| Kernel SDK MODIFIED — Kernel 提供中立能力查询 | runtime-consistent queries; `skill_view`; workspace-then-shared ordering; shared-only query | SDK query and ordered/shared-only contract tests — aligned |
| Kernel skills MODIFIED — preview/list/runtime 集合一致 | multiple ordered roots; preview/runtime parity; legacy single-directory default; returned location | common root builder and list/preview/runtime/`skill_view` tests — aligned |
| Kernel skills ADDED — 兼容读取不改变管理写入 root | compatibility read and native-root write | `skill_manage` native-writer regression — aligned |
| Kernel skills ADDED — 无真实 workspace 时只查 shared roots | prospective candidates exclude repo workspace | `list_shared_skills` leakage regression — aligned |

## Canonical merge fitness

All six `MODIFIED` requirements are complete replacements:

| Requirement | Full-replacement audit |
|---|---|
| CLI product integration | Retains both current scenarios and adds three compatible-root cases |
| Gateway builtin bootstrap | Retains bootstrap/refresh/failure/concurrency/listener behavior; refines former generic/empty allowlist cases into explicit-nonempty, default and explicit-empty outcomes |
| Gateway config operation recovery | Retains all four current idempotency/recovery scenarios and adds rolling schema negotiation |
| IM runtime capability proxy | Retains all six current feature/model/location scenarios, extends grouping and adds old-payload fallback |
| Kernel neutral capability query | Retains all three current scenarios and adds shared-only prospective query |
| Kernel preview/list/runtime consistency | Retains preview/runtime/location behavior; deliberately replaces the stale omitted-dir scenario with the documented current `.nano` default and adds ordered readers |

The six `ADDED` requirements are complete and there are no `REMOVED` items. Their
scenarios describe durable consumer-visible behavior. No delta names functions,
classes, tests or incidental storage layout. Operation id/fingerprint/receipt/status
and stable error-code terms are IM↔Gateway protocol guarantees already present in
canonical requirements, not an implementation walkthrough. Mirror `null`,
distiller-unavailable and SlashPicker refresh are observable wire/UI contracts.

Original `spec.md` acceptance remains fully projected: compatible-root discovery,
first-root-wins resolution, explicit selection on the next reply, grouped selection
and missing-root tolerance all map to the final CLI/Gateway/IM/Kernel deltas.

## Uncovered Observable Behavior

None. The final production diff is covered by ordered roots/native writer; CLI/PA
composition; capability `location`/`source_group`; selection persistence and all
automatic writers; IM/Gateway operations and mirror projection; preview/runtime/
SlashPicker/distill; and grouped create/detail UI contracts.

## Command evidence

| Command/scope | Result |
|---|---|
| `git diff --name-status fbdddd881..c146cc555` | only `design.md` and Gateway/IM delta-specs changed |
| `git merge-base --is-ancestor c146cc555 6790ad5e9` | PASS |
| non-doc diff `fbdddd881..6790ad5e9` | empty; implementation snapshot unchanged |
| delta heading audit | 12 requirements / 54 scenarios; 6 MODIFIED, 6 ADDED, 0 REMOVED |
| `git diff --check fbdddd881..c146cc555` | PASS |
| `PYTHON=/Users/czj/miniforge3/bin/python ./scripts/docs-check` | PASS; 226 maintained Markdown sources and 67 required routes |
| retained Round 4 implementation evidence | 93 affected Python, 98 focused frontend, 3169 full Python, 640 full frontend; build/Ruff/format all PASS |

## Findings and outcome

No delta-mismatch, implementation-mismatch or non-blocking suggestion.

Outcome: **aligned**. The corrected design and Gateway/IM delta-specs match the
final implementation, original acceptance criteria and canonical current
requirements, and are suitable for canonical merge.

## Round 5 — user-directed protocol scope correction

The user rejected the following addition as redundant backward compatibility:

> 傻逼，不做这种多余的后向兼容！！！！冗余设计

This supersedes Round 4's mixed-version protocol conclusion. The delivered
operation contract has one current canonical fingerprint that includes effective
`skills_selection_mode`; it retains same-version idempotency, lost-ACK status
recovery, compensation and crash recovery. It deliberately removes
`agent-config-v1`/`agent-config-v2` negotiation, capability advertisement,
schema persistence, representability rejection, old operation/receipt recovery
and their migrations. Existing persisted profiles whose selection mode is absent
remain readable without eager migration; that is preservation of user data, not
mixed-version protocol support.

Local scope verification is recorded in the M1 progress log. The archived Round
4 browser evidence remains a record of the then-tested implementation; it must
not be read as acceptance of the removed rolling-compatibility behavior.

The user-directed patch passed 54 focused protocol tests, 115 expanded
IM/Gateway/contract tests and 86 frontend Agent-config/chat tests. Patch-mode
code review and its independent verifier found no actionable issue.
