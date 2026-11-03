# iOS Client delta

## MODIFIED Requirements

### Requirement: iOS 独立客户端保持 IM 业务与权限契约
IM SHALL 提供原生 iPhone 客户端。聊天、任务、Agent 和我的及其管理页面 SHALL 保持现有 IM 业务契约，内部业务页面 SHALL NOT 委托网页容器完成。Intelligent UI 回复内容允许使用随包共享渲染组件，原生宿主 SHALL 保持业务权限与交付权威。公共可见性 SHALL NOT 推导出管理权限。

### Requirement: 原生通用交互回复
客户端 SHALL 呈现当前 openui/nano-iui-1 通用交互回复，并保持与 Web 一致的组件、布局、绘图和动作语义；私人编辑、显式继续、只读历史和原聊天权限 SHALL 保持。

#### Scenario: 跨端阅读同一回复
- **WHEN** 用户在 iPhone 打开含新版 Intelligent UI 的消息
- **THEN** 酒店照片卡片、看板图表/SVG 和会议选择使用同一源码呈现，正文仍独立可读；组件资源不要求在线 Web 页面。

#### Scenario: 本地探索与显式继续
- **WHEN** 用户修改回复内的选择并明确请求继续
- **THEN** 本地探索不触发 Agent，显式请求携带当时完整状态，只创建一次用户消息；私人草稿可恢复并保持原有冲突处理。

#### Scenario: 内容与宿主权限隔离
- **WHEN** 回复包含沙盒页面、查询、草稿采用或继续请求
- **THEN** 内容不能取得会话凭据或调用未注册 API；历史只读、访问撤销及退出登录后不能绕过原生权限发起业务请求。
