# M132 Gateway stop 命令产品验收

## Scope
- Milestone: M132 — Gateway stop 命令产品验收
- Review target: `/Users/czj/Repos/nano-multiagent/.worktrees/M132`
- Review date: 2026-03-14
- Review mode: product-manager-style acceptance review
- Focus: 从 README / runbook / CLI help / 真实命令行为判断，普通用户是否能发现并使用 Gateway stop 命令完成后台关闭，而不需要手工找 pid 或依赖开发者知识。

## Materials Read
- `/Users/czj/Repos/nano-multiagent/.worktrees/M132/README.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M132/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M132/src/personal_assistant/main.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M132/TASKS/M131-gateway-stop-command.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M132/PROGRESS/M131-gateway-stop-command.md`

## User Journeys Exercised
1. Discoverability path:
   - 阅读 `README.md` 与 `docs/operator-runbook.md` 的默认启动链路。
   - 确认两处都把 stop 明确写在默认主链路里，而不是藏在调试附录或要求用户自己 kill pid。
   - 运行 `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M132/src python3 -m personal_assistant.main --help` 与 `... stop --help`，确认 CLI help 能发现 stop 子命令及其 `--config` 用法。
2. Real happy path:
   - 在临时目录 `/private/tmp/nano-multiagent-m132` 写入独立 `node-config.yaml`，避免污染现有环境。
   - 启动真实 IM：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M132/src python3 -m uvicorn IM.app:app --host 127.0.0.1 --port 8111`
   - 启动真实 Gateway：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M132/src python3 -m personal_assistant.main --config /private/tmp/nano-multiagent-m132/node-config.yaml`
   - 观察到 `STARTED pid=65395 health_url=http://127.0.0.1:8100/v1/health log=/private/tmp/nano-multiagent-m132/gateway.log`。
   - 验证 `http://127.0.0.1:8100/v1/health` 可访问，且运行态文件 `/private/tmp/nano-multiagent-m132/.gateway-state.json` 已落盘。
   - 运行 stop：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M132/src python3 -m personal_assistant.main stop --config /private/tmp/nano-multiagent-m132/node-config.yaml`
   - 观察到 `STOPPED pid=65395 state=/private/tmp/nano-multiagent-m132/.gateway-state.json`，随后端口 8100 不再监听，状态文件已删除。
3. Boundary path A — not running:
   - 在成功 stop 后再次执行同一条 stop 命令。
   - 观察到 `NOT RUNNING config=node-config.yaml state=/private/tmp/nano-multiagent-m132/.gateway-state.json`。
   - 结论：用户不需要查 pid，也能得到可执行、可理解的反馈。
4. Boundary path B — stale state:
   - 人工写入伪造的 `.gateway-state.json`，其中 pid 为不存在的 `999999`。
   - 再次执行 stop。
   - 观察到 `STALE pid=999999 state=/private/tmp/nano-multiagent-m132/.gateway-state.json`，且状态文件会被自动清理。
   - 结论：陈旧运行态不会把用户逼回到手工删文件或手工 kill 的开发者路径。

## Passes
1. **可发现性达标。**
   - `README.md` 在默认“启动 Gateway”段落后，直接给出“停止当前配置对应的后台 Gateway”命令，且明确解释 `STOPPED / NOT RUNNING / STALE` 三类反馈语义。
   - `docs/operator-runbook.md` 也把 stop 放在主链路步骤中，不要求用户自己推断实现细节。
   - CLI 顶层 help 直接展示 `{stop}` 子命令；`stop --help` 也足够清楚地说明需要 `--config`。

2. **真实主链路成立。**
   - 默认启动命令会后台返回 `STARTED ...`，并为 stop 留下对应配置目录下的 `.gateway-state.json`。
   - 用同一份 `--config` 执行 stop 后，真实后台 Gateway 被关闭，健康检查端口不再可达，状态文件同步清除。
   - 整个关闭过程不要求用户查询 pid、手动 kill、手动删状态文件，符合里程碑目标。

3. **异常/边界反馈符合产品预期。**
   - 无运行实例时返回 `NOT RUNNING ...`，语义直白。
   - 状态陈旧时返回 `STALE ...`，并自动清理陈旧文件，避免用户陷入“明明没跑但 stop 不了”的困惑。
   - 三类反馈都直接围绕用户动作展开，而不是暴露底层异常栈或让用户猜下一步。

4. **文档与真实行为一致。**
   - README、runbook、CLI 行为三者一致指向同一产品路径：默认 start 是后台启动，默认 stop 是显式子命令，`--foreground` 只是调试路径。
   - 这避免了“文档写的是产品路径，实际还得靠开发者知识收尾”的常见落差。

## Issues
- None.

## Retest Focus
1. 后续若该 CLI 再演进，重点回归以下三点：
   - 顶层 `--help` 是否仍能直接发现 stop；
   - `STARTED` 后是否仍稳定生成与配置目录绑定的状态文件；
   - `NOT RUNNING / STALE / STOPPED` 三类反馈是否继续保持清晰且无需 pid 知识。
2. 若未来支持多配置并行运行，需补一轮产品复验，确认 stop 不会误停其他配置实例，且文案仍让普通用户理解“停止的是当前配置对应的 Gateway”。

## Final Verdict
- Final verdict: Pass
- Blocking issues: 0
- Major issues: 0
- Minor issues: 0

结论：M132 在当前范围内可通过产品验收。

原因：普通用户已经能从 README / runbook / CLI help 发现并执行 stop 命令，且真实启动后的关闭主链路、未运行路径、陈旧状态路径都能给出直接且可执行的反馈，不需要查 pid，也不需要依赖开发者知识。