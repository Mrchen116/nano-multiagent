# 本地真实产品证据（2026-09-30）

实施基线：本 evidence 所在提交；IM 与 Gateway 均来自 unit-feat-572 worktree，IM 127.0.0.1:50620，实际构建的前端由同一 IM 提供。桌面 1440×900、手机响应式 390×844；不是 iPhone 实机验收。原型对照见 ../prototype-visual-20260930/。

- pending / ordinary-me / policies-readonly：真实注册、管理员批准、普通成员入口及只读策略；保留原产品认证布局和双语言切换。
- group-tasks / task-node / task-return / protected-root：两个不同 owner 的真实 Gateway Agent 经聊天调用 task_graph 创建/修改同一图，两群保留不同节点活动，原聊天访问仍隔离；详情和回聊引用保留草稿。two-owner-task-results.json 为 API 投影复核，不能替代聊天截图。
- attachment-partial-failure / text-only-retains-files：实际拖入小 PNG 与 11 MiB PNG，单文件 413 后仅发送文字，成功附件及失败文件保留；移除失败文件后小图成功发入会话。
- capacity-*：只在隔离环境 attachment_storage 账本建立 1 GiB owner / 10 GiB service 容量 fixture，触发真实上传 API 507 和 UI；没有执行 GiB 实际上传。之后精确删除 fixture。文字发送成功且失败文件保留。
- suspend-impact / suspended-live：先取消并核对旧连接仍有效，再真实停用；既有页面即时失去访问，旧用户 HTTP 401、机器 HTTP 401、旧机器 WS 403，历史记录保留。
- bind-* / handoff-result：停用旧 owner 后从本机真实 CLI 发起交接，浏览器同意前中断并恢复相同操作，再浏览器同意和本机 yes，整机交接成功、原 node/Agent IDs 和任务/聊天记录保留。
- public-launcher-redaction：隔离 public launcher 真实握手日志使用 [redacted]，并未公开公网服务。

截图已查看关键移动端 pending、附件错误与交接成功画面；独立产品验收尚待完成。未用旧成员列表截图作为证据（早期布尔值显示问题已修复）。

真实公网域名 R6 尚需当次上线授权及 Cloudflare 控制权限核实；真实飞书 R7 的专用 Bot 被其他 unit 使用，未抢占或伪造成功。以上本地结果不代表 R6/R7 已通过。
