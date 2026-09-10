# M1 progress

## 实现

在已有 PR287/worktree 完成用户追加的私聊菜单与会话改名。复用 PATCH、Radix Dialog、既有样式和 i18n；保存失败显示可重试的用户提示。所有会话 describe 使用 title。新增内部 title_is_custom 默认0，显式 PATCH direct 标题后为1；外部正常复用/竞争恢复均保留手动改名 direct，其他同步不变。主分支 f455c6220 的 Fork 修复已无冲突合入；主仓 dirty 内容未改。

## 验证

- 相关前端 108 项、后端 27 项通过；名称 PATCH→真实 WebSocket describe 及测试文件契约补跑5项通过。最后错误文案调整补跑菜单4项；构建/Ruff/diff check 通过。
- 真实演示 IM :59669/Gateway 已重载保留全部历史数据。独立 playwright-cli session feat548，桌面1280×800、手机390×844。实际菜单、编辑、保存、刷新、空白禁用、取消、注入503保留输入/重试、Agent配置路由均通过。已查看手机菜单/失败截图，无溢出；英文菜单自然宽度避免换行，最终失败提示不暴露内部请求文本。
- 两条同 Agent qa-inbox-vision-0910 私聊：443e835d643442d3bf0134e09b18974a 改为简历修改 · 548，再改旅行计划 · 548；c7c408ff0bae48d7954c996a2f4d4e25 保持改名验证 · 保持原名。
- 真实 DeepSeek V4 Flash 先后答出这两个新标题，保留校验词枫叶；Proxy 原始 Inbox tool_result 两次分别为对应新标题，同一 target，没有通过重建会话实现改名。主 Session sess_15257fe98d153b35 保持。
- 外部私聊 bce608f96f8840b0b1c70aad35c3b423 通过 UI 改为外部私聊 · 我的命名，调用真实 find-or-create 同步入口传入新来源名后，标题与 ID 保持。此项使用 API 模拟外部同步，不声称飞书客户端端到端重跑。
- 原始证据 output/direct-chat-rename/{live.json,request-audit.json,*png}，真实请求 /Users/czj/Repos/LLM_PROXY/logs/session/2026-09-10_12-21-19_088_sess_15257fe98d153b35/；不提交运行数据。

## 现场

用户此前要求保留演示现场，继续保留 /tmp/feat546-feishu-authorized 和当前 unit worktree。仅独立测试浏览器在交付时关闭。无生产部署、无 PR 合并。
