# feat-532-M0: H02 非计分基础设施 Pilot — Tasks

> 对齐: ../design.md（2026-08-11，R3 Approved）

## 目标

以版本化 provisional H02 fixture 真正运行 `1 case × 1 repeat` 的 Baseline/Treatment，证明 feat-532 独立实验 overlay 的角色隔离、Memory 构建与直接加载、Candidate–Owner 对话、审计、负担计量、盲评、下一版 scheme 和封存/重放链路闭合；只输出 `infrastructure_pass/fail`，不得形成正式效果结论。

## 退出标准

- [x] overlay 不修改 feat-397 protocol、dataset 或共享 H02 private truth；全部 pilot 资产标记 `formal_eligible=false`。
- [x] 每个 LLM 角色由 schema-validated role-context manifest 驱动，并保存 expected/actual visible files 与输入 envelope hashes。
- [x] H02 allowed corpus 被匿名机械投影；Memory builder 只运行一次且看不到 case/brief/truth；Treatment 以 direct-load 方式消费冻结 store，并保存 provenance/consumption trace。
- [x] Candidate 仓只暴露 spec-only envelope 与唯一 `.agents/skills/change-spec-author` closure；两条 arm 除 Memory task context 外一致。
- [x] 真实 Codex Baseline/Treatment Candidate 与独立 Native Owner sessions 各运行一次；Owner 使用 Simulator-safe provisional context 开放回答，不经过 decision router。
- [x] 两次 run audit、一次 batch audit、两次 burden scoring、neutral judge repo + deterministic conclusion projection、两个 blind judge 和一次 Loop experimenter 全部真实运行并封存。
- [x] schema、seal、receipt、泄漏检查、自动测试、重放验证全绿，pilot 结论仅为 `infrastructure_pass/fail`。
- [x] 不提交 auth、secret、主机完整 Codex history、临时 session home 或未脱敏运行数据。

## 测试策略

- 保护的回归风险与可观察 seam: 从 overlay CLI 运行或 replay 时，任一角色越权文件、envelope/hash 漂移、Memory/arm 污染、缺失真实 role receipt、非 provisional/formal 结论或缺产物都会使命令非零退出；成功时输出可重放的 sealed pilot result。
- 已有保护与处置: `evals/spec_design_alignment/base_repo/tests/test_materialize.py` 与 `test_suite_recipes.py`（keep）保护共享 base 物化，`validate_dataset.py`（keep）保护 feat-397 语义；新风险没有 owner，新增 overlay 自有测试，避免把 feat-532 契约塞入 feat-397 validator。
- 落层/目录/marker: `evals/spec_design_alignment/experiments/feat_532_spec_memory/tests/`，marker 无；它以真实 CLI 子进程覆盖 overlay 的公开入口和 replay seam。真实 Codex pilot 是当次 durable evidence，不放入日常 pytest。
- 文件归属: 新建 overlay 自有 runner/tests/schema/fixture/prompt/scheme/results；理由是 feat-532 是独立 experiment overlay，不能改写共享 suite/feat-397 owner。
- 可选依赖 importorskip: 无；schema 校验复用仓内 dependency-free subset。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 临时 candidate/role workspaces、evaluation homes、auth copy 和 Codex session state；提交前只保留脱敏后的 pilot evidence/receipt/result。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| H02 clean-room base 仍保持原 feat-397 语义 | `evals/spec_design_alignment/base_repo/tests/test_suite_recipes.py` | keep | overlay 只消费现有 recipe，不修改 registry/protocol | 既有 10 tests + dataset validator |
| 确定性物化器安全边界 | `evals/spec_design_alignment/base_repo/tests/test_materialize.py` | keep | 继续通过公开 CLI 物化，不复制内部实现 | 既有 materializer tests |

前端 UI：N/A。

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — Overlay 契约与确定性控制面

- 状态: DONE
- 步骤: 先写失败入口测试，再实现 schema/fixture/manifests、匿名 corpus projection、candidate/neutral repo projection、hash/seal/receipt、泄漏与 replay 校验。
- 验证: overlay tests、共享 base tests、dataset validator、Ruff、`git diff --check`。

### R2 — 真实 Candidate/Owner 与 Memory 链路

- 状态: DONE
- 步骤: 实现 manifest-driven Codex adapter、Memory builder 一次、Treatment direct-load、两条 arm 的持久 Candidate/Owner 对话与实际 context 记录。
- 验证: isolated dry invocation、真实 Baseline/Treatment 各一 run、两 arm 固定输入差异审计。

### R3 — 独立评价与下一版 scheme

- 状态: DONE
- 步骤: 真实运行 run/batch auditor、burden scorer、neutral-repo conclusion judges 与 Loop experimenter；冻结匿名评价后才解盲与归因。
- 验证: 全角色 receipt/schema、judge blindness、experimenter 输出 schema 和禁用 case-specific atom scan。

### R4 — Pilot 封存、重放与交付证据

- 状态: DONE
- 步骤: 生成 `infrastructure_pass/fail` report、seal 和脱敏 evidence，重放全部确定性检查，补齐 progress。
- 验证: replay CLI、overlay/shared tests、dataset validator、docs-check、Ruff、compile、`git diff --check`。

### R5 — Round 1 执行隔离与独立 attestation

- 状态: DONE
- 步骤: 用 macOS Seatbelt profile 把每次 role invocation 限制到本角色 workspace、runtime 与系统运行面，拒读 parent/sibling/control/host home；expected 在执行前封存，独立 wrapper 在调用后回收 argv、cwd、environment policy、readable roots、初末文件 hash 与真实工具观察。
- 验证: read-only/workspace-write 两种角色的 workspace 外 canary 对抗测试；actual schema、expected/actual 对账及 replay 篡改测试。

### R6 — Round 1 确定性 fail-closed 契约

- 状态: DONE
- 步骤: Gate 1 拒绝 untracked/ignored scratch 与 symlink；corpus 只读 clean tracked commit/tree；result 从 sealed evidence 重建并纳入 evidence manifest；补齐 run audit、blind judge、动态 Owner atom 与默认 config 校验。
- 验证: `test_pilot_fail_closed.py` 红转绿；25 项非 replay focused/shared tests 通过。

### R7 — Round 1 新 seal 实跑与证据替换

- 状态: DONE
- 步骤: 代码提交后从 clean tracked snapshot 运行全新 H02，旧 bundle 不复用；新 bundle replay/泄漏/schema/secret/diff 门禁通过后替换版本化结果并更新 progress。
- 验证: 真实 Codex invocation receipt 数、新 seal/evidence hash、全量 focused/shared tests、docs/Ruff format/diff checks。
