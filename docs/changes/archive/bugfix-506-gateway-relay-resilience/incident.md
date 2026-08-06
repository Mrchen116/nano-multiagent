# bugfix-506: Gateway 重连后的中继可靠性

## 原始报告

用户要求在真实 IM 群聊实验中运行一支临时 Agent 团队。实验期间发现 Gateway 重连和远端 IM ACK 延迟会使群消息中继积压、同一 Agent 回复重复出现或 Gateway 频繁断线；用户要求直接修复，并将这三项稳定性问题补入一个 PR。

## 澄清记录

- 此 unit 只覆盖 Gateway 与远端 IM 之间的配置收敛、流式回复重传和业务 ACK 稳定性。
- LLM_Bridge OAuth 刷新是独立仓库的修复，不纳入本 PR。
- 三项问题合并为一个 PR，不拆分多个 unit。

## 现象与复现

1. IM 重启或远端网络变慢后，Gateway 已完成注册却仍被节点绑定 HTTP 或全量 Agent 配置对账占住，节点迟迟不可用，群消息中继积压或失败。
2. IM 对业务帧的 ACK 晚到时，Gateway 重连并重传同一个 Agent 流式 `message_delta`；IM 将每次重传都当作新正文追加，用户会看到两到四遍相同回复。
3. 本机 Gateway 到 Mini IM 的往返延迟约半秒时，1 秒业务 ACK 上限把慢但正常的确认误判为超时，主动断线并触发重连。

## 影响范围

受影响的是远端 IM 上的 Web IM 群聊和单聊中继。Agent 模型实际只会执行一次，但用户可能看见重复回复，或在重连期间看到延迟/失败；外部 Channel 的本地自治路径不受 IM 离线影响。

## 根因分析（RCA）

连接注册后的 `ConnectionReadyCoordinator` 同步等待节点绑定和 Agent profile reconciliation 的 HTTP 工作，使收发 loop 的 ready callback 被慢控制面工作占用。后台化 profile reconciliation 的初版还冻结版本快照并允许重连任务重叠，旧任务可在新 `config.sync` 后覆盖较新配置。业务 ACK 超时设为 1 秒，低于跨机连接中网络、IM 调度和持久化的正常预算，因而引发不必要断线。断线后的补发机制正确保留了未确认 frame，但 `message_delta` 没有携带稳定事件身份，IM 只能追加，无法区分首次投递和重传；初版去重还把正文与事件分两次提交，崩溃窗口仍会重复正文。

## 修复方向

将节点绑定和 profile reconciliation 转为后台任务，让已注册连接立即恢复业务收发；对账任务单飞并在发布前重读最新 profile version。把默认业务 ACK 上限调整为 10 秒。Gateway 从内核 assistant 事件派生稳定的 delta 幂等键，IM 以同一 SQLite 事务持久化该键、正文和 delta event，重复到达时仅确认、不再次追加或广播。
