## Why

目前系统只支持通过 IM（Web 界面）与 Agent 对话。接入微信个人号后，用户可以直接在微信里与自己的 Agent 交互，无需打开额外界面，大幅降低使用门槛。微信 iLink 是腾讯官方为个人号开放的 bot API，合法稳定，现在已具备直接对接的条件。

## What Changes

- 新增 `WeChatILinkAdapter`：实现 `ChannelAdapter` Protocol，通过 iLink HTTP 长轮询接收微信消息，通过 `sendmessage` 接口回复
- 新增 iLink 鉴权流程：扫码登录获取 `bot_token`，持久化存储供 Gateway 重启后复用
- 新增配置字段：`LocalConfig` 增加微信 iLink channel 配置项（`enabled`、`bot_token`、`token_path`）
- Gateway 启动时按配置注册 `WeChatILinkAdapter` 到 `ChannelRegistry`

## Capabilities

### New Capabilities

- `wechat-ilink-adapter`: WeChat iLink channel adapter — 长轮询接收消息、解析 iLink 消息格式、回传 context_token 完成回复
- `wechat-ilink-auth`: iLink 鉴权流程 — QR 扫码登录、bot_token 持久化、Gateway 启动时自动加载

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- `src/personal_assistant/channels/` — 新增 `wechat_ilink_adapter.py`
- `src/personal_assistant/config/local_store.py` — 新增 `WeChatILinkConfig` dataclass 及 `LocalConfig` 字段
- `src/personal_assistant/main.py` — Gateway 启动逻辑新增 adapter 注册
- 新增依赖：`httpx`（已有）用于 iLink HTTP 调用；二维码展示可用 `qrcode` 库或直接打印登录 URL
- 无 breaking change，现有 `web_relay` channel 不受影响
