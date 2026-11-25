# feat-786: 通用文件附件上传与跨节点 Agent 下载

## Relations

- Depends on: `feat-780-chat-topics`, `feat-762-agent-node-awareness`
- Related: `feat-721-agent-attachments`

## 原始需求

> https://github.com/Mrchen116/nano-multiagent/pull/546 这个pr希望做的更新合过来本分支，你看看他解决问题的做法和raft的对比，raft有没有更好的做法
>
> （引用：Raft 明显更好。PR #546 解决的是“别静默读错文件（防事故）”；Raft 解决的是“跨机 Agent 怎么一步把任意文件交到对方手里（提效率）”。）—— 我认同
>
> 完全理解了。按照短期这个做。通用文件附件应该有限制吧？不可能什么格式什么大小都可以吧？看看raft的做法，参考就行。
>
> 都按照你的建议来。我看我基本同意

## 澄清记录

- Q1: 格式限制与单文件上限采用哪套方案？（参考 Raft 上传放开通用文件 + 下载强隔离头，单文件 25 MiB；还是固定白名单 / 其他上限？）
  A: 都按照你的建议来（上传放开通用文件、未知格式归一化为 `application/octet-stream`，图片继续校验魔数，下载侧非安全位图强制 `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff` + `Content-Security-Policy: default-src 'none'; sandbox`；单文件上限 `25 MiB`、静态图仍 `≤ 10 MiB` 且 `≤ 4096×4096`、拒绝 0 字节、单条消息合计最多 5 个附件；沿用单用户 `1 GiB` / 全服务 `10 GiB` 配额与每分钟 30 次、并发 2 路限流）。
- Q2: 分支与交付安排？（单独基于 `codex/feat-780` 开新分支/新 unit，还是直接叠进 `codex/feat-780`？）
  A: 都按照你的建议来（基于 `codex/feat-780` 独立建 `feat-786` unit 与分支，不继续膨胀 PR #541）。

## 用户场景

1. **跨机器 Agent 一步交接任意文件**：运行在 MacBook Air 的 Agent 生成了一份 `.csv` 数据表、`.md` 设计稿、`.pdf` 报告或 `.zip` 日志包，在原群聊（或群话题）中直接随消息作为受保护附件发出，无需先发本地路径等 Mac mini 上的同伴开口索取。
2. **跨机器 Agent 直接下载并处理收到的文件**：Mac mini 上的 Global、PA 或 SingleThread Agent 看到有权限访问的群聊、私聊或历史消息里的文件/图片附件（无论来自人类还是另一台机器的 Agent），能直接按消息中的短附件标识将受保护附件下载到本机工作区下载目录，随后用本地读取或脚本工具检查和处理，不再因“非图片附件”报错或只能看到文件名却拿不到内容。（PA 参与群里非主人发来附件的现有输入安全审查 fail-closed 边界保持不变；PA 可在主人私聊、观察会话及历史读取路径中下载可见附件。）
3. **安全隔离与合理限额**：人类和 Agent 都可以上传常见开发/办公/归档文件（如 `.csv`、`.yaml`、`.log`、`.zip`、`.py`、`.docx`、`.svg`、`.html` 等）最大至 `25 MiB`，不会因为窄白名单被拒；但 `.html`、`.svg` 等潜在可执行文件在浏览器下载或访问时只能作为附件安全下载，绝不在主站域直接渲染执行。超限文件、空文件、伪装图片或超配额上传给出明确失败反馈。
4. **PA 外发披露边界不退化**：PA 向主人自己的私聊可以直接交付任意允许范围内的文件；向其他群聊外发时，可审阅的 UTF-8 文本类文件（如 `.txt`、`.md`、`.json`、`.csv`、`.yaml`、`.xml` 在安全审阅体积内）进入外发披露审阅，无法审阅内容的二进制/压缩包/PDF 仍按现有外发安全门禁拒绝外发，不绕过披露审查。

## 验收标准

### Requirement: IM 托管通用文件附件支持跨格式安全上传与下载

#### Scenario: 上传并下载常见非图片通用文件
- **GIVEN** 登录用户或授权 Agent 对某原生 IM 会话具有写权限
- **WHEN** 上传 `.csv`、`.yaml`、`.zip`、`.log` 或未知扩展名的非空文件（大小 `≤ 25 MiB`）并随消息发送
- **THEN** 上传与消息发送成功，有该会话读取资格的成员可以下载到逐字节一致的原文件
- **AND** 无该会话读取资格的用户或 Agent 持同一附件链接无法读取。

#### Scenario: 潜在可执行文件强制隔离下载
- **WHEN** 会话成员请求下载 `.html`、`.svg` 或任意非位图附件
- **THEN** 服务端以附件下载方式返回字节，并携带防止浏览器嗅探与脚本执行的响应头，不在主站域直接渲染执行
- **AND** Web 客户端将其展示为文件下载入口而非内联图片，不影响 PNG/JPEG/GIF/WebP 位图的正常预览。

