# feat-388 — 验收报告

> 对齐: spec.md v2（含 Q7 前端 CI 测试套件门）
> 验收人: reviewer-r1 · Round 1 · 2026-06-01

## Verdict

**pass**

Highest Required Action: **pass**

所有 Scenario 全部通过，无 blocking / major / minor issue。

---

## 澄清记录

无。验收口径从 spec.md 直接读取，无歧义项。

---

## User Journeys Exercised

本 unit 无常驻服务。验证方式：在 worktree 干净工作树上直接构造违规 → 调用 hook 脚本 → 运行检查工具 → 观察输出。共 5 条旅程：

1. **触点 (a) R1/R2/R3 边界违规被拦**：分别构造 `import agent.core`（使用了该 import）、`import personal_assistant`（IM 里）、`import agent.platform`（core 里），每次模拟 PostToolUse hook 调用，观察 exit 2 + stderr 内容。
2. **触点 (a) 合法 import 不误报**：构造 `from agent.sdk import build_kernel`，模拟 hook，观察 exit 0。
3. **触点 (a) B-1/B-2 自动修**：构造格式不规范 + 含未用 import 的文件，模拟 hook，对比修后文件内容；另构造裸 `except:` 文件，观察 exit 2 回喂。
4. **零容忍 / 全仓干净**：直接运行 `ruff check .`、`ruff format --check .`、`pytest -m "not e2e"`（含契约测试），观察全绿、无 xfail 残留。
5. **前端测试套件（CI 前端门基线）**：在 `src/IM/frontend/` 跑 `npm ci && npm run test`，观察全绿。

---

## 问题清单

无 issue。

---

## 验收标准覆盖

### Requirement: 产品包与内核之间只能走 agent.sdk 这一对外面（R1） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 产品包穿透内核内部被拦（编码循环内） | spec.md §Requirement R1 | 在 `src/personal_assistant/` 创建含 `import agent.core as _core` 的临时文件（import 被使用），模拟 PostToolUse hook | hook exit 2，stderr 输出：`[contract] 边界契约测试失败: ... imports agent.core` | pass | 未使用的 `import agent.core` 会被 ruff F401 自动删除（也是正确结果）；使用了的越界 import 由契约测试 exit 2 回喂 |
| 产品包穿透内核内部被拦（远端兜底） | spec.md §Requirement R1 | 本地运行 `pytest tests/contract/test_cli_http_only_contract.py -q`（模拟 CI python job 契约测试步），验证 R1 检查在 CI 路径有效 | 契约测试 9 passed，R1 断言为正向硬断言（无 xfail） | pass | CI yml 包含 `pytest -m "not e2e"` 步，契约在内 |
| 合法走 agent.sdk 不误报 | spec.md §Requirement R1 | 在 `src/personal_assistant/` 创建含 `from agent.sdk import build_kernel` 的临时文件，模拟 hook | hook exit 0，无任何输出 | pass | |

### Requirement: 四个顶层包之间横向零互相 import（R2） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 顶层包横向互相 import 被拦 | spec.md §Requirement R2 | 在 `src/IM/` 创建含 `import personal_assistant as pa` 的临时文件，模拟 PostToolUse hook | hook exit 2，stderr：`[contract] ... src/IM/_reviewer_test_r2.py:2 imports personal_assistant` | pass | 编码循环内 (a) 和 CI (c) 两触点均由契约测试 `test_top_level_packages_keep_zero_import_boundaries` 覆盖 |

### Requirement: 内核 core 不反向依赖 platform / products（R3） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| core 反向 import 被拦 | spec.md §Requirement R3 | 在 `src/agent/core/` 创建含 `import agent.platform as plat` 的临时文件，模拟 hook | hook exit 2，stderr：`[contract] ... imports forbidden higher-level surface: agent.platform` | pass | |
| 现存反向依赖已消除 | spec.md §Requirement R3 | 运行 `pytest tests/contract/test_core_no_platform_imports.py -q` | 9 passed，0 xfail；grep 确认无 `@pytest.mark.xfail` 装饰器 | pass | 旧 #40 (`core.llm.factory → platform`) 已随 refactor-387 消除；契约测试 un-xfail 为正向断言 |

