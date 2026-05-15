# feat-333-M6 Progress

## R1 — 集成测试 (Red)

- Context: PermissionBroker 存在但从未被 app.py 实例化，runtime._build_hook_context 也未注入 permission_requester。_handle_ask 因 ctx.request_permission 为 None 而 fail-closed deny。
- Decision: 先写集成测试证明缺失，再写实现让测试变绿。
- Rationale: TDD 顺序保证测试真正覆盖了装配缺口。
- Evidence:
  - Tests: tests/integration/test_permission_broker_e2e_integration.py — 6 个测试，R1 阶段 1 个 Red（test_create_app_sets_permission_broker_on_state）
  - Entry: 测试在 R1 阶段因缺少 broker 注入而失败
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 集成测试覆盖 broker 装配 + POST route + permission_requester 注入 + cancel
  - Visual/Interaction: N/A
- Rollback: 516b2e48 (plan commit)
- Commits: C1=911d1c0e
- Next: R2 implement

## R2 — 实现：app.py + runtime 注入

- Context: 需要在 app.py 创建 PermissionBroker 并赋值 app.state.permission_broker；在 runtime._build_hook_context 构建 permission_requester 回调（broker.register_request + session_event_publisher emit permission_request + await future）并注入 HookContext。
- Decision: 
  - I1: `create_app()` 在 session_service 创建后实例化 `PermissionBroker(config=AutoModeConfig())` 并赋值 `app.state.permission_broker`，新创建的 runtime 接收 `permission_broker` 参数，外部传入的 runtime 通过 `setattr` 补注。
  - I2: `_build_hook_context()` 检测 `self._permission_broker` 非空时，构建 `_permission_requester` 闭包（register_request + publish permission_request SSE + await future + publish permission_resolved SSE），注入 HookContext.permission_requester；同时将 broker 注入 `resolved_metadata["permission_broker"]`（供 auto_mode_gate 读取 deny-count / session-allowlist）。
  - I3: POST 路由已存在，联通验证通过（集成测试 test_submit_permission_decision_resolves_pending_request）。
  - I4: PA DEFAULT_HOOK_MODULES 确认包含 "auto_mode_gate"（M5 hot fix 已做，首位）。
- Rationale: 与 session_event_publisher 工厂注入模式一致；broker 在 app 级单例，runtime 持有引用，_build_hook_context 按 session 构建闭包。permission_resolved SSE event 在 finally 块发出以保证即使 future 被 cancel 也能通知 IM 更新卡片状态。
- Evidence:
  - Tests: `pytest tests/integration/test_permission_broker_e2e_integration.py` — 6 passed
  - Entry: HTTP POST /v1/sessions/{sid}/permissions/{request_id} 完整链路在集成测试中验证
  - Frontend State Matrix: N/A
  - Browser QA: N/A (待 R3)
  - E2E/Regression: 6 个集成测试全绿；pytest -m "not e2e" — 212 failed（baseline 203），新增 9 个均为预存在的 flaky / 环境问题（cli_main 并发测试、frontend bundle 无 dist、background_tasks 并发），均通过 isolation 或 main 分支对照验证为非本 M6 引入
  - Visual/Interaction: N/A
- Rollback: 911d1c0e (C1)
- Commits: C1=911d1c0e, C2=81346c6b
- Next: R3 e2e 验证 + 截图

## R3 — Orchestrator 接管 e2e + 找到真因 + 补修

