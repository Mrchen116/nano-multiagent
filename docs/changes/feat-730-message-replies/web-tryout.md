# Web 试用记录（作者自检，待用户验收）

## 实际实现

- Web 在现有菜单和工具条提供“回复”；输入区可取消引用，正文与附件草稿保留，切换聊天后恢复各自草稿。
- 服务端只接受当前聊天内可回复的消息，保存原发送者、正文和附件的单层快照；实时消息、历史、重试身份和 fork 一并保留引用。拒绝跨聊天目标、system 条目和未完成的 Agent 消息。
- 新消息的引用可点击定位；原消息未在已加载页时沿用现有历史分页定位。Web 与共享消息契约有可选新增字段，未修改原生 iOS。
- 单线程模型输入与 Global Inbox 包含标明为聊天数据的完整引用；PA 来源证据和审核补充原消息。群聊引用某个 Agent 时向其发出明确 attention。
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
