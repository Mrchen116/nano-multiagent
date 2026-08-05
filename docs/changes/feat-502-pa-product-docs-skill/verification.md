# Verification Report: feat-502

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → ea59765053a8bc8fb253f5b3f1ae3dc6d73cda0b`

## Summary

- Mode: `full`
- Delta range: N/A
- Focus issues: N/A
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone；5/5 requirements |
| Correctness | 17/17 scenarios mapped |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: M1 的 R1 Red、R2 Green、R3 Verify 均已完成。`tasks.md:3-5` 的三个 roadpoint 分别由 `progress.md:14-60` 的 Red/Green、影响面和隔离真栈证据支撑；本轮又在 `validated_at` 上独立复跑了 39 个聚焦/IM 创建测试、9 个显式选择/skill gate/架构测试、Ruff、docs-check、diff check 和 skill validator，全部通过。
- Spec 覆盖：5 条 Requirement 均有实现投影。产品手册供给/默认选择由 `bootstrap.py:74-121`、`upstream_reporter.py:123-142` 和现有 IM 选择链完成；全部内置 skill 刷新由 `bootstrap.py:30-71,99-120` 完成；产品问答、版本与现场证据边界由 `nanoassistant-docs/SKILL.md:8-14,175-186,219-319` 完成。
- Milestone 退出标准：worker 轨的安装、恢复、保护、可发现性、`default_on`、无 `read` 完整可达性和容量边界均有永久测试（`test_builtin_skill_bootstrap.py:26-254`）。reviewer 轨的真 IM/Gateway/LLM 旅程已有一次实施期真栈证据（`progress.md:43-54`），全部用户场景由并列的 `change-reviewer` gate 独立验收，不用单元测试伪造模型触发结论。
- Prototype / Reference 覆盖：N/A。`design.md` 明确无前端改动且不产出 prototype（`design.md:113-120`）；手册设计明确拒绝 references/read 第二跳（`design.md:93-101`）。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试 / 证据 | 状态 |
|---|---|---|---|
| 产品说明书作为可关闭的默认 PA skill / 新建 Agent 默认启用 | `src/personal_assistant/reporter/upstream_reporter.py:123-142`; `src/IM/api/routes/nodes.py:244-263`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:31-36,374-386` | `test_builtin_skill_bootstrap.py:172-229`; `test_agent_create_contract.py:126-190`; `agent-create.test.tsx:282-361` | covered |
| 同 Requirement / 默认 skill 集合获得手册 | `src/personal_assistant/gateway/agent_config_sync.py:195-203`; `src/personal_assistant/builtin_skills/bootstrap.py:99-121` | `test_gateway_im_config_sync.py:899-934`; `test_builtin_skill_bootstrap.py:172-254` | covered |
| 同 Requirement / 升级不改写已有显式选择 | installer 只写全局 skill root：`bootstrap.py:74-121`；IM profile 继续是选择真值：`src/IM/api/routes/agents.py:181-205` | `tests/im_service/unit/test_gateway_node_persistence.py:83-128`; `progress.md:43-54` | covered |
| 同 Requirement / 用户关闭后不再使用，可重新开启 | 详情页直接按 profile 选择并保存：`agent-detail-page.tsx:1735-1749`；`skill_view` 以 session skills gate 强制 | `tests/unit/test_skill_view.py:193-221`; 实施期真栈仅启用手册后成功调用：`progress.md:43-54` | covered |
| 随包内置 skills 与当前 PA 版本一致 / 升级刷新全部内置 skills | 稳定排序枚举包内直接子目录并逐项同步：`bootstrap.py:99-120` | `test_builtin_skill_bootstrap.py:26-59,147-158` | covered |
| 同 Requirement / 本地修改的内置 skill 被完整替换 | 目录级 staging/rename：`bootstrap.py:30-56` | `test_builtin_skill_bootstrap.py:42-59` | covered |
| 同 Requirement / 非内置用户 skills 保持 | 安装器只处理当前包声明的名称：`bootstrap.py:99-120` | `test_builtin_skill_bootstrap.py:61-71` | covered |
| 同 Requirement / 刷新不改变 Agent skill 选择 | 同步实现无 IM/profile 依赖：`bootstrap.py:5-16,74-121`；配置依旧从 profile/runtime 流入 | `test_gateway_node_persistence.py:83-128`; `test_gateway_im_config_sync.py:937-970` | covered |
| Agent 按需用说明书 / PA 对话入口询问产品能力 | frontmatter 触发描述：`nanoassistant-docs/SKILL.md:1-4`；完整手册：`nanoassistant-docs/SKILL.md:6-319` | `test_builtin_skill_bootstrap.py:172-254`；真模型完成 `skill_view(nanoassistant-docs)` 并回答：`progress.md:43-54` | covered |
| 同 Requirement / 普通任务不触发 | 触发描述仅列 PA 产品问题，正文不入每轮 prompt：`nanoassistant-docs/SKILL.md:1-4`; 候选注入依旧复用 Kernel skill 链 | 按 design 由 reviewer 真模型旅程验收；本 unit 未加随机模型行为的伪回归测试 | covered |
| 同 Requirement / 超出 PA 手册边界 | `nanoassistant-docs/SKILL.md:14,26,310-319` | 手册本体契约 + reviewer 用户旅程 | covered |
| 回答与用户使用的 PA 版本一致 / 基础问答无需联网 | 随包自包含手册与离线规则：`nanoassistant-docs/SKILL.md:8-14`；只需 `skill_view` 可取全文 | `test_builtin_skill_bootstrap.py:216-254`；真栈工具轨迹只有 `skill_view`：`progress.md:43-54` | covered |
| 同 Requirement / 明确询问最新版或升级差异 | `nanoassistant-docs/SKILL.md:10-13` | 手册本体契约 + reviewer 用户旅程 | covered |
| 同 Requirement / 远端信息不可用 | `nanoassistant-docs/SKILL.md:12-13` | 手册本体契约 + reviewer 用户旅程 | covered |
| 产品说明与现场状态有证据边界 / 询问当前配置或运行状态 | `nanoassistant-docs/SKILL.md:10-13,167-173,219-228` | 真栈回答区分 started 与 Gateway ready：`progress.md:43-54`；reviewer 覆盖其余现场旅程 | covered |
| 同 Requirement / 现场行为与说明书不一致 | `nanoassistant-docs/SKILL.md:11-13,306-308` | 手册本体契约 + reviewer 用户旅程 | covered |
| 同 Requirement / 说明书没有覆盖答案 | `nanoassistant-docs/SKILL.md:13-14,310-319` | 手册本体契约 + reviewer 用户旅程 | covered |

