# bugfix-525: 后台自进化原始输出泄漏到聊天

## Relations

- Related: feat-349
- Related: feat-524

## 原始报告

> 那这个消息又是啥意思

> 截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png`

> 直接开unit修

## 现象 / 复现

当开启 self-evolution memory curation 的 Agent 在外部飞书会话中达到后台 review 阈值时，正常回答之后会额外出现一条由 Agent 头像发送的英文消息，例如：

```text
Saved: user expects reference behavior to be verified before proposing or implementing an imitation, rather than inferred.
```

该英文内容不是用户请求的回答，也不是 runtime footer。它来自后台 self-evolution review side-chain：side-chain 调用 `memory` 成功后，模型生成了一条面向 review 调度者的完成确认；该确认被错误地当成普通 assistant 气泡投递到原飞书聊天。

2026-08-10 的生产复现证据：

- Kernel session：`sess_5f9eeb9f7479dd13`；
- `09:41:03` 的模型调用收到系统注入的 memory review prompt，并调用 `memory(action=add)`；
- `09:41:09` 的下一次模型调用生成上述 `Saved: ...` 文本；
- 对应用户偏好确实写入 workspace `USER.md`，说明后台整理本身成功，错误只发生在其原始输出的可见性边界；
- 飞书截图显示该文本成为正常回答后的独立 Agent 消息气泡。

预期行为是：后台 review 继续完成 memory/skill 更新，但用户界面只沿既有 `self_evolution_review` 结构化 system notification 得知更新结果；review prompt、工具结果和模型完成确认均不得成为普通聊天消息。对于外部 channel，system/debug/后台维护文本继续遵守 current spec，不作为普通 channel 消息外发。

## 根因

`feat-349` 的原始设计把 self-evolution 定义为不打断当前对话的后台 fork，并规定结果只通过轻量 system/meta notification 回显。当前实现也在 review 完成后单独发布 `self_evolution_review` session event，Gateway 与 Web IM 已有结构化通知路径。因此修复必须保留：

- 达到阈值后仍自动运行 memory/skill review；
- review fork 仍继承主会话上下文、实际模型、工具能力与 unattended 权限语义；
- memory/skill 写入结果不回滚、不丢失；
- 用户仍可收到既有、可本地化且可归因的结构化更新通知；
- 普通后台 Agent 明确产生的用户可见结果继续按既有产品语义投递，本修复不能一刀切屏蔽所有 `background_task` origin。

坏值源头位于 self-evolution fork 的 HookContext 继承边界：

1. 前台 turn 完成后，`make_fork_conversation()` 从父 turn 复制 HookContext 与 metadata，仅把 `run_origin` 改为 `background_task` 并清除递归 fork 能力；
2. fork 内部的 `AgentLoop.run()` 继续使用这份父 HookContext 执行 observe/realtime hooks；
3. 父上下文中的会话事件发布与 Gateway delivery identity 因而也被 side-chain 继承；
4. side-chain 的 `assistant_message` / `turn_end` 被实时流误认为原聊天 run 的用户可见输出，Gateway observer 随后把文本镜像成普通 IM/外部 channel 气泡；
5. review 完成后，`self_improvement` 又按设计发布真正的 `self_evolution_review` 通知，形成“原始完成确认气泡 + 正式系统通知”两条并行可见路径。

该缺陷能进入生产，是因为现有测试分别覆盖了“fork 能调用允许的 memory/skill 工具”“review 完成后发布结构化 session event”和“Gateway/IM 展示结构化通知”，但没有覆盖一个真实 self-evolution fork 在父 run 已绑定实时 delivery observer 时的端到端可见性；也没有断言 side-chain 的原始 assistant/tool/turn 事件不会进入前台聊天投递面。

本问题不是 `NO_REPLY` 或 tool-only 空气泡缺陷：本次 side-chain 产生了真实文本并完成了真实 memory 写入，错误在于后台维护输出被错误归类为用户可见回复。

## 修复

在 self-evolution fork 的既有 `make_fork_conversation()` HookContext 派生边界过滤
`session_event_publisher`：fork 仍保留父 run 的模型调用能力、workspace execution
scope、tool registry、permission requester 与 `background_task` unattended 语义；其
内部 realtime assistant/tool/turn events 不再进入父 session，但成功
`skill_manage(create)` 产生的 `skill_created` 作为显式业务事件白名单继续转发给父
publisher，使 Gateway `AgentConfigSync.handle_skill_created()` 仍能启用显式 skill
allowlist 并刷新相关 session。fork 返回后，`self_improvement` 仍使用父 background hook
context 发布结构化 `self_evolution_review`。

没有按 `RunOrigin.BACKGROUND_TASK` 做全局过滤；普通后台 Agent assistant result 的既有
Gateway subscriber 路由保持不变。

修复提交：

- `de432ddd1` — 隔离 self-evolution raw session events，并补真实 Kernel fork integration regression 与继承不变量断言。
- `2ecdd1cc4` — reviewer fix：把 blanket no-op 收窄为仅转发 `skill_created` 的 side-chain 业务事件白名单；新增真实 skill-create 回归并加固受控 LLM driver。

## 验证

修前生产症状由以下只读证据交叉定位：

- session `sess_5f9eeb9f7479dd13` 的 `2026-08-10_09-41-03_357-req-anthropic_messages.json` 含 memory review prompt，响应调用 `memory(action=add, target=user)`；
- 同目录 `2026-08-10_09-41-09_400-non-stream-res-anthropic_messages.json` 的终态 assistant content 是 `Saved: user expects reference behavior ...`；
- `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png` 显示该 raw completion 成为正常回答后的独立 Agent 气泡。

永久 regression `tests/integration/test_self_evolution_output_visibility.py` 从 public Kernel
SDK 入口创建真实 session，并分别驱动 memory review 与 skill review。fake LLM 只按受控
请求状态及 assistant tool-call / tool-result 结构推进，不匹配内部 prompt 或工具结果文案。
memory 路径真执行 `memory(add)`；skill 路径真执行 `skill_manage(create)`；两条路径随后都
生成生产同形态的 `Saved: ...`。修后同时证明：

- workspace `USER.md` 确实写入 sentinel，memory side effect 未丢失；
- 四次模型调用（两个前台、两轮 review）都使用父 session 的 `test-model`；
- 父 session event stream 不含 review assistant、memory `tool_start/tool_end` 或额外 `turn_end`；
- skill 文件真实落盘，父 stream 收到一条 `skill_created`，且不含对应 raw `tool_start/tool_end` 或 assistant completion；
- stream 仍有正常 foreground answer 与 completed `self_evolution_review`；结构化通知的 exact-once owner 由跑完整 handler 边界的 `TestSessionEventPublish.test_event_published_after_fork` 以 `assert_called_once()` 保护；
- 既有 `test_bg_subscriber_routes_background_task_assistant_message_to_callback` 继续通过，普通 background Agent result 未被抑制。

门禁结果：

- reviewer-fix focused self-evolution / fork / realtime / Gateway observer/config-sync suites：`90 passed`；
- 完整非 E2E：`3183 passed, 26 deselected`；
- Ruff：全仓 check 通过，`876 files already formatted`；
- docs-check：`217 maintained Markdown sources, 67 required routes`；
- `git diff --check`：通过。
