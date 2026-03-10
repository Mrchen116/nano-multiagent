# PROGRESS (Milestone: M85)

- Milestone: M85
- Title: 多产品架构重构十二期：canonical wiring 实化与内部 legacy import 收口
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85`
- Branch: `milestone/M85`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: `593 passed, 4 skipped`
- Notes:
  - 遵循 `LOGBOOK.md`：对 active runtime/canonical layers 通过 contract/import-guard 防回流；live 验收前需补完整命令与结果。
  - 遵循 `COMMENTING_GUIDE.md`：public API/docstring 写契约，注释只写意图/边界/取舍。

## Roadpoints

### R85.1 resolver/profile 驱动的 canonical wiring 打通
- Context:
  - 审计指出 loaders 已支持 `ConfigResolver`，但 live bootstrap/create_app/runtime/task 仍未把 resolver 真正贯穿到 skill/tool/hook 搜索与 profile 装配。
  - 当前 profile 模式下 runtime/task 仍可落回 `.codex/.nano/CODEX_HOME` 语义，违背 milestone 目标。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - Tests: 待补。
  - Entry: 待补。
- Rollback:
  - 最近稳定点：基线 `8330bd8`。
- Commits: C1=, C2=, C3=
- Next:
  - 先写 red tests 锁定 profile workspace skill root 与 task skill 校验必须走 resolver。

### R85.2 canonical import 收口与 product prompt ownership 实化
- Context:
  - 当前 active layer 仍存在 `session.service` / `skills.workspace` / `server.sse` / `llm.protocols.*` 等 legacy import；`products/local_coding/prompts.py` 仍反向依赖 `agent/prompting.py`。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - Tests: 待补。
  - Entry: 待补。
- Rollback:
  - 最近稳定点：R85.1 的 C3。
- Commits: C1=, C2=, C3=
- Next:
  - 先写 import-guard/ownership red tests，再收口 canonical imports。

### R85.3 full sweep、live 验证、main 集成与清理
- Context:
  - 根据技能要求，DONE 前必须跑完整 sweep，并对本 milestone 相关默认 skip live tests 给出精确命令与结果，然后 merge main / update board / remove worktree。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - Tests: 待补。
  - Entry: 待补。
- Rollback:
  - 最近稳定点：R85.2 的 C3。
- Commits: C1=, C2=, C3=
- Next:
  - 待 R85.1 / R85.2 完成后执行 full sweep、live、merge、board、cleanup。
