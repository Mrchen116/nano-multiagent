# M62 - Codex CLI研究三期：TTY/non-TTY契约与交互可观测

## Milestone Contract
- milestone_id: `M62`
- title: `Codex CLI研究三期：TTY/non-TTY契约与交互可观测`
- goal: 研究 codex 的交互态与脚本态输出边界、状态行/事件折叠策略、错误提示分层与可观测统计，形成 nano CLI 商业化前契约模板（映射 M52/M53/M54）。
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M62`
- branch: `milestone/M62`
- test_command: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- dev_tasks_path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- allowed_scope:
  - `TASKS/**`
  - `PROGRESS/**`
  - `LOGBOOK.md`
  - `data/dev-tasks.json`（仅脚本更新）
- forbidden_scope:
  - `src/nano_multiagent/**`
  - `tests/**`
  - 其他与研究文档无关文件
- prevention_rules:
  - 仅文档落盘，不写实现代码。
  - 不改内核/API/CLI 实现。
  - 忽略并行里程碑改动，不回退非本里程碑内容。

## Startup Checklist
- [x] 已阅读 `LOGBOOK.md`
- [x] 已阅读 `COMMENTING_GUIDE.md` 并承诺遵守
- [x] 已阅读 `内核设计蓝图.md`（仅边界约束）
- [x] 已阅读 `PROGRESS/M44-Codex-CLI-研究补充-输入历史-事件折叠-去重策略.md`
- [x] 已确认 worktree/branch：`M62` / `milestone/M62`
- [x] 已建立共享 `data/dev-tasks.json` symlink
- [x] 已跑 baseline：`113 passed, 42 warnings`

## Roadpoints

### R1 TTY/non-TTY 输出边界研究（规则 + 反例 + 代码锚点）
- Acceptance:
  - 明确 codex 在 TTY 与 non-TTY 下的输出边界规则（至少 6 条）。
  - 每条规则给出可复核代码锚点（文件+行号）。
  - 输出至少 4 个反例/误用场景（会导致 JSON 污染、状态行错乱等）。
  - 给出 nano CLI 的迁移约束（仅文档，不改代码）。
- Tests Plan:
  - unit: 不选（研究里程碑，无代码变更）。
  - contract: 不选（仅输出契约草案，不改运行契约）。
  - integration: 不选（无链路改动）。
  - e2e: 不选（本里程碑只做研究文档）。
- Expected Artifacts:
  - `PROGRESS/M62-*.md` 的 R1 章节（规则+反例+锚点）。
- Validation Commands:
  - `rg -n '^#### R1\\.Q1|^#### R1\\.Q2|^#### R1\\.Q3' PROGRESS/M62-Codex-CLI研究三期-TTY非TTY契约与交互可观测.md`
  - `rg -n 'TTY边界规则|non-TTY反例|迁移约束' PROGRESS/M62-Codex-CLI研究三期-TTY非TTY契约与交互可观测.md`
- DoD:
  - 规则、反例、锚点三件套齐全，且与 M52 目标可映射。
- Status: `TODO`

### R2 状态行/事件折叠 + 错误分层 + 可观测指标研究
- Acceptance:
  - 提炼 codex 的状态行门控与事件折叠策略（含 phase 切换）。
  - 提炼错误提示分层模型（input/network/runtime 及建议策略）。
  - 形成指标建议清单：`dedup_dropped/orphan/tool_timeline` 及采样位置。
  - 给出 nano CLI 的可落地埋点草图（仅文档层）。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（研究文档）。
- Expected Artifacts:
  - `PROGRESS/M62-*.md` 的 R2 章节（策略矩阵+观测指标表）。
- DoD:
  - 覆盖状态、错误、可观测三条主线，能直接支撑 M53。
- Status: `TODO`

### R3 商业化前契约模板 + M52/M53/M54 测试矩阵草案
- Acceptance:
  - 输出 `nano CLI 商业化前契约模板`（TTY/non-TTY、事件折叠、错误分层、观测）。
  - 输出 M52/M53/M54 的测试矩阵草案（层级、入口、断言、风险）。
  - 在 `LOGBOOK.md` 追加可复用规则（仅规则，不写过程）。
  - 完成 main 集成 + push + dev_tasks DONE。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（文档里程碑；保留 baseline 门禁结果作为健康检查）。
- Expected Artifacts:
  - `PROGRESS/M62-*.md` 最终交付章节。
  - `LOGBOOK.md` 新增 M62 规则条目。
- DoD:
  - M52/M53/M54 执行者可直接按矩阵拆实现与验收。
- Status: `TODO`
