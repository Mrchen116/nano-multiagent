# R15 可撤销联系人限制验收

结论：桌面限定旅程 PASS；移动端由 caller 追加证据。本报告不把后端测试或合成 fixture 宣称为真实模型群聊样本。

验证基线：`41ce20314fd7c156b04d941cfd4a5dc5a8582dd7` + R15 frozen dirty diff，caller 提供已重建服务 `127.0.0.1:53808`。独立 CUA 1280×720 tab，R12 可丢弃主人、小夏 PA。未改主 nano 的数据、权限或名字，未启动额外模型节点。

## 实际旅程

| 场景 | 观察与结果 | 裁决 |
|---|---|---|
| 当前限制可辨认 | 配置页 Blocked contacts 卡显示数量 1、林悦、最新原因、Unblock；解释直接请求限制、群消息仍送达并提示风险、本人聊天不受影响。没有永久信用等级或人品标签 | PASS |
| 完整历史按需展开 | Reasons and records 展开 5 条历史，包括本轮两条合成来源与前轮三条证据 | PASS |
| 主人观察自己 PA 私聊 | 点击原消息进入林悦 ↔ 小夏，准确定位；底部明确 Agent collaboration · read only，无发送框。数据库成员仅林悦与 PA，未把主人加入 | PASS |
| 非成员私群证据 | 该证据只提供 View risk notice，并说明主人不是原群成员；点击定位 canonical PA 内的主人通知，不授予私群访问 | PASS |
| 解除失败 | 仅针对 R12 binding 的临时 SQLite trigger 令 delete 失败；UI 保留联系人、Unblock，并显示 The change was not saved. Please retry.；policy、blocks、incidents 与 before 完全相同 | PASS |
| 成功重试 | 清除 trigger 后点击同一按钮，名单变 0，显示正常检查未来请求的成功说明；刷新后仍 No blocked contacts | PASS |
| 限制与历史分离 | 当前 block 删除，revision 4→5；incident 数量、状态、理由均与之前完全一致，未删除历史 | PASS |
| 桌面层级 | 访问范围后独立卡片；联系人与解除动作同一行、原因和详情次级；失败红字在卡内。实际画面能直接判断当前限制与解除后果 | PASS |
| 手机卡片与列表 | caller 使用同一合成 fixture，在 583×827 视口完成配置卡→展开证据→原私聊只读→返回→解除→刷新；按钮和原文正常换行，解除后名单保持为空 | PASS（caller） |

## 合成资源与证据

以下来源明确为本轮合成 fixture，不代表新分类器/通知生成样本：

- PA–真人只读来源：`http://127.0.0.1:53808/chat/r15_pa_peer?message_id=r15_msg_1`
- 私密群不提供给主人直接入口：`r15_private_group`，原消息 `r15_msg_2`。
- 主人通知替代入口：`http://127.0.0.1:53808/chat/c_dc8cd27d6aee?message_id=r15_notice_2`

原始目录：`data/acceptance/feat-616/r15-blocked-contacts/`；截图包括 blocked-records-desktop.png、owner-readonly-dm.png、private-group-notice.png、unblock-failed.png、unblock-success.png；before.json / after-failure.json / after-success.json 记录持久化比较。失败注入 trigger 已删除。

## 边界

群内接收风险提示、正常群发与原生 direct 拒收由 caller 后端测试覆盖，本轮没有真实模型样本，不扩大本报告 PASS 范围。复用原配置入口；没有对其他主人/普通 Agent 的权限做本轮新增 UI 实验。当前名单删除后的历史通过数据库与原通知留存验证，未声称新增历史管理页面。

交接：按 caller 指示，成功解除及刷新验收完成后，通过 R12 owner API 对 r15_incident_2 再次执行 block，供 caller 窄屏检查；最终卡片恢复 1 人，截图 final-blocked-desktop.png。保留 R12 登录供接续，由 caller 完成后恢复 nano。自己的 tab3 已关闭。


## Caller 窄屏与最终验证补充

583×827 实际 IAB：`blocked-mobile.png`、`readonly-mobile.png`、`unblocked-mobile.png`。独立桌面 reviewer 的失败/成功证据保留；caller 另验证窄屏返回、解除以及刷新后的空名单。操作均在 R12 disposable fixture；主账号的聊天排除和联系人状态未修改。

最终：后端/runtime 448 项、Web 933 项、Python 62 项通过（31 E2E 不在本次 Python 门禁）；IM/PA build 与 typecheck、前端 build、docs-check 通过。contactRisk 的完整传递链由服务端/运行时测试验证；此次不宣称新增真实 LLM 套话对抗样本。测试暴露的一条旧 PA-human DM owner_can_read=false 断言按新只读权限改为 true，并保留私密群 false 断言。
