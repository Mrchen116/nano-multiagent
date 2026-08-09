# IM web-chat-ux Specification (delta for bugfix-518)

## MODIFIED Requirements

### Requirement: 历史会话蒸馏 conversation 选择入口

用户可从 IM 左侧 conversation 列表选择已完成、属于同一 Gateway 的会话生成 skill。IM 只按 source Agent
与其 `source_node_id` 做 owner、idle 和同节点选择；不扫描/读取 Gateway JSONL。用户确认 execution Agent 与
scope 后，IM 保留既有 distiller/`skill_view` preflight，并向该 Gateway 请求当前格式的 distill prompt。成功才新建
固定到该 node 的 execution Agent 单聊并原样预填 prompt；后续普通 relay 优先该固定 node，不因 Agent profile
重新注册而改送其他 Gateway。用户随后按既有普通聊天发送；builtin skill 继续从 prompt fields 读取该 Gateway
本机的 JSONL paths。

#### Scenario: 选择第一个来源后锁定同一 Gateway
- **WHEN** 用户在 conversation 列表进入“生成 skill”多选模式并选择一个 idle、带 source Agent 的会话
- **THEN** IM 用该会话的 `source_node_id` 锁定本次选择
- **AND** running、无 source Agent 或其他 Gateway 的会话不可选，并显示现有可理解原因

#### Scenario: Gateway 返回当前格式 prompt 后预填普通聊天
- **GIVEN** 用户选择同 Gateway sources、execution Agent 与 target scope
- **WHEN** IM 通过该 Gateway 成功取得 distill prompt
- **THEN** IM 创建 execution Agent 的 direct conversation，并原样预填包含
  `/skill:conversation-skill-distiller`、`source_jsonl_paths`、`execution_agent_id` 与 `target_scope` 的 prompt
- **AND** 用户可按既有方式补充意图并作为普通聊天消息发送；服务端固定路由优先于任何 client node hint，消息仍到生成该 prompt 的同一 Gateway

#### Scenario: execution Agent 不具备 distiller 或 skill_view 时不创建空聊天
- **WHEN** execution Agent 缺少 `conversation-skill-distiller` 或 `skill_view`
- **THEN** dialog 显示不可执行原因，且不请求/不接受 prompt
- **AND** 不创建或导航到新的 execution conversation

#### Scenario: 取得 prompt 失败时不创建空聊天
- **WHEN** target Gateway 离线，或不能为任一 source 解析本机 path
- **THEN** IM 在 dialog 显示可理解失败原因
- **AND** 不创建或导航到新的 execution conversation，也不发送普通 relay

#### Scenario: 普通 sidebar 浏览不显示蒸馏选择状态
- **WHEN** 用户未进入“生成 skill”选择模式
- **THEN** conversation 列表保持既有普通浏览外观
- **AND** 不显示 running、different Gateway 或 checkbox 等只服务于蒸馏选择的标签