### 刷新失败扩展契约

Gateway delta 还要求“单项失败恢复旧完整目录并继续启动”。实现在 staging 切换失败时移除不完整新目标、把 backup 原子改回原名，再由外层记录 skill 名和异常并继续枚举（`bootstrap.py:45-71,110-120`）；故障注入测试同时断言旧主文件、旧额外文件、后续 Lark skill 成功与可观测错误（`test_builtin_skill_bootstrap.py:74-111`）。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 全部随包内置 skill 由 PA 托管，以整目录替换 | 是 | `src/personal_assistant/builtin_skills/bootstrap.py:99-120`; 只枚举包内含 `SKILL.md` 目录，非内置名不被扫描 |
| D2 同文件系统 staging + backup，单项失败恢复并继续 | 是 | `bootstrap.py:30-71,110-120`; `test_builtin_skill_bootstrap.py:74-111` |
| D3 单份自包含 `nanoassistant-docs/SKILL.md`，无 `read`，低于 50,000 字符结果预算 | 是 | 包内目录只有 `SKILL.md`，文件 20,233 bytes；`test_builtin_skill_bootstrap.py:233-254` 断言全文相等及序列化结果低于 tool budget |
| D4 已安装手册优先，现场要核实，只在明确询问最新版时查官方远端 | 是 | `nanoassistant-docs/SKILL.md:8-14`，并在模型、Gateway 与排障章节重申现场证据边界（`:167-173,219-228,280-308`） |
| D5 不改 IM/前端，复用现有 `default_on` 和显式 allowlist | 是 | unit 实现 commit 只改 PA 包资源、installer、lifecycle 文案和聚焦测试；既有链路在 `upstream_reporter.py:123-142`、`nodes.py:244-263`、`agent-create-page.tsx:31-36,374-386` |
| 生产 owner 仍是 Gateway foreground lifecycle，runtime 构建前刷新 | 是 | `src/personal_assistant/gateway/process_lifecycle.py:39-56,120-148` |
| 不改 Kernel 公共契约，不新建平行发现/配置机制 | 是 | 复用 `build_pa_kernel`、`list_skills`、prompt preview 和现有 `SkillViewTool`；无 `src/agent` / `src/IM` 产品改动 |
| 跨包依赖和注释/docstring 规范 | 是 | `src/personal_assistant` 新生产代码未 import `agent.core` / `agent.platform`；两个架构 contract 测试通过；public installer/lifecycle 入口的 docstring 已更新（`bootstrap.py:74-90`; `process_lifecycle.py:39-44`） |

