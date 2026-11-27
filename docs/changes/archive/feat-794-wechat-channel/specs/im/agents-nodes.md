# im/agents-nodes.md (delta for feat-794)

## MODIFIED Requirements

### Requirement: Agent 通道页统一管理外部 channel 与安全凭据

Agent 详情页的“通道”页只管理可配置的外部 channel，不把内置 Web IM 列为 channel。页面和 REST 资源按 provider 通用建模；provider catalog 包含飞书（`feishu`）与个人微信（`wechat`），同一 Agent 每种 provider 最多一个实例，不同 provider 可同时并存。飞书向导给简短准备说明和开放平台入口；微信在 Web 端通过节点受控的二维码扫码与手机数字验证码确认完成绑定与重绑（服务端拒绝客户端直接经普通通道创建/更新接口提交明文微信凭据，仅允许通过节点扫码确认原子建档/重绑及以 `keep` 模式切换启停）。飞书 App Secret 只在新增或显式替换时提交，微信连接凭据由节点扫码确认后经服务端直接以目标节点公钥封装为密文；list/get/edit/setup 响应均不返回明文密钥、令牌或 envelope，Gateway 的普通 `config.yaml` 也不是该凭据的持久化位置。原生 iOS 客户端支持在添加入口区分飞书与微信（对微信给出前往电脑或网页端扫码绑定的明确指引），如实展示飞书与微信通道的提供商名称、绑定标识摘要与连接状态，并支持对两类通道执行启用、停用、重连与删除；原生 iOS 端不向微信通道展示飞书专属字段、表单或外链。

#### Scenario: 空态与添加入口不展示 Web IM 且支持多 provider 并存
- **GIVEN** 当前 Agent 没有外部 channel
- **WHEN** 用户在 Web 端打开“通道”页
- **THEN** 页面显示通用空态和“添加通道”，provider picker 包含飞书与微信，不展示 Web IM
- **AND** 已添加某一 provider 时 picker 将该项标为已添加并禁止同 provider 第二个实例，未添加的另一 provider 仍可继续添加

#### Scenario: 飞书向导提供轻量开放平台入口
- **WHEN** 用户选择添加飞书
- **THEN** 页面简要提示准备应用、Bot 与长连接，并提供 `https://open.feishu.cn/page/launcher?from=backend_oneclick`
- **AND** App ID/App Secret 缺失时在字段处提示，不提交连接请求

#### Scenario: Web 端微信扫码与数字验证码绑定、取消恢复及禁传明文凭据
- **GIVEN** 目标 Agent 所属节点在线且已登记节点凭据公钥
- **WHEN** 用户在 Web 端选择添加微信（或对已有微信通道点击重新扫码），用手机微信扫描二维码并在需要时输入手机显示的数字验证码完成确认
- **THEN** 页面依次反映待扫码、已扫码待确认、数字验证码输入（含校验失败就地提示重试）或二维码过期刷新状态；确认成功后保存微信通道并展示掩码绑定标识摘要与连接状态，浏览器全程不接收明文令牌
- **AND** 用户在确认前取消或关闭弹窗时，节点立即终止本次扫码轮询，不产生半成品通道或破坏既有已保存通道
- **AND** 客户端若绕过扫码流程直接向通道创建或更新接口提交 `wechat` 明文凭据，服务端明确拒绝写入

#### Scenario: 原生 iOS 端查看与管理微信通道并提供添加引导
- **GIVEN** 用户在原生 iOS 客户端打开某 Agent 的外部通道页
- **WHEN** 用户点击添加通道并选择微信，或查看已绑定的微信通道
- **THEN** 选择添加微信时展示前往电脑或网页端扫码绑定的清晰说明，不误入飞书专属编辑表单；若飞书尚未添加仍可正常添加飞书
- **AND** 已绑定的微信通道以「微信」分组展示掩码绑定标识与真实连接/离线状态，支持启用、停用、重连与删除，不展示飞书 App ID、飞书编辑表单或飞书开放平台权限外链，并在登录失效时提示前往网页端重新扫码

#### Scenario: channel 列表读取失败不伪装成空态
- **WHEN** IM 无法读取当前 Agent 的 channel resources
- **THEN** 页面显示失败原因和重试入口，不显示“尚未配置”的空态

#### Scenario: 已保存密钥不可读取且 App ID 换绑必须换密钥
- **GIVEN** 飞书或微信 channel 已保存加密凭据
- **WHEN** 用户再次读取、启停或编辑该 channel
- **THEN** 响应只表明 `secret_configured=true`，不返回明文或 envelope；启停切换可沿用 `keep` 保留原加密凭据
- **AND** 飞书 App ID 改变时 keep 被拒，必须同时 replace App Secret；通过 IM 新建/更新不会把凭据写入 Gateway `config.yaml`

#### Scenario: 节点尚未登记 credential public key
- **GIVEN** IM 从未取得目标节点的 credential public key
- **WHEN** 用户新增 channel、替换飞书密钥或发起微信扫码绑定
- **THEN** IM 拒绝凭据写入并说明需让节点至少上线一次以建立安全存储
- **AND** 不把该错误误报成飞书或微信凭据无效