#### Scenario: 空文件、超限文件与伪造图片被拒绝
- **WHEN** 上传 0 字节文件、超过 `25 MiB` 的通用文件、超过 `10 MiB` 的图片，或声称是 PNG/JPEG/GIF/WebP 但字节头不匹配的文件
- **THEN** 服务端明确拒绝并释放预占配额，不产生残留文件或损坏消息。

### Requirement: Agent 可在原生 IM 中直接发送本地文件附件

#### Scenario: Agent 随消息附带本地文件交付到群或话题
- **GIVEN** Global、PA（主人私聊或允许外发的文本类文件）或 SingleThread Agent 拥有本机可读文件且对目标原生 IM 会话或话题有写权限
- **WHEN** Agent 调用消息发送工具附带本地文件路径（`≤ 25 MiB`，与已有附件/图片合计 `≤ 5` 个）
- **THEN** 文件作为目标会话受保护附件随该条消息发出，人类与同群其他节点 Agent 均可获取；公开正文不暴露本机绝对路径
- **AND** 同一发送在不确定回执下重试时按原幂等身份恢复，不重复发两条消息。

#### Scenario: 超过数量/大小上限、路径非法或权限不满足时明确失败
- **WHEN** Agent 传入相对路径、不存在文件、超限文件、单条消息总附件数超过 5 个，或非自发/非原生 IM 目标
- **THEN** 发送在发布前被明确拒绝并返回可操作错误说明，不发出残缺消息。

#### Scenario: PA 向非主人群外发不可审阅二进制文件被门禁拦截
- **GIVEN** PA 向非主人私聊的原生群发送消息
- **WHEN** 附带无法做内容披露审阅的二进制文件（如 `.zip`、`.pdf` 或超大文本）
- **THEN** 外发门禁拒绝交付并说明原因；向主人私聊发送同类文件或向群发送可审阅限额内的文本类文件（如 `.md`、`.csv`、`.json`）仍正常走对应流程。

### Requirement: Agent 可将收到的受保护附件下载到本机处理

#### Scenario: Global、PA 与 SingleThread Agent 下载并读取收到的文件或图片附件
- **GIVEN** 会话中存在人类或其他节点 Agent 发出的受保护原生 IM 文件或图片附件
- **WHEN** Global 或 SingleThread Agent 通过 `inbox`、`read_messages`、`search_messages` 或 SingleThread 入站消息，或 PA 通过主人私聊、观察会话或 `read_messages`/`search_messages` 看到该附件，并使用其短附件标识（`≤ 8` 字符）调用下载工具
- **THEN** 工具校验当前会话读取资格后将文件下载到该 Agent 工作区内的受控下载目录，返回本地路径、文件名、MIME 类型与字节数，Agent 可直接读取其内容
- **AND** SingleThread Agent 收到非图片附件时不再报错崩溃，而是看到清晰的文件提示与短附件标识；收到原生图片附件时亦保留内联看图并提供短附件标识供按需落盘处理。
- **AND** PA 参与群收到非主人发来的附件时，继续维持既有输入安全审查 fail-closed 边界，不因此降低防注入保护。

#### Scenario: 无权或未知附件标识被拒绝且下载不越出受控目录
- **WHEN** Agent 传入不属于自己的未知附件标识，或目标会话权限已被撤销
- **THEN** 下载被拒绝，本机不写入目标文件，也不会覆盖工作区下载目录之外的任意路径。

## 范围与非目标

- **在范围**：
  - IM Server 通用附件上传放开（参考 Raft：未知类型归一化为 `application/octet-stream`，单文件 `25 MiB`，静态位图保持 `10 MiB` + 魔数校验）、下载侧安全响应头（`X-Content-Type-Options: nosniff`、`Content-Security-Policy: default-src 'none'; sandbox`、非位图 `Content-Disposition: attachment`）、Gateway 幂等文件上传/查询路由、PA 文本类附件外发审阅支持。
  - Node 侧受保护通用文件上传与受控目录下载实现。
  - Personal Assistant / ToolReferences 的 `≤ 8` 字符短附件标识（`a_xxxxxx`）投影、SingleThread 非图附件入站兼容、`send_message(local_files)` 投递与幂等回执、`download_attachment` 调用路由。
  - DSH Integration 工具注册、审批边界对齐与跨节点文件交接提示词更新。
  - Web 前端位图判断收口（仅安全位图内联预览，SVG 等走文件芯片）与 `25 MB` 大小提示同步。
- **非目标**：
  - 不实现 Raft 风格的版本化多文件 Artifact、独立泛域名 Content Worker、iframe 划词批注或在线 HTML 沙箱渲染。
  - 不修改外部通道（飞书等）的非图片文件双向适配。
  - 不修改原生 iOS 客户端代码（本轮仅后端、Node、PA、DSH 与 Web 最小安全同步）。