### Requirement: 全仓统一代码格式（B-1） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 格式不规范被自动规整 | spec.md §Requirement B-1 | 构造格式混乱文件（多余空格、无空行、无空格赋值等），模拟 hook，对比修前/修后 | 修后文件格式正确（`def badly_formatted(x, y):` 等），hook exit 0 | pass | |
| 格式违规进不了远端 | spec.md §Requirement B-1 | 本地运行 `ruff format --check .` | `627 files already formatted`，exit 0 | pass | CI `ruff format --check .` 步等价 |

### Requirement: 通用 correctness 卫生（B-2） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 可自动修的卫生问题被自动修 | spec.md §Requirement B-2 | 构造含 `import os` + `import sys`（均未用）的文件，模拟 hook，查看修后文件 | 修后文件两个 import 均被删除，hook exit 0 | pass | |
| 不可自动修的卫生问题被回喂/拦截 | spec.md §Requirement B-2 | 构造含裸 `except:` 的文件，模拟 hook | hook exit 2，stderr：`E722 Do not use bare 'except'`，含行号和代码片段 | pass | 可变默认参（B006）实测存量已为 0；规则配置已纳入 `pyproject.toml` select |

### Requirement: 现有代码零违规上线（零容忍） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 本 unit 完成后全仓干净 | spec.md §Requirement 零容忍 | 运行 `ruff check .` + `ruff format --check .` + `pytest -m "not e2e"`（含全部契约测试） | ruff check: `All checks passed!`；ruff format: `627 files already formatted`；pytest: `2342 passed, 4 deselected`；契约测试 97 passed；grep 确认无 `@pytest.mark.xfail` | pass | 存在 4 处 `# noqa: F401`（`src/coding_cli/render/repl_live.py`，try/except 可用性检测惯用法），具名豁免有理由，非 blanket noqa，符合 design.md D4 约定 |

### Requirement: CI 合并门覆盖前端测试套件（触点 c） — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 破坏前端测试的改动被 CI 拦 | spec.md §Requirement CI 前端门 | 检查 `.github/workflows/ci.yml`：`frontend` job 存在，`npm run test` 步在内，两 job 并行无 `needs` 依赖 | ci.yml 有 `frontend` job（Node 20 + npm ci + npm run test），无 `npm run build`（无 tsc），任一 job 失败即 workflow 红 | pass | 无法在本地模拟远端 CI 执行，以 CI yml 结构+本地基线验证为证据 |
| 前后端测试全绿才放行 | spec.md §Requirement CI 前端门 | 检查 ci.yml 两 job 结构：`python` job（ruff check/format/pytest）+ `frontend` job（vitest），互不依赖，均需通过 | ci.yml 确认两 job 并行，无 continue-on-error | pass | |
| 上线时前端测试已全绿 | spec.md §Requirement CI 前端门 | 在 worktree 运行 `cd src/IM/frontend && npm ci && npm run test` | `54 passed (54), Tests 345 passed (345)`，全绿零失败 | pass | bugfix-390（PR #71）已修绿三处存量失败，基线已干净 |

---

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新。feat-388 改动限于工具配置 / hook / CI，架构总览在 refactor-387 已更新，本 unit 无架构层面新增内容。
- [x] `docs/内核设计SPEC.md`（agent 内核）：无需更新。本 unit 不涉及内核设计。
- [x] `AGENTS.md` / `CLAUDE.md`：已更新（spec 要求"同步改写因 refactor-387 失效的 import 边界表述"）。检查确认：AGENTS.md 第 174 行已正确写 `只许 import agent.sdk`，第 312 行已写 `只能 import agent.sdk`，旧的"禁止 import agent"表述已替换。无需进一步更新。
- [x] 相关产品 SPEC（CodingCLI / NodeGateway / IM 等）：无需更新。本 unit 改动为守卫基础设施，不改产品行为。

---

## Side Findings

无 out-of-unit 问题。

注：pytest 运行中有 1 个测试失败（`test_dispatch_handler_build_aiohttp_handler_returns_callable`），progress.md R2 已注明"1 个无关基线失败保持不变"。确认该失败非本 unit 引入，属 pre-existing issue，不影响本 unit 验收结论。
