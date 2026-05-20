# bugfix-371: 测试套件无法全量收集 + 无 CI 兜底

## Relations

- Related: feat-370（测试规范，已立规则杜绝同类新发生；本 unit 治存量并补 CI 兜底）

## 原始报告

来自对测试现状的审视（用户要求"从代码规范、代码仓管理角度审视测试"时发现）：

> ```
> $ pytest --co -q
> ERROR tests/unit/test_m170_rerun_acceptance.py
> !!!!! Interrupted: 1 error during collection !!!!!
> 2170 tests collected, 1 error in 1.17s
> ```
> ImportError: `from playwright.async_api import TimeoutError` → ModuleNotFoundError: No module named 'playwright'

用户后续确认要清理存量：

> 然后现在要清理过去的存量了。你给我规划一下，你要怎么做？

## 澄清记录

- Q1: Phase 0（修 m170）与 Phase 1（加 CI）合成一个 unit，还是拆开？
  A(原话): 「ok，按你说的开始」（确认采纳规划中"Phase 0+1 可以合成一个 bugfix unit"）
  Agent 解读: 合成本 unit。m170 修复是 fix，CI 是 RCA 推出的系统性预防，两者同属"恢复并守护测试可运行性"，合一更完整。

- Q2: 本 unit 是否包含测试清理（重命名/合并/拆分/删快照）？
  A(原话): （来自规划对齐）「按你说的开始」——规划中 Phase 2/3 的清理被划为独立 refactor unit，靠覆盖率测量清单驱动。
  Agent 解读: 本 unit 只做"恢复全量可收集 + 建绿色基线 + 加 CI 兜底"，不动任何其它测试内容。清理另立 unit。

## 现象与复现

- 环境：仓库根，`.venv` 已装 `pip install -e ".[dev]"`，playwright **不在依赖中**。
- 步骤：`pytest --co -q`（或 `pytest` 全量）。
- 期望：收集全部用例并运行。
- 实际：`tests/unit/test_m170_rerun_acceptance.py` 在模块顶层 `from playwright.async_api import ...`，缺依赖 → `ModuleNotFoundError` → **整个收集阶段 `Interrupted: 1 error`，2170 个用例一个都跑不了**。
- 该文件还有两个叠加问题：① 它是浏览器 E2E（13 个用例）却放在 `tests/unit/`；② 没有 `@pytest.mark.e2e`，所以 `pytest -m "not e2e"`（AGENTS.md 写的标准命令）也跳不过它。

## 影响范围

- 谁受影响：所有开发者 + 所有 worker agent。任何人跑全量 `pytest` 或 `pytest --co` 都直接被中断。
- 多严重：高。**这套测试现在大概率没人在本地完整跑通过**——否则不可能留着这个硬报错。测试资产事实上处于"写完即冻结、无人持续执行"的腐烂状态。
- 数据损坏：无。但有"虚假安全感"风险——大家以为有 2170 个测试在守护，实际全套跑不起来。

## 根因分析（RCA）

- **直接原因**：可选/重依赖（playwright）在模块顶层裸 import，缺依赖时 pytest 收集阶段即抛错中断全局。
- **为什么这种错能进来且长期存活**：
  1. **无 CI**——没有任何自动门禁在每次 push 跑全量收集，坏了没人知道，能长期沉在仓库里。
  2. **当时无测试规范**——没有"可选依赖必须 importorskip / 浏览器测试必须落 e2e + marker"的规则告诉 worker（已由 feat-370 立规则，杜绝同类新发生）。
  3. **命名/落层失序**——文件按 milestone 编号命名（m170）且错放 unit 目录，掩盖了它其实是 e2e。
- **预防**：本 unit 补 CI 兜底（直接堵住"坏了没人发现"）；规则层 feat-370 已立。

## 修复方向

1. **修 m170**：顶层 import 改 `pytest.importorskip("playwright")`；文件移到 `tests/e2e/`、打 `@pytest.mark.e2e`、按行为重命名去掉 `m170` 编号。
2. **扫并加固同类**：全量收集恢复后，确认没有其它顶层裸 import 重依赖的测试。
3. **建绿色基线**：`pytest --co` 不再中断；`pytest -m "not e2e"` 完整收集并跑出基线（既有失败只记录，不在本 unit 修）。
4. **加 CI 兜底**：GitHub Actions（开源仓免费无限），Linux runner，`pytest -m "not e2e"` + 前端 `npm test`，触发限 `pull_request` + `push: main`；e2e 单独 workflow 手动/定时，不进每次 CI。

行级方案在 milestone 进行。
