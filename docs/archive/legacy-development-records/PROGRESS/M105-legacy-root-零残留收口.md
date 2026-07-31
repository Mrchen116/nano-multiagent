# M105 - legacy root 零残留收口

## Context
- 工作树：`/Users/czj/Repos/nano-multiagent/.worktrees/M105`
- 分支：`milestone/M105`
- 编码前已阅读：`/Users/czj/Repos/nano-multiagent/SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/CodingCLI-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/ROADMAP.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`。

## Updated Reality
- 用户复核后确认：M105 初次收口时，主仓 `main` 仍一度存在本地文件系统残留 `/Users/czj/Repos/nano-multiagent/src/nano_multiagent`。
- 该残留随后已由 control tower 直接在主仓 `main` 上移除；当前 `main` 再次满足 legacy-root negative checks。
- 因此 M105 的性质应更新为“真实 closeout milestone”：负责记录这次残留被发现、由 control tower 修复、并由里程碑文档与门禁验证完成最终收口，而不是把它描述成纯 no-op verification。

## Baseline Verification
- 当前主仓验证命令：`PYTHONPATH=src pytest -q tests/unit/test_core_agent_location.py tests/contract/test_multi_product_architecture_acceptance.py`
- 当前主仓验证结果：`5 passed`
- 这说明 closeout 后的 `main` 已重新满足：
  - `src/` 顶层只保留权威四包结构；
  - `src/nano_multiagent/` 本地残留已被移除；
  - legacy-root negative checks 恢复为绿色。

## Decision
- 本次 follow-up 只保留 M105 docs 收口，不复用之前不安全的 `56538e5`，因为它会连带删除 milestone 分支上的 `data/dev-tasks.json`。
- M105 的正确交付方式改为：
  1. 在 `milestone/M105` 上补一笔 docs-only follow-up commit，准确记录“main 曾有残留、后由 control tower 移除”的事实；
  2. 将该 docs-only 结果合并回本地 `main`；
  3. 仅在 `main` 更新 `data/dev-tasks.json`，把 M105 标记为真正完成。

## Notes
- 依据 LOGBOOK 的“零残留批量替换防误伤规则”，已显式复查负向断言与 forbidden snippets，而不是仅凭目录观感判断完成。
- `docs/archive/` 与历史 `TASKS/PROGRESS` 中仍可见 `nano_multiagent` 字样，但它们不在 M105 exit criteria 所定义的目标态收口范围内；当前 contract test 也只约束权威文档与运行态结构，不约束归档历史文本。
