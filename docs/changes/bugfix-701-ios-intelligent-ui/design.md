# iOS Intelligent UI — as-built design

本文在快修实现后记录实际设计；不代表事前 Gate 2 审查。用户验收尚未完成。

## 关键决策

- `nano-iui-1` 的内容使用系统 WKWebView 和随包资源，复用 Web 的 Renderer、`renderer-library.ts` 和全部组件；不复制 Swift 组件目录。原生聊天、业务页面及导航仍由 SwiftUI 持有。旧 `nano-1` 保持既有 JavaScriptCore 路由。
- 从 `catalog.tsx` 抽出只负责渲染的库定义，Agent 提示词输出不变。没有新增 Agent prompt、工具权限、校验规则或服务端浏览器。
- 私人状态、修订号冲突、自然文字携带选择、显式继续和 ComposeMessage 沿用 `InteractiveRuntime` / Session / ChatStore。Web 只上报当前完整状态和动作，Native 保持唯一网络与交付权威。
- 卡片用聊天内容可用宽度，移除该类型消息外部气泡的额外边框、填充和侧边头像占位；身份仍在卡片上方显示。组件的颜色、间距和绘图使用共享样式。

## 模块与接口

`InteractiveCardView` 按协议选择 `InteractiveWebView` 或旧原生节点树。`InteractiveWebContent.Coordinator` 只加载 App 内 IntelligentUI/index.html，持有绑定的 runtime generation，使用 WKScriptMessageHandlerWithReply 返回 JSON 或错误。`webRequest` 接口处理 ready、state、error、resource、action、tool；高度消息只调整本地容器。

JS 宿主使用同一个 `interactiveLibrary`：普通计算、输入、图表与 SVG 在本地更新；状态含递增序号，避免较早回调覆盖较新值。用户触摸/输入后的修改才触发私人保存。动作自带当前状态，显式请求完成先前保存后由 ChatStore 提交；发送身份与不确定发送恢复均沿用原路径。ComposeMessage 仍需原生目标访问检查和草稿替换确认。

## 权限、失败和生命周期

WKWebView 使用 nonPersistent 数据存储，JS 没有 token/cookie。Native 桥接要求主 frame 和随包 index URL；HtmlView 子页面沿用沙盒，不能使用 Native 权限。只连接 conversation_messages / continue_conversation，以及 image-search、wiki、street-route 三条既有资源端点。链接仅交系统处理 http(s)，主文档不能导航到远程站点。资源仍由 Session 认证并限制同源。

原生只读、历史/替代、并发冲突和 pending 请求禁用编辑/动作；每次业务调用检查 Session 身份及 generation。重新读取会重建 Web 内容；旧页回包不能污染新页错误。页面退出清理 bridge、取消加载，私人保存仍沿用原实现；退出账号后现有卡片不能继续访问。

Renderer 的诊断与异常交原生错误提示，正文保留。显式重试可读取最新内容。此实现不承诺发现上游静默接受的错误源码，也不修复此前未加引号中文字段导致的空图。

## 构建与运行代价

`vite.ios.config.ts` 打包一份 IIFE，内含共享组件、动态图标、公式字体和样式，避免 file-origin 下的模块/动态导入问题。MapLibre 使用随包 worker 字符串生成 blob URL，资源 API 在构建时替换为 Native bridge；不携带 Web 登录宿主或凭据。许可证按实际依赖模块一并生成。

构建资源约 7.3 MB（压缩约 2.5 MB），使用系统内核，不打包浏览器引擎。生成目录被忽略，由 build.sh 在 Xcode 前构建，Xcode 保留该资源文件夹层级。共享组件或构建依赖变更也触发 iOS CI；本地首次需要安装仓库和前端依赖。图片与地图底图仍依赖网络，不承诺离线远程内容。

## 验证与回滚

测试使用酒店、看板既有运行产出的原样源码，以及独立会议上下文。XCTest 在真正 WKWebView 中检查手机宽度、SVG 几何、当地编辑、草稿恢复和显式回复；原生权限、工具、沙盒 frame、只读与退出也有回归。截图和本地日志留在临时目录，不进 Git。最终结果记录在 validation.md。

没有数据迁移。回滚客户端代码和资源构建入口即可；历史消息仍有独立文字正文。没有执行安装包发布、生产部署或合并。
