# feat-333-M7 Progress — post-M6 链路收尾

> M6 broker wiring 真接通后(单测 6 个绿 + 直连 Coding CLI Allow once tool 真执行),IM 端到端测试发现 user-explicit `rm -rf /tmp/test-fff` 仍看不到卡片。Orchestrator 接管 debug,定位到 4 个 M6 范围之外的真因,逐个修复。M7 不走完整 spec/design/worker 流程,以 hot-fix 形式直接落,留 reviewer round 5 验。

## R1 — Bug C: safety policy substring 误判

- Context: `safety.check_command_policy('rm -rf /tmp/test-fff')` 返回 denied → hook line 697 一票否决 → 永远不到 classifier → ask 链路不可达。
- 真因: M1 在 `bash_blocked_fragments` 写 `"rm -rf /"` substring,`"rm -rf /tmp/x"` 包含子串 `"rm -rf /"` 误判 denied。CC 源码完全不 substring 匹配 `rm -rf`(`bashSecurity.ts:45-75` 的 `ZSH_DANGEROUS_COMMANDS` 是 Set + base command token 匹配,只列 zsh 模块攻击向量),CC 的 rm 处理 100% 交给 yoloClassifier system prompt "Irreversible Local Destruction" 类别由 LLM 判。
- 修法 (用户选 B 方案,略严于 CC):
  1. 拆 `bash_blocked_commands` (新, base command token 匹配) vs `bash_blocked_fragments` (substring,仅留 `:(){`fork bomb 语法)
  2. `bash_blocked_commands` = mkfs/reboot/shutdown/halt/poweroff (略严于 CC,dev agent 无场景) + zmodload/emulate/ztcp/zsocket/zpty/sysopen/sysread/syswrite/sysseek/zf_rm/zf_mv/zf_ln/zf_chmod/zf_chown/zf_mkdir/zf_rmdir/zf_chgrp/mapfile (mirror CC ZSH_DANGEROUS_COMMANDS)
  3. 新增 `_extract_base_command()`: 剥 `VAR=val` env 前缀后取首 token,小写
  4. `.nano/policy.toml` 加 `deny_commands` key 覆盖默认
- Evidence:
  - 7 个新单测 + 1 个旧测改写(`rm -rf /` → `:(){:|:&};:`)
  - 11 个 safety 单测全绿;auto_mode_gate 64 测全绿
  - `safety.check_command_policy('rm -rf /tmp/test-fff')` → review (验过)
- Commit: `502c9174` fix(feat-333-M6): safety policy 对齐 CC

## R2 — Bug D: PermissionBroker `deny_limit` 永远是默认值

- Context: 即使 R1 通后 classifier 给 deny, hook 1 次 deny 不触发 ask。workspace `.nanocode/config.yaml` 写 `deny_limit: 1` 无效。
- 真因: `app.py:124` `PermissionBroker(config=AutoModeConfig())` 用默认值实例化,`broker._config.deny_limit` 永远 = 3。workspace config 改 deny_limit 不能传到 broker (broker app 级单例,不知道 per-session workspace)。
- 修法:
  1. `broker.is_deny_limit_exceeded(run_id, tool_name, *, deny_limit: int | None = None)` 加 optional override,None fallback 到 `self._config.deny_limit`
  2. `auto_mode_gate.py:705` + `:741` 调用时传 `deny_limit=config.deny_limit` (hook 已读 workspace config 到本地变量)
  3. 加单测 `test_deny_limit_override_per_call`:同一 broker default=3,override=1 → 1 次 deny 即 exceeded;override=5 → 1 次 deny 不达标
- Evidence: 77 个 broker / auto_mode / safety / integration 测试全绿
- Commit: 待 R3 完成后一起 commit

## R3 — Bug E: SSE 长 idle 连接断开(待真诊断,留作下一个 unit)

- Context: R1+R2 修后,kernel SSE 直连 curl 看到 `event: permission_request` emit,但 PA inbound_pipeline 永远收不到 — PA `RAW event=` 卡在 tool_start 后,再没下个 chunk。
- 关键诊断证据:
  - PA `_kernel_event_observer` 内 `elif event_name == "permission_request":` 加文件 trace,测试中**从未写入** → 证实 PA observer **从未收到** permission_request event
  - 同时直接 `curl -sN ... -H 'Last-Event-ID: 0'` 同一 session 的 SSE 端点 **能看到** permission_request event(history replay 有它)
  - 结合两点 → PA 的 live SSE 连接在 permission_request emit 之前被某种方式中断
