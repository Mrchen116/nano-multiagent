# bugfix-724 实际设计

本文在快速开发实现后形成。原始报告与已确认范围见 [incident.md](incident.md)。

## 实现与约束

- 根 PA 系统提示按上下文确定发言主体。它用 `send_message` 继续自己参与的对话，用 `send_user_message` 完成对特定受众的真实委托。通用 UI 指引让具体任务规则和用户要求先于普通文本偏好。
- 已知目标、仅起草且交互能力和 Skill 可用时，PA 加载 `nano-interactive-ui`，用 `send_message` 在与用户的 Nano IM 私聊交付带 `TextArea` 和 `ComposeMessage` 按钮的草稿。按钮使用指定目标和当前编辑文本。
- 独立外发审核的 `planned_action` 用工具名表达发送主体，带上待发参数和完整受众。审核 Prompt 以当前动作参数确定发出去的内容，并把历史卡片和编辑状态用于理解用户原话。用户回答 PA 的澄清并要求转达时，审核器按实际受众和 PA 自己发言的范围核对授权。
- 发送入口、冻结证据、审核判定、提交时权限复核和持久回执继续使用现有链路。服务端仍用内部 `representation` 绑定身份。回滚可直接撤销本单元代码，历史记录可按原结构读取。

## 验证证据

- 最终复审明确区分卡片私聊与按钮目标，覆盖发布给模型的提示词。用户从共享群发起起草的场景采用组装回归和独立代码复审验证，未重新用真实模型重放。

- 空白 Nano IM 测试实例使用 GPT-6.1 Sol / High 作为 PA，独立审核使用测试模板配置。浏览器验证卡片编辑后只填写群输入框。同一句「你直接发到群里吧，内容用原稿」通过审核，送达消息 `2f4c5a45ffe54ba9af2c3a48b04a811c`。PA 在场的群中，原样重放「周四上午可以，你直接发给他吧」后，以 PA 身份送达 `16fc90dba6354429b85b0d5eb9429695`。首次拦截与复测分别记录在两个隔离实例。
- 移除审核输入中的内部身份字段后，另用真实模型经 Nano IM 复测起草、代发和 PA 自身发送。待审请求 `request-011.json` 和 `request-026.json` 的当前动作分别为 `send_user_message` 和 `send_message`，两条送达消息为 `ab295e6011064ff0a8c7d1a39c1cc7ad` 和 `9b2673a5736f48eb91072603cc1da611`。原始请求只留在隔离测试目录，归档只记定位。
- 用户先确认 Prompt 版本，要求复测，随后审阅 Prompt 文本、提出简化并授权提交 PR。上述浏览器和模型验证由 Agent 执行。

## 长青契约

本修复恢复既有的 [IM 起草和代发契约](../../../specs/im/personal-agent.md#requirement-pa-回复草稿复用-intelligentui) 与 [Gateway 发送身份及授权契约](../../../specs/gateway/personal-agent.md#requirement-pa-自身发送与代表用户发送使用明确工具边界)，无规范增量，无数据迁移。
