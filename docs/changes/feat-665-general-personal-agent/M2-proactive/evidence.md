# M2 worker evidence

这些是边界与回执的确定性验证；自主选择是否准备、最终交付和真实浏览器操作由acceptance/evaluation单列。

| 合约 | 可复查测试与实际结果 |
|---|---|
| 查询独立cursor与覆盖 | `apps/im-server/tests/personal-attention.test.ts`真实SQLite消息：分页独立于原Inbox；partial/来源撤销不会给complete覆盖；变更来源使cursor失效。 |
| 主动通知与原交办区分 | 同文件：无host证据需attention；quiet拦探索，原直接请求和真实Schedule来源可回复；错误owner原消息拒绝。实际消息提交前不能伪造sent。跨caller key候选去重，来源变更需重核，已送版本不重复。 |
| feedback、snooze与budget | 同文件：版本冻结、同一业务点击不同HTTP key仅一条原消息，变更后旧卡拒绝；单项dismiss不改主题；host batch变化不破坏同key重放；daily/batch限制；snooze在Schedule创建成功前为pending。`/tmp/pa665-child-return-test2.log`包含attention+PA+native 34 passed。 |
| 真实原生Schedule与开关 | `packages/dsh-integration/tests/personal-context.test.ts`：冷runtime初次catalog正确；独立选中工具在Feature关闭时可用；cron缺失时snooze失败且无完成回执，启用完整依赖后创建真实Schedule并核对ID。`personal-delivery-evidence.test.ts`：重启后的真实定时wake携带原创建人来源，只对该次wake生效，下一人类回合不沿用。 |
| 外部owner私聊同样受控 | `packages/personal-assistant/tests/personal-assistant.test.ts`及`apps/im-server/tests/personal-attention.test.ts`：未经分类外发不dispatch；只能保存adapter真实provider message ID；重复投递复用原收据。实际外部账号本轮未连接，不当外部E2E通过。 |
| 撤权后不再读取 | `personal-sources.test.ts`在排除后插入新消息，source list仅返回id/excluded；search/read/info均拒绝或排除。真实模型泄漏PA-4及全新canary修复复验在acceptance保留；`/tmp/pa665-source-revocation.log`10 passed。 |
| 子执行返回延续原交办 | `personal-delivery-evidence.test.ts`原生return/cancel/restart：真正子执行在后续回合返回时携带原spawn来源；取消不授予，下一无关人类回合不沿用；重启后实际native续用仍可溯源。`/tmp/pa665-child-return-cold.log`4 passed。PA桥忽略模型参数伪造claim，IM重验owner原消息。对应D08真实失败与修复后重跑不得混为一份。 |

真实Web新卡dismiss、snooze实际到期、旧卡不恢复、draft采用不发送、并发409后重新审核只送一份，见acceptance。P01/P03等主动行为的失败或未采到终态按实际evaluation分类，机制测试不替代模型选择。