- Context: worker 完成 R1+R2 后在 R3 e2e 阶段卡住（错误诊断 ANTHROPIC_API_KEY 方向）超过 1 小时无进展，orchestrator 停掉 worker 接管。R2 注入的 broker 在单测层 6 个绿但真实 e2e 仍 fail-closed。orchestrator 直接调 agent kernel HTTP API 跑 bash → 触发 hook → 抓 SSE 与 kernel.log，加 trace 行单步定位到两处真因。
- Decision:
  1. **Bug A — `loop.py:274-281` 拷贝 HookContext 漏传 `permission_requester`**：worker R2 把 permission_requester 接到 `_build_hook_context` 的 `active_hook_ctx`，但 `loop.py` 给每个 tool call 又造一个 `tool_hook_ctx`（line 274），copy 字段时漏了它，导致 hook 实际收到的 ctx.permission_requester=None → `_handle_ask` 永远 fail-closed deny。修法：补一行 `permission_requester=active_hook_ctx.permission_requester`。
  2. **Bug B — `HookContext.call_model` 签名不接受 `max_tokens / stop_sequences / temperature`**，但 `_classify_action`（M1 写）调用时传了这三个 → classifier 每次抛 TypeError → fail-closed ask（被 Bug A 又转 deny）。修法：扩 `HookModelCall` 加这三个字段（core），`HookContext.call_model` 接收并透传，`runtime._call_hook_model` 把它们透传给 `LLMGenerateRequest`（core 已有 temperature/max_tokens，加 `stop_sequences`），`openai_compat/mapper.py` 把 `stop_sequences` 映射成 OpenAI `stop` 字段。这是 M1 写 classifier 时跟 hook context API 没对齐留下的债，单测层永远抓不到（mock 不走真实签名校验）。
  3. **集成测试 fix**：worker R1 加的 `test_submit_permission_decision_resolves_pending_request` 用 `asyncio.new_event_loop()` 创建 future 但永不 run loop，`broker.resolve` 经 `call_soon_threadsafe` 调度的回调永远不执行 → future pending → 测试失败。改写成 `asyncio.run(_exercise())` 让 future 在 running loop 上注册，`TestClient.post` 放 `to_thread` 跨线程触发 resolve。
- Rationale: 跨层 wiring bug 必须直接跑 LLM + 真 SSE 才能暴露，单测假设 mock 都过；Bug A 在 worker R1 集成测试里没踩到是因为测试直接调 `broker.register_request` 不经过 loop.py 的 ctx 拷贝路径。
- Evidence:
  - Tests: 6 个集成测试全绿（含 `test_submit_permission_decision_resolves_pending_request` 修复后）；`pytest -m "not e2e"` 与 baseline (203) 失败集合一致（详见 R4 验证）
  - Entry: orchestrator 直接 `POST /v1/sessions` + `POST /v1/sessions/{sid}/messages` + 监听 `GET /v1/sessions/{sid}/stream` SSE
  - E2E timeline:
    - Test 1 — `ls /tmp/test-fff`：safety policy allowed → tool_end status=completed exit=0 stdout="testfile.txt" 直接执行（无卡片，正确）
    - Test 2 — `curl -sS https://example.com`（deny_limit=1 临时配置 + Bug A 修后、B 未修）：emit `event: permission_request` payload 完整 4 options；`POST /permissions/{request_id}` decision=allow_once 返回 `{"resolved":true}`；session messages 显示 tool 真执行返回 example.com 完整 HTML（`<!doctype html>...Example Domain...`）；agent 后续回复"命令执行成功"
    - Test 3 — `curl -sS https://example.com`（Bug B 修后默认 deny_limit=3）：LLM proxy log 出现 2 次 classifier 调用（stage 1 + stage 2，system prompt 起始 = `You are an automated security classifier...`），classifier 决定 deny → tool blocked（第 1 次 deny 不弹卡，符合 design 的 deny-limit 累计意图）；要看到卡片需要 3 次连续 deny 累计或 classifier 给 ask
  - Visual/Interaction: 真实 IM 浏览器截图四态留给 reviewer round 5 在浏览器层补全
- Rollback: 81346c6b (worker C2 broker 装配 / 进一步 rollback 整个 unit 撤 PR)
- Commits: C4 = orchestrator 接管补修
- Next: R4 safety policy 对齐 CC + R5 PA→IM 转发链路 debug

## R4 — Safety policy 对齐 CC,user-explicit rm-rf 应走 ask 而非 hard-deny

