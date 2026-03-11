# M105 - legacy root 零残留收口

## Context
- 工作树：`/Users/czj/Repos/nano-multiagent/.worktrees/M105`
- 分支：`milestone/M105`
- 编码前已阅读：`/Users/czj/Repos/nano-multiagent/SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/CodingCLI-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/ROADMAP.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`。

## Baseline Verification
- `ls src` 结果仅有：`IM/`、`agent/`、`coding_cli/`、`personal_assistant/`。
- `Glob("src/nano_multiagent/**")` 无结果，说明 worktree 内已经不存在 `src/nano_multiagent/` 物理目录。
- `python3` + `importlib.util.find_spec("nano_multiagent")` 在 `PYTHONPATH=src` 下返回 `None`。
- 关键负向与架构验收测试在变更前已通过：
  - `tests/unit/test_core_agent_location.py` -> `2 passed`
  - `tests/contract/test_multi_product_architecture_acceptance.py` -> `3 passed`

## Decision
- M105 主目标实际上已被当前代码基线满足；未发现需要继续删除的 legacy root 残留。
- 因此本 milestone 执行收口为：补齐 M105 任务/进度文档、保留验证证据、更新 dev board 状态，并按要求做本地合并与 worktree 清理。

## Notes
- 依据 LOGBOOK 的“零残留批量替换防误伤规则”，已显式复查负向断言与 forbidden snippets，而不是仅凭目录观感判断完成。
- `docs/archive/` 与历史 `TASKS/PROGRESS` 中仍可见 `nano_multiagent` 字样，但它们不在 M105 exit criteria 所定义的目标态收口范围内；当前 contract test 也只约束权威文档与运行态结构，不约束归档历史文本。