### Prototype / Reference Contract

N/A. 本 unit 没有前端原型或 reference artifact；单文件手册本身就是 design 批准的运行时资源。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

## Corrected Delta Reconciliation

N/A for `verification_mode=full`.

# Round 2

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → b4dc3bbaf2471a383627b17c373c5135fe2c6f2a`

## Verification Report: feat-502

### Summary

- Mode: `targeted-closure`
- Delta range: `ea59765053a8bc8fb253f5b3f1ae3dc6d73cda0b..b4dc3bbaf2471a383627b17c373c5135fe2c6f2a`
- Focus issues:
  - backup cleanup failure leaves old skill discoverable ahead of canonical directory
  - concurrent Gateways with different config but shared HOME can roll successful refresh back to old directory
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/2 focus issues fully closed |
| Correctness | 1/2 focus issues fully protected |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Targeted Closure

### Focus 1: cleanup 失败后旧版 skill 被优先发现

**Closed.** staging 与 backup 现在都位于 skill root 下的 `.archive` 隔离目录（`src/personal_assistant/builtin_skills/bootstrap.py:49-63`）；现有 `SkillRegistry` 在递归扫描时明确剪掉 `.archive`（`src/agent/core/skills/registry.py:41-58`）。故障注入测试让 backup 删除真实失败后，通过正式 `SkillRegistry` seam 确认发现位置仍是 canonical `nanoassistant-docs/SKILL.md`，且描述来自新版（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:115-154`）。

### Focus 2: 共享 HOME 的并发 Gateway 可把成功刷新回滚为旧版

**Implementation closed; permanent regression coverage remains incomplete.** `install_builtin_skills()` 现在以 destination root 下稳定的 `.builtin-skills-sync.lock` 作为用户全局锁文件，用 `fcntl.flock(..., LOCK_EX)` 获得跨进程排他锁，并在整个内置 bundle 的目录切换期间持有（`src/personal_assistant/builtin_skills/bootstrap.py:35-46,118-140`）。本轮一次性双进程检查确认：第二进程在第一进程释放锁前不能获得同一 root 的锁，释放后才继续（`CROSS_PROCESS_ROOT_LOCK_PASS`）。这一局部串行化复用现有 PA root，未新建跨包或跨机机制，不触发 full verification 升级。

## Coherence

