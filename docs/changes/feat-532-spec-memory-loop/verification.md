# Verification Report: feat-532

> Validation snapshot: `5e822e33a0a0c6d664333ebcb8490675cecb217a → 4ef7629cc4c7842a995b4dde35ad9989eea9c542`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

本轮只验证 design 已实施的 `M0-pilot`。`M1-benchmark-freeze` 的真实 owner freeze、八例 formal Baseline 和 `M2-memory-loop` 的正式双门禁尚未实施，符合 design 的串行边界，不计为 M0 缺失。

| 维度 | 结果 |
|---|---|
| Completeness | 6/7 |
| Correctness | 8/8 |
| Coherence | 有偏离 |

1 critical issue(s), 1 warning(s) found. Fix before PR.

## Completeness

- Tasks: M0 的 7 条退出标准中 6 条有完整实现和 durable evidence；“每个角色只看见获准上下文”的 role-context closure 未被执行层强制或独立证明，见 `C1`。
- Pilot scope: `pilot/h02/config.json:4-24` 固定 H02、`1 case × 1 repeat`、`formal_eligible=false` 与仅 `infrastructure_pass/fail`；`pilot-result.json:1-35` 保持 `effect_claim=null`。
- Real execution: 29 个 context bundle 均有 `thread.started` + `turn.completed`，`thread.started.thread_id` 与各自 `invocation-receipt.json.session_id` 一致；角色计数为 Candidate 9、Owner 9、Memory trace 2、builder 1、run audit 2、batch audit 1、burden 2、judge 2、Loop experimenter 1，总计 29，非 mock。
- Memory: `runner.py:831` 启动一次 task-blind builder，`runner.py:699` 生成只多 `.experiment/task-memory.md` 的 Treatment，`memory/build-receipt.json:1` 记录 `builder_invocations=1` 和真实 Codex，`memory/runtime-consumption-receipt.json:1` 记录 24 条 direct-load entry，`memory/provenance.json` 与两份 run `memory-trace.json` 闭合 build/use 溯源。
- Baseline/Treatment: `runner.py:699-758` 机械比较初始 repo；提交 receipt 显示两臂 base HEAD 相同，共享文件 hash 全等，唯一额外输入为 Treatment Memory。两臂 Candidate 初始 envelope 内容一致，同用一份 `change-spec-author` closure、model、reasoning、tool/network 设定和 Gate 1 契约。
- Native Owner and evaluation: `runner.py:948-1141` 为两臂各启动独立持久 Candidate/Native Owner session；`runner.py:1321-1567` 真实运行 2 次 run audit、1 次 batch audit、2 次 burden、2 个 blind judge 与 1 次 Loop experimenter。
- Judge boundary: `runner.py:1434-1480` 从 neutral repo 建立 judge workspace，只加入 public brief、provisional judge context 和两份确定性 conclusion projection；`runner.py:1787-1799` 精确检查 `.experiment/` 只有这 4 件输入，不含 Q/A、trace、burden、Memory 或 arm identity。
- Seal/replay: `runner.py:1819-1926` 封存 result 和全部 durable artifacts，`runner.py:1953-2082` 校验 seal、schema、identity、role/session 计数、projection、Memory context、leakage 和 evidence manifest；独立 replay 返回 `replay=verified`, `role_invocations=29`, `conclusion=infrastructure_pass`。
- Prototype / Reference 覆盖: N/A，design 无前端原型或外部 must-match reference contract。

## Correctness

M0 是正式 M1/M2 之前的非计分基础设施 pilot；下表只核对本轮应投影的 spec 场景，不把尚需真实 owner 的 formal 冻结与八例效果结论冒充为 M0 要求。

