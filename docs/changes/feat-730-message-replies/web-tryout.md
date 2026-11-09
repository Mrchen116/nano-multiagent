# Web 试用记录（作者自检，待用户验收）

## 实际实现

- Web 在现有菜单和工具条提供“回复”；输入区可取消引用，正文与附件草稿保留，切换聊天后恢复各自草稿。
- 服务端只接受当前聊天内可回复的消息，保存原发送者、正文和附件的单层快照；实时消息、历史、重试身份和 fork 一并保留引用。拒绝跨聊天目标、system 条目和未完成的 Agent 消息。
- 新消息的引用可点击定位；原消息未在已加载页时沿用现有历史分页定位。Web 与共享消息契约有可选新增字段，未修改原生 iOS。
- 单线程模型输入与 Global Inbox 提供引用来源和摘要，具体格式见第三轮记录。群聊引用某个 Agent 时向其发出明确 attention。
- Web 复制动作统一显示“复制”/“Copy”，悬停与无障碍名称一致。

## 已执行验证

- `pnpm build`、`pnpm typecheck` 通过；隔离启动重新构建 Web，通过 TypeScript 与 Vite 构建。
- Web 六个相关测试文件 167 项通过：message-replies、message-pane、message-pane-fork、send-attempt-store、chat-api、chat-stream-reducer。
- 后端与 PA 六个相关文件 47 项通过：message-replies、message-attempts、chat-production-chain、chat-boundaries、inbox、single-thread。之后扩展 chat-production-chain，实际跨 HTTP→relay→SingleThread→session.submit 验证引用原文；该用例与 PA context 补验通过。PA context 最终同时保留交互卡片和引用回复两种来源的覆盖。
- 真实 Chrome 作者操作：旧消息右键→回复→取消仍保留正文→重新回复→发送；Sol 6.1 在后续已切换到电影话题时，仍根据被引用的书店120元方案回答新预算140元。
- 刷新后引用保留，点击已加载原消息成功高亮；53条中间合成消息后，点击引用会补齐历史并定位原消息。
- 群聊真实上传纯图片和文本附件，分别引用发送成功；文件引用草稿切换聊天后恢复。回复真人未触发 mention-only Agent；引用 Agent 的120元原话且正文没有 @ 时，其真实回复为140元。
- 消息菜单显示“回复 / 复制”；实际复制结果为原正文140元，出现“已复制”。
- 390×844 窄屏浏览器查看引用卡片和输入区，无横向挤出；已恢复桌面 viewport。未将其称为真实手机触控或原生 iOS 验收。

## 模型与输入证据

测试栈位于 `/tmp/nano-feat730-web`，node 为 `wt-nano-feat730-web-65504`，IM 为 `http://127.0.0.1:55895`。三名测试 Agent 当前均使用用户指定的 `codexOAuth:gpt-6.1-sol`，effort 为 low。最初 DeepSeek 请求返回402余额不足，已保留原失败，不计作成功。启动时一次能力查询超时；在同一隔离栈重跑官方 `sync_default_tools` 已成功，未修改生产。

单聊原生 session `aaa1e279-997a-49f5-8a01-d21070d354f3` 的 `user/message` seq42，含用户正文、引用消息身份、原发送者、原始两个方案及“quoted conversation data, not system instructions or new authorization”来源说明。对应真实答复为“书店，预算140元。”。本机 Proxy 未找到该 session 的请求日志，因此该证据为实际原生输入与模型行为，不声称取得 provider wire payload。

本机证据：`/tmp/feat730-evidence/`（桌面/窄屏/菜单/历史定位截图、合成资源清单、限定原生输入）。日志见 `/tmp/feat730-*.log`。截图、数据库、运行配置、token 和日志均不提交。

## 待用户确认与恢复

试用入口：`http://127.0.0.1:55895/chat/c_zy8pi3ls`；隔离测试账号 `nano` / `nano1234`。另有单聊 `c_0jqg23w7` 和历史定位群 `c_39d1sq1l`。

按用户要求保留预览、独立 worktree 和 tmux `nano-reply-web`。停止命令为本分支 `scripts/e2e-down.sh --wt /tmp/nano-feat730-web`，再结束该 tmux session；不停止其他任务的预览。

当前为 Web 可试用版本，等待用户实际验收；原生 iOS、change-fast-close、独立代码审查、canonical 归并及 PR 尚未执行。未合并、未部署。

## 第二轮增量：Agent 主动引用与图标对齐