- `.archive` 复用 Kernel 已有的归档隔离约定，没有为临时目录再造发现排除规则；符合 design D1/D2 对整目录替换、失败恢复和成功项不回滚的约束（`docs/changes/feat-502-pa-product-docs-skill/design.md:75-91`）。
- 锁仅位于 `personal_assistant.builtin_skills` 内，没有增加 `personal_assistant → agent.core/agent.platform` 依赖；针对性架构 contract 5 tests 通过。
- 受影响代码 Ruff check 和 format-check 通过。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:157-193` 只把 `_builtin_skill_sync_lock` 替换为观察 context manager，再断言私有 `_sync_skill_directory` 在 context 中被调用；它没有观察两个进程不能交叉切换这个运维结果，而且 `_builtin_skill_sync_lock` 即使退化为 no-op，该测试仍会通过。这不满足 `docs/development/testing.md:9-20` 的可观察 seam 和“不测私有实现细节”要求，也没有把本轮并发回滚失败原因留在永久回归门禁中。请把该测试改为确定性的双进程行为测试：一个进程持有同一 target root 的刷新锁/进入切换段时，第二个进程不得进入切换段，释放后才能继续；或直接编排原始交叉并断言最终 canonical 目录仍是当前包版本。保留在现有 bootstrap 测试 owner 中，不需要增加另一层重复测试。

### SUGGESTION（可以修）

- None.

# Round 3

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → ffb7ec40b2a17ff196a6b9059e1c0a6ede3847ab`

## Verification Report: feat-502

### Summary

- Mode: `targeted-closure`
- Delta range: `b4dc3bbaf2471a383627b17c373c5135fe2c6f2a..ffb7ec40b2a17ff196a6b9059e1c0a6ede3847ab`
- Focus issues:
  - Round 2 WARNING: root-lock regression test mocks private helper and would pass if real `fcntl` lock became no-op
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 focus issue closed |
| Correctness | 1/1 focus issue protected |
| Coherence | Followed |

All checks passed. Ready for PR.

## Targeted Closure

### Focus: root lock 回归测试只验私有 helper

**Closed.** 新测试通过公开 `install_builtin_skills()` 分别启动两个 `spawn` 子进程（`tests/unit/personal_assistant/test_builtin_skill_bootstrap.py:30-58,191-217`）。第一个 installer 已进入真实 skill 切换段后，父进程对同一 root 锁文件执行 `LOCK_EX | LOCK_NB`，必须收到 `BlockingIOError`，因而直接观察到操作系统级跨进程 lock contention（`:218-232`）。若生产 `fcntl` 锁退化为 no-op，父进程会立即获锁并在 `assert root_lock_is_held` 失败；结论不再依赖 mock 的 context-manager 调用或私有 helper 调用次数。

测试随后启动第二个 public installer，在第一个释放切换段后等待两者完成，断言两个进程都以成功结果退出，最终 canonical `nanoassistant-docs/SKILL.md` 是当前包内容，且锁已可再次获取（`:234-263`）。这一可观察 seam 同时保护“切换期间真实互斥”、“第二 installer 最终完成”和“两进程后 canonical 内容不回滚”三个运维结果。对 `_sync_skill_directory` 的局部替换只用于把第一个真实切换段确定性暂停，不是测试结果的观察点。

## Verification Evidence

- 定向双进程测试连续运行 5 次：5/5 PASS，单次约 0.95–1.36s。
- 整个 `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py`：13 passed。
- Ruff check：PASS；Ruff format-check：1 file already formatted；`git diff --check` 对本轮 delta：PASS。
- 归属合规：测试继续放在现有 bootstrap owner 文件，保护的是稳定的跨进程运维边界；未新建 milestone 命名文件，也未在 integration/e2e 层重复同一失败原因。

## Coherence

- 此 delta 只替换不足的回归测试并追加证据记录，未改变产品实现、spec/design 映射、依赖方向或用户可观察行为，因此不需要升级 full verification。
- `spawn` 进程在当前 macOS/Python 门禁中稳定运行；超时与 `finally` 回收确保失败时不留子进程。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.
