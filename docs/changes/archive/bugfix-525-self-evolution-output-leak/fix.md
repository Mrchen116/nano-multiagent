# bugfix-525: 后台自进化原始输出泄漏到聊天

> 历史入口：本文件由并行调查记录创建；Full unit 的权威问题定义见 [incident.md](incident.md)，技术方案见 [design.md](design.md)。

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

`feat-349` 的原始设计把 self-evolution 定义为不打断当前对话的后台 fork，并规定结果只通过轻量 system/meta notification 回显。当前实现也在 review 完成后单独发布 `self_evolution_review` session event，Gateway 与 Web IM 已有结构化通知路径。

坏值源头位于 self-evolution fork 的 HookContext 继承边界：fork 继承父会话事件 publisher，导致 side-chain 的 assistant/tool/turn realtime events 被当作原聊天输出；review 完成后又按设计发布真正的 structured notice，形成两条并行可见路径。本问题不是 `NO_REPLY` 或 tool-only 空气泡缺陷。

## 修复

- self-improvement caller 显式选择私有 fork event policy；raw assistant/tool/turn 留在 side-chain，只把带来源标识的 `skill_created` 业务事件交回父 session。
- Gateway 的 session 级持久 subscriber 成为该业务事件的唯一 owner，跨 foreground terminal 与 stream replay 调用既有 config-sync；普通后台 Agent 文本保持原路径。
- config-sync 在既有 operation lock 内串行完成 read/merge/PATCH/publish，避免同一 Agent 并发 Skill 创建时丢失 explicit allowlist 激活。

## 验证

详见 [regression.md](regression.md)、[verification.md](verification.md) 与两个 milestone 的 `progress.md`。最终隔离真栈覆盖 no-save、真实 `skill_manage(create)`、explicit allowlist、新 session 使用、terminal 后断线重放不漏不重及清理；产品验收与实现核对均通过。

收尾时已合入最新 `origin/main`，并在同一 fork seam 同时保留 bugfix-527 的 `skill_creation_source=F3` metadata 与本 unit 的 private event policy。冲突相关定向测试 75 条通过；最终 non-E2E 为 `3203 passed, 29 deselected`，架构契约 148 条通过，Ruff、docs-check（226 sources / 67 routes）与 diff-check 全绿。未使用真实 Feishu 凭据；隔离 Web IM 走与外部 channel 共用的 production Gateway/Kernel 事件路由。

PR 首轮 Python CI 在全仓并发负载下仅有 post-terminal Skill 同步集成测试超时：真实完成耗时 `5.14s`，超过测试原有 `5s` 调度预算。回归仍等待真实 handler 完成并校验 catalog、selection mode 与 Skill 文件；只把跨 Kernel worker、persistent stream、config-sync thread 的等待预算调整为 `15s`，未修改生产逻辑或弱化结果断言。