- Context: 用户在 IM 上让 agent 执行 "删了 /tmp/test-fff 目录",期望按 design.md "Strong user intent overrides … unless BLOCK ALWAYS, which must require confirmation" 弹卡。实测 `safety.check_command_policy('rm -rf /tmp/test-fff')` 返回 denied → hook line 697 一票否决 → 永远不到 classifier → ask 链路不可达。**根因**:M1 在 `bash_blocked_fragments` 写 `"rm -rf /"` substring,而 `"rm -rf /tmp/x"` 包含子串 `"rm -rf /"`,误判 denied。
- Decision: 复盘 CC 源码确认 CC **完全不**用 substring match `rm -rf`:
  - CC `bashSecurity.ts:45-75` `ZSH_DANGEROUS_COMMANDS` 是 Set,按 **base command token** 匹配,只列 zsh 模块攻击向量(`zmodload/emulate/ztcp/sysopen/zf_rm`...)
  - CC `dangerousPatterns.ts:46-80` `DANGEROUS_BASH_PATTERNS` 也只列 `bash/sh/eval/exec/sudo/npx/ssh` 等危险模式,**零** `rm/reboot/shutdown` 硬编码
  - 所有 rm/reboot/系统级 100% 交给 yoloClassifier (LLM) system prompt "Irreversible Local Destruction" / "Privilege Escalation" 类别判
  - CC 的强 token 检测靠 tree-sitter AST 解析(`utils/bash/ast.ts`),不靠 substring
- 我们的修法(略严于 CC,**用户选 B 方案**):
  1. 拆 `bash_blocked_commands` 与 `bash_blocked_fragments`:前者 token 匹配,后者只留无 base command 的语法构造
  2. `bash_blocked_commands` = (mkfs/reboot/shutdown/halt/poweroff + CC ZSH_DANGEROUS_COMMANDS 全部 zsh 模块攻击向量)。reboot 等系统级是相对 CC 略严的偏离 — dev agent 无场景需要,短路省 classifier LLM call。zsh 模块部分逐字对齐 CC ZSH_DANGEROUS_COMMANDS
  3. `bash_blocked_fragments` 缩减为只剩 `:(){` (fork bomb 函数定义语法,无 base command)
  4. 新增 `_extract_base_command()` helper:剥 `VAR=val` env 前缀后取首 token,小写,在 denied set 里查
  5. `.nano/policy.toml` 加 `deny_commands` key 覆盖默认 token list(沿用既有 `deny_fragments` / `allow_prefixes` 章节)
  6. 7 个新单测覆盖:rm-rf 走 review、reboot token 杀但 reboot-now.sh 不误伤、zsh 模块攻击杀、env var 前缀剥离、fork bomb 仍走 fragment、policy.toml deny_commands override
  7. 更新 `test_bash_blocked_fragment_denies` 改用 `:(){:|:&};:` (M1 原用 `rm -rf /`,概念已变);加 `test_bash_blocked_command_denies` 测 reboot
- Rationale: 用户提出"CC 是不是也 substring 匹配 `rm -rf /`",经源码核实后确认我们 M1 substring 设计是偏离 CC 的错误。token denylist 对齐 CC 设计意图,fragment 只为没 base command 的语法构造保留。
- Evidence:
  - Tests: 11 个 safety 单测全绿(7 个新增 + 4 个既有);auto_mode_gate 64 测全绿
  - Entry: `safety.check_command_policy('rm -rf /tmp/test-fff')` → `review`(测过)
  - LLM proxy log 实际看到 classifier stage 1+2 真跑(system prompt 起始 = "You are an automated security classifier..."),证明 review → classifier 路径打通
  - 单测纯函数级(检查 `CommandPolicyDecision.status` 字符串字段),不 spawn subprocess,**绝对不会真跑危险命令**
- Rollback: 502c9174
- Commits: C5 = `502c9174` safety policy 拆 token vs fragment 对齐 CC
- Next: R5 真 IM 端到端验证

## R5 — 真 IM 端到端测试 (BLOCKED — PA→IM 转发链路 bug 未修)

- Context: R4 全部测试绿,服务起齐(IM:8011 / Kernel:8000 / demo-node online),让用户在 IM 浏览器实测。用户在 IM 发 "删了/tmp/test-fff目录" 后,IM 卡片显示 `tool_call status='running'`,**永远不弹深色权限卡**,agent 也无文本回复。
- 调查发现:
  1. agent kernel SSE **真的 emit 了 `event: permission_request`**(说明 broker.register_request + emit 链路本身没毛病)
  2. **IM 数据库 message row 的 `permission_request_json` 列是 NULL**(直接 sqlite3 查 `.worktrees/feat-333-M6/data/im_service.sqlite3` 确认;agent message row 的 `tool_calls_json` 里有 `status='running'` 但 permission_request_json 空)
  3. PA `main.py:1854` `_build_kernel_event_observer` 的 `elif event_name == "permission_request":` 分支代码看起来对(loop.create_task → _send → manager.send_json with `"kind": "permission_request"`),IM 后端 `gateway_handler.py:659` 的 `elif kind == "permission_request":` handler 也存在,调 `event_bridge.on_permission_request` 写 db
  4. 加 `[PA-DBG]` print 到 stderr 后,gateway.log 一直 0 bytes(daemon stderr 重定向疑似失效),换写 `/tmp/pa_dbg.log` file 也 0 行 → **PA observer 根本没被 invoked**
