# M1 实施记录

## 基线与范围

- unit 分支 `unit/feat-623`；文档基线 `e63501054`，以 `2f789f62a` 显式整合未合并 PR #371 的 `bc59dfa72`。没有自行合并依赖 PR，也没有部署生产。
- IM 可信事实与授权修改见 [IM 实施证据](im-identity-evidence.md)。主实施负责 PA 同一 Inbox 的事实投影、时序与迁移恢复，以及运行时固定指导；不改已有 custom_prompt。

## 测试策略

| 风险 | 既有保护与处置 | 实施与证据 |
|---|---|---|
| 主人身份、参与关系、真实授权与外发失效 | IM personal-sources/disclosure/agent tests，rewrite-merge 旧 role 断言，其余 keep | 见 IM 证据；可信事实统一，guard 与完整上下文分离 |
| 完整摄取、分页/附件来源、通知与消费独立 | PA inbox.test.ts keep 并扩展 | 旧实现下新增三个用例失败，恢复新实现 9/9；`/tmp/feat-623-inbox-{red,green}.log` |
| PA 观察批次与原群触发、旧未读恢复/ACK/撤销 | 普通 Global attention/global tests keep；新增 personal-attention.test.ts | PA 特有后台期限属于独立时序风险；旧实现四用例均有行为断言失败，新实现与 Inbox 共16/16；`/tmp/feat-623-attention-{red,green}.log` |
| 非主人请求审核与当前风险提示 | personal-assistant.test.ts rewrite-merge 可信准入 fixture | PA 包127/127通过；新增生命周期用例另在上述16项内 |
| 真实 DSH 下一 step steering 与 onlyIfIdle 空闲接纳 | global-inbox-native.test.ts keep 并扩展 | 真子进程、锁定 DSH、确定性模型 fixture；原及时更正与 PA 忙碌背景合并均通过。与 personal-security tests 合计7/7；`/tmp/feat-623-native.log` |
| 普通工具权限、能力目录与已有 editable prompt | personal-security.test.ts keep | 与真实 DSH fixture 同轮通过，不替代真实模型意图验收 |

新永久测试均归属现有 backend Vitest gate；无一次性验收脚本进入长期测试集。构建 `pnpm build` 已通过；PA typecheck 已通过。完整 CI、独立产品与静态门禁在最终版本继续记录。
