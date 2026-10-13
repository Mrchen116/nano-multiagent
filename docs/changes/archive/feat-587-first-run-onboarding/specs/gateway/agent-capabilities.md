## ADDED Requirements

### Requirement: 由节点验证并持久化模型连接

模型路由由 Node 持有，新 API/OAuth 凭据保留在节点的 DSH 原生凭据存储。原生 Codex 接入沿用 DSH 执行运行时；发现 CLI 不等同于授权或验证成功。已运行的兼容代理可以复用，无需安装第二套执行引擎。

#### Scenario: API 或已有代理
- WHEN owner 通过 IM 完成连接设置与验证
- THEN 新助手可使用通过验证的模型，节点重启后配置仍可用，回传状态不包含密钥。

#### Scenario: Codex 登录
- WHEN 用户选择 Codex 订阅连接
- THEN 在需要时显示一次性登录指引与取消/重试动作；成功后才允许验证模型，不复制 CLI refresh token 制造另一刷新所有者。
