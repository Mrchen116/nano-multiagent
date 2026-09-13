# feat-554 — gateway/routing-delivery

> 目标: docs/specs/gateway/routing-delivery.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## MODIFIED Requirements

### Requirement: 当前会话的 Agent 图片回复具有统一交付语义

Gateway MUST 将普通 assistant 回复中的可交付图片与文字按原顺序交付到当前聊天；全局 Agent 向已有聊天显式调用 `send_message` 时沿用相同图片交付。支持本地 PNG/JPEG/WebP 产物和既有可获取网络图片。图片引用不授予额外文件读取权限。每气泡最多五个不同来源、单图最多 10 MiB；同来源重复引用不重复准备资源。

#### Scenario: 本地产物跨机器查看
- **WHEN** 用户请求 Agent 展示其通过工具准备的本地图片
- **THEN** 原聊天可以直接查看图片和说明，无需用户访问运行机器。

#### Scenario: 图片语法不绕过权限
- **WHEN** 回复引用无权读取或未准备为可交付产物的文件
- **THEN** 图片不发送，对应位置出现可读失败说明。

#### Scenario: 图文投递保持入口路由
- **WHEN** 飞书触发的 run 产生中间或最终图文回复
- **THEN** 原飞书聊天和内部影子会话收到等价内容，普通富文本和运行信息卡片均可显示图片
- **WHEN** 内部 IM 影子会话触发同类回复
- **THEN** 只在内部 IM 显示，不回写飞书。

#### Scenario: IM 离线不阻塞飞书图片
- **GIVEN** 飞书可用、IM 暂不可用
- **WHEN** Agent 产生图片回复，随后 IM 恢复
- **THEN** 飞书先收到图文，IM 后续补齐相同图片的历史且不重复创建气泡。

#### Scenario: 局部图片失败
- **WHEN** 图片不可读、格式不支持、超限或上传失败
- **THEN** 对应位置显示失败原因，正文和其余可用图片仍可阅读。

#### Scenario: 普通文本和示例保持原语义
- **WHEN** Agent 回复纯文字或代码中的 Markdown 图片示例
- **THEN** 保持原有文字，示例不触发文件读取或图片发送。

#### Scenario: 全局 Agent 向已有聊天显式发送图片
- **GIVEN** 全局 Agent 已有可投递的 IM 聊天目标
- **WHEN** Agent 通过 `send_message` 发送其准备的本地图片及说明
- **THEN** 聊天成员直接看到保护后的图片，刷新后仍可回看；持同一 URL 的非成员不能读取
- **AND** 同次投递重试复用原快照与上传回执，群消息提交前的复核不会提前上传未获提交的图片。

### Requirement: 入站消息按四步决策路由并回发原通道原目标

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](../../../../../specs/gateway/global-agent.md) 为准。 Agent 身份解析与未知 Agent 拒绝适用于两种模式；global 的入站持久接受后交 Inbox，不预建等待主模型回复的聊天消息。

任一通道（外部 IM 或内置 Web IM）收到一条入站消息时，Gateway 依次决策：路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标，不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待主模型返回和自动整理上下文三类“活着但安静”的窗口都有周期性 liveness 心跳，看门狗不再以“无业务输出事件”判卡死；等待用户权限决策的窗口则完全豁免于 idle 看门狗超时。只有该轮收到 `permission_resolved` 或判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway,且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent(显式 `agent_id` → channel/chat 绑定 → 节点默认 Agent),交内核执行, 最终 Agent 回复经原通道的出站路由回发到发起会话

#### Scenario: 同会话串行、跨会话并行
- **GIVEN** 同一会话已有一轮在执行,另有一条属于不同会话的消息同时到达
- **WHEN** 两条消息先后进入 Gateway
- **THEN** 同一会话的消息排进串行 FIFO 队列、前一轮结束后才消费下一条;不同会话的消息并行推进,互不阻塞

#### Scenario: 失去 liveness 后释放同会话队列
- **GIVEN** 同一会话的前一轮已开始运行,但在判定窗口(120 秒)内既无业务事件也无任何 liveness 心跳,后一条消息正在 FIFO 中等待
- **WHEN** Gateway 判定前一轮失去进展
- **THEN** Gateway 取消前一轮并上报失败,随后消费后一条消息,不得让该会话永久阻塞

#### Scenario: 执行静默长命令期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在执行一个耗时远超判定窗口、其间无标准输出的命令
- **WHEN** 命令持续在执行(有周期性 liveness 心跳)
- **THEN** 该轮不被看门狗取消,命令跑完结果正常返回

#### Scenario: 等待 LLM 返回期间不被 idle 看门狗误杀
- **GIVEN** 某轮长时间等待 LLM 返回但连接活着(有周期性 liveness 心跳)
- **WHEN** 等待时长超过判定窗口
- **THEN** 该轮不被看门狗误判卡死

#### Scenario: 自动整理上下文期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在自动整理过长上下文且摘要仍正常推进（有周期性 liveness 心跳）
- **WHEN** 等待时长超过判定窗口
- **THEN** Gateway 不把该轮误判为 idle 超时
- **AND** 该轮后续普通消息连同已有上下文照常进入对话并得到正常回复

#### Scenario: 等人工权限决策期间不被 idle 看门狗误杀
- **GIVEN** 某轮已发起一个需要授权的工具,正等待用户在权限卡片上决策
- **WHEN** 等待时长超过判定窗口(即使用户离开、关闭 IM 页面、其间没有 liveness 心跳到达)
- **THEN** 该轮不被 idle 看门狗取消;用户随后批准则工具正常执行、该轮继续推进,不报「relay idle for 120s」
- **AND** 一旦用户做出决策、内核发出 `permission_resolved`,正常 idle 看门狗立即恢复,决策后的卡死/断连仍会被捕获

#### Scenario: 路由到未知 Agent 被拒
- **WHEN** 入站消息显式指定一个 Gateway 未注册的 `agent_id`
- **THEN** Gateway 拒绝该路由(抛 `LookupError`),不创建会话也不执行

#### Scenario: 同群跨账号输入保持真实身份
- **GIVEN** 不同账号与该 Gateway 的 Agent 共同参与一个 IM 群
- **WHEN** 群内不同的人按既有规则向该 Agent 发消息或插话
- **THEN** 消息保留实际发送者，按同一聊天和 Agent 执行上下文处理，回复回到该群；不会因发送者不是 Gateway 管理者而另建会话或忽略输入。
