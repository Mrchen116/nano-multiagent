# bugfix-641: As-built Design

> 实现后根据代码和已确认决定整理；不补造设计评审或用户验收。

## 实现范围

Base: `b6db5d02345b63691d6198ea3abe63c17a353e4e`。工作分支 `codex/pa-group-delivery`；本次 code review 的精确版本见 code-review.md。

## 最终结构与调用链

1. IM PersonalActions 沿原 prepare/review/commit 冻结并校验动作。
2. 事务内写消息和 delegation，queueDirectAgentRelays 与 groupReply(deferDelivery) 写已有 relay_tasks，最后更新 operation/disclosure revision。
3. 事务完成后返回 confirmed。即时浏览器通知可失败；RelayDelivery 现有 250ms 定时器/重连通道按权限和 epoch 消费持久任务。
4. PA 传递冻结证据至 DSH `pa.review`，宿主验证 scope 后调用 `personalReviewAction` 生成 planned_action；原 evidence 在 IM 中继续用于复核，未参与投影的字段并未删除。
5. 现有 Codex reviewDisclosure 仍提供当前有效上下文和 PA 策略，无额外历史检索、窗口裁剪或新 Agent。

## 已采用决定

| 决定 | 原因及约束 |
|---|---|
| 复用 relay_tasks，显式 deferDelivery | 发送原子性与接收端恢复分开；不在未提交事务中向节点发送 |
| 接收者成员身份生成 relay | 发送者允许是未入群但已获主人授权的 PA；不能伪装作者或偷偷加入 PA |
| 仅 PA commit 延迟传输 | 通用 Agent 群回复/直接派发仍保留现有立即 drain 行为 |
| 明确投影，不改冻结存储 | last_owner_message_id 只防止主人已回复，不能误作当前授权来源；后端全部拦截继续生效 |
| audience 使用 IM user_id | 与原始 mention target_id 和消息 sender_user_id 可关联；不同时给同一成员两套 ID |
| restrictions 只携带真实限制或 unknown | 正常可读的历史来源列表不复制；缺失事实不能变成没有限制 |
| 安全通知保留 receipt 事实 | 不丢失服务端已核定的固定拒绝语授权；继续使用原安全通知上下文例外 |

## 失败与兼容边界

无 schema 或持久协议迁移。任一 relay 写入失败回滚整条新发送；传输尚未成功则保留 queued，由已有恢复通道继续处理。回滚代码不删除已持久的 relay；历史已 confirmed 且没有 relay 的消息不会被本修复自动重发。

完整当前动作不能放入模型预算时沿原流程 unavailable；实际限制缺失以 unknown 呈现。投影不是授权器，不能保证模型对主人语义永不误判。冻结证据接口不变；仅模型 planned_action 及对应规则同步调整。

## 验证与归并

验证定位见 fix.md 与 code-review.md；原生 fixture 使用合成文本，不提交私人生产上下文。用户验收待完成。最窄 canonical 目标为 `docs/specs/im/personal-agent.md` 与 `docs/specs/gateway/personal-agent.md`，拟归并内容见 delta-spec.md；当前保持 active。