- **初次错误诊断**(已撤销): 怀疑 kernel uvicorn 默认 `--timeout-keep-alive=5` 关闭 idle SSE 连接,尝试两种修法:
  1. server-side `_session_stream_generator` 用 `asyncio.wait_for(__anext__(), timeout=2.0)` 包 hub iterator + yield `": keepalive\n\n"` heartbeat —— **失败**:`wait_for` 超时 cancel `__anext__()` 会传播 `CancelledError` 到 hub generator 内部 `await asyncio.sleep`,**破坏 generator 内部 state**,使后续 SSE yield 0 个 events(实测 SSE 完全无输出)。已 revert。
  2. PA spawn kernel 加 `python -m uvicorn ... --timeout-keep-alive 3600` —— **理论无效**:`--timeout-keep-alive` 控制的是 **HTTP/1.1 keep-alive 等待复用连接的空闲超时**(完成请求后等待新请求复用 socket),不是 active response body streaming 的超时。SSE 处于 active body 写入状态,该参数对它不起作用。已 revert。
- 真因待查的可能方向(留给下一个 unit 接手):
  - **A**:PA `_send_turn_start_and_store` await ack 时 IM 返回 ack 字段格式跟 observer 期望不一致 → message_id 写不进 run_context_store → 后续 permission_request observer 进 `if message_id:` False 跳过转发(但 IM DB 看到 agent message row 存在并有 tool_calls_json,看似 ack 路径走通,需要进一步核实 message_id 是否真传回 ctx)
  - **B**:hook 在 emit permission_request 后 `await future`,期间 hook 跑在 kernel 进程的 asyncio event loop。`event_hub.publish` 是 sync 函数(`with self._lock`),发布完后 hub 内部 buffer 应已 put 入 subscriber.queue。但若 hub `_session_stream_generator` 的 `await asyncio.sleep(tick_seconds)` 在某点 raise / cancel,subscriber 在 `__finally__` 里被从 `_subscribers` 移除 → publish 后续 events 不再 fanout 给它
  - **C**:PA `_kernel_client.stream_session` 的 httpx `aiter_bytes` 在 kernel 某次写 SSE chunk 时,响应 chunk 解析失败 / TCP 层错误 / anyio 调度问题,导致 generator 提前退出但无异常抛出(silent return)
  - **D**:SSE chunked transfer encoding 在 hook park 时 chunk 间隙长 → 中间路径(uvicorn worker thread / asyncio executor / anyio transport)某层 idle timeout
- 推荐下一步: 写一个独立 SSE listener(纯 python httpx,与 PA 同时连同 session,记录 chunk 时间戳),与 PA SSE 并行观测 — 看 publish permission_request 后是 PA 连接先断还是两者都收到。如果两者都收到,问题在 PA observer / message_id 路径(假设 A);如果只 PA 断,问题在 PA httpx client 配置(假设 C/D)。
- **Status: BLOCKED for M7**,需要新 unit 处理。M6 范围内的 broker wiring 真接通(单测全绿 + Coding CLI 直连 e2e Allow 后 tool 真执行),Bug E 是 M2 IM 集成层的链路 bug。
- Commit: N/A(无修复 commit,仅文档记录)

## 整个 feat-333 IM 端到端最终缺陷链(从 M1 写错到 M7 修齐)

| Bug | 位置 | M1 原意 | 实际 | 修复 |
|---|---|---|---|---|
| A | `loop.py:274` HookContext copy | 让 tool_hook_ctx 继承 active_hook_ctx 所有字段 | 漏传 `permission_requester` → fail-closed deny | M6 C4 (commit 20fe0d45) |
| B | `HookContext.call_model` 签名 | 接 classifier 需要的 max_tokens/stop_sequences/temperature | 签名只接 4 参,classifier 调用抛 TypeError | M6 C4 (commit 20fe0d45) |
| C | `safety.py` `bash_blocked_fragments = ("rm -rf /",)` | 阻止 `rm -rf /` 根目录 | substring 误伤 `rm -rf /<任意路径>` 全 hard-deny | M7 R1 (commit 502c9174) |
| D | `PermissionBroker(config=AutoModeConfig())` 全局单例 | broker 应按 workspace 应用 deny_limit | broker._config.deny_limit 固化 3,workspace override 无效 | M7 R2 (待 commit) |
| E | PA SSE 长 idle 连接断开(真因不明) | PA 持续收 kernel SSE events | hook park 后 PA 不再收 chunk;permission_request 到不了 PA observer | **BLOCKED** — 见 R3 失败修法 + 待查方向 |

reviewer round 1-4 全靠单测 + 文件检查通过,**从未在 IM 端到端 真实触发 ask 流程**,这 5 个 bug 一个都没暴露。修齐后 reviewer round 5 应在 IM 浏览器实测 user-explicit rm-rf 看到卡片 + 点 Allow / Deny 真生效。

## Commits 累积 (M7)

- C1 = broker deny_limit override + 单测(本 commit)
- C2 = ~~SSE generator keepalive heartbeat~~ 撤销,Bug E 待真诊断
- (R1 已在 M6 C5/502c9174 commit) safety policy 对齐 CC
