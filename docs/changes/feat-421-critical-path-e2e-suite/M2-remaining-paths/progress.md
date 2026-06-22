# feat-421-M2 — Progress

> 在 M1 底座（conftest 起栈 fixture + _im_client.py 黑盒客户端 + 奠基 2 条）之上补齐
> 其余 9 条关键路径 e2e + catalog 四列填全 + AGENTS.md 挂链。

<!-- 每个 roadpoint 完成后追加。 -->

## R1 — 工具循环 3 条（bash 前台超时 / bash 后台通知 / subagent）

- Context: 这三条都压在「工具调用主循环」这条最高频接缝上，且各自验一个真进程才暴露的子接缝：前台超时是否卡死 session、后台作业完成通知能否作为第二条消息回流、子 agent 跨事件循环是否崩（#117 直接守护场景）。
- Decision:
  - bash 前台超时：要求 agent 给 bash 调用设 `timeout=3` 跑 `sleep 30` → 走工具 OWN timeout 收口（exitCode 124），而非 120s 前台预算自动后台化；超时后要 agent 仍回哨兵 → 验「会超时的前台工具没把 session 阻死」。断言只看 `message.completed` 含哨兵（session 卡死则此事件永不到、测试超时即红）。
  - bash 后台通知：要求 `run_in_background=true` 跑 `sleep 3 && echo <哨兵>`，哨兵由后台命令自己产出 → 只有「丢后台→跑完→通知回流→agent 再发一条」整链打通历史里才出现含哨兵的第二条消息。断言走 REST 历史轮询 `wait_for_agent_reply_with`（后台通知最终态在历史最稳）。
  - subagent：要求用 `agent` 工具派前台子 agent、子 agent 回出哨兵、父 agent 带回 → 强制走子 agent 链路而非父直接答（子 agent 真崩则父拿不到哨兵）。
- Rationale: 哨兵 token 是真 LLM 不确定输出里唯一稳的锚（design 决策 4）。三条都把哨兵的「产出位置」放在被测接缝的另一端（后台命令输出 / 子 agent 返回），确保断言真覆盖那条链路，而非被父 agent 直接糊弄过去。
- Evidence:
  - **真端到端证据（live-critical）**：`scripts/e2e-critical.sh` 等价命令真跑，真 IM + 真 Gateway 子进程 + 真 LLM `:4000`：
    - `test_foreground_bash_timeout_still_replies` PASSED — bash 设 timeout=3 跑 sleep 30 超时后，agent 仍在 IM 上 `message.completed` 回出哨兵 `TMO*`。
    - `test_background_bash_completion_sends_followup` PASSED — `run_in_background` 跑完后第二条 agent 消息含后台命令产出的哨兵 `BGN*`。
    - `test_foreground_subagent_carries_back_output` PASSED — 父 agent 回复带回子 agent 产出的哨兵 `SUB*`（#117 守护，跨事件循环未崩）。
  - Tests: 3 passed in 48.57s（`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 pytest <三文件>`）。
  - Entry: 经 `IMClient` 走 IM 公开 HTTP/WS，断言只看用户在 IM 上可观察信号。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 这三条即永久回归用例；env 关时干净 skip（M1 已验门控）。
  - Visual/Interaction: N/A
- Rollback: 纯新增测试文件，`git revert` 撤回。
- Commits: C1=test(plan 后第一 commit), C2=旅程脚本即测试本身（与 C1 同一文件，真跑验证），C3=docs（本段）。
- Next: R2 控制流 2 条（/stop / 经 IM 建 agent）。