| Requirement / Scenario | 实现位置（file:line） | 测试 / evidence | 状态 |
|---|---|---|---|
| 从广义首文档语料构建 Memory | `runner.py:500-593`, `runner.py:831-907` | projection test + 196 份 corpus / 24 entries / provenance receipt | covered（M0 provisional） |
| Memory 进入当前 spec 流程 | `runner.py:673-758`, `runner.py:948-1141` | direct-load receipt + Treatment Gate 1 first document | covered |
| 单 case 的 whole-lineage / control 排除 | `runner.py:500-593`, `pilot/h02/config.json:10-16` | `test_projection_is_anonymous_whole_lineage_and_replayable` | covered（H02） |
| Memory 影响可区分 loaded / used / rejected / overridden | `runner.py:1094-1120` | Baseline empty trace；Treatment 24-entry complete trace | covered |
| Memory 是两臂唯一工作流变量 | `runner.py:699-758`, `prompts/candidate-task.md:3-15` | arm-difference test + runtime consumption receipt | covered |
| 每个 run 只评一次 author 直接 Gate 1 产物 | `runner.py:1014-1092` | 两臂各一份 first document/patch/run receipt，无 reviewer | covered |
| 对齐负担按 Owner 实际语义贡献计数 | `prompts/burden-scorer.md:1-12`, `runner.py:1379-1406` | 两份 ledger，5/7 contribution units | covered（pilot diagnostics） |
| Native Owner 事后 audit / batch audit，并保持 exploratory 结论边界 | `runner.py:948-1069`, `runner.py:1321-1432`, `runner.py:1886-1925` | auditor `critical_error=false`；`formal_eligible=false`；`effect_claim=null` | covered（M0 provisional） |

## Coherence

| design 决策 | 遵守? | 实现证据（file:line） |
|---|---|---|
| M0 只做 H02 `1 × 1` 非计分全链 pilot | 是 | `design.md:105-109`; `runner.py:1819-1925` |
| Builder task-blind，Treatment direct-load 且两臂其他输入相同 | 是 | `runner.py:831-907`; `runner.py:699-758` |
| Candidate 只有 spec-only envelope 和单 Skill closure | 是 | `runner.py:600-670`; `prompts/candidate-task.md:1-20` |
| Native Owner 保持开放问答，auditor 不介入热路径 | 是 | `runner.py:948-1069`; `runner.py:1321-1432` |
| Blind judge 只看 neutral repo + brief + conclusion + judge context | 是 | `runner.py:1434-1480`; `runner.py:1787-1799` |
| Role-context manifest 是真实、封存且 fail-closed 的 Agent 边界 | 否 | `runner.py:137-165`, `runner.py:168-213`, `runner.py:394-408`; 见 `C1` |
| Pilot 可离线重放，不形成效果主张 | 是 | `runner.py:1886-1925`; `runner.py:1953-2082` |

### Prototype / Reference Contract

N/A.

## Validation Evidence

