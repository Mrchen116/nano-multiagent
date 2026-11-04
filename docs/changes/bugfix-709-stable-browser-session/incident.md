# bugfix-709 稳定浏览器登录会话

## 原始报告与决定

用户原话：
- “昨天晚上没重启过正式服务，今天我浏览器访问，还是必须登录。帮我排查下原因”
- “服务端为什么轮换？”
- “那你妈的，不就是实质性要一直登录吗”
- “改啊”

用户已经选择 30 天滚动有效期，并明确要求把浏览器会话改为稳定凭据，后台延长有效期，保留主动退出和撤销。

## 现状、证据和根因

关联 bugfix-702。生产 70ee96ab7 包含登录页恢复及 30 天 TTL。2026-11-04 09 时调查确认服务从前日 14:54 持续运行，当前 Chrome 续期 401，响应 session revoked or expired。通过浏览器网络请求对会话指纹只读比对，浏览器凭据签发于 11-03 23:58:36，服务端最后轮换于 11-04 00:33:45。会话 revoked=0，双方 epoch=0，服务端期限为 12-04，refresh hash 不一致。原始 JWT、Cookie 和会话标识不写入仓库。

identity.issuePair 在响应交付前覆盖 refresh_hash，旧 refresh 立即不可再用；浏览器丢失新 Cookie 后没有恢复路径。具体是哪次请求中断或浏览器操作造成失步仍未知。bugfix-702 未覆盖此故障模式。

## Requirements

### Requirement: 稳定浏览器凭据与滚动期限

#### Scenario: 续期响应丢失、页面重载和并发
- WHEN 有效浏览器 Cookie 发起续期，响应丢失，随后同一或另一个标签页用原 Cookie 重试
- THEN 继续恢复聊天，Cookie 凭据不变，每次成功续期延长 30 天，access 继续短期有效。

#### Scenario: 重启
- WHEN 沿用同一数据库和配置重启 IM，浏览器再打开 /login
- THEN 恢复 /chat，无需密码。

### Requirement: 退出和失效边界

#### Scenario: 主动退出或撤销
- WHEN 用户退出该会话，或账号认证 epoch 变化
- THEN 原 Cookie 和 access 都无法继续恢复；其他独立会话按现有规则处理。

#### Scenario: 过期与错误凭据
- WHEN 连续 30 天未续期，或 Cookie 被篡改
- THEN 拒绝恢复，显示登录表单。

### Requirement: 现有身份与客户端接续

#### Scenario: 已有有效浏览器凭据
- WHEN 升级前当前仍有效的 JWT refresh Cookie 首次续期，或升级响应丢失后重试
- THEN 可重复取得同一个稳定 Cookie，后续正常续期。

#### Scenario: 已经失步的旧 Cookie
- WHEN 升级前凭据已经被消费，与服务端 hash 不匹配
- THEN 保持拒绝，不能恢复被撤销或已消费凭据。此类浏览器须重新登录一次。

#### Scenario: 程序客户端
- WHEN 无浏览器标记的客户端使用 JSON refresh
- THEN 继续一次性轮换，旧令牌失效；浏览器 Cookie 仍要求许可 Origin 和浏览器标记，不向页面持久存储写凭据。

## 范围

单 M1，后端鉴权和持久状态，Web 表单和信息组织不变。登录时间/设备记录沿用 bugfix-702。无 Agent Context 影响，无生产操作授权。
