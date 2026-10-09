# Verification Report: Simulator S13 / S21 scope R1

2026-10-07。独立 `change-verifier` 契约核对，并沿用 `change-code-review` 的有据问题原则。范围仅当前全局 PA 的人工权限 pending 生产前置及 S21 故障证据边界。源码基线 `aa7876fa9ab443b4cf12d1a4119fd2abc7d428d3`，读取时 HEAD `4c7134600724f01b9078252ae00529de27438b13`；后续提交为报告同步，产品源码未变。本地 `origin/main=d87ffa3d1` 已为 HEAD 祖先，本角色未 fetch。未操作 Simulator、服务或物理手机，未改变 Auto、规则、配置或源码，未运行产品测试。

## Limited outcome

**限定契约核对完成；不下产品 pass / Full pass。** 当前已核对的普通 global main、普通 child、Workflow child、Heartbeat 和 Cron 生产路径均不挂人工权限 Future。没有发现可以在这些现行路径上自然产生 Work `waiting_permission` 的明确入口。Work 的事件接收、历史显示与决定协议仍然存在，但保留支持不证明现行生产入口可达。

S21 的“实际停止失败”是明确要求；“natural stop 异常”是此前 reviewer 对未执行证据的限定，不是 spec 加上的验收条件。真实 native 用户动作、真实隔离服务和明确一次 stop 故障条件可以证明该受控分支的用户结果；当前报告没有执行或接受该旅程。

`review_mode: targeted-contract-check`；新增代码 finding：`[]`。本次无修正 delta，不重开已有效的代码审查，也不由这份契约报告覆盖其他 Full 退出标准。

## S13: producer versus consumer

| 现行入口 / 条件 | 直接实现和契约证据 | 是否能产生人工 pending |
|---|---|---|
| 普通全局真人消息 / Inbox wake | `docs/specs/gateway/global-agent.md:174-187,214-216` 明确不弹卡、不挂 Future；`session_composition.py:100-104` 为 global_main 投影 `return_to_agent`；`auto_mode_gate.py:449-460,513-533` 返回 block/reason 而不调用 `_handle_ask` | **不能通过当前权限 gate 产生**。分类拒绝、故障、拒绝阈值、工具明确 ask 都不改变此路由。普通聊天询问/用户随后回复是 Agent 协作，不是 Work 权限实体 |
| 普通 child，含后台 child | `agent/sdk/kernel.py:154-187,258-262` 捕获并继承父 `auto_mode_interaction` 与有效 Auto 配置；`auto_mode_gate.py:451-452` 优先识别 global subagent，BACKGROUND_TASK 不切到人工等待 | **不能**。子执行的调度 origin 不是新增审批入口 |
| 普通全局主会话发起 Workflow / Workflow child | Workflow launch 明确 ask 仍走同一 gate；`auto_mode_gate.py:582-590` 的非 human / ultracode launch 分支直接允许，其他 launch ask 经上述 return 路由。`workflows/child.py:174-193` 经共享 `create_subagent` 创建 child；后者必合并父 approval snapshot。`kind=workflow_subagent` 虽不同于普通 child，`auto_mode_gate.py:456-459` 仍先命中继承的 global_interaction | **不能**。Workflow 的父会话权限转发及 correlation 支持不是绕过继承的审批生产路径 |
| Heartbeat，包括复用 global main | `auto_mode_gate.py:453-455,518-529` 按实际 HEARTBEAT origin 走 unattended；`kernel_client.py:289-296` 明确映射 origin；`docs/operations/auto-permissions.md:48-50` 与 global-agent:187 一致 | **不能**。默认 fallback deny，配置 allow 也只是自动裁决，不建立人工 Future |
| Cron / 其 Workflow 等 unattended 执行 | 同一 CRON origin 与 unattended 路由；无 global 策略的自动 child 还受 BACKGROUND_TASK / workflow_unattended 分支约束。若普通 subagent 继承 global 策略，则 return 路由仍不问人 | **不能**。两种路由均不会调用 `_handle_ask` |
| 工具硬性 safety ask | `auto_mode_gate.py:555-561` 识别 safety_check 并 escalate；return 路由直接 block，unattended safety_locked 分支直接 manual_required deny（:516-520） | **不能**。不能把“需要人工确认”文字当作“已创建人工审批卡/Future” |
| CLI / 单聊天 human 交互 | `docs/operations/auto-permissions.md:50` 保留人工审批；`session_composition.py:100-104` 非 global 返回 None，gate 最后为 interactive，`auto_mode_gate.py:530-532,393` 调用权限 requester | **仍可真实产生聊天审批**，但不提供当前 global Work 前置。`IM/api/routes/agent_work.py:13-24` 只允许 work_mode=global 的 Work 资源；不能把单聊天审批挪给 global Work 作为证据 |

共享 requester 的真实入口是 `auto_mode_gate.py:393`；`agent/core/agent/runtime.py:1616-1684` 只有实际调用它才注册 broker Future、发布 `permission_request`，并附 execution_session_id / Workflow correlation。此次检索 `src/agent/platform` 和 `src/personal_assistant` 未发现另一项直接调用该 requester 的现行生产入口。上述判断针对当前源码/契约，不声称检查了所有历史版本的持久会话 metadata。

