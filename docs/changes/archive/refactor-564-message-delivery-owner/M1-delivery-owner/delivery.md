# M1 Gateway 交付 owner 实施证据

## 所有权变更

- 新增 Gateway 私有 `MessageDelivery`、`ReplyCandidate` / `DeliveryResult`；移除 `PaReplyDelivery` 及其 SDK 输出回调依赖。composition 仅连接事件收集器、owner、通道与生命周期依赖，不保留 prepare/publish 业务闭包。
- 普通完整候选、显式消息和后台图片回复在 owner 准备资源；原生 IM、显式 IM 与外部 provider 的首次提交和恢复共用 `_commit_publication`。已确认目标不重复提交，未知回执保留原身份与恢复 payload，provider 重试窗口保持原限制。
- `DeliveryLedger` 接管原 SQLite 表中的消息回执、未确认 dispatch identity 及请求级反馈额度。`ReplyImages` 仅保留不可变资源快照、provider 资源信息和投影。
- `ImageReplyConnection` 仅接收 owner 准备好的正文投影；拒绝未准备的正文，不在完成时读取源文件。完成帧查询 owner 回执，ACK 未确认时不能通过 completion 绕过原提交；同身份恢复确认后才可结束气泡。
- Shadow 保留 ingress、锚点与过程事实；Agent 正文写入及终态正文对账移交 owner。恢复只载入已保存快照，不重新读取 Agent 源路径。
- 普通图片权限复用 `Kernel.authorize_tool`，授权期间保留已打开描述符；同一候选重放复用批准的快照。反馈额度通过 owner/ledger 提供给 coordinator，成功准入才消耗额度。

## 验证

以下聚焦单测共 **80 passed in 1.04s**：

```sh
PYTHONPATH=src .venv/bin/pytest -q tests/unit/personal_assistant/test_pa_reply_delivery.py tests/unit/personal_assistant/test_reply_delivery_recovery.py tests/unit/personal_assistant/test_im_reply_image_delivery.py tests/unit/personal_assistant/test_reply_image_delivery_strict.py tests/unit/personal_assistant/test_internal_dispatch_endpoint.py tests/unit/personal_assistant/test_reply_images.py tests/unit/personal_assistant/test_gateway_shadow_sync.py
```

以下集成验证共 **15 passed in 16.38s**：

```sh
PYTHONPATH=src .venv/bin/pytest -q tests/integration/test_background_reply_images.py tests/integration/test_pa_candidate_delivery.py tests/integration/test_pa_candidate_recovery.py tests/integration/test_pa_offline_image_shadow.py
```

覆盖缺图整条扣住、权限拒绝、批准期间替换路径、删源后重放、批准/ACK 去重、额度持久化、ACK 丢失后原身份恢复、恢复期间活跃 run 不提前完成、provider 过期窗口、reset 清理、外部离线主交付及 IM shadow 后补。修改文件通过 Ruff。以上是 worker 聚焦证据，不代表完整 PR 门禁或真实产品验收已结束。

## 旧测试处理

- 原 `test_pa_reply_delivery.py` 的 Kernel callback/control mock 测试替换为真实 Gateway owner + SQLite/文件快照测试。
- 原 native writer 的“完成时准备图片”测试撤回；改测仅接受已批准投影、完成不读原路径、未知 ACK 阻止 completion、同身份恢复及 reset 清理。
- recovery、strict resource 与 shadow/dispatch 测试改为使用真实 owner/ledger，保留原来源、幂等、过期窗口和生命周期断言。
- 已删除 handler 的旧图片 owner/account provider/router 构造参数与全部调用；资源和外部发送依赖只注入交付 owner。

## 集成排查后的修正

- 完整候选等待人工授权会阻塞原模型事件消费者；新增 `DeliveryPermission` 在本次授权开始的 SDK sequence 之后只消费同 run 的 `permission_request` / `permission_resolved`，owner 按真实 request id + 事件去重。正文仍只有原完整轮消费者一个入口。stop/reset 通过 context 的撤销事件取消授权 SDK task。
- 在任何目标解析或资源准备之前应用 `visibility_policy`，协议静默仅产生 `reply_suppressed` 事实；字面文本策略不受影响。
- 普通候选准备前及发布准入后检查 Gateway 保存的未消费输入，过时输出返回 `stale/new_input`，不启动图片错误反馈。实际输入消费事实释放后续候选；该检查不改变已提交输出的恢复资格。
- 移除旧 handler 构造参数后，更新 `gateway_im_relay`、`shadow_auth`、`group_send_revalidation` 的真实 owner fixture；不添加生产兼容分支。

追加验证：`test_pa_reply_delivery.py`、`test_gateway_im_relay.py`、`test_shadow_auth.py`、`test_group_send_revalidation.py` 与新 `tests/integration/test_pa_delivery_manual_permission.py` 共 **21 passed in 10.09s**。三个人工授权用例走真实 composed Gateway/Kernel broker，无 `can_use_tool` 自动批准：先看见卡片再允许、拒绝或 stop；覆盖卡片/解决事件不重复、批准前无正文/上传、拒绝与 stop 不发图片、stop 后 broker 不再接受旧决定。两条静默单测断言目标解析、资源准备和渠道正文提交均未发生。
