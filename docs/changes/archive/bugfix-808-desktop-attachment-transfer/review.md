# bugfix-808 代码与契约审查

独立 change-code-review 审查 `1bdc4646c..95f1a7f63`，核对受保护附件的真实 URL、通用代理、下载与预览调用方、会话通知更新及[验证记录](fix.md)。结论为通过，current spec 与实现对齐。最终归档只更新证据和文档位置。

- 完整文件和中途断流有独立的 HTTP 回归断言。成功的会话写入继续更新角标，短正文返回 502。前端仅在完整读取成功后触发保存。
- R1（低，证据限定）：首次 WKWebView 检查在预览成功后退出，随后才检查 IM 连接状态，退出本身也可能导致关闭。Owner 用相同产品代码补验：上游先写入连接关闭确认，仍在运行的 WKWebView 进程读取确认后退出。先后顺序已通过，修订后的结果写入 fix.md。
- Windows 由 PR 的 windows-2022 原生 candidate 运行宿主回归。本地证据覆盖 macOS arm64，未操作 Windows WebView2 界面或系统保存对话框。
- 已回收临时宿主、上游 fixture、WKWebView、依赖链接和本轮编译缓存。开发 worktree 随开放 PR 保留。
