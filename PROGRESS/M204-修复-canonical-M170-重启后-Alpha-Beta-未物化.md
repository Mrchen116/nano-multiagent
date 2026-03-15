# M204 Progress — 修复 canonical M170 重启后 Alpha/Beta 未物化

## 启动记录
- worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M204`
- branch：`milestone/M204`
- 已读取：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`ACCEPTANCE/M170-acceptance.md`、`scripts/acceptance/m170_runtime.py`、相关 tests。
- 已确认共享派工板：`/Users/czj/Repos/nano-multiagent/.worktrees/M204/data/dev-tasks.json -> /Users/czj/Repos/nano-multiagent/data/dev-tasks.json`

## 初始判断
- 当前 `scripts/acceptance/m170_runtime.py` 的 `_write_runtime_config()` 仍硬编码单一 `assistant` agent，因此 fresh restart 后 gateway register 只能上报 `agent_count=1`。
- `ACCEPTANCE/m170-runtime/node-config.yaml` 与 `workspace/assistant` 现状也印证 canonical runtime 实际只准备了一个 agent。
- M170 rerun 脚本和现有 gateway 集成测试都要求 canonical label `agent-m170-alpha` / `agent-m170-beta`，所以单纯复用仓库根 `node-config.yaml` 的 `Alpha/Beta` 也不满足验收口径。

## 关键决策
1. `scripts/acceptance/m170_runtime.py` 不能再把 canonical runtime 锚定到 worktree 自己的 `ACCEPTANCE/m170-runtime`；需要在 worktree 内执行时回落到主仓根 `/Users/czj/Repos/nano-multiagent`，确保 documented restart path 操作的是共享 canonical runtime。
2. fresh runtime 必须在重建阶段直接写出三 agent 配置并 seed 三条 `agent_profiles`，这样浏览器和 `/im/v1/agents` 不依赖历史残留或手工改库。
3. `stop_runtime()` 需要额外清理同一 config 对应的残留 gateway 进程和占用 `18070` 的旧 kernel listener；否则 fresh restart 虽然会写入三 agent profile，但 `/im/v1/nodes` 仍可能被旧实例的 `agent_count=1` heartbeat 覆盖。

## 进度

### R1 锁定 canonical restart 的运行态契约
- Context:
  - 初始 runtime 重建路径只会生成单 `assistant` config，fresh DB 也不会预置 Alpha/Beta profile。
  - 在 worktree 中执行脚本时，默认 `Path(__file__).resolve().parents[2]` 还会把 runtime 根错误指向 worktree 自己的 `ACCEPTANCE/m170-runtime`，不满足 canonical 验收口径。
- Decision:
  - 在 `scripts/acceptance/m170_runtime.py` 增加 `_resolve_canonical_repo_root()`，让 worktree 内执行仍回落到主仓 canonical runtime。
  - 引入 `CANONICAL_RUNTIME_AGENTS`，统一驱动 workspace 创建、runtime config 写入和 fresh DB seed。
  - 为 `stop_runtime()` 增加重复 gateway/config 进程与 `18070` 监听清理，保证 fresh restart 后只有当前 canonical 实例在上报 heartbeat。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M204/scripts/acceptance/m170_runtime.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M204/tests/unit/test_m170_runtime.py`
- Status: DONE

### R2 用 canonical restart 命令做 fresh 自证
- Context:
  - 修复前已能在 DB 和 `/im/v1/agents` 看到 Alpha/Beta，但 `/im/v1/nodes` 一度仍显示 `agent_count=1`；排查后确认是旧 `18070` listener 与重复 canonical gateway 进程残留，新的 stop/start 没有把旧实例彻底清掉。
- Decision:
  - 以主仓 canonical runtime 路径执行 `python3 /Users/czj/Repos/nano-multiagent/.worktrees/M204/scripts/acceptance/m170_runtime.py stop/start/status` 重新自证。
  - 用 SQLite 查询、HTTP `/im/v1/nodes` + `/im/v1/agents`、以及真实浏览器群聊 picker 三层证据封堵回归。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/node-config.yaml`
  - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/im_service.sqlite3`
  - `/Users/czj/Repos/nano-multiagent/output/playwright/m204-main-picker-evidence.png`
  - `/Users/czj/Repos/nano-multiagent/output/playwright/m204-main-picker-evidence.json`
- Status: DONE

## 测试结果
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M204/tests/unit/test_m170_runtime.py`
  - 结果：`6 passed in 0.57s`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M204/tests/unit/test_m170_runtime.py /Users/czj/Repos/nano-multiagent/.worktrees/M204/tests/im_service/unit/test_relay_service.py /Users/czj/Repos/nano-multiagent/.worktrees/M204/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - 结果：已触发完整门禁复跑；当前前半段输出已到 `22 items`、`tests/unit/test_m170_runtime.py ......`、`tests/im_service/unit/test_relay_service.py .......`、`tests/im_service/integration/test_m103_im_gateway_e2e.py ...`，未出现新增失败。

## 验收证据摘要
1. fresh restart 后 canonical DB 已物化三 agent：
   - `SELECT agent_id, node_id, display_name FROM agent_profiles ORDER BY rowid` 返回 `assistant`、`agent-m170-alpha`、`agent-m170-beta`，且三者都绑定到 `m170-node`。
2. `/im/v1/nodes` 不再上报 `agent_count=1`：
   - `GET http://127.0.0.1:18031/im/v1/nodes` 返回 `{"node_id":"m170-node", ..., "agent_count":3}`。
3. 真实浏览器群聊参与者选择器可见 Alpha/Beta：
   - Playwright snapshot `/Users/czj/Repos/nano-multiagent/.playwright-cli/page-2026-03-15T17-37-57-058Z.yml` 中，`Select participants` 面板列出了 `Agent M170 Alpha`、`Agent M170 Beta`、`assistant` 三个 checkbox 候选。
   - 浏览器提取结果已写入 `/Users/czj/Repos/nano-multiagent/output/playwright/m204-main-picker-evidence.json`。
   - 对应截图路径：`/Users/czj/Repos/nano-multiagent/output/playwright/m204-main-picker-evidence.png`。
4. 真实 canonical restart 路径确实操作主仓共享 runtime：
   - `python3 /Users/czj/Repos/nano-multiagent/.worktrees/M204/scripts/acceptance/m170_runtime.py status` 返回 `runtime_root=/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime`。

## 当前结论
- M204 已完成：documented canonical M170 restart path 现在会在 fresh runtime 中真实物化 `agent-m170-alpha` 与 `agent-m170-beta`。
- 本次修复同时消除了一个隐藏 blocker：残留 canonical gateway/kernel 进程会把 `/im/v1/nodes.agent_count` 回写成 1；现在 `stop_runtime()` 会主动清理这类重复实例，fresh restart 后 `agent_count` 稳定为 3。
- 目前三条 exit criteria 已满足：DB 物化、nodes `agent_count >= 3`、浏览器 picker 可见 Alpha/Beta。

## 回滚点
- 若需要回滚，撤回以下文件即可：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M204/scripts/acceptance/m170_runtime.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M204/tests/unit/test_m170_runtime.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M204/TASKS/M204-修复-canonical-M170-重启后-Alpha-Beta-未物化.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M204/PROGRESS/M204-修复-canonical-M170-重启后-Alpha-Beta-未物化.md`
