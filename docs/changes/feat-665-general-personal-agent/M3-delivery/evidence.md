# M3 worker evidence

| 合约 | 可复查测试与实际结果 |
|---|---|
| 原生执行与canonical Task关联 | `packages/dsh-integration/tests/task-native-execution.test.ts`两种live/cold：真实continuable child等待模型，真实task_graph绑定收到host root id；running不重复调度root，更正needs_coordination使root再协调；canonical移除实际中止；持久重启后旧child接受native消息也不再调用模型、不复活Task。`/tmp/pa665-coldtask1.log`含维护共3 passed。 |
| task/observer最小能力 | `personal-child-delivery.test.ts`两种原生role：task只读显式复制文件、写自己目录、回父；私有文件、shell、memory、任意外发被执行guard拒绝。observer foreground one-shot零工具，返回走native result；schema和实际调用双核对。`/tmp/pa665-observer-test2.log`2 passed。不是OS沙箱。真实child最终上游输入无无关私人canary另见acceptance。 |
| 产物字节/版本/权限 | `personal-artifacts.test.ts`真实workspace文件→host bytes/hash，拒绝child/非PA/越界/symlink/超限；`apps/im-server/tests/media.test.ts`真实文件+SQLite幂等key、旧版bytes、新版revision及hash冲突；真实Web两版下载、外发冻结副本和不同身份权限见acceptance。 |
| unknown不自动重试 | 既有`packages/personal-assistant/tests/external.test.ts`的“never reports completed before the platform response and preserves unknown outcomes across restart”：真实Promise/持久状态转换，平台未返回前不completed，unknown后重复请求不再次dispatch；`apps/im-server/tests/personal-disclosure.test.ts`确认事务后通知失败仍保留committed结果。此处adapter可控，不冒充真实外部平台故障。 |
| 用户配置/默认与技能 | `personal-security.test.ts`真实配置apply后custom指导清空、Skill禁用且不回填；`personal-agent.test.ts`已有custom_prompt保持；升级不自动迁移/启用旧PA主动性。12个按需通用方法在现有`packages/personal-assistant/assets/skills/nano-*`，沿既有Skill安装与选择，不建新loader。 |
| 可运行评测 | collect=58，显式adapter非标题路由；`test_protocol.py`原11+观测结束真实主/子执行稳定等待回归共12 passed（`/tmp/pa665-observe-protocol.log`）。checkpoint、外部缺连接、缺最终provider、执行失败均不同分类，不能用collect/protocol通过代替行为通过。 |

完整CI在最终validation绑定版本。真实同模型多次核心重放及旧基线结果单独汇总，包括实际路线内容错误和已有交办的投递失败；不能因为已经修复而删除旧失败。没有使用生产实例、真实外部联系或交易，没有发布安装包。
