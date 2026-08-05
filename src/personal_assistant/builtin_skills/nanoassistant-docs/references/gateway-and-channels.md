# Gateway、节点与飞书渠道

## Gateway 与节点状态

Gateway 是本地常驻进程，同一 config 同一时刻只允许一个实例。start、stop、restart 由 config-scoped lock 串行化。

- 后台状态写入 config 同目录的 `.gateway-state.json`，日志写入 `gateway.log`。
- `STOPPED` 表示目标实例已关闭；`NOT RUNNING` 表示没有可管理实例；`STALE` 表示旧进程身份失效且状态已清理。
- Gateway 主动连接 IM；IM 暂时不可达时会指数退避重连。
- IM 离线期间，已经接入的外部渠道尽可能保持本地自治；Web IM 要等连接和节点 online 恢复。
- 判断 Gateway 可用性时，同时核对存活进程、process birth、当前日志、节点 online 和一次真实消息往返。旧 PID、历史日志或“start 没报错”都不能单独证明可用。
- 节点首次绑定到 owner 后，其他 owner 不能直接改绑；需要迁移时不要假设重新点确认会转移所有权。

## 飞书渠道

飞书是当前主要外部渠道，由 Web IM 的 Agent 通道页托管。

### 配置

1. 先让目标 Gateway 至少上线一次、完成节点绑定并登记凭据公钥。
2. 在 `/settings/agents/<agent_id>` 的“通道”页添加飞书。
3. 填写飞书 App ID 和 App Secret；飞书应用启用 Bot、长连接和消息收发权限。
4. 需要把群内未 @Bot 的普通消息作为后续上下文时，额外授予 `im:message.group_msg`。

同一 Agent 最多配置一个飞书实例。App Secret 经加密 envelope 交给目标节点，不写入普通 `config.yaml`、日志或 HTTP 响应。

### 运行行为

- 保存成功只表示 desired state 已提交；以通道页 runtime 状态和 diagnostics 判断是否真正连接。
- Gateway online 时，新增、编辑、停用、重连和删除会热调和，不要求改本地 YAML 或重启 Gateway。
- 已应用的飞书配置以节点密文 cache 支持 Gateway 重启和 IM 暂时离线；IM 恢复后再收敛到最新 desired state。
- 私聊消息触发绑定 Agent 回复；群聊通常要求 @Bot、回复 Bot 或发送明确控制命令。
- 飞书用户消息和 Agent 回复会镜像为 Web IM 中独立 shadow conversation。IM 离线时本次镜像可以暂缺，但飞书主路径不应因此阻塞。
- 多个 Agent/Bot 在同一节点或同一外部群中保持独立 runtime、影子会话和上下文。
- 普通 Gateway 飞书对话由 Gateway 拥有；用户明确要求的独立 Lark event 监听不接管普通入站和回复链路。
- 内置完整 Lark skill bundle 让飞书绑定 Agent 能操作文档、云盘、表格、日程、任务、审批、邮件、知识库和会议等资源；具体操作仍受 Lark 登录身份、权限和对应 skill 规则约束。
