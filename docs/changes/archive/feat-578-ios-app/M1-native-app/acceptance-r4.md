# feat-578 — 原生产品功能续验 R4

> 2026-10-05 11:57–12:03 Asia/Shanghai；增量报告，保留 R1/R2/R3 与 acceptance-visual-r3 的有效证据。原生 binary 051abdcf8 / visual-build-r5，390 iPhone14 / iOS26.4 Simulator；服务端开始为 c4794acef，IM69765，主 Gateway45904，均由 caller 管理。本段结束已交还 UI 供 caller 窄修复更新，尚未验新 binary。

## 结论

**fail / 未收口**。飞书专用通道的凭据与真实连接生命周期有新增通过证据；心跳续验遭真实 operation_conflict，未能关闭 R3-01，并发现错误反馈不在当前视野的 R4-01。未完场景不扩大为 pass。没有重跑 P6 视觉矩阵。

## J16 心跳回读窄复验与冲突

解锁后 fresh AX 确认上轮添加通道表单保存仍禁用，取消该表单。进入 e2e-peer 配置，以 click/typeText/Tab 输入 24h、03:00、03:01 并开启心跳；真实画面确认字段完整后点顶部保存。约 11:58–12:00，当前滚动位置全表单一直 disabled，滚至顶部仍没有可见 pending/rejected/错误文案。截图 `output/feat578/reviewer-r4/heartbeat-save-disabled.jpg`。返回触发“离开并放弃未保存草稿？”；确认离开后回详情。没有重复提交，没有声称保存成功。

caller 辅助观测：Gateway 未暂停、两个节点 online，operation 实际已 rejected / operation_conflict。此为后端状态辅助证据，不能替代原生反馈。caller 正在修复空 cadence 指纹冲突和保存后反馈可见性；本段尚未产品复验。R3-01 继续未关闭。

## J17 专用飞书通道真实闭环

授权仅限 e2e Agent 与专用测试 Bot；caller 已确认 listener 锁和私钥前置。未发送外部真人消息、未改飞书平台权限、未打开旧私密 e2e 聊天。凭据只在 CUA 内存读取指定 env，真实 typeText 输入 SecureField，未打印/截图 Secret；提交后敏感变量清除。

1. 新增：空字段保存禁用；填完整后保存成功，提示“期望配置已保存。请返回查看实际连接与诊断”。完成返回先见 v1 applied / 连接中，随后实际“已连接”，各权限 satisfied。截图 `feishu-connected.jpg`。
2. 编辑回读：App ID 正确，替换密钥默认关闭，无已保存 Secret 回显。把 App ID 临时改为 cli_test_changed，替换开关自动 true 且不可关闭，空 Secret 时保存禁用；未提交这个错误 App ID。截图 `feishu-appid-requires-secret.jpg`。
3. 保留：恢复原 App ID，关闭替换开关，保存；返回 v2 applied。此步复用原凭据，无需重新输入。
4. 替换：重新编辑，开启替换但不填时保存禁用；输入同一现有测试 Secret 并提交，返回 v3 applied，实际恢复“已连接”。这是替换路径验证，不是飞书平台密钥轮换。截图 `feishu-replaced-connected.jpg`。
5. 停用：点击停用，期望状态停用、v4 applied、实际已停用三者一致。截图 `feishu-disabled.jpg`。
6. 删除：确认“删除通道并停止连接？聊天历史保留。”后实际“暂无通道”。截图 `feishu-deleted.jpg`。没有在该通道发送测试消息，因此历史保留语义尚未本轮实证。

连接详情还发现 minor：`feishu.receive_p2p · satisfied` 展开却显示 “The bot cannot receive direct messages.” 和 “Grant the recommended scope and publish the app.”，与 satisfied 结论矛盾。截图 `feishu-satisfied-detail.jpg`。未根据此文案去修改平台权限。

## 问题与场景增量

| ID | 级别 | 状态 / 下一步 |
|---|---|---|
| R4-01 | major | 保存已遭冲突拒绝，但当前页面只剩 disabled 表单，顶部没有可见原因；返回仍问放弃草稿。需修复后从同一底部保存路径确认结果可见、可恢复。caller 已接手修复。 |
| R4-02 | minor | satisfied 权限详情显示失败补救文案；宜按当前诊断状态展示描述。非本轮额外实施门禁。 |
| R3-01 | major/open | 未能完成 24h/时段成功保存及重开回读；不能借后端修复声明关闭。 |

| Scenario | 当前状态 | 本轮增量 / 剩余边界 |
|---|---|---|
| S18 | fail | 前轮 pending/非owner/冲突恢复证据保留；本轮新冲突反馈不可见 R4-01 待闭环。 |
| S19 | fail | R3 Cron/HEARTBEAT.md 与 R2 Skills 用量证据保留；心跳成功重开回读仍未完成。 |
| S20 | pass（本轮凭据旅程） | 新增、密钥不可读、保留、替换、改 App ID 必填约束真实完成；不等价平台换密钥。 |
| S21 | inconclusive | 新增连接、停用、删除实际状态已完成；权限缺失分支/重连/离线及历史保留未全覆盖。 |
| 其余 S1–S30 | 保留 R2/R3 | 无新增证据不扩大通过；History65、合成图片撤权、多节点路径等待续，S29/S30与真机 IME/VoiceOver后置。 |

## 安全交接

12:03 左右已告知 caller 无在途操作，可更新本次隔离 IM/Gateway/native。UI 在 e2e 外部通道空状态。当前通道已删除，凭据内存变量已清空；没有新增本地服务。截图为本地产物不提交。后续先验证 caller 新版本与服务，再按增量继续；本报告不是整个 App 的验收通过结论。