`global_run_coordinator.py:140-150` 注册真实 global main；`global_work.py:186-220` 按已知父归属记录真实 child/Workflow 的 session_linked，并把 Workflow 权限事件归给 execution_session_id；`:241-247` 跟踪已收到的权限请求。`IM/infra/repositories/agent_work.py:286-293` 由 permission_request 置 waiting_permission、真实 resolved 后恢复状态。`AgentWorkView.swift:103,130` 则在在线 waiting_permission 时默认展开。这是一条**消费真实事件的完整接线**，没有凭空生产权限请求。

已核对的相关测试（本次只读、不新报执行成功）：

- `test_pa_time_prompt_policy.py:88-103`：global runtime 在 human/heartbeat/cron 场景保留 return_to_agent，single runtime 为 None。
- `test_auto_mode_interaction.py:15-41`：global human/background/普通 subagent 返回，heartbeat/cron 按 fallback，所有条件断言 request_permission 未调用；`:59-91` 覆盖跨 run / tool 拒绝阈值及故障后继续分类。
- `test_auto_mode_gate_hook.py:492-513,520-544`：unattended 不 ask，以及非交互 / ultracode Workflow launch 不生成卡。
- `test_global_work.py:174-214`：**测试直接发布** permission_request，验证 execution_session 归属和决定关联；它证明 recorder 协议消费，不证明当前 global 调用能够自然生产请求。

历史真实 Chat allow_once、Deny、延迟确认证据保留在 [acceptance-r18](acceptance-r18.md) 的 S13 行，不因当前 Work 前置核对而撤销。历史 Work permission 记录及兼容显示亦不应删除，但不能将已解析的旧审批或人工注入 pending 称为当前自然 pending。新增 Work 默认展开当前仍无实际 pending UI 证据；本报告不造伪审批、不建议关闭 Auto / 改规则来人为满足前置，也不自行把这个条件宣告为通过或 waive。

## S21: what the contract requires

| 来源 | 明确要求 / 证据 | 边界 |
|---|---|---|
| active `spec.md:156-159` | 用户启停/重连，或确认删除后节点离线 / **实际停止失败**；期望与实际分开，受限/未知权限/失败修复清楚，最后已知说明，回执/重试保持到真实停止，聊天历史保留 | 没有 natural / 自然故障限定 |
| current `docs/specs/gateway/external-channels.md:435-438` | runtime 先摘出站 registry，再有界 stop；失败可重试，不伪造 applied；成功删除只清 runtime/cache identity，不清 IM shadow/history | 描述服务实际执行结果，不规定故障来源必须不可控 |
| [acceptance-r18](acceptance-r18.md):7,17,21,57 | 节点真实 SIGSTOP、离线 pending / conflict、恢复后删除闭环已观察；注明不是 stop 抛异常，并保留未自然发生分支 | “natural stop”用于限定该轮观察，未改变 requirement。该轮 conflict 不足以证明 runtime_stop_failed |
| `channel_manager.py:386-408` | 真正 `_stop_active` 异常产生 runtime_stop_failed + failed removal outcome，继续保留 retryable 状态 | 不等同于直接写假状态/拦截 API 响应 |
| `test_channel_manifest_store.py:32-52,256-314` | adapter.stop 首次抛 `worker exit timed out`，同 revision 再试；首次 retryable_failed / failed / runtime_stop_failed 且缓存仍 v1，第二次 applied / v2，两次 stop 被观察 | 现有公开 reconcile 行为测试提供明确一次故障条件；不是原生体验证据 |

**可行的受控验收边界：** 在 caller 持有的隔离现场，用明确标识且可恢复的一次故障条件让真实 stop 操作抛异常；产品 reviewer 在真实 native 发起确认删除、观察真实 Gateway→IM removal outcome 所形成的失败与修复提示，再从 native 重试并观察真实停止和删除收敛。保留条件、版本、执行结果及清理证据，故障 fixture 仅改变该次 stop 的环境结果，不给 native 伪造状态、不直接插数据库、也不留固定 demo 在产品。此链路可以支撑“真实客户端在受控 stop 失败后可恢复”的声明，不支撑“自然飞书 worker 故障已出现”的声明。

一次 stop fault **不能**顺带覆盖权限 missing/unknown、飞书真实历史保留或其他平台分支；这些用户结果仍需各自真实输入和观察。真实 shadow/history 删除前后仍在，必须单独给服务数据与 native 可见结果，不能由“不删除”的源码或 stop fixture 代替。当前报告未启动现场、未实现 fixture、未实际观察 native，也未改变 S21 整体状态。

## Evidence / handoff limits

本报告只解释当前代码与 current/active 契约。按 `docs/development/evidence.md:9-16,39-44`，源码、测试和报告不能替代尚未执行的真实产品旅程；按 design 的 M1-R1，完整模拟器范围仍由 reviewer逐条观察。用户只跳过物理真机，模拟器工作的授权继续有效；S29/S30、物理 IME、无线续签及自然到期不由此核对完成。报告不提出 Ready PR、merge、部署或减少 Requirement；其他有效检查保留原 scope，不机械重跑。

文档检查 `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` 通过：310 maintained Markdown sources / 75 required routes。只暂存此报告并检查 staged diff；未提交 `output/` 或其他角色文件，无 push。
