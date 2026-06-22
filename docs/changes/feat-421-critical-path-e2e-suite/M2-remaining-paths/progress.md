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

## R3 — 群聊 + 权限 2 条（群聊双向定向@ / 权限审批 approve+deny）

- Context: 这两条都验单聊不存在的接缝。群聊：多成员广播 + @ 定向唤醒 + 未点名不抢话 + agent→agent 协作闭环；权限：人在回路审批的 approve（工具执行）/ deny（工具不执行）双向。
- Decision:
  - 群聊双向定向@（自建两个 MENTION-policy agent A/B，owner 归属正确、system_prompt 明确「被 @ 才答 + 用 XML 标签 @ 别人」）：
    - 场景1（人@A→A@B）：用户只 @A 让 A 去 @B 回哨兵；断言 A 的消息含 `<mention type="agent" target_id="B"/>`（**只认 XML 标签**，正则匹配标签本身，不锁 A 措辞），再断言 B 发出含哨兵的消息（agent→agent 唤醒）。
    - 场景2（未点名不抢话）：只 @A 且要求 A 不 @ 任何人；正向断言 A 应答（排除整群没动的假阴性），否定断言 25s 窗口内 B 始终不发言。
    - **发送者区分走 REST 历史 `sender.id`**（== agent_id）：`message.completed` WS 帧 payload 不带 sender（确认 `event_types.build_message_completed_payload` 只有 conversation_id/message_id/content/token_usage/elapsed_ms），REST item 的 `sender` ActorPayload 才是黑盒区分 A/B 的稳锚。
  - 权限审批 approve/deny：用 **`write` 工具写 dangerous basename `.gitconfig`** 触发审批——`write.check_permissions` 对 DANGEROUS_FILES basename **硬性返回 behavior="ask"（bypass-immune）**，审批必然触发，不依赖 LLM classifier 概率判定。**工具是否执行的确定性锚 = 文件系统副作用**：approve → 含哨兵的 `.gitconfig` 真出现在 workspace 树；deny → 该哨兵文件全树不出现。比断 LLM 回复措辞稳得多。
- Rationale: 群聊 @ 的语义锚必须是 XML 标签（relay_service 正则只认它）+ REST sender 区分（WS 不带 sender）。权限的语义锚必须是工具真执行与否，文件系统副作用是不受 LLM 措辞影响的铁证。
- **[排障] 权限 approve 首轮假失败 — workspace 子目录臆测**：
  - 现象：approve 测试报「文件未出现在 `default-agent/.gitconfig`」，但 permission.resolved + message.completed 都到了。
  - 排障（systematic-debugging）：搜 pytest tmp 发现文件**真被写出**了，落在 `ArchA/.gitconfig`、内容正是 approve 哨兵 `PERMOK*`——即工具其实执行成功了，只是 `first_agent_id()`（IM 列表第一个=default-agent）≠ 实际处理消息的 agent（ArchA），workspace 子目录名臆测错了（该栈 workspace 树里实际只有 ArchA）。
  - 修复：改 `_find_written_sentinel` **递归搜整个 `.gateway-workspace/**/.gitconfig`**，靠随机唯一哨兵精确归因，不锁定 agent 子目录。deny 同步改用全树搜「该哨兵从未出现」。这是测试断言归因方式的修正，非产品问题。
- Evidence:
  - **真端到端证据（live-critical）**：
    - `test_human_mentions_a_then_a_mentions_b` PASSED — A 应答含 `<mention type="agent" target_id="grpB*"/>`，B 因被点名回出哨兵 `GRP*`。
    - `test_unmentioned_agent_stays_silent` PASSED — 只 @A 时 A 回 `SOLO*`、B 在 25s 窗口内零发言。
    - `test_permission_approve_lets_tool_run` PASSED — approve 后 `.gitconfig` 含 `PERMOK*` 真出现在 workspace。
    - `test_permission_deny_blocks_tool` PASSED — deny 后含 `PERMNO*` 的文件全树不出现。
  - Tests: R3 四条 `4 passed in 99.42s`（修 workspace 臆测后）。权限审批确认真触发 `permission.request` → `permission.resolved`。
  - Entry: 经 `IMClient` 走 IM 公开 HTTP/WS + 文件系统副作用（工具执行的确定性外部锚）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 四条永久回归；env 关时干净 skip。
  - Visual/Interaction: N/A
