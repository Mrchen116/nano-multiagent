# M1 验证

实现为 `159c045b3`，追加回归为 `d7eb4999a`。本机使用 Node 24.22.1、pnpm 11.7.0、Chrome 158.0.8127.37 和 CuaDriver 0.38.0。测试均使用独立临时目录、合成消息和本地页面。

| 使用入口 | 操作与实际结果 |
|---|---|
| 节点 CLI 与安装包 | 临时节点配置下，合成 token 经本机输入后得到 paired，文件为 0600，断开后为 not_paired。Web IM（`POST /im/v1/nodes/:node_id/browser` `no-store` 直通不落库，覆盖电脑详情抽屉、新建/编辑助手启用 `computer_use` 就地提示与 `/settings/nodes?pair_browser=1` 深链）、Crewden Desktop「这台电脑」配对栏及交互式 `browser pair` 均已验证半自动引导：未安装扩展时自动打开官方商店页并在检测到扩展落盘后自动打开扩展 Token 管理页（0.6.0+ 为 `manage.html`，兼容 0.5.x `status.html`），支持手动粘贴整行 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=…` 或裸值，不读取系统剪贴板且 Token 不外泄。安装包执行冻结锁文件的生产依赖离线安装，可启动 Playwright MCP 0.0.86。paired 只证明已保存配对信息。 |
| 隔离与日常浏览器 | 两个真实 headless Chrome Profile 访问本地 HTTP 页面，任务内可输入、复制、粘贴和切换标签，另一 seat 无法使用其剪贴板；审批后的旧 ref 被拒绝；关闭最后一页后在原 seat 重开成功。实机 Chrome 158.0.8127.37 安装官方 Playwright Extension `0.6.0` 并通过 Web IM 完成配对后，真实验证修复了两项实机体验问题：(1) 扩展 `chrome.debugger` 禁止 `browserContext.newCDPSession`，改为复用所属标签页现有主帧 CDP 会话开启 `Emulation.setFocusEmulationEnabled`；(2) 移除宿主前置单句字面 URL 正则误拦，保留剪贴板隔离、显式隔离环境与同名多窗口消歧硬约束，多轮上下文与自然语言目标统一交由 `NanoApproval` 结合会话历史裁决，并为 `screenshot` 落盘返回工作区图片路径以衔接 `send_message(local_images)`。实机双轮连续测试（首轮打开 `https://example.com` 读内容并关闭 → 次轮直接追问「截个图发给我」）一次通过，真图（29KB JPEG）直接送达聊天会话；无搜索/航班工具时仅发「帮我看看 MU5101 航班的信息」（未提 Chrome），Agent 自主打开后台 Chrome 检索 FlightAware 实时起降信息并自动关页，配对状态为 `verified`。 |
| 根 DSH 与 Worker | 合成模型通过原生工具执行器请求 clipboard；一次系统操作由可计数的合成读取替代。主、Worker 共享消费位，私有 stdio MCP 的 Worker 先读时，根随后得到 already consumed。无关人类消息不能取值。一次浏览器写被宿主拒绝，未启动后端。 |
| 原始消息来源 | 在真实 DSH 进程、GlobalAgent、InboxStore 和临时数据库中传递相同的主人/协作者群消息。只有主人原始 IM ID 到达持久化 claim；这里在驱动边界主动停止。重放和别的窗口中复制的新内容均不能据同一交办重新取得。 |
| 本机桌面后端 | 真实 CuaDriver stdio 握手、无提示权限检查和空 PID 枚举。夹具覆核窗口归属、焦点变化拒绝、导航复用、后台投递形状及剪贴板读的执行时点。普通用户窗口和系统剪贴板未用于测试。 |
| 三种外部 CLI | 本地协议子进程验证 Codex/Claude/Antigravity 配置、允许与拒绝的路由和取消。私有 stdio MCP 的实际往返验证了受绑定的宿主入口。本机三个商业 CLI 核实启动参数或配置解析；未向真实云端账号派发任务。 |

## 初始 Context

请求原件在本机 `/tmp/nano798-context-evidence/requests.jsonl`。采集点为实际 DSH 出站的 `llm/stream`，使用受控模型。第 2 和第 6 条为相同普通输入、相同既有工具选择：关闭时 0 增量，启用后工具数组只多一个入口，紧凑 JSON 多 640 字节（约 125 tokens）。第 7 条才出现具体桌面动作。第 3–5、8–12 条含合成剪贴板交付与拒绝；第 13–15 条是受审写操作。第 16–17 条覆盖同一 Global 根在开启与随后关闭能力时的委派 schema；关闭后主工具与委派扩展字段同时消失。

## 尚待本机验收

- 专用测试 Chrome Profile 中安装官方扩展并配对。用本地测试站点设置合成登录态，双任务分别打开后台标签并实际输入，核实登录态、前台应用、标签所有权和断开回收。当前机器没有已配对的测试 Profile。
- 启动应用身份的 CuaDriver 并由机器主人授予必要系统权限。使用可丢弃的真实窗口测试后台点击/输入以及用户切换目标时拒绝。当前 app-owned daemon 未运行，权限状态 unknown。
- Windows 尚无运行证据。真实 CLI 云模型调用、日常 Chrome 和真实窗口操作不能由协议夹具代验。正式契约归并和 unit 归档留到验收收口。

## 交付检查

Node 构建、全仓 TypeScript、iOS 共享渲染器、文档完整性及 Ruff 通过。Web IM 1,319 项和 Python 非 E2E 138 项通过。一次根 Vitest 全量运行 1,586 项，有 8 项到达测试或能力检查超时；将失败文件串行复跑后 7 个文件通过，余下的 single-thread public send 用例单跑通过。现场确认并清理了 supervisor 超时测试留下的独立 CPU 循环进程。未修改测试超时值。普通启动现在延迟至首次 MCP 连接才加载客户端依赖，相关宿主、浏览器及 Worker 测试 10 项通过。

测试节点的临时配对配置保留给机器主人进行日常轨验收。工作树保留到 PR 合并；真实验收结束后回收测试节点配对、专用 Profile 与临时配置。
