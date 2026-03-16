# M217 Progress — 查明并修复 M170 fresh rerun 证据漂移

## 启动记录
- 用户指令：`M217现在还没合并吗？你后面不拍worker了，亲自干，亲自闭环`。
- 结论：`M217` 当时确实未进入 main，因此直接在 canonical repo 上手工整合，而不是继续依赖旧 worker/worktree。
- 关键运行态：`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime`

## Roadpoint 记录

### R1. 将 M217 rerun 硬化整合到 current main
- Context:
  - canonical main 的 `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` 仍缺少 M217 已验证过的关键加固。
  - `.worktrees/M217` 中存在可参考实现，但其测试文件带有 worktree 绝对路径，不能直接照搬。
- Decision:
  - 手工把 rerun 硬化合入 canonical main：artifact staged publish、conversation-scoped lookup、gateway quiet-window wait、mention picker fallback、turn timeout 扩大。
  - 保留 canonical-relative test loader，避免把 `.worktrees/M217` 路径污染进主仓。
- Evidence:
  - 代码：`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
  - 测试：`/Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
  - 验证：`pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py` → `13 passed`
- Rollback:
  - 若需回退，仅撤销上述两个文件上的 M217 rerun hardening 改动。

### R2. 修正 fresh runtime 下的 websocket/时序问题
- Context:
  - 首次 fresh rerun 在 alpha turn 超时；进一步检查 runtime DB、im.log 与 kernel run 发现 turn 最终会完成，但完成时间晚于旧预算。
  - 同时，Gateway→IM websocket 在短断连窗口里存在 sent-but-unacked frame 可能丢失的问题。
- Decision:
  - 在 `src/personal_assistant/ws/im_connection.py` 中引入“发出后等待 ack 才真正出队”的策略，断连后重连重发 unacked frame。
  - 为 rerun 提高 timeout budget，并增加 gateway quiet-window wait。
  - 修复 picker 路径的根因：UI composer 可见值是 `@Agent M170 Beta `，而真实入库消息是 `@agent:agent-m170-beta ...`；rerun 应按稳定 token 查库，而不是按显示名查库。
- Evidence:
  - 代码：`/Users/czj/Repos/nano-multiagent/src/personal_assistant/ws/im_connection.py`
  - 测试：
    - `/Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
    - `/Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_main.py`
    - `/Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
  - 验证：
    - `pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
    - `pytest -q /Users/czj/Repos/nano-multiagent/tests/unit/test_m170_rerun_acceptance.py`
  - Live picker capture：
    - listbox: `role=listbox`, `aria-label="Mention candidates"`
    - option 1 visible text: `Agent M170 Alpha` / `Agent M170 Alpha mention`
    - option 2 visible text: `Agent M170 Beta` / `Agent M170 Beta mention`
    - composer visible value after pick: `@Agent M170 Beta `
    - persisted message text: `@agent:agent-m170-beta please answer via picker route.`
- Rollback:
  - 若需回退，优先撤销 ack buffering 与 picker lookup 文本切换；NO_REPLY 验收报告需要同步重新生成。

### R3. fresh real acceptance 复跑并闭环 M170
- Context:
  - 用户要求不是“测试看起来对”，而是真正 fresh runtime + 真实前端验收通过。
- Decision:
  - 在 canonical runtime 直接复跑 `m170_rerun_acceptance.py`，并把成功结果写入正式 `ACCEPTANCE/M170-acceptance.md`。
- Evidence:
  - 真实通过 run：`run-67b6122ad5834b32b554c32646974c63`
  - 结构化结果：`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-result.json`
  - 截图：
    - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-home.png`
    - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-group-panel.png`
    - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-group-thread.png`
    - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-picker.png`
    - `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-no-reply.png`
  - 报告：`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M170-acceptance.md`
  - 验收要点：
    - alpha turn passed → `ALPHA_ACK_M170`
    - beta turn passed → `BETA_ACK_M170`
    - picker turn passed → `BETA_ACK_M170`
    - `no_reply_turn.status = passed`
    - `no_reply_turn.violations = []`
- Rollback:
  - 若需重做，重新 rebuild/start runtime 后重跑 rerun，并覆盖 acceptance report。

## 结论
- `M217` 已在 canonical main 上手工整合完成。
- `M170` 已在 fresh current-main 真实前端验收中闭环通过。
- 本轮最关键的可复用经验：带 mention picker 的 UI 可能显示 display label，但持久化 payload 仍是稳定 token；自动验收脚本必须按稳定 token 查库，不能按可见显示值查库。
