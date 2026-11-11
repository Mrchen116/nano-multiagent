# feat-762 · 群聊 Agent 识别执行节点与本地文件归属

## 原始需求

> 现在群聊中的agent，好像不能理解到不同agent可能处在不同的机器上。是不是现在没给提供agent的gateway信息，让agent能知道不同gateway就是不同机子，就不能相互看文件。raft也是多机的，他有这个设计吗

> 那很好，能模仿raft的做法。新建个unit开始做

## 已对齐的方向

用户同意参考 Raft。Agent 在工作时知道自己的执行节点，知道群聊同伴可能在其他电脑上，并能在需要协作时查询可见同伴的设备归属。Raft 的常驻提示说明多机环境并给出自身 Computer，查询可见同伴档案时可看到对方的 Computer 信息，文件通过会话附件显式交接。[Raft 系统提示](https://github.com/botiverse/raft-source/blob/db5e399f017d584e49597e3a28757645d6807893/packages/daemon/src/drivers/systemPrompt.ts#L61-L85) · [Raft 同伴档案](https://github.com/botiverse/raft-source/blob/db5e399f017d584e49597e3a28757645d6807893/packages/server/src/routes/internal.ts#L848-L870) · [Raft 文件交接](https://github.com/botiverse/raft-source/blob/db5e399f017d584e49597e3a28757645d6807893/manual/agent-knowledge/attachment.md#L53-L78)

源码已确认，Nano IM 根据 Agent 的节点归属投递消息，用户在 Agent 目录也可以辨认已知设备。普通群聊和 Global 群聊的模型侧成员信息缺少设备归属。现有执行环境说明覆盖 Agent 和用户端的区别。这次要补的是群聊 Agent 之间的执行位置与文件交接。用户所述具体一轮没有请求日志佐证。[节点投递](../../../apps/im-server/src/messaging.ts#L669) · [普通群聊上下文](../../../packages/personal-assistant/src/single-thread.ts#L173) · [Global 群聊成员](../../../apps/im-server/src/work.ts#L194) · [设备归属](../../specs/im/agents-nodes.md#requirement-agents-列表可辨认归属设备状态由头像角标表达) · [执行环境说明](../../specs/gateway/routing-delivery.md#requirement-agent-获得执行环境与用户界面的背景)

## 用户场景

用户在同一个 Nano IM 群里请 A 生成报告、请 B 复核。A 发来的本地路径只定位 A 执行环境里的文件。B 可以先查 A 的设备归属，遇到异地或未知时，请 A 发受保护的聊天附件或已有的可访问链接。B 获得有权读取的副本后再复核。若两者在同一执行节点，B 仍根据实际文件权限和读取结果判断能否复核。设备归属无从确认时，B 可以直接说明未知，继续请求可读的文件副本。

## 验收标准

### Requirement: 群聊 Agent 知道自身执行节点并可按需辨认同伴归属

#### Scenario: 查询群成员的执行位置

- **GIVEN** Nano IM 群内有同节点和不同节点的 Agent
- **WHEN** 用户问其中一个 Agent 自己和其他群成员分别在哪里运行
- **THEN** Agent 可以根据平台提供的身份回答自己所在的节点，并查询可见同伴的归属，正确区分同节点与不同节点。

#### Scenario: 节点归属未知或不可见

- **WHEN** 用户问及平台无法确认或当前 Agent 无权查看设备归属的同伴
- **THEN** Agent 表达归属无法确认，并遵循现有成员和设备信息的可见范围。

### Requirement: 群聊 Agent 根据文件所在环境协作

#### Scenario: 对方只发了本地路径

- **GIVEN** A 在群里发出其本地报告的路径，B 与 A 位于不同节点或无法确认同一执行环境
- **WHEN** 用户请 B 复核该报告
- **THEN** B 把该路径当作 A 环境中的位置，请对方提供有权读取的附件或链接，并在获得文件后基于其内容复核。

#### Scenario: 同节点的文件访问

- **GIVEN** A 和 B 位于同一节点
- **WHEN** 用户请 B 复核 A 给出的本地路径
- **THEN** B 以实际访问权限和读取结果判断能否复核，无法读取时请对方提供可访问的副本。

## 范围与非目标

- 范围覆盖 Nano IM 群聊中普通与 Global Agent 的自身执行环境说明、同伴归属查询，以及使用已有交付能力交换可读副本。
- 文件访问继续由本机权限和现有聊天资源权限决定。本期范围止于识别归属和使用已有交付路径，远程文件系统、通用本地文件上传、飞书同伴设备发现和用户界面改版均留在范围之外。