- `python -m pytest -q .../test_pilot_control_plane.py .../test_materialize.py .../test_suite_recipes.py` → `18 passed in 4.13s`.
- `runner.py replay --artifacts .../h02-pilot-v1` → `replay=verified`, `role_invocations=29`, `conclusion=infrastructure_pass`.
- `scripts/docs_check.py` → `documentation integrity passed: 236 maintained Markdown sources, 67 required routes`.
- `ruff check runner.py test_pilot_control_plane.py` → pass.
- `ruff format --check runner.py test_pilot_control_plane.py` → fail，两个文件均 `Would reformat`，见 `W1`.
- `validate_dataset.py` → 只有 4 条 feat-397 broken link；两个 source 文件在 `executed_base`、M0 baseline `29e8a8d1` 和 `validated_at` 的 SHA-256 分别始终为 `21bd9b...` / `7ab8be...`，两个 target 在三个快照均不存在；feat-532 diff 没有修改 feat-397 protocol/dataset。因此这 4 条是 baseline / out of scope，不归因 M0。
- 安全扫描未发现 durable bundle 中的 `auth.json`、host config/history、sqlite/session DB、cookie/token/Authorization 或临时 role-home 路径；仓内保留的是脱敏 events、hash receipt 和已有版本化首文档的匿名投影。

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — Role-context closure 没有成为真正的执行边界，`expected/actual` 是同一 runner 的自证循环。** `CodexSession.invoke()` 在同一次调用前用 workspace 生成 `expected.json`，紧接着调用同一个 `visible_file_manifest()` 重算 `actual.json`（`runner.py:137-165`, `runner.py:394-408`）；`actual` 不是 Codex 执行侧的 request/capability attestation，也没有记录 resolved argv、可读 roots 或调用后可见闭包。随后的 CLI 只配置 `read-only` / `workspace-write` 与 network-off（`runner.py:168-213`）；当前封存的 Codex CLI 0.145.0 这两种 sandbox 保护写边界，但默认允许读取 workspace 外文件。因此 manifest 中的 `visible_files` 只是 cwd 文件清单，不是强制的 read allowlist；`leakage-check` 只复查这批自报 manifest（`runner.py:1696-1761`），无法证明 builder/Candidate/Owner/judge “只看见获准上下文”。已提交 events 中未观察到越界命令，但这不能替代 design `131-135` 和 M0 退出标准要求的强制边界。**修复：**在 `runner.py:125-264` 的执行 adapter 中使用真正的 per-role filesystem read confinement（隔离 container/mount namespace 或等价的 restricted-readable-roots profile）；在执行前封存 expected manifest，由隔离执行 wrapper 独立回收 resolved cwd/argv/environment policy/readable roots/文件 hash 作为 actual attestation，再 fail closed 对账。在 `tests/test_pilot_control_plane.py:181` 附近增加对抗用例：在 role workspace 外放 canary，验证 shell-capable 与 read-only 角色都无法读取，并验证伪造/篡改 actual 不能与 expected 一起自洽通过。修复后必须从新 seal 重跑 M0，旧 29-call bundle 不得继续作为 `infrastructure_pass`。

### WARNING（提 PR 前必须修）

- **W1 — 新增 Python 实现未通过仓库 Ruff format gate。** 当前 `ruff format --check` 对 `evals/spec_design_alignment/experiments/feat_532_spec_memory/runner.py:1` 和 `evals/spec_design_alignment/experiments/feat_532_spec_memory/tests/test_pilot_control_plane.py:1` 都返回 `Would reformat`，与 `progress.md:60` 的全绿记录不一致，并会被 `.github/workflows/ci.yml:42-43` 拦截。**修复：**用仓库锁定版本执行 `ruff format` 于这两个文件，然后重跑 scoped tests、`ruff check`、`ruff format --check` 和 `git diff --check`。

### SUGGESTION（可以修）

None.

# Round 2

## Verification Report: feat-532

> Validation snapshot: `5e822e33a0a0c6d664333ebcb8490675cecb217a → b9b44035aa7f2b9fb25e96a27e23a7c6e65266d4`

### Summary

Mode: full
Delta range: `30a2be4fb953f6a552c06ddc1883f4fb341ea925..b9b44035aa7f2b9fb25e96a27e23a7c6e65266d4`
Focus issues: `C1 role-context confinement / independent attestation`; `W1 Ruff format`
requires_full_verification: false

本轮继续只验证 design 已实施的 `M0-pilot`。尚需真实 owner freeze 的 formal M1/M2 不计为 M0 缺失。W1 已关闭；C1 的 post-call 独立 attestation、parent/sibling 拒读和子工具断网已实现，但工具仍可读取 role runtime 内的临时 `auth.json`，因此 role-context closure 尚未真正闭合。

| 维度 | 结果 |
|---|---|
| Completeness | 7/8 |
| Correctness | 8/8 |
| Coherence | 有偏离 |

1 critical issue(s), 1 warning(s) found. Fix before PR.

## Completeness

