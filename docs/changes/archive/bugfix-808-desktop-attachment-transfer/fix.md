# bugfix-808 桌面附件传输

## 原始报告

> 两端共用的 apps/desktop/src/host_server.rs:2146-2222 把上游正文错误替换为成功的空文件，并在正文读完之前不向客户端传，导致 512KiB 文本预览整文件预读。修复真实 IM 附件下载与预览路径，让断流可见、前端不保存假成功文件、流式预览可提前取消。保留现有会话更新等副作用，用正常/慢/中途断流 fixture 做定向验证。

## 现象与根因

在 develop 基线 `1bdc4646c`，受保护的 `GET /im/v1/conversations/:id/attachments/:resource_id` 经 capability 校验后进入桌面通用 IM 代理。IM 从文件流返回正文，代理却一直等待 EOF。连接中断时，代理把读取错误转换成空字节，同时沿用上游成功状态。附件按钮随后把空 Blob 当作完整文件保存。

[feat-790 的设计](../feat-790-desktop-client/design.md) 要求桌面 WebView 从同源回环访问 IM，并同步桌面角标。引入该代理的 `c75e0415e` 为解析成功的会话写入响应并更新通知状态，统一缓冲了所有响应。现有宿主测试覆盖登录与会话生命周期，前端预览测试使用已完成的响应，未覆盖代理读正文时失败或客户端取消。

## 本次审查安排

M1-fix 在桌面 HTTP 入口验证完整文件、慢速前缀取消、传输中断，以及会话写入后的通知状态。附件组件验证断流后的错误提示和保存行为。独立代码审查核对代理分支、回归证据和未验证平台。

Platform-Parity-Exempt: 两个桌面平台共用受修复的回环代理。Web 组件仅补回归测试；iOS 与独立 Web 客户端直连 IM。

## M1-fix 修复

桌面宿主按客户端读取速度转发普通 IM 正文，保留上游的状态、文件名、长度与编码，并向客户端传播读取错误。成功的会话 POST/PATCH 仍在完整读取后更新通知状态；正文中断时返回 502。现有下载按钮与预览弹窗依据 fetch 正文读取结果显示错误或保存文件。

## 验证

- macOS arm64，隔离宿主、临时目录、随机回环端口。修前正常二进制通过，未结束的 chunked 文件被识别为完整正文，慢流的响应头超时，会话写入短正文返回 200。修后 `cargo test --manifest-path apps/desktop/Cargo.toml --locked` 通过 9 个原有用例与 4 个 HTTP 回归用例。慢流用例在读到 512 KiB + 1 字节后关闭客户端，并从 IM 端观察到连接关闭；断流用例在客户端读到 200 和首段后切断 IM，再确认正文读取失败。会话测试先通过宿主登录入口建立有效通知会话，再核对完整响应使角标变为 3、截断响应返回 502 且角标仍为 3。
- 前端 `vitest run src/features/chat/attachments/attachment-preview.test.tsx` 通过 11 个用例，覆盖附件按钮和弹窗下载失败时显示错误且没有触发保存。
- macOS 系统 WKWebView 载入隔离宿主提供的实际 AttachmentChip、authFetch 与预览弹窗，通过 bootstrap cookie 访问受保护附件 fixture。观察下载动作携带的文件名及 Blob 字节，完整文件为 `ok.txt` / `intact`；断流后出现下载与预览错误，保存次数仍为 1；慢流在上游尚未完成时显示 512 KB 截断提示，上游观测到连接关闭并写入确认文件，WKWebView 进程读到确认后才退出。该检查拦截保存动作，未操作系统保存对话框。
- Windows 原生宿主用例随现有 Desktop candidate 在 windows-2022 执行；本地未运行 WebView2 界面。
