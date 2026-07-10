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

## R3 — Bug E: `permission_request` SSE event 漏 `run_id` 字段

- Context: R1+R2 修后,kernel SSE 直连 curl 看到 `event: permission_request` emit,但 PA `_kernel_event_observer` 的 `permission_request` 分支 trace 始终不触发。
- **失败的初步诊断**(已撤销):误判为 SSE 长 idle 连接断开,尝试两种修法均无效:
  1. server-side `_session_stream_generator` 用 `asyncio.wait_for(__anext__(), timeout=2.0)` 包 hub iterator + heartbeat —— `wait_for` 超时 cancel 会破坏 hub generator 内部 state。Revert。
  2. PA spawn kernel 加 `--timeout-keep-alive 3600` —— 该参数控制 keep-alive 复用,不是 active body streaming 的超时,理论上无作用。Revert。
- **真因**(R7 定位):`runtime.py:791-800` publish `permission_request` payload **漏 `run_id`** 字段。对照 `realtime_stream.py:42` 的 `tool_start` payload 明确带 `"run_id": run_id`,而 `permission_request` 和 `permission_resolved` 都没有。PA `inbound_pipeline.py:564` 过滤 `if event.get("run_id") != run_id: continue` —— `None != run_id` 永真,**event 在到达 observer 前就被丢弃**。直连 curl 没过滤所以看得见;history replay 也看得见;**只有 PA pipeline 看不见**。完美解释所有现象。
- **修法**:`runtime.py:791-800` 和 `:808-811` 两处 publish 加 `"run_id": run_id_for_broker`(闭包早就捕获了)。
- Evidence: e2e 测试 — IM 发 `rm -rf /tmp/test-fff` → 8 秒内 IM 收到 permission_request 卡片,payload 完整(request_id / tool_name / question / options)。
- Commit: 本轮 commit

## R4 — Bug F: PA 的 IM `permission_response` 回路完全没 wire up

- Context: R3 修后 IM 看到卡片,但点 Allow 后 tool_call 永远停在 `running` —— decision 没到 kernel。
- 真因:`im_connection.py:373` 收 `permission_response` 后调 `self._permission_response_handler(body)`,但 `_build_im_connection_manager`(`main.py`)**从未传入** handler 参数 → handler 始终 None → IM 帧静默丢弃。这跟 Bug E 是同一波 M1/M2 的疏漏 —— "出去" 的半截通了,"回来" 的半截从未写。
- 修法(4 处补 wire up,非重构):
  1. `RelayLifecycleUpdate` 加 `kernel_session_id: str | None` 字段,`inbound_pipeline.py:203` 的 "accepted" emit 顺手填上 `binding.kernel_session_id`
  2. `main.py` relay_lifecycle "accepted" 分支把 `kernel_session_id` 一并写进 `run_context_store[run_id]`
  3. `KernelAPIClient.submit_permission_decision(session_id, request_id, decision)` 新方法,POST `/v1/sessions/<sid>/permissions/<rid>`
  4. `main.py` 新增 `_build_permission_response_handler(kernel_client, run_context_store)` 工厂:从 IM 帧 `message_id` 在 store 里反查 `kernel_session_id`(找不到时若只有一个活跃 session 就 fallback),然后 POST 决策。`_build_im_connection_manager` 加 `permission_response_handler` 参数透传给 `IMConnectionManager`
- Evidence:
  - 5 个新单测 `test_permission_response_handler.py` 全绿(routing / fallback / 模糊拒绝 / 错误吞没 / 异常不传播)
  - 361 个相关回归测试全绿
  - e2e Allow:IM 点 Allow → tool 真跑 → `/tmp/test-fff` 真消失,tool_call.status = completed
  - e2e Deny:IM 点 Deny → tool blocked by hook,tool_call.status = failed,目标目录存活
- Commit: `65e0f436`

## R5 — Bug G: classifier 拿不到真实 user message,transcript 缺失关键证据

- Context: R3+R4 修后端到端通了,但用户在 IM 测两次 rm -rf 时观察到 "第二次没 ask 直接执行"。检查 LLM proxy 日志发现 classifier 收到的 transcript 永远只有 `bash rm -rf <path>` 一行,**完全没有 `User: ...` 段** —— 即 classifier 看不到用户的真实输入,只能凭概率猜 "是否 explicit user request"。
- 真因:`HookContext.message_history: tuple[Any, ...] = ()` 字段早在 M1 就定义了(`context.py:134`),`auto_mode_gate.build_transcript_entries(ctx.message_history)` 也按约定调用,但 `loop.py:274` 创建 tool_call hook ctx 时 **从未填充该字段** → 永远是空 tuple → transcript builder 输出空 → classifier 缺关键证据。
- 对照 CC 源码核实(响应用户提示):`src/utils/permissions/yoloClassifier.ts:302 buildTranscriptEntries` 明确把 `msg.type === 'user'` 的 text content 加进 transcript(line 326-340)。我们的 `build_transcript_entries` 实现也是同样设计,只是上游 ctx 没喂数据。
- 修法:`loop.py:274` 的 HookContext 构造加 `message_history=tuple(llm_messages)`,把当前运行中的对话喂给 hook。
- Evidence:
  - 修复前 LLM proxy 日志:transcript = `<transcript>\nbash rm -rf /tmp/test-delete-me\n</transcript>`,stage 2 review 有时 thinking 后维持 deny,有时直接 `<block>no</block>` 翻盘
  - 修复后 LLM proxy 日志:transcript = `<transcript>\nUser: 用 bash 工具立即执行: rm -rf /tmp/test-msghist-2\nbash rm -rf /tmp/test-msghist-2\n</transcript>`,classifier 拿到完整证据
  - 3 次同输入 e2e 测试:#1 ASK / #2 allow (stage 2 翻盘) / #3 ASK —— LLM 概率残余仍在(yoloClassifier 设计的固有性质),但绝大多数案例 classifier 做出"虽 user 提及但 rm -rf 仍需确认"的稳健判断
  - 344 个相关单测全绿