- Tasks: M0 的 8 条退出标准中 7 条有实现和 durable evidence；“每个角色只看见获准上下文且不接触认证秘密”仍未被执行层强制，见 `C1`。
- Pilot scope: `pilot/h02/config.json` 仍固定 H02、`1 case × 1 repeat`、`formal_eligible=false`；`pilot-result.json:1-35` 为 `effect_claim=null` 和 `conclusion=infrastructure_pass`，未冒充 formal 效果结论。
- Real execution: 当前 bundle 有 33 个 context，角色计数为 Candidate 11、Native Owner 11、Memory trace 2、builder 1、run audit 2、batch audit 1、burden 2、blind judge 2、Loop experimenter 1。每个 receipt 都有 `real_codex_cli=true`、exit 0、唯一真实 thread id 和一个 `turn.completed`；多轮 Candidate/Owner session 按 5/6/6/7 次 invocation 复用。
- Independent attestation: `runner.py:203-248` 调用前写 expected，`sandbox_wrapper.py:141-256` 在 subprocess 返回后独立写 actual；33/33 的 argv/cwd/env/readable-roots/input hash/初始文件/tool flags 对账一致。actual 的 `command_execution_observed` 与 events 逐份重算一致，18 份观察到 command execution。
- OS isolation: 现有测试和独立探针确认 read-only/workspace-write 两种 profile 的 parent canary 被 Seatbelt 拒读，sibling workspace canary 也被拒读；33/33 actual 记录 child-tool loopback bind 被拒绝。33 次真实 Codex 请求全部成功返回，证明 Codex 主进程的模型网络未被误断。
- Clean corpus / Gate 1: corpus 固定到 clean tracked commit `96f17e3199a28b3aacfd096eb3d241d45938e7c7` / tree `db940222ae7225668c62a03cfa00c2d0fa835156`，196 份首文档从 Git bytes 投影；回归测试拒绝 dirty/untracked corpus，也拒绝 Gate 1 的 ignored untracked 文件、symlink、超出唯一首文档的 diff 和初末 manifest 漂移。
- Memory / arm equality: builder 唯一真实调用产生 24 条 `M01..M24`，source refs/provenance 闭合；Treatment 直接加载全部 24 条。独立比较两臂首次 Candidate expected manifest，共享的 3736 份 path/hash 全等，Treatment 唯一多 `.experiment/task-memory.md`。Baseline trace 为空；Treatment 封存 trace 实际为 used 5、rejected 18、overridden 1。
- Native Owner / evaluation: Owner refs 从冻结 atoms 动态推导并拒绝未知/重复 ref；两次 run audit findings 为空且 `critical_error=false`，batch audit 无矛盾，burden 为 8/7 units。两个 judge 工作区的 `.experiment/` 都精确为 public brief、P1/P2 conclusion 和 provisional judge context，不含 Q/A、trace、Memory、burden 或 arm identity。
- Seal/replay: 当前 seal 为 `ff49010e9066c5d20f29b82ebb62019e3eac839d6e63059c18b070ab672f3045`，新 bundle 仅保留 33-call 证据，旧 29-call bundle 没有在当前 tree 冒充新证据。离线 replay 重算 audit/leakage/judge/result semantics 和全量 evidence manifest，返回 `replay=verified`, `role_invocations=33`。
- Prototype / Reference 覆盖: N/A，design 无前端原型或外部 must-match reference contract。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试 / evidence | 状态 |
|---|---|---|---|
| 从广义首文档语料构建 Memory | `runner.py:680-731`, `runner.py:1073-1148` | clean-snapshot/dirty-corpus tests + 196-document projection + 24-entry provenance | covered（M0 provisional） |
| Memory 进入当前 spec 流程 | `runner.py:937-998`, `runner.py:1266-1433` | direct-load receipt + Treatment Gate 1 first document | covered |
| 单 case whole-lineage / control 排除 | `runner.py:692-922`, `pilot/h02/config.json` | anonymous projection regression + sealed source snapshot | covered（H02） |
| Memory 影响可区分 used / rejected / overridden | `runner.py:1435-1485` | Baseline empty trace；Treatment 24-entry complete trace | covered；Loop 汇总误报见 `W2` |
| Memory 是两臂唯一工作流变量 | `runner.py:937-998`, `runner.py:2172-2190` | 3736 shared path/hash 全等，唯一 extra 为 task-memory | covered |
| 每个 run 只评一次 author 直接 Gate 1 产物 | `runner.py:1187-1263`, `runner.py:1266-1433` | dirty/untracked/symlink/diff fail-closed tests | covered |
| 对齐负担按 Owner 实际语义贡献计数 | `runner.py:1801-1835`, `prompts/burden-scorer.md` | 两份 ledger，8/7 contribution units | covered（pilot diagnostics） |
| Native Owner 事后 audit / batch audit，保持 exploratory 结论边界 | `runner.py:1166-1184`, `runner.py:1668-1712`, `runner.py:2249-2316` | refs/audit/duplicate-judge/default-config/result-semantic 对抗测试；`formal_eligible=false`, `effect_claim=null` | covered（M0 provisional） |

