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

## 验证