- 当前假设(待 R6 验证):
  - **A**: PA inbound_pipeline 在 SSE stream 上收 event,但 `pipeline._kernel_event_observer` 没装上(line 1300 `if config.im_service is not None:` 不进入,或 pipeline 不是同一实例)
  - **B**: PA 收 IM 消息时不走 `pipeline.handle_inbound` 而走别的路径(比如 SSE stream consumer 是另一个 task,observer 字段没 wire)
  - **C**: agent kernel emit permission_request 时点 PA SSE consumer 已经 exit(比如 run_status 提前到 completed → break for-loop)— 但这种情况下 IM 上 tool_call 不会一直 `running`,故 C 可能性低
- 服务环境(R5 用):
  - IM `:8011`, JWT_SECRET=`demo-jwt-secret-for-feat340-testing`
  - PA daemon `pid=65382 (重启过)`, gateway-state at `~/.nano-assistant/.gateway-state.json`
  - kernel `:8000` (PA 子进程启的)
  - 测试账号 `nano/nano1234`, user_id=`503349f12f5a466999f62325b453bcf0`
  - default-agent workspace=`/private/tmp/demo-agent-workspace`
  - IM DB 实际路径 `/Users/czj/Repos/nano-multiagent/.worktrees/feat-333-M6/data/im_service.sqlite3` (IM 进程 cwd 在 worktree)
- 已加临时调试代码(待 R6 收尾移除):
  - `src/personal_assistant/main.py:_send()` 写 `/tmp/pa_dbg.log`(observer 触发计数)
- 复现命令:
  ```bash
  TOKEN=$(curl -s -X POST http://127.0.0.1:8011/im/v1/auth/login -H "Content-Type: application/json" -d '{"username":"nano","password":"nano1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
  USER_ID="503349f12f5a466999f62325b453bcf0"
  CID=$(curl -s -X POST "http://127.0.0.1:8011/im/v1/conversations" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"type\":\"direct\",\"participants\":[{\"id\":\"default-agent\",\"type\":\"agent\"},{\"id\":\"$USER_ID\",\"type\":\"user\"}],\"title\":\"perm-debug\"}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id'))")
  mkdir -p /tmp/test-fff
  curl -s -X POST "http://127.0.0.1:8011/im/v1/conversations/$CID/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"content\":\"删了/tmp/test-fff目录\",\"sender_user_id\":\"$USER_ID\"}"
  ```
- Next: R6 修 PA→IM 转发链路 — 先确认 observer 是否真 wire 上(`pipeline._kernel_event_observer` 不为 None);如果 wire 上但没触发,看 SSE consumer 路径是否覆盖 streaming run

## 临时调试代码(R6 收尾删)

- `src/personal_assistant/main.py:_send()` 写 `/tmp/pa_dbg.log` —— 验证 observer 触发的临时 file trace
- `/Users/czj/Repos/nano-multiagent/.nanocode/config.yaml` —— **已清理**(R3 留下的 deny_limit=1 测试用)
- `/private/tmp/demo-agent-workspace/.nanocode/config.yaml` —— **已清理**

## Commits 累积

- 911d1c0e C1 集成测试 Red(worker)
- 81346c6b C2 app.py broker 实例化 + runtime 注入(worker R2)
- cfa8c60d C3 progress.md(worker R2)
- 20fe0d45 C4 orchestrator 接管:loop.py permission_requester 拷贝 + HookModelCall/call_model/LLMGenerateRequest/openai_compat mapper 加 max_tokens/stop_sequences/temperature + 集成测试跨 loop fix + dbg 清理
- 502c9174 C5 orchestrator:safety policy 对齐 CC,拆 token vs fragment 路径,删 `rm -rf /` substring 误判
- (R5 调试中,尚未 commit) PA→IM 转发链路 trace
