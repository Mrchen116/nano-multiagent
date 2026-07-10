# Design 评审:bugfix-426-midrun-message-steering

**结论**:Issues Found(1 WARNING + 建议;无 CRITICAL,接近 Approved)

## 核实台账(逐条核过的承重原子;结论附独立追到的证据)

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状:inbound 用户消息一律 `_run_queue.submit` 串行排队(bug 机制) | 从 IM 入站正向追投递路径 | ✓ 成立。`inbound_pipeline.py:285` `_kernel.submit` 包在 `_run` 里,`_run` 经 `_run_queue.submit(session_key, _run)`(:424)进 per-session FIFO+Lock;`_run` 内 `_await_terminal_run_async`(:332)阻塞到 run 终态——下条消息的 `_run` 必须等前一个跑完才启动。bug 真实存在于生产路径 |
| 现状:`/stop` 在 `_run_queue` 之前走 `_active_runs`+`interrupt`(可参照位置) | 核 stop 路径落点 | ✓ 成立。`_handle_stop_command`(:237-240)在 `_run_queue.submit` 之前调用,`interrupt` 经 `_kernel.interrupt`(:696)。design「仿 /stop 位置插 steer」位置真实可用 |
| 现状:CLI `_run_repl` 全程 await 阻塞,运行中无法输入 | 读 REPL 输入循环 | ✓ 成立(design 引 :716,实际阻塞 await 在 `commands.py:719` `_send_message_async`,off-by-3 不影响)。run 执行期 `read_line`(:660)根本不被触达 |
| 现状:registry stranded 续跑硬编码 `BACKGROUND_TASK`+文本重建丢多模态 | 读 registry.py:635-648 | ✓ 成立。`:646` `origin=RunOrigin.BACKGROUND_TASK`;`:644` `{"type":"text","text":msg.content}` 把 content 强转 text part,list 多模态会丢。决策3 落点正确 |
| 现状:`inject_pending_message`/`get_active_run_id` 完好,唯一调用方 background_tasks | 追 wiring 范式 | ✓ 成立。`background_tasks/wiring.py` 先 `get_active_run_id` 有则 `inject_pending_message` 否则 submit;registry `:453`/`:508` 符号在 |
| 现状:产品只能 import `agent.sdk`,注入须经 SDK 接出 | 核分层约束 | ✓ 成立,符合 AGENTS.md 依赖方向 + incident Q4 |
| 决策1:`submit(steer=bool)` + `RunInfo.injected` | 拍死/自洽/spec 驱动 | ✓ 拍死(签名给定,默认 False);驱动自 spec「SDK 内核级 affordance」Req;与既有 `interrupt`(now 侧)无重叠。`kernel.submit`(:831)/`interrupt`(:908)行号对得上 |
| 决策2:注入携带完整 parts 多模态 | spec 驱动/自洽 | ✓ `LLMMessage.content: str\|list` 原生支持;与决策3 一致 |
| 决策3:续跑保 origin=USER+完整 content | 自洽/数据流闭合 | ✓ 修 registry 真实缺陷;origin 载法下沉 worker——需扩 `inject_pending_message` 带 origin 参数,属 M1 范围(registry.py 已列入),可行 |
| 决策4:CLI 非阻塞 REPL+运行中走 steer | 拍死/边界 | ✓ 钉死「运行中输入必须非阻塞且 steer=True」,具体改法下沉 worker;abort 侧保留 interrupt |
| spec Req「运行中下一轮注入」+4 Scenario | 覆盖 | ✓ 决策1+gateway delta 全覆盖(中途发/不掐工具/连发保序/空闲新 run) |
| spec Req「SDK 内核级 affordance 复用」 | 覆盖 | ✓ 决策1 统一 affordance,IM/CLI 同路径 |
| spec Req「IM+CLI 两端」 | 覆盖 | ✓ M1=IM、M2=CLI |
| 非目标:不掐工具/不取最新/群聊路由不变/无特殊 UI | 不越界 | ✓ round-boundary(Q1=A)、FIFO、不动 routing、不动前端;均守住 |
| delta-spec kernel/gateway/cli 三份 + im=no delta | 覆盖/ADDED 用法/THEN 可观察 | ✓ 长青契约层无 mid-run 注入既有条目(`kernel/spec.md:425` 的 `append_message` 是另一机制——带外持久化+需新 submit,非活跃 run 注入),故 ADDED 正确非 MODIFIED;THEN 用 `RunInfo.injected`/run_id/下一轮上下文,无内部符号断言 |
| M1/M2 拆分 | 垂直 vs 横切/举证 | ⚠ 非横切(两条均端到端可观测、按 consumer 垂直切),但「为何不并进单 M1」举证薄;M2 依赖 M1 故非并行,A/B 并行组标注实际是串行 |
| 并行组范围交集 | 文件重叠? | ✓ M1=sdk+core+gateway,M2=coding_cli,无交集(且串行) |
| 退出标准两轨 | 齐/可验 | ✓ 每 M 都有 `[reviewer]`(引 spec Scenario)+`[worker]`(单测/injected 正确/多模态/origin) |

## Issues

- **[WARNING] [Gateway 数据流 / 决策1]**:steer 路径的 parts 构建边界未钉死,群聊有静默回归风险。现状 `_run` 内(`inbound_pipeline.py:248-281`)对群消息做 sender 前缀(`_format_sender_text`)+ group buffer drain + 附件组装;design「解析 binding → `kernel.submit(steer=True)`」把 parts 构建下沉 worker,但**没明确要求 steer 路径复用同一套 parts builder**。worker 若在 steer 分支只取 `message.text` 裸文,群聊 steer 会丢 sender 前缀与缓冲上下文——违反非目标「群聊行为不变」。
  - **不改→下游坏事**:M1 worker 可能建出群聊降级的 steer 路径,群聊运行中 steer 丢失发言人标识与缓冲上下文。
  - **建议**:决策1/Gateway 数据流补一句——steer 路径必须复用 `_run` 现有 parts 构建(群前缀+buffer drain+附件),只把「投递动作」从 `_run_queue.submit` 换成 `submit(steer=True)`。

## Recommendations(不阻断门禁)

- M1/M2 拆分补一句举证(M2 = CLI 非阻塞 REPL+终端并发,独立验证旅程且组合进 M1 可能超单 worker 窗口);并发组标注建议从 A/B 改为体现「M2 依赖 M1 串行」(mermaid 已对,表头并行组列误导)。
- 决策3 origin 载法虽下沉 worker,可在风险段点明「需给 `inject_pending_message` 加 origin 参数 + pending 队列承载 origin」,让 worker 不必从零推断。
