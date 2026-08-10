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
- 实际：`tests/unit/test_m170_rerun_acceptance.py` 在 collection 时用 `importlib` exec 了一次性验收脚本 `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`，该脚本**顶层** import playwright（line 11-12，不在 deps）→ `ModuleNotFoundError` → **整个收集阶段 `Interrupted: 1 error`，2170 个用例一个都跑不了**。
- **实施期修正**：最初判断"它是浏览器 E2E 放错了 unit/"。核实后**并非如此**——这 13 个用例全是纯逻辑 unit 测试（读 DB schema、拼 turn summary JSON、解析 picker 候选、monkeypatch 掉超时的 turn-completion），**不驱动真实浏览器**，`PlaywrightTimeoutError` 只当异常类型用。它放在 `tests/unit/` 是对的。playwright 在脚本里实际只用于真实浏览器跑批（`async_playwright`，line 392）和那个异常类型（line 357）。

## 影响范围

- 谁受影响：所有开发者 + 所有 worker agent。任何人跑全量 `pytest` 或 `pytest --co` 都直接被中断。
- 多严重：高。**这套测试现在大概率没人在本地完整跑通过**——否则不可能留着这个硬报错。测试资产事实上处于"写完即冻结、无人持续执行"的腐烂状态。
- 数据损坏：无。但有"虚假安全感"风险——大家以为有 2170 个测试在守护，实际全套跑不起来。

## 根因分析（RCA）

- **直接原因**：单测把被测的纯逻辑放在一次性验收脚本里，靠 `importlib` 在 collection 时 exec 整个脚本来取函数；该脚本顶层裸 import playwright（可选/重依赖），缺依赖时 pytest 收集阶段即抛错中断全局。
- **为什么这种错能进来且长期存活**：
  1. **无 CI**——没有任何自动门禁在每次 push 跑全量收集，坏了没人知道，能长期沉在仓库里。
  2. **当时无测试规范**——没有"可选依赖必须惰性/容错 import"的规则告诉 worker（feat-370 已立"可选依赖 importorskip"规则，但本例是"被测逻辑住在一次性脚本里"这个更深的反模式，建议补进 TESTING_GUIDE）。
  3. **命名失序**——文件按 milestone 编号命名（m170），掩盖了它测的真实行为。
- **预防**：本 unit 补 CI 兜底（直接堵住"坏了没人发现"）；规则层 feat-370 已立，并就"被测逻辑不应住在一次性脚本里"向 TESTING_GUIDE 提议补充。

## 修复方向

本 unit **收窄为只做 M1**（解锁收集）。实施期发现"无绿色基线"这一更大问题（见下），CI 与 161-failure triage 移交后续测试清理 unit。

1. **修 m170（最小改动，本 unit 范围）**：让 13 个 unit 测试在缺 playwright 时也能收集+运行，真实浏览器跑批不变——把 `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` 的 playwright 改成容错/惰性 import（`try/except ImportError` 兜住 `PlaywrightTimeoutError` 给测试引用；`async_playwright` 移到浏览器函数内惰性 import）。测试文件留在 `tests/unit/`（它确实是 unit），按行为重命名去掉 `m170`。**不重构脚本逻辑、不把纯函数搬进 src/**（那是后续 refactor unit）。
2. **扫同类**：全量收集恢复后，确认没有其它顶层裸 import 重依赖的测试。结论：无（另发现 `test_e2e_conftest_finalizer.py` 同样 importlib-exec 脚本但不阻断收集，记入清理 unit）。

### 实施期重大发现：无绿色基线（移交清理 unit）

收集恢复后跑 `pytest -m "not e2e"` 得 **161 failed / 2018 passed**。我的改动只碰 ACCEPTANCE import + 重命名，不可能引发；抽样确认是**存量测试腐烂**——套件长期跑不起来，没人发现里面早已和代码漂移：

- 契约漂移：`test_core_types_contract` 断言的 `Message`/`ToolSpec` 字段列表与现码不符。
- auth fixture 漂移：`test_conversation_rename` 全返回 401（预期 200/400/404）。
- API 改名漂移：`test_sdk_client` 报 `ServerClient` 无 `send_message` 属性。
- marker 缺失：`test_m112_real_process_roundtrip_e2e.py` 在 e2e 目录却没 `@pytest.mark.e2e`，被 `-m "not e2e"` 误跑。

**后续测试清理 unit 的头等任务因此升级为：triage 这 161 个红测试（真回归 / 该删 / 该改），产出分类清单后再动手。**

### 移交后续 unit（非本 unit 范围）

- **加 CI 兜底**：GitHub Actions（开源仓免费无限），Linux runner，`pytest -m "not e2e"` + 前端 `npm test`。**前提是先有绿色基线**——必须在清理 unit 把 161 个红测试处理完之后再开，否则 CI 立刻全红无意义。
- 161-failure triage、命名/落层清理、合并重复、拆巨型文件、删一次性快照。

行级方案在 milestone 进行。