- Rollback: 纯新增两 test 文件；`git revert` 撤回。
- Commits: C1=test(R3 四条旅程), C2=test(修权限 workspace 臆测为全树搜), C3=docs（本段）。
- Next: R4 时间驱动 slow 2 条（cron / heartbeat）+ catalog 四列填全 + AGENTS.md 挂链。

## R4 — 时间驱动 slow 2 条（cron / heartbeat）+ catalog + AGENTS.md

- Context: cron / heartbeat 无对外触发路由（design 决策 5），只能「配秒级周期 + 等其自跑 + 观察 IM 是否收到推送/冒泡」，归 @pytest.mark.slow。两条都需要先经 IM API 给 agent 开对应 feature（cron 工具 / heartbeat 调度仅在 feature 开启时生效）。
- **[底座扩展] `_im_client` 加 get_agent_config / update_agent_config**：cron 需 `features['cron_scheduling']`、heartbeat 需 `features['heartbeat']` + `heartbeat_json` 节律，二者都靠 PATCH `/im/v1/agents/{id}/config`（全量 + 乐观锁）。新增两 helper：GET 现配置拿 profile_version → 合并改动 → PATCH。**关键坑**：PATCH 的 model_validator 见到 body 里 `heartbeat_json` 键存在（即使=None）时会把 heartbeat dict 形式 pop 掉不转换 → helper 改为「heartbeat_json 只在显式传入时才放进 body」，避免 None 占位污染。
- cron（DONE，绿）：
  - Decision: 自建一个 agent → PATCH 开 `features['cron_scheduling']` → 建直聊 → 让 agent 用 cron 工具注册 every-5s 任务（payload 输出哨兵）→ 等 cron 到点自跑推送。**排除注册确认回声**：记下注册阶段已出现的含哨兵消息 id，只认一条**新的、id 不在已见集合**的含哨兵消息（= cron 真触发那条）。
  - Evidence（live-critical）: `test_cron_job_auto_pushes_message` PASSED（42.74s）— cron 真触发自跑、推一条新的含哨兵 `CRON*` 消息到直聊。
- heartbeat（**BLOCKED — 真实产品/模型集成行为，非测试 bug**）：
  - 深度排障（systematic-debugging）结论：heartbeat-state.json 证明 **scheduler 真拾取该 agent 并 triggered 了 run**（`last_due_at` 有值）→ enable✓ cadence(5s)✓ PATCH 同步到 gateway✓ tick✓ 判 due✓ 提交 run✓。**run 真跑了**。
  - 真正卡点 = **投递静默抑制**：`_consume_heartbeat_run` 的 observer 做 NO_REPLY/empty/HEARTBEAT_OK suppression（main.py:1254/1304，design decision 6）。verbatim openclaw heartbeat prompt 末句 "If nothing needs attention, reply HEARTBEAT_OK" → model 回 HEARTBEAT_OK → observer 抑制投递 → IM 无消息。
  - 实测三组都不冒泡（run triggered 但消息被抑制）：① 默认 kimiCoding:K2.6（命中已知「K2.6 HEARTBEAT_OK 死反射」）② volcanoArk:doubao ③ 强措辞 HEARTBEAT.md（明写"needs attention/必须发言/不可回 HEARTBEAT_OK"）。
  - 判断：spec #7「**有可行动内容时**冒泡/无内容静默」——现有可用 model 对 openclaw 心跳 prompt 一律判静默，这条路径在真栈下无法稳定经黑盒驱动出可观察消息。属真实模型×心跳 prompt 集成行为，非本 unit 测试缺陷。已 SendMessage 上报 orchestrator 请示收口方案（skip 占位 + catalog backlog + gh issue），等裁决。
- Evidence:
  - Tests: cron `1 passed in 42.74s`（真栈）。heartbeat 旅程已写好（可复现资产），待 orchestrator 定 skip 方案。
  - Frontend State Matrix / Browser QA / Visual: N/A
- Rollback: 纯新增测试 + helper；`git revert` 撤回。
- Commits: C1/C2=test(cron+heartbeat 旅程 + helper), C3=docs（本段）。
- Next: 待 orchestrator 裁决 heartbeat → 定稿 heartbeat + catalog 四列 + AGENTS.md 挂链 → 全套验证 → 集成。
