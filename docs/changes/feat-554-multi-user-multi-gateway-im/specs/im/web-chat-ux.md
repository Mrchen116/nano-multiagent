# feat-554 — im/web-chat-ux

> 目标: docs/specs/im/web-chat-ux.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## MODIFIED Requirements

### Requirement: 历史会话蒸馏 conversation 选择入口

用户可从 IM 左侧 conversation 列表选择本人参与、已完成且来源明确的 single_thread 会话生成 skill。来源和执行 Agent 保留原 owner 管理归属，均为 single_thread，按 source Agent 与其 `source_node_id` 做 idle 和同节点选择；不扫描或读取 Gateway JSONL。用户确认 execution Agent 与
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
- **THEN** dialog 显示不可执行原因，且不请求或不接受 prompt
- **AND** 不创建或导航到新的 execution conversation

#### Scenario: 取得 prompt 失败时不创建空聊天
- **WHEN** target Gateway 离线，或不能为任一 source 解析本机 path
- **THEN** IM 在 dialog 显示可理解失败原因
- **AND** 不创建或导航到新的 execution conversation，也不发送普通 relay

#### Scenario: 普通 sidebar 浏览不显示蒸馏选择状态
- **WHEN** 用户未进入“生成 skill”选择模式
- **THEN** conversation 列表保持既有普通浏览外观
- **AND** 不显示 running、different Gateway 或 checkbox 等只服务于蒸馏选择的标签

#### Scenario: Skill 写入范围与 Agent 工作模式分开
- **GIVEN** 用户选择同 Gateway 的 single_thread 来源与执行 Agent
- **WHEN** 选择 agent 或 global Skill 写入范围
- **THEN** 两个既有范围均保留；global 指该 Gateway 的全局 Skill 目录，不使全局 Agent 聊天成为本次支持的蒸馏来源或执行者。

#### Scenario: 可见聊天不自动取得 Skill 管理资格
- **GIVEN** 用户是聊天成员，但不管理其 source Agent 或 execution Agent
- **WHEN** 尝试以这些 Agent 发起本机 transcript 蒸馏
- **THEN** 不接受该组合，不创建执行聊天；正常聊天、成员 slash 候选与公开 Work 仍按各自规则使用。


### Requirement: Web IM slash 面板发现并填写会话控制命令

用户在聊天输入框开头输入 `/` 时，slash 面板将 `/stop`、`/new`、`/compact`、Gateway 报告的当前 Agent 动态命令与可用 skill 一起显示并按前缀过滤；用户可通过键盘或指针选择命令，输入框收到可直接发送的文本命令。在群聊中，`/new` 明确说明它会为群内所有 Agent 开始新会话。有效模型声明 selectable reasoning 时，Gateway 报告 `/effort` 与完整 levels；前端不硬编码或在 Workflow 关闭时过滤普通档位。只有 Workflow 已启用且模型支持 `xhigh` 时，同一命令说明额外列出 `ultracode`。

#### Scenario: 单聊中从 slash 面板选择新会话
- **WHEN** 用户在单聊 composer 开头输入 `/` 或 `/new` 的未完成前缀
- **THEN** 面板显示 `/new` 及“在当前聊天中开始新会话”的说明
- **AND** 用户选择后，composer 填入可发送的 `/new`

#### Scenario: 群聊中从 slash 面板选择全体新会话
- **GIVEN** 当前群聊有多个 Agent 参与
- **WHEN** 用户在 composer 开头输入 `/`
- **THEN** 面板显示 `/new` 并说明它会为群内所有 Agent 开始新会话
- **AND** 用户选择后，composer 填入可发送的 `/new`

#### Scenario: 群聊中选择模型专属的推理档位
- **GIVEN** 群聊中的多个 Agent 报告不同有效模型或不同 `/effort` levels
- **WHEN** 用户在 composer 打开 `/effort` 候选
- **THEN** 每个候选显示其来源 Agent 和该 Agent 的完整 levels，不合并成公共集合
- **AND** 用户选择其中一项后，composer 填入指向该 Agent 的 `@Agent /effort `，使任意 group reply policy 下也只更新该 Agent 的 session

#### Scenario: 跨管理归属的聊天成员取得命令候选
- **GIVEN** 当前真人是包含他人 Agent 的聊天成员
- **WHEN** 打开该聊天的 slash 面板
- **THEN** 获得各成员 Agent 的已启用 Skill 名称／说明和运行命令，包含各自完整命令描述；不以读取完整 Agent 配置为前提，不返回本机路径或其他管理字段。
- **AND** 一个 Agent 离线或查询失败不使其他 Agent 候选消失；被移出聊天或切换账号后原候选缓存不可继续使用。

#### Scenario: 同名不同来源 Skill 在成员候选中保留
- **GIVEN** 多个聊天 Agent 暴露同名但实际位置或节点不同的 Skill
- **WHEN** 用户打开 slash 候选
- **THEN** 不同来源保留独立行与各自说明，同节点同位置的候选合并来源 Agent；用于区分的 opaque key 不暴露本机路径。


## ADDED Requirements

### Requirement: 协作入口沿用现有 IM 导航和语言设置

#### Scenario: 桌面和移动端寻找协作者
- **WHEN** 用户从新聊天、建群或成员入口查找人和 Agent
- **THEN** 沿用现有导航、搜索与弹层，能选择合法对象并开始沟通；原有聊天、消息操作与附件能力继续可用。

#### Scenario: 新增协作界面跟随中英文切换
- **GIVEN** 用户正在编辑未发送内容
- **WHEN** 从桌面头像菜单或手机“我的”切换中英文，随后刷新
- **THEN** 界面文案及反馈使用所选语言，刷新后保留语言选择；切换当下不清空未发送内容，聊天正文、名字和原始 Work 内容不被翻译。
