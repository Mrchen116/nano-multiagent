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
