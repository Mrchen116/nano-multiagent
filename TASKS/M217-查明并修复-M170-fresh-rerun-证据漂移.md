# M217 Task — 查明并修复 M170 fresh rerun 证据漂移

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/.codex/skills/project-lead-orchestrator/SKILL.md`、既有 `M170` / `M217` milestone 描述与 fresh runtime 证据。
- 当前处境：用户要求不再派 worker，由主 agent 亲自把未合并的 `M217` 收进 current main，并直接闭环 `M170` 真实验收。
- 当前范围：
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
  - `/Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
  - `/Users/czj/Repos/nano-multiagent/src/personal_assistant/ws/im_connection.py`
  - `/Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
  - `/Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_main.py`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M170-acceptance.md`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-*.{png,json}`
  - `/Users/czj/Repos/nano-multiagent/TASKS/**`
  - `/Users/czj/Repos/nano-multiagent/PROGRESS/**`
  - `/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- 禁止范围：
  - 不提交 `data/dev-tasks.json`
  - 不提交 runtime DB / `.staging/` / workspace / state 文件
  - 不改与 M170/M217 无关的现存脏文件

## Roadpoints

### R1. 把未合并的 M217 rerun 硬化合入 current main
- Status: DONE
- Acceptance:
  - current main 的 rerun 脚本具备 conversation-scoped lookup、artifact staged publish、mention picker fallback、gateway quiet-window wait。
  - 对应单测补齐，且保持 canonical path，不把旧 worktree 路径写入 main。
- Tests Plan:
  - `pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
- DoD:
  - rerun 逻辑与单测在 current main 上落地；不引用 `.worktrees/M217/...` 硬编码路径。

### R2. 修掉 fresh runtime 下 rerun 的真实阻塞项
- Status: DONE
- Acceptance:
  - websocket 短断连后，Gateway→IM 的 sent-but-unacked frame 不会永久丢失。
  - rerun 超时预算与 picker lookup 足以覆盖 fresh runtime 的真实时序。
- Tests Plan:
  - `pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
  - `pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_main.py`
  - `pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
- DoD:
  - 新增 unacked resend 回归；rerun 用稳定 token 查询 picker 消息，不再被显示名误导。

### R3. 重新跑 fresh M170 并形成正式验收证据
- Status: DONE
- Acceptance:
  - fresh runtime 下群聊创建、alpha/beta 两个 direct mention、picker mention 与 NO_REPLY 静默全部通过。
  - `ACCEPTANCE/M170-acceptance.md` 更新为 pass，并记录本轮 run id 与关键截图/json。
- Tests Plan:
  - `python3 /Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
- DoD:
  - `run-67b6122ad5834b32b554c32646974c63` 通过，`no_reply_turn.status = passed`，并把 evidence 落盘。
