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

## R2 — 控制流 2 条（/stop 中止 run / 经 IM 建 agent）

- Context: /stop 验「运行中能否被打断」这条只有真起 run、真发中止才暴露的接缝；经 IM 建 agent 验「IM 配置中心 → 节点落地 → 上线可聊」整条配置链路。
- Decision:
  - /stop：让 agent 跑 `sleep 45` 前台 bash 制造活跃 run → 等 `tool_call.upserted`（run 真进了工具循环再发 /stop，避免「无活跃 run」分支）→ 发 `/stop` → 正向断言收到 Gateway 硬编码固定 ack `已停止当前操作。`（非 LLM 措辞，可逐字断言）→ 否定断言：随后 20s 窗口内被中止任务的完成哨兵 `never_sentinel` 不出现（run 真停了它永不到）。
  - 经 IM 建 agent：取在线 node_id → `create_agent`（带随机后缀 agent_id + default_model）→ 轮询 `/agents` 直到新 agent 出现（落地上线信号）→ 建直聊发哨兵 → 等含哨兵的 `message.completed`。
- **[底座缺陷修复] `_im_client.py` 漏传 owner_id**：
  - 现象：建 agent 后新 agent 永不出现在 `/agents` 列表（40s 超时），路径 11 不可用。
  - 根因：M1 的 `create_agent` 没传 `owner_id`，也没缓存登录返回的 `owner_id` → profile.owner_id 落空串。IM 的 `repositories.list_runtime_selectable_profiles_for_owner` 按 owner 过滤：`ap.owner_id='' ` 仅当 `n.owner_id=''`（ownerless 节点）才返回；而 e2e 节点已 auto-bind 归属 nano → 新 agent 既不满足 owner 匹配也不满足 ownerless，被过滤掉。
  - 修复：`register_or_login` 缓存 `body["user"]["owner_id"]`；`create_agent` 默认带 `owner_id=self.owner_id`（IM `CreateNodeAgentRequest.owner_id` 字段本就存在，前端正常建 agent 也传它）。这是让 M1 已备方法真正可用的最小修复（§0.1 复用扩展，非新造平行物），不改任何产品代码。
  - 验证：修复后建 agent 即出现在列表、直聊收到含哨兵回复，PASSED。
- Rationale: /stop 的 ack 是判 run 是否真被打断的唯一稳锚（固定串，非 LLM）；否定哨兵补「停了之后不再产出」这层。建 agent 的 owner_id 是 IM 归属过滤的硬约束，黑盒客户端必须按真实前端契约带它。
- Evidence:
  - **真端到端证据（live-critical）**：
    - `test_stop_aborts_active_run` PASSED — sleep 45 跑起来后 /stop 收到固定 ack `已停止当前操作。`，被中止任务的 `STOP*` 哨兵在 20s 窗口内未出现。
    - `test_agent_created_via_im_lands_and_replies` PASSED — 新建 `e2eNew*` agent 落地上线、直聊回出哨兵 `NEW*`。
  - Tests: R2 首轮 `1 failed, 1 passed`（建 agent owner_id bug）→ 修 `_im_client.py` 后建 agent 单跑 `1 passed in 5.49s`；/stop 首轮即 PASSED。
  - Entry: 经 `IMClient` 走 IM 公开 HTTP/WS。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 两条永久回归；env 关时干净 skip。
  - Visual/Interaction: N/A
- Rollback: 新增两 test 文件 + `_im_client.py` 单点补 owner_id；`git revert` 撤回。
- Commits: C1=test(R2 两条旅程), C2=fix(_im_client owner_id), C3=docs（本段）。
- Next: R3 群聊 + 权限 2 条。
