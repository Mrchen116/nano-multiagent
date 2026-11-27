# IM Agents and Nodes 增量

## ADDED Requirements

### Requirement: 节点拥有者可通过网页引导完成日常 Chrome 配对且凭据不落中心服务

#### Scenario: 电脑详情与助手工具配置的就地配对引导
- **WHEN** 节点拥有者在 Web IM 打开在线电脑详情抽屉、访问 `/settings/nodes?pair_browser=1` 深链（聊天中点击该链接在应用内路由跳转：仅有一台在线电脑时直接展开其配对抽屉，多台在线电脑时停留在电脑列表供明确选择而不猜测），或在新建/编辑助手时勾选 `computer_use`
- **THEN** 页面读取该电脑当前的日常 Chrome 状态与可用 Profile；拥有者触发引导连接时，节点在所选 Chrome Profile 自动打开官方扩展商店页并在检测到扩展安装后自动打开扩展 Token 管理页（已安装则直接打开 Token 管理页），拥有者手动粘贴 Token（支持粘贴 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=…` 整行或裸值）即可免重启保存生效，并可随时断开连接。

#### Scenario: 瞬时直通不保存扩展凭据且跨租户隔离
- **WHEN** 客户端经 `POST /im/v1/nodes/:node_id/browser` 查询状态、启动引导、提交 Token 或断开配对
- **THEN** 仅该电脑所属拥有者可调用，IM 以 `Cache-Control: no-store` 经在线节点通道瞬时转发，不将 Token 写入 IM 数据库、响应体或日志；节点离线、跨用户访问或不支持的平台分别返回明确状态。