## Coherence

| design 决策 | 遵守? | 实现证据（file:line） |
|---|---|---|
| M0 只做 H02 `1 × 1` 非计分全链 pilot | 是 | `runner.py:2007-2008`, `runner.py:2319-2383` |
| expected 调用前封存，actual 由独立 wrapper 在调用后回收 | 是 | `runner.py:203-248`; `sandbox_wrapper.py:141-256` |
| Role-context manifest 是真实可读边界，认证只经受控层 | 否 | `runner.py:84-95`; `sandbox_wrapper.py:89-107,227-240`；见 `C1` |
| Builder task-blind，Treatment direct-load 且两臂其他输入相同 | 是 | `runner.py:937-998`; `runner.py:1073-1148` |
| Native Owner 开放问答，auditor 不介入热路径 | 是 | `runner.py:1166-1184`; `runner.py:1266-1433`; `runner.py:1668-1687` |
| Blind judge 只看 neutral repo + brief + conclusions + judge context | 是 | `runner.py:1737-1800`; `runner.py:2159-2160` |
| Loop experimenter 根据冻结结果和 Memory trace 生成下版 scheme | 否 | `next-scheme.json:5` 与 `runs/treatment/memory-trace.json:7-145` 的封存计数不符，见 `W2` |
| Pilot 可离线重放，result semantics 重算，不形成效果主张 | 是 | `runner.py:2249-2316`; `runner.py:2410-2563` |

### Prototype / Reference Contract

N/A.

## Validation Evidence

