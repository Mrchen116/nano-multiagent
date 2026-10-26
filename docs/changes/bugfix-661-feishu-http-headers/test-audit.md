# 与飞书故障相关的测试有效性审视

## 范围与结论

2026-10-26，基于 main a16859ac4 及本 unit diff。先扫描 apps/packages/Python/Web 的测试入口、显式 mock 和文件读取模式，再阅读飞书解析、渠道业务、生命周期、Node 分区、IM external/PA、WebSocket、知识迁移以及 Web UI 的代表文件。扫描用于定位，不能把 mock 次数或文件读取次数当无效测试统计；文件读取也可能是在核对真实持久化结果。

**已确认一个系统性的接线覆盖空洞，不能据此宣称全仓存在大量无效测试。** 飞书相关三段分别通过，却没有测试实际 Node HTTP adapter。此次保留有独立价值的单元测试，用真实组合测试填补该空洞，不批量删除测试制造数量下降。

## 具体发现与处置

| 已审对象 | 能证明什么 / 不能证明什么 | 处置 |
|---|---|---|
| PA external.test.ts（6 个用例） | owner 标记、离线/去重、未知交付、卡片权限、PA 投影业务；所有 im 回调替身均不经过真实传输 | keep；新增真实 HTTP 组合覆盖缺口 |
| PA agent-lifecycle.test.ts 的 external 用例 | 旧代次图片等待不得跨停用恢复；不是在线入站成功测试 | keep；与成功入站集成互补 |
| Node agent-lifecycle/runtime-partitions | 调度、取消、宿主路由与代次隔离，依赖端口替身；不承担 HTTP 协议兼容 | keep，不用其绿灯证明飞书可用 |
| channels/feishu.test.ts（2 个用例） | 实际消息解析与图片转换；没有真实飞书 SDK 长连接或 provider 回执 | keep；本次不冒充 provider E2E |
| IM e2e/control-work 的 external shadow 用例 | 真服务上的 shadow identity、投影与 fork；请求由自有 f.http 构造，绕过 Node adapter | keep；不是重复的新入站组合测试 |
| IM personal-disclosure | 披露/owner 私聊/回执权限，不能证明渠道消息已正确发包 | keep |
| channels/web-relay.test.ts | 本地真实 WebSocket、线上序列化头、重连/ACK/令牌更新 | keep；这是接线测试已存在的反例 |
| PA knowledge.test.ts | 迁移协调、失败隔离、通知恢复；配置变化由 im 替身模拟，不能代表配置 HTTP 真正落库 | keep，仅作为协调测试；共享 adapter 已新增协议保护 |
| Web chat-workspace.integration.test.tsx | 组件与状态恢复组合；mock user-stream/FakeWebSocket，不是客户端—服务端兼容验收 | keep，结果按组件集成解释 |
| builtin-skills / capability-editor / DSH knowledge-policy | 文件 I/O、公共能力 fixture 或真实 native runtime 的可观察结果，不是简单读源码比字符串 | keep，不因 grep 命中文件读取而误删 |

## 可复查反证

暂时恢复旧对象展开实现，运行原有 external、PA lifecycle、knowledge 加新增两份测试：原有 15 个用例通过，新增 5 个失败。恢复修复后，相邻 14 文件 84 用例全部通过。原实现还暴露 tuple headers 丢失与大小写 Authorization 合并问题，同一修复覆盖，未发现第二处生产 RequestInit headers 对象展开。

该实验说明原测试对这一失败原因无感，并不说明原有 15 个测试对其他失败原因无用。

## 后续边界

本次没有做全仓逐测试 mutation 或实际外部服务验收，不给出“全仓有效率”。现有文档规范已经要求最低可观察边界和避免 mock 调用次数充当结果；本次问题是没有落实，不再添加平行制度或静态规则。实际 Feishu SDK 连接/回调、真实模型消费及回复仍须隔离产品环境或用户真实旅程证明；生产不自动制造测试消息。
