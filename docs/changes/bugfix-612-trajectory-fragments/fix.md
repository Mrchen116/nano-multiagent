# bugfix-612：完整原生轨迹的传输分片与重组

## Relations

- Related: feat-583, feat-589

## 原始报告

用户截图显示 Personal Agent 的子执行「核对其他面试知识工程论述」报 `trajectory_read_failed: trajectory_frame_too_large`。

用户原话：

> 我要看这个subagent才刚启动，也超过1M了？
> 那查一下这次到底是哪部分超限了，我觉得不合理，既然是单帧限制，那单帧就不应该超吧
> 那修一下我们这层的分片和重组，保留完整轨迹，拿这次 subagent 的数据验证。

附件引用：`codex-clipboard-10dc227e-5939-47e9-926a-42a5f403ecf9.png`（对话附件，不提交图片缓存）。

## 现象 / 复现

生产 Mini 的原生子会话 `b64d6e64-e0bb-4fe3-accf-af3cb479d29d`（父会话 `8d36509c-91d0-423d-97d4-2f6419162253`）于 2026-10-15 11:38:13 +08:00 创建，fork 继承 2018 条事件。

只读解码生产持久日志并按已安装 DSH 的窗口规则重建启动初期 `cursor=2029` 的 opening：224 条事件，快照至少 1,256,641 bytes；其中继承记录 1,252,187 bytes，本次新增记录 3,952 bytes。缺少当时实时 projection/assistant baseline，因此这是重建的体积下限，并非声称捕获了截图对应的原始网络帧。最大单条事件仅 137,909 bytes。用线上同一 `TrajectoryStream` 读取重建 opening 已复现原错误。

退出标准：该真实会话的 opening、后续事件与向前分页能完整通过 Nano 传输，重组后与原始 DTO 相同；每个物理消息仍在 1 MiB 以内；慢观察者、关闭、身份撤销和附件授权继续生效。

## 根因

feat-583 的意图是只读、按需检查官方原生轨迹，观察流独立于业务 ACK，且慢观察者只终止读取。feat-589 明确保留 fork 继承历史，不能通过过滤历史、删除字段或缩短上下文来消除报错。

引入坏行为的提交为 `7e22a91d28`：`TrajectoryStream` 将 DSH 完整 opening DTO 当成必须小于 `1 MiB - 1 KiB` 的传输帧；只按消息数量划页的官方 opening 可以自然大于该上限。原实现只将多个完整帧装入有限批次，没有拆分单个 DTO。Node/IM 专用 WebSocket 对完整响应同样使用 1 MiB 限制，因此 unary 历史分页也需要一致的分片处理。

修复应保持 DSH 的公开读取与原生 DTO，不 fork/patch DSH，不修改 session、surface、分页或执行语义。原始上下文、工具结果、附件元数据和继承事件都须完整保留；附件字节仍经过既有来源授权。