- `pytest -q test_pilot_control_plane.py test_pilot_fail_closed.py` → `20 passed in 7.23s`；shared `base_repo/tests` → `10 passed in 3.65s`。包含 parent canary、child network-off、dirty corpus、Gate 1 untracked/symlink、audit critical flag、duplicate judge id、dynamic Owner refs、semantic result tamper、forged actual 和 default-config fail-closed 回归。
- 独立 attestation/events 交叉校验 → 33 contexts，argv/cwd/env/roots/input/initial-files/tools/session/turn/receipt 差异为 0；18 份 `command_execution_observed=true` 与 events 一致。
- 独立 Seatbelt 探针 → parent 与 sibling canary 拒读；33/33 child-network probe 拒绝；33 次真实模型请求成功。同一探针的 verifier-only 假 `role_runtime/codex-home/auth.json` 被 shell 成功读取，见 `C1`。
- `runner.py replay --artifacts .../h02-pilot-v1` → `replay=verified`, `role_invocations=33`, `conclusion=infrastructure_pass`。
- `ruff check` → `All checks passed!`；`ruff format --check` → `4 files already formatted`，上轮 W1 已关闭。四个新增 Python 文件的只读 syntax compile 通过。
- `scripts/docs_check.py` → `documentation integrity passed: 237 maintained Markdown sources, 67 required routes`。
- implementation diff 排除历轮 verifier 自有报告后 `git diff --check` 通过；本轮同时清除了 Round 1 报告自身的 3 处 Markdown 行尾空格。
- `validate_dataset.py` 仍只报 4 条 feat-397 broken link。两个 source 在 M0 baseline `29e8a8d1`、`executed_base` 和 `validated_at` 的 SHA-256 恒为 `21bd9b...` / `7ab8be...`，两个 target 在三个快照均不存在；feat-532 diff 未改 feat-397 protocol/dataset/shared truth。因此四条确属 baseline / out of scope。
- 当前 durable bundle 文件名与内容扫描未发现真实 `auth.json`、cookie/token/Authorization、host config/history、session DB 或临时 role-home 路径；这只证明本次 33-call 证据没有已发生泄漏，不能抵消 `C1` 的可读边界缺口。

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — Role-context confinement 仍将临时 OAuth 认证副本暴露给子工具。** `CodexSession` 把主机 `auth.json` 复制到 `role_runtime/codex-home/auth.json`（`runner.py:84-95`）；Seatbelt profile 以 `(allow default)` 开始，只 deny host home、artifacts、parent/sibling/control 路径，没有 deny `runtime_root`（`sandbox_wrapper.py:89-107`），actual 反而把整个 `role_runtime` 宣告为 readable root（`sandbox_wrapper.py:227-240`）。独立对抗探针在不接触真实凭据的前提下写入 verifier-only 假 auth，同一 profile 内的 shell 可成功 `cat` 该文件。因此当前 33-call bundle 虽未观察到 secret 进证据，但恶意或误操作的 role 可把 OAuth token 打印进 events/output；`check_pilot_leakage()` 只拦截特定文件名和 runtime path marker（`runner.py:2094-2203`），也不会识别被打印的 token value。这违反 design `131-135,354` 的获准 context 与“受控认证层”边界，所以上轮 C1 尚未关闭。**修复：**将 credential 从 tool-readable runtime 移到只有 Codex 主进程可读的认证层（process-scoped Seatbelt file-read rule、credential broker 或等价隔离），工具仍可读必需 schema/tmp 但不能读 auth。在 `test_pilot_fail_closed.py:25-76` 附近加入 fake-auth canary，对 read-only/workspace-write 两种 profile 断言 child tool 拒读且 Codex 主网络/认证仍成功；泄漏检查也应用 verifier-only sentinel 证明内容不可进 durable evidence。修改 runner/wrapper 后必须从 clean snapshot 重跑新 seal，现有 33-call bundle 不能继承。

### WARNING（提 PR 前必须修）

- **W2 — Loop experimenter 的下版 scheme 对冻结 Memory trace 做了错误的数字引用，replay 仍放行。** 封存 Treatment trace 有 5 条 `used`、18 条 `rejected`、1 条 `overridden`（`runs/treatment/memory-trace.json:7-145`）；`evaluation/next-scheme.json:5` 却写成 4/19/1，`M0-pilot/progress.md:68` 又重复了该错误。`verify_next_scheme()` 只验非空字段和 forbidden atoms（`runner.py:1506-1532`），replay 因此无法发现这个可机械校验的 evidence 矛盾。这与 design `333,421-423` 要求 Loop experimenter 基于冻结 trace 解释并导出下版 scheme 不一致。**修复：**由 runner 从 trace 生成不可自由改写的聚合计数并传给 Loop role；若 proposal 包含这类精确计数，封存前/replay 时必须与 trace 重算值一致，或删除无法保真的数字声称。增加 tampered next-scheme aggregate 的 replay 拒绝测试，然后重跑完整 seal 产生自洽的 next scheme/progress。

### SUGGESTION（可以修）

None.