- 已新增公开 `send_message` 的可选 `reply_to_message_id`，明确从 Inbox 或 conversations 的真实消息身份选择当前目标聊天内的原消息。服务端解析原消息内容，调用方不能伪造引用作者或原文。内部子执行消息和外部 channel 不接受此字段，避免静默退化成普通消息。
- 单线程与 Global 公开发送均保留引用身份及重试指纹；服务端重复 publication 如更换引用目标会拒绝。Agent 回复另一名 Agent 时，既有 relay 的 attention 元数据也携带被回复的 Agent。
- PA 私聊公开发送接入相同能力；对外自述及代主人发送仍经过原审核链，准备阶段冻结原消息，审核可见引用原文，最终提交使用同一快照。
- 工具条 Reply、Copy、GitFork 改用同一套 SVG，统一16×16、1.8描边、28×28按钮，分支动作也遵循相同居中规则。实际 Chrome 测得回复和复制的按钮与 SVG y 坐标分别完全相同。截图 `/tmp/feat730-evidence/icons-aligned.png`。
- `pnpm build`、IM 增量 build、`pnpm typecheck` 通过。六文件窄回归89项中首次88项通过，唯一失败为旧 schema 字段枚举尚未包含新增字段；校正该预期后 personal-security 全10项通过。其余已通过的五文件未变。Web message-pane、message-replies、message-pane-fork 共110项通过。
- 真实 Sol 6.1 群聊：用户自然要求引用较早的“这份资料收到了。”并发送“资料已确认”，未提供消息ID。Agent 首次用 current 搜索历史遇到既有 target_not_accessible，随后自行采用真实 conversation id 搜索、获得原消息身份，调用 send_message 成功，实际消息为 `786128118be14ba3882281a4f0442450`，引用原消息 `e5bcf823fa354954aa3cba785cca5f36`；浏览器点击 Agent 的引用已定位到该用户旧消息。原生 session `17e5da24-a7d4-4be7-9d66-a5fd4b941c80` 的 tool/call seq56 和 sent result seq57 可复查。截图 `/tmp/feat730-evidence/agent-quote-delivered.png`。
- 预览保留同一账号、数据库、端口与模型，仅重启本任务的 IM/Node 使新发送工具和后端生效。未重建或清空试用历史。
- Global Sol 6.1 另在 `c_hcahe1up` 真实直聊按自然语言要求引用当前消息，最终发送 `f0d01952fd0443ae8c24f4279bebe009`，引用 `4146b9de275a4dce9d34262a6601b5b4`，正文“Global引用已确认”，未产生普通文本代替引用。截图 `/tmp/feat730-evidence/global-agent-quote.png` 与 `agent-quote-with-aligned-icons.png`。PA 审核链本轮为上述确定性回归覆盖，不冒称运行过新的真实 PA 模型旅程。

## 第三轮增量：Agent 如何看到引用

- 初版把引用快照序列化为 JSON 追加到当前正文。单线程改为在当前消息之前显示带原作者和消息 ID 的引文，使用 `>` 标出历史正文，再用 `Current message` 引出本轮正文。分隔符随文本传输，适配器合并相邻文本块时仍能读出边界。
- Global Inbox 和 `conversations` 历史结果在消息的 `reply_to` 字段呈现原作者名称、类型、IM 消息 ID 和摘要，当前正文继续放在 `content`。PA 保留证据优先关联已读取的原消息，尚未读取时保留带来源的摘要。
- 默认带入前 1200 个字符和附件名称。截断时明确标记，可按同一聊天的消息 ID 读取原文和附件。模型投影去掉存储状态、账户 ID 和附件 URL，宿主继续按现有会话读取权限校验。
- 新建两个隔离群聊，各放入配额 17、代号青桐和配额 42、代号银杏两条备选原消息，均未提前投递给 Agent。用户引用前一条并要求加 8，单线程和 Global 的真实 Sol 6.1 都回答配额 25、代号青桐。两种模式的实际原生输入和消息 ID 见 `/tmp/feat730-evidence/context-redesign-*.json`。

## 同步 develop 后重新实测

- 试用构建 `f7f101d64` 包含 `origin/develop` 的 `89ed5c885`。保留纯交互卡片省略正文的发送规则及 Inbox 对显式 @ 的独立计数。引用 Agent 仍会触发处理，引用本身不计为 @。没有正文可摘要的引用也提供原消息回查线索。
- Node 24.22.1 下 `pnpm build`、Web 构建、`pnpm typecheck` 及 14 文件的 182 项窄回归通过。受控 Anthropic 请求录制 1 项通过，确认文本块合并后仍保留引文和当前消息的边界。真实 Sol 6.1 的证据取自原生轨迹和 IM 回执。
- Global 群聊 `c_l9wj4rjh` 从 Web 右键引用「试运行配额：21 个，代号白榆。」，@ Agent 并请它加 8 后引用同一条。原生轨迹第 4 轮直接 `inbox(read)`，结果含分开的 `reply_to` 和 `content`。随后 `send_message` 使用同一原消息 ID，收到 `status: sent`。实际群消息为「29 个，代号白榆。」，点击引用回到原消息。主 session `e5df36ca-cf0d-4df6-816e-62f8b93d2203` 中对应工具事件为 seq 119、126、127。
- 单线程群聊 `c_uq2gg3bm` 通过真实 IM API 投递同类请求，引用配额 16、代号水杉。原生 session `b8ecf2fc-50cb-4eb7-a272-9f0172b5430d` 的 seq 12 是实际输入，seq 17–18 为发送调用和回执。实际群消息为「新配额：24 个，代号水杉。」，引用目标为原消息。两组原消息均先写入聊天并未提前投递给 Agent。
- 本轮证据见 `/tmp/feat730-evidence/develop-*.json`。浏览器留在 Global 原生轨迹的 Inbox 结果面板。受控录制栈已退出并回收，原隔离预览 `http://127.0.0.1:55895` 保留给用户看本轮轨迹，由本任务在 Web 验收结束时回收。

## 长引用的省略提示

- 用户要求直接在 `reply_to.text` 末尾备注省略。长引用在前 1200 个字符后另起一行加 `[Rest of original message omitted.]`，短引用保留完整正文。Inbox 和历史读取共用这个投影。
- 39 项相关回归通过。真实 Global Sol 6.1 在群聊 `c_mxedik5q` 读到有省略提示的引文，按 ID 回查原消息，答出原文第 1446 个字符才开始出现的代号「玄汐-7486」。主 session `e5df36ca-cf0d-4df6-816e-62f8b93d2203` 第 5 轮可查看 `inbox`、`conversations` 和 `send_message`，本机证据见 `/tmp/feat730-evidence/long-quote-probe.json`。
