# M1-fix Progress

## 澄清记录

- `on_other` 分支（非本 run_id 事件）是否也重置 idle deadline？
  决策：**不重置**。`on_other` 收到的是其他 run 的事件，跟本 run 是否卡死无关。
  只有本 run_id 的事件才说明本 run 仍在活跃，才值得重置 idle deadline。
  即使有其他 run 的事件持续流出，本 run 已经无事件就是卡死。

---

### R1 — 新增失败测试（Red）

- Context: 需要在不实际 sleep 1800s 的前提下验证两个语义：① 持续有事件不被杀；② 卡死被杀。通过 `idle_timeout` 参数注入小值控制。
- Decision: 在现有 `tests/unit/test_session_stream.py` 追加两个测试。
- Rationale: 现有文件已有完整 fixture 结构，就地追加而非新建文件。
- Evidence:
  - Tests: 两个新测试在修改前均 FAIL（Red 状态确认）
  - Entry: N/A（纯单元）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 之前的最后 commit（unit 分支 HEAD 59cff151）
- Commits: C1=dec4e479

### R2 — 修改 drain_run 为空闲超时实现（Green）

- Context: `session_stream.py` 的 `drain_run()` 把 `deadline` 算死后不更新，改为每收到本 run 事件就重置。参数名 `terminal_timeout` 改为 `idle_timeout`，保留向后兼容默认值改为 1800s。
- Decision: 重命名参数 `terminal_timeout` → `idle_timeout`（更准确描述语义），默认 1800s。每次收到 `run_id` 匹配的事件重置 `deadline`。
- Rationale: `terminal_timeout` 命名误导，是命名与语义不一致的根因之一（见 fix.md 根因段）；借此修复顺手纠正。
- Evidence:
  - Tests: 全部测试通过（8 原有 + 2 新增 = 10 通过）
  - Entry: N/A（纯单元）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 commit dec4e479
- Commits: C2=8eaa5bdd

### R3 — 更新 commands.py + 补文档（docs）

- Context: `commands.py` 两处 `terminal_timeout=120.0` 需更新；fix.md 修复/验证两段需回填。
- Decision: 两处调用改为 `idle_timeout=1800.0`（明确传参，让 reader 清晰知道调用方意图）。
- Rationale: 虽然 1800s 是新默认值，但显式传参比依赖默认值更好——阅读代码时不需要跳去看函数签名。
- Evidence:
  - Tests: 全部通过（pytest -m "not e2e" 全绿）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C2 commit 8eaa5bdd
- Commits: C3=见下（本次提交）
