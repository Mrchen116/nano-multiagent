# refactor-372: 测试套件健康化（triage 161 红 + 清理存量）

## Relations

- Depends on: bugfix-371（已解锁全量收集，是本 unit 能跑全量的前提）
- Related: feat-370（测试规范，本 unit 按其规则清理存量；清理完才有条件上 CI）

## 原始诉求

> 当前代码仓里面有大量的测试，但我怀疑有很多都是没用的，或者可以整合的。你帮我从代码规范，以及代码仓管理的角度去审视一下现在的情况。

> 然后现在要清理过去的存量了。你给我规划一下，你要怎么做？

bugfix-371 实施期暴露出比预想更大的问题后，确认本 unit 的范围：

> 好，起

## 澄清记录

- Q1: 本 unit 先做什么？直接动手清理，还是先测量分类？
  A(原话): 「清理 unit 的体量比一开始预想大(161 个失败要逐个判)。我建议它先只做一件事:测量 + 分类...你看完清单再决定」——用户答「好，起」采纳。
  Agent 解读: 拆成两段。M1 = 只测量+分类，产出 triage 报告，不动代码；人看完清单决定批量删/派 worker 修。M2+ = 按清单执行。

- Q2: 161 个失败里如果发现是产品真坏了（不是测试腐烂），怎么处理？
  A(原话): （沿用项目既有约定）out-of-unit 的真实产品 bug → `gh issue create`，不在本 unit 顺手修。
  Agent 解读: 本 unit 是测试健康化，不改产品逻辑。triage 若判定"测试对、产品错"=真回归，立 issue 单独走 bugfix，不靠删测试掩盖。

- Q3: CI 算本 unit 吗？
  A(原话): 「CI 往后挪，挂到测试清理 unit 之后」「留给清理unit没问题」
  Agent 解读: CI 不在本 unit。本 unit 的产出（绿色基线）是 CI 的前提；CI 另立。

## 现状痛点

可证据化（均为本轮审视实测）：

- **基线不绿**：`pytest -m "not e2e"` = **161 failed / 2018 passed**。套件长期跑不起来（被 m170 阻断收集，bugfix-371 才修），无人发现里面早已和代码漂移。抽样确认三类腐烂：
  - 契约漂移：`test_core_types_contract` 断言的 `Message`/`ToolSpec` 字段列表与现码不符。
  - auth fixture 漂移：`test_conversation_rename` 全返回 401（预期 200/400/404）。
  - API 改名漂移：`test_sdk_client` 报 `ServerClient` 无 `send_message`。
  - marker 缺失：`test_m112_real_process_roundtrip_e2e.py` 在 e2e 目录却没 `@pytest.mark.e2e`，被 `-m "not e2e"` 误跑。
- **体量与冗余**：320 个测试文件 / 61k 行（源码 46k，比 1.3:1）。milestone 编号命名一批（`m102`/`m103`/`m85`/`m86`/`m236`/`refactor353_corrigendum`），其中 `m102`+`m103` import 同一批 gateway 模块，疑似跨层重复。
- **巨型文件**：6 个 >1000 行（`test_cli_main.py` 2754、`test_main.py` 2120、`test_gateway_pipeline.py` 1676…）。
- **一次性快照沉淀**：`tests/acceptance/`、`*_rerun_acceptance` 等一次性验收脚本被当永久测试留存。
- **importlib-exec 反模式**：`test_e2e_conftest_finalizer.py` 同 m170 一样 exec 一次性脚本取被测逻辑（不阻断收集，但同类隐患）。

不改的后果：测试资产持续腐烂、虚假安全感、无法上 CI（基线红，CI 立刻全红无意义）。

## 目标状态

- `pytest -m "not e2e"` 跑到**绿**（真回归立 issue 走 bugfix 后，其余靠修/删/更新腐烂测试达成）。
- 测试套件符合 `docs/TESTING_GUIDE.md`：无 milestone 流水号命名、e2e 目录测试均带 marker、无巨型文件、一次性验收证据不混在套件里。
- 为后续上 CI 备好绿色基线。

## 用户侧验收标准（不变性）

本 unit 面向内部（测试套件），对产品用户**无新行为**。回归基线镜头——清理前后产品行为必须一致：

- [ ] 产品代码（`src/`）行为不变：本 unit 原则上只增删改 `tests/`、命名、markers、文档；不改产品逻辑。（triage 若发现产品真 bug → `gh issue create` 单独走 bugfix，不在本 unit 改）
- [ ] 删除/合并测试不削减真实覆盖：被删的测试，其覆盖的行为要么是重复（别处已覆盖）、要么是一次性验收证据（无回归价值）；唯一覆盖某真实行为的测试不得净删。
- [ ] 现有四个包的对外契约（HTTP API、CLI、事件 schema）行为与清理前一致——contract 测试修正的是"测试对齐现码"，不是放宽契约。

实现层目标（绿基线达成路径、文件如何拆分合并、覆盖率口径）归 design.md。

## 影响范围

- 主要：`tests/`（unit/integration/contract/e2e/im_service/acceptance）+ `ACCEPTANCE/` 一次性脚本。
- 次要：`pyproject.toml`（markers 定义可能补充）、`tests/conftest.py`（e2e 目录自动 marker，若采用）。
- 不动：`src/` 产品逻辑（除非 triage 判定真回归 → 另立 bugfix）。

## 迁移与回滚策略

- **行为不变如何保证**：本 unit 几乎只动测试代码，产品逻辑不碰；每个清理步骤后重跑相关测试 + 全量 `pytest -m "not e2e"`，failed 数只能减不能增。
- **分段推进（design 阶段细化为 milestone）**：
  - M1 测量+分类（不动代码）：跑全量 + 覆盖率，把 161 failed 归类为 `真回归 / 该删 / 该改`，并盘点重复/快照/巨型文件，产出 triage 清单（`regression.md` 式报告）。**人审清单后才进 M2。**
  - M2+ 按清单执行：修腐烂测试、删一次性快照与重复、按行为重命名去流水号、补 e2e marker、拆巨型文件。每类独立小 commit、可 `git revert`。
- **回滚**：每步独立 commit；测试-only 改动天然低风险，单步可 revert 到上一稳定态。真回归 issue 与本 unit 解耦，不阻塞清理推进。
