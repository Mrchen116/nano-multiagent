# bugfix-592: 工具失败后主 Agent 继续处理用户事项

## Relations

- Related: refactor-581-dsh-personal-assistant；当前契约见 [Global Agent](../../../specs/gateway/global-agent.md)。

## 原始报告

> 这里有两个问题，一个问题是为什么会被拒绝？不应该拒绝。第二个问题是，主agent为什么不继续工作？没有一点主动性。正常来说，它遇到工具报错，它应该要么尝试别的路径去做，要么可以跟用户汇报，对吧？那它现在都没做，它直接停在那了。

> 模型它可以是空响应，但是我是说这个场景下不应该是空响应，所以我们的session prompt啊，或者哪个prompt肯定有问题，需要调整。

> 那你尝试一下怎么能够改一下，然后测一下。我感觉这个Prompts得一点点调一下。

本轮范围为第二个问题：逐步调整主会话持续执行及失败反馈指令，并用真实模型对照验证。审核器对原聊天正常回执的误拒绝单独保留，不用修改审核规则掩盖失败后静默的模型行为。

## 现象 / 复现

2026-10-13 Mini 的 personal-agent 已成功拷贝并核验技能文件，但向发起请求的飞书私聊汇报时被 Nano 自动审核拒绝。错误作为工具结果进入下一次 Astra 请求，模型返回空正文、无工具调用并结束。用户没有收到成果或阻塞说明。

- Session: `8d36509c-91d0-423d-97d4-2f6419162253`。
- 证据：Mini LLM_Bridge 的 `logs/session/2026-10-13_20-19-06_046_8d36509c-91d0-423d-97d4-2f6419162253/`；主模型请求时间 `20-22-07_176`，审核请求时间 `20-21-49_682` / `20-22-00_511`。
- 上游原始响应为 `completed`、空 `output_text`；请求包含真人原话、主 Prompt 与完整拒绝原因，不是代理丢字或工具错误未回传。
- 验收：失败后选择允许且有实际意义的后续动作，或向原用户解释具体阻塞并询问；不能绕过权限拒绝，不能只生成不会投递的私人文字；已交付或无事项的后台轮次仍可静默。

## 根因

Native DSH 保留工具结果并继续采样，Nano 主 Prompt 已要求“拒绝后选替代方案或询问用户”，但持续承担事项与安静等待的指令没有明确规定失败后的决策及进入等待前的沟通条件。自动拒绝和审核不可用结果只包含原因，没有在决策当下提供下一步指导。这是已确认的指令覆盖缺口；模型本次选择空响应的内部原因不可从未公开的推理内容断定，改进效果必须通过真实模型实验检验。

原设计意图是全局主 Agent 通过 send_message 交付结果，已发送后的空正文无需再写私人完成说明。`c8e20a763` 允许静默结束；`f881314a4` 已明确先交付再静默。本轮保留静默能力，不增加强制非空、宿主自动回复、拒绝重试循环或第二套 Agent Loop。

参考本地 Codex `806d9732c9`：模型主 Prompt 的 autonomy/persistence；`prompts/src/permissions_instructions.rs` 的拒绝后替代/询问说明；`prompts/src/model_messages/guardian.rs` 的拒绝与超时分别指导。不能复制其“final 即公开回复”假设：Nano 全局模式必须使用 send_message。

## 修复

仅加强 global-mode 主会话指令：失败不等于完成，执行错误可修正并继续，权限拒绝走允许的替代或原聊天独立询问，明确阻塞未处理时不能静默放弃。对照中叠加通用拒绝反馈反而出现私人文字代替投递，因此不采用该处理。本轮不改审批规则、拒绝路由、运行时空响应处理或生产 custom_prompt。

## 验证

真实模型固定拒绝对照：原 Prompt 0/3 继续处理，采纳的会话指令 8/8 发起原聊天独立询问；发送成功和无待办后台各 2/2 静默，可恢复技能错误 2/2 改用 read。后续询问也被拒绝的 2 次只有私人未送达记录，不能冒充交付完成。详见 [模型对照](evidence/model-comparison.md)。

定向 native runtime/approval/communication 回归 3 文件 8 测试通过。指令为模型行为改进，不新增镜像实现的字符串单测；保留现有原生审批、通信及静默测试，真实模型行为由隔离实验验证。pnpm build、pnpm typecheck、pnpm test（74 文件 / 255 测试）、pytest -m "not e2e"（56 通过 / 31 deselected）、docs-check、Ruff check/format 均通过。原生 configuration.preview 确认实际 session Prompt 包含实验指令，逐字匹配。独立 code review 覆盖 d07c7578f..099a59ebe，无存活 finding；见 [审查记录](code-review.md)。

validated_at=099a59ebed2a6efa27763b5f598ad971dcc48c33；executed_base=d07c7578f210ee7fe830e2e7de4407209e7c75fc；final sync 的 origin/main 未变，effective_base 同 executed_base。后续仅回填证据和归档，产品源码与已审查版本一致。未部署生产，也未解决审核器正常回执误拒绝。原始上下文和模型输出含私人信息，仅存本机临时证据，不提交仓库。
