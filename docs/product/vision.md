# Product Vision

## 产品定位

nano-multiagent 是一套让用户在自己的机器上运行、配置和协作多个 Agent 的系统，同时复用同一个产品中立的 Agent 内核支撑个人助手与本地 Coding CLI。

它面向希望长期拥有一组可持续工作的 Agent 的用户：Agent 有稳定身份、独立工作区和长期上下文，既能与用户直接协作，也能在会话中相互协作，并通过周期任务主动推进工作。

## 长期产品原则

### 一个内核支撑多种产品

Agent 执行、工具、skills、会话和持久化能力由同一内核提供；个人助手、Coding CLI 和未来产品通过公开 SDK 装配各自的工具、提示词、权限和交互方式。新的产品形态不复制一套专用 runtime。

### 长期 Agent 与临时执行单元分开

配置级 Agent 是用户可以识别、配置和持续对话的长期主体，拥有自己的工作区与长期上下文。subagent 是某次任务内部按需创建的临时执行单元，不冒充新的长期团队成员。

### 对话是人与 Agent 团队的共同协作界面

用户可以直接与 Agent 对话，也可以通过群聊和 Agent 间会话观察或组织协作。会话身份和历史应保持连续，让协作关系能够跨消息、重启和入口延续。

### 本地执行，中心协调

Agent 与内核运行在用户节点上；中心 IM 负责账号、会话、配置、节点状态和 Web IM 中继，不直接执行 Agent。节点主动连接中心，中心暂时不可达时，本地可运行路径和已经接入的外部通道尽可能保持自治。

### Web IM 是默认入口，外部通道是扩展

用户无需先接入第三方 IM 即可通过内置 Web IM 使用系统。飞书等外部通道扩展触达范围，但不成为建立 Agent 团队的前置条件；跨入口产生的会话需要保持可理解的身份和上下文关系。

### 用户拥有自己的节点、Agent 与数据边界

账号归属决定用户能够看到和管理的节点、Agent、会话与配置。多用户场景保持租户隔离；涉及本地工作区、凭据和执行权限的能力由对应节点与安全边界共同约束。

### Agent 可以主动工作，但行动必须可见、可控

heartbeat、cron 和后台任务让长期 Agent 从被动问答扩展到主动推进。用户需要看到运行状态、结果和失败，并能通过权限审批、中断、配置和历史记录理解及控制这些行动。

## 如何落到当前系统

本文定义产品方向和长期取舍，不定义具体 API、页面字段或状态机：

- 四个包的职责和依赖方向：[`../../SPEC.md`](../../SPEC.md)
- Kernel current behavior：[`../specs/kernel/`](../specs/kernel/spec.md)
- IM 与 Web IM current behavior：[`../specs/im/`](../specs/im/spec.md)
- Gateway、主动任务和外部通道 current behavior：[`../specs/gateway/`](../specs/gateway/spec.md)
- Coding CLI current behavior：[`../specs/cli/spec.md`](../specs/cli/spec.md)

本文从早期 [`需求.md`](../archive/product-source-materials/需求.md) 蒸馏，并以当前架构、specs 和代码重新核对。旧稿中尚未实现、已经改变或属于具体方案的内容不进入本页。
