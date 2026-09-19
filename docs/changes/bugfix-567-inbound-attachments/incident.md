# bugfix-567: 入站附件类型、失败范围与群上下文消费

## Relations

- Closes: https://github.com/Mrchen116/nano-multiagent/issues/298
- Related: feat-554

## 原始报告

用户原话：

> https://github.com/Mrchen116/nano-multiagent/issues/298 这个问题还存在不
> 更 general 地看，它是不是涉及一大类问题？
> 好，我们把这些问题一个unit一并修复

Issue #298 报告普通 TXT 被当作图片，图片损坏错误阻断同条文字；群中未消费的 TXT 也影响后续请求。上传、下载、历史与 fork 的文件字节正常。

## 范围对齐

用户明确确认图片失败策略：“保留当前图片失败提示，隔离群历史失败（推荐）”。

Agent 解读：一个 Full bugfix 覆盖普通文件类型分流、混合消息保真、失败范围、群缓冲消费和模式间基本类型语义一致性。普通文件只保证描述与来源进入上下文并明确未读取，不承诺自动解析文件内容。保留既有图片校验和成员访问保护；不改变上传、存储、下载、历史、fork、内核多模态协议或新增文件解析工具。

沿用现有当前消息图片失败契约。历史缓冲图片失败作为未读取事实进入上下文，不阻断新请求；不是把失败图片标记成已读取。用户可提供文件文本或重发图片。

## 现象与复现

基线：远端 main `09cd75bd53ad56c1f81b66743b43009607cdd0f2`，2026-09-19。

Web IM single_thread Agent 收到文字加 `text/plain` 附件。以真实 ImageAttachmentResolver 下载器 seam 返回 TXT 字节，结果 `ImageResolution(parts=(), failure='corrupt')`；SessionRunCoordinator 消息投影为 `model_parts=[]`，失败为 `corrupt`。这是代码级复现，非生产重放。

## 影响范围与 RCA

1. WebRelay 保留全部有 URL 的附件。SessionRunCoordinator 将所有附件传入只识别图片的 resolver；MIME 读取后不用于区分普通文件。TXT 已复现，其他非图片格式具有相同路径风险。
2. resolver 和消息投影采用整体失败语义，一项错误丢弃同条文字及其他有效输入。真正异常图片的本轮停止有现行契约依据，但不应套用到普通文件或扩散到后来新请求。
3. 群上下文通过 `drain_with_metadata` 在解析/内核接收前删除。后续解析或提交失败时待处理上下文已经移除。IM 历史不受此删除影响。
4. GlobalRunCoordinator 已按 MIME 分流并保留普通附件描述；single_thread 缺少同等类型区分。需共享类型判断，保留两种模式各自会话/Inbox 消费机制。

证据：`web_relay_adapter.py` 附件映射；`image_attachments.py` 的 resolve；`session_run_coordinator.py` 的 _build_message_parts、dispatch、_run_one；`group_context_store.py` 的 drain_with_metadata；`global_run_coordinator.py` 的 _content。当前约束见 `docs/specs/gateway/relay-protocol.md` 与 `global-agent.md`。

## 修复方向与验收

### Requirement: 按附件类型保留有效输入

#### Scenario: 普通文件伴随文字
- **WHEN** 用户发送 TXT、CSV、PDF、Office 或压缩包等普通文件及文字要求
- **THEN** Agent 可执行文字要求，不报告图片损坏；上下文保留文件名称、类型和来源并标明内容未读取
- **AND** 不因修复获得超出原有成员权限的文件读取能力

#### Scenario: 混合有效图片与普通文件
- **WHEN** 同条消息包含文字、有效图片和普通文件
- **THEN** 文字和有效图片均进入模型，普通文件保留描述，不被误认成图片
- **AND** single_thread 与 global 模式均满足该基本语义

### Requirement: 失败不扩散到无关的新请求

#### Scenario: 当前消息的异常图片
- **WHEN** 当前消息包含损坏、超大或无法获取的图片
- **THEN** 本轮明确提示图片未送达及重试办法，不生成假装看过图片的回答
- **AND** 已有群缓冲仍可在后续正常请求中处理

#### Scenario: 历史缓冲附件失败
- **GIVEN** 群历史缓冲含普通文件或无法读取的图片
- **WHEN** 新请求触发 Agent
- **THEN** 普通文件不会阻断新请求；失败历史图片标明未读取，历史文字及有效图片与新请求保留

### Requirement: 未被接受的群上下文不丢失

#### Scenario: 解析或接收失败后重试
- **WHEN** 输入准备或内核接收失败，尚未接受本次上下文
- **THEN** 缓冲仍可用于下一次正常请求；已接受内容不会在随后正常请求重复出现

#### Scenario: 处理中新增群消息
- **WHEN** 处理一批缓冲期间又收到其他群消息
- **THEN** 只消费本次已接受的内容，后来消息保留给后续请求