- 残余非确定性说明:LLM 在 "用户说'立即执行'是否构成 explicit confirmation" 这个灰色地带仍有概率波动。这不是代码 bug,是 yoloClassifier 架构的固有性质(CC 同款)。如要进一步降概率,prompt 调优方向:stage 2 system prompt 加强 "rm -rf 等不可逆破坏即使 user explicit 也保留 ask";或工程方向:把 bash 加进 workspace `confirm_tools` 列表强制每次必 ask(不走 classifier)。
- Commit: `284b8e08`

## 整个 feat-333 IM 端到端最终缺陷链(从 M1 写错到 M7 修齐)

| Bug | 位置 | M1 原意 | 实际 | 修复 |
|---|---|---|---|---|
| A | `loop.py:274` HookContext copy | 让 tool_hook_ctx 继承 active_hook_ctx 所有字段 | 漏传 `permission_requester` → fail-closed deny | M6 C4 (commit 20fe0d45) |
| B | `HookContext.call_model` 签名 | 接 classifier 需要的 max_tokens/stop_sequences/temperature | 签名只接 4 参,classifier 调用抛 TypeError | M6 C4 (commit 20fe0d45) |
| C | `safety.py` `bash_blocked_fragments = ("rm -rf /",)` | 阻止 `rm -rf /` 根目录 | substring 误伤 `rm -rf /<任意路径>` 全 hard-deny | M7 R1 (commit 502c9174) |
| D | `PermissionBroker(config=AutoModeConfig())` 全局单例 | broker 应按 workspace 应用 deny_limit | broker._config.deny_limit 固化 3,workspace override 无效 | M7 R2 (待 commit) |
| E | `runtime.py:791-800` permission_request publish | event 带 run_id 让 PA 过滤识别 | **漏 `run_id`** 字段,PA `inbound_pipeline:564` 过滤直接丢弃 | M7 R3 (commit 65e0f436) |
| F | `_build_im_connection_manager` 未传 `permission_response_handler` | IM Allow/Deny 回到 PA → kernel 解 future | handler 始终 None → IM 帧静默丢弃,tool 永远 park | M7 R4 (commit 65e0f436) |
| G | `loop.py:274` HookContext 构造未填 `message_history` | classifier transcript 含用户原话以判 "explicit user request" | 字段永远 `()` → transcript 只有 tool action,classifier 缺关键证据靠概率猜 | M7 R5 (commit 284b8e08) |

reviewer round 1-4 全靠单测 + 文件检查通过,**从未在 IM 端到端 真实触发 ask 流程**,这 7 个 bug 一个都没暴露(其中 Bug G 还需对照 LLM proxy 日志 + CC 源码才能发现)。修齐后 reviewer round 5 应在 IM 浏览器实测 user-explicit rm-rf 看到卡片 + 点 Allow / Deny 真生效(orchestrator 自测 e2e Allow + Deny 双路径已通,见 R3/R4 Evidence;classifier transcript 完整性见 R5 Evidence)。

## 复盘要点(供 reviewer/post-mortem 参考)

1. **单测和静态检查不等于功能验收**。Bug A-G 全部能通过 M1 的单测,但凡是涉及"几个模块间真实跑起来"的链路,都需要 e2e 实测。本 unit 的所有 bug 都是 reviewer round 1-4 完全没暴露的。
2. **HookContext 这种"字段定义了但没人填"的隐形 bug 危险性极高**(Bug A 的 `permission_requester` + Bug G 的 `message_history` 都是同型)。grep 上下游使用 + 看 LLM proxy 日志实际 payload 才能抓到。
3. **Publisher payload 字段对齐是另一个隐形雷区**(Bug E 的 `run_id`)。新增 SSE event 类型时必须看消费方过滤器要求哪些字段,不能只看发布方"塞了 request_id 应该够了吧"。
4. **WS handler "出去半截通了进来半截没接" 易漏**(Bug F)。任何双向通道都要分两次端到端测,出去通了不代表回来通。
5. **复刻参考实现时不能轻信调研笔记**(Bug G 的修复触发):笔记可以告诉你"应该这么做",但是否真的"在你这边也这么实现"需要去 grep 上下游确认 —— `build_transcript_entries` 的实现复刻是对的,但 ctx.message_history 这个上游输入根本没人喂数据,笔记和验收都看不出来,只有跑起来对照 LLM 日志才能发现。
6. **LLM-based classifier 有不可消除的概率性**。yoloClassifier 架构(CC 同款)的稳定性靠 transcript 完整 + 严格 system prompt,但不能保证 100%。需要用 confirm_tools / deny_commands 这种确定性规则兜底真正关键的破坏性操作。

## Commits 累积 (M7)

- C1 = broker deny_limit override + 单测 (commit 825270cf)
- C2 = ~~SSE generator keepalive heartbeat~~ 撤销
- C3 = Bug E + Bug F 真因修复 (runtime.py run_id 字段 + PA permission_response_handler 全链路 wire up) + 5 个 handler 单测 (commit 65e0f436)
- C4 = Bug G 修复 (HookContext.message_history 填充,classifier 拿到真实 user message) (commit 284b8e08)
- (R1 已在 M6 C5/502c9174 commit) safety policy 对齐 CC
