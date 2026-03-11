# M105 - legacy root 零残留收口

## Preconditions
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/CodingCLI-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/ROADMAP.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`。
- 工作目录限定在：`/Users/czj/Repos/nano-multiagent/.worktrees/M105`。

## Scope
- 仅处理 legacy `src/nano_multiagent` 根清理相关的测试/文档/导入收口。
- 如主目标已满足，则只补齐 M105 必需的里程碑文档与看板状态。

## TDD / Execution Steps
1. Baseline：先验证 `src/` 顶层目录与负向测试现状，不做盲删。
2. Residue check：复查 `nano_multiagent` 物理目录、importability、contract tests、forbidden snippets。
3. Cleanup/update：若发现残留，则做最小修复；若无残留，则只补齐 M105 文档与看板。
4. Re-check：显式复跑 forbidden legacy snippets、`find_spec(...) is None`、顶层目录期望测试。
5. Delivery：记录证据，提交 M105 分支，合并回本地 `main`，更新 `data/dev-tasks.json` 为 DONE。

## Target Tests
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M105/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M105/tests/unit/test_core_agent_location.py`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M105/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M105/tests/contract/test_multi_product_architecture_acceptance.py`

## Definition of Done
- `src/` 只保留 `agent/`、`coding_cli/`、`personal_assistant/`、`IM/` 四个顶层包。
- `find_spec("nano_multiagent") is None` 持续成立。
- M105 的 `TASKS/` 与 `PROGRESS/` 文档齐备，且写明编码前已阅读 SPEC 与相关模块 SPEC。
- `data/dev-tasks.json` 标记 M105 为 DONE 并附结果摘要。
