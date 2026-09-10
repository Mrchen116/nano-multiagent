# Gateway Routing and Delivery delta — feat-551

## ADDED Requirements

### Requirement: 当前会话的 Agent 图片回复具有统一交付语义

Gateway MUST 将普通 assistant 回复中的可交付图片与文字按原顺序交付到当前聊天，支持本地 PNG/JPEG/WebP 产物和既有可获取网络图片。图片引用不授予额外文件读取权限。每气泡最多五个不同来源、单图最多 10 MiB；同来源重复引用不重复准备资源。

#### Scenario: 本地产物跨机器查看
- **WHEN** 用户请求 Agent 展示其通过工具准备的本地图片
- **THEN** 原聊天可以直接查看图片和说明，无需用户访问运行机器。

#### Scenario: 图片语法不绕过权限
- **WHEN** 回复引用无权读取或未准备为可交付产物的文件
- **THEN** 图片不发送，对应位置出现可读失败说明。

#### Scenario: 图文投递保持入口路由
- **WHEN** 飞书触发的 run 产生中间或最终图文回复
- **THEN** 原飞书聊天和内部影子会话收到等价内容，普通富文本和运行信息卡片均可显示图片
- **WHEN** 内部 IM 影子会话触发同类回复
- **THEN** 只在内部 IM 显示，不回写飞书。

#### Scenario: IM 离线不阻塞飞书图片
- **GIVEN** 飞书可用、IM 暂不可用
- **WHEN** Agent 产生图片回复，随后 IM 恢复
- **THEN** 飞书先收到图文，IM 后续补齐相同图片的历史且不重复创建气泡。

#### Scenario: 局部图片失败
- **WHEN** 图片不可读、格式不支持、超限或上传失败
- **THEN** 对应位置显示失败原因，正文和其余可用图片仍可阅读。

#### Scenario: 普通文本和示例保持原语义
- **WHEN** Agent 回复纯文字或代码中的 Markdown 图片示例
- **THEN** 保持原有文字，示例不触发文件读取或图片发送。
