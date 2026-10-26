# bugfix-661: As-built Design

> 本文在实现后形成。快速开发，未记录用户验收，因此保持 active。

## 实现范围

- Base: 09eb59bd9073bfd1d071bdfc84bf75a0be99c018（实施分支 parent）。部署故障基线为 a16859ac4；两者只差生产验证范围的文档/Skill 更新，生产代码相同。
- 生产修改：apps/node/src/main.ts、apps/node/src/im-http.ts。
- 测试：apps/node/tests/im-http.test.ts、apps/im-server/tests/external-ingress.test.ts。
- 首文档与测试审视属于同一变更；未修改 PA/IM 业务策略。

## 最终结构

`main.ts` 保留调用时读取当前 relay registration token 的职责，委托 `requestIm(baseUrl, token, path, options)` 发送。adapter 负责已有的 ws/wss → http/https 转换、十秒超时、非成功响应报错和 JSON 解码。

唯一行为修复是通过 `new Headers(options?.headers)` 复制 headers，再以大小写无关的 `set` 设置当前 Authorization。接受 RequestInit 声明的三种 headers 形式；不修改调用方对象，不新建兼容分支或注入 fetch mock。

调用链：Feishu 已解析消息 → ExternalChannels 持久化与生命周期包装 → requestIm → HTTP → IM 鉴权/JSON 或图片解析 → shadow message → PA durable source event。测试中的 provider 与模型侧是替身，HTTP、IM 鉴权、路由、附件存储、消息及来源事件是真实实现。

## 状态、恢复与失败边界

无 schema/config/identity 迁移，无一次性部署脚本。原已接收但未投影的消息由既有 ExternalChannels.recover 在连接恢复后处理；沿用原 provider message ID、shadow 幂等键和生命周期代次，禁用过的旧代次不复活。

测试模拟 IM 已提交但调用方未收到回执，重建渠道对象后恢复，确认只有一个入站消息和一个 PA source event。没有改动实际 Feishu SDK、LLM 或回复出口，因此该证据不宣称真实飞书端到端回复已完成。回滚代码会恢复本次故障；无需回滚数据库。

## 测试策略与处置

- 现有 external、lifecycle、knowledge、Feishu parser 测试保留：各自保护业务状态、代次、解析等独立风险，不能作为 HTTP 接线证据。
- 新增 Node adapter 用例负责三种 RequestInit headers 及凭据替换/调用方不可变性，在本地 HTTP 接收端观察。
- 新增 IM external-ingress 用例负责生产调用方组合后的真实路由兼容、图片内容类型和重启去重；这是原有测试没有承担的集成风险。
- 均由根 `pnpm test` 收集，不引入外部账号、生产数据或固定端口。文件均小于 400 行，关闭服务并删除临时目录。
- 旧错误实现 mutation：新增 5 个用例失败，原有 15 个 external/lifecycle/knowledge 用例通过。修复版相邻套件 14 文件/84 用例通过。

## Canonical 与 Context 影响

无 spec delta：恢复 gateway/external-channels.md 已承诺的渠道入站及重放行为；不新增产品能力。

受影响的 Context surface 是既有飞书原文及附件进入 PA 来源事件的交付链。来源 owner、原文、生命周期与披露规则均由原实现继续决定；独立 code review 按 agent-context-review 的 Implementation Review 核对这段交付，不把入站持久化等同模型已经消费。

## 验证状态

本地窄测试、build/typecheck、共享 runtime、文档/Python/ruff 与独立审查通过。完整 TS 首次 755/758，通过失败项串行复跑 10/10；详见 [code-review.md](code-review.md)。用户验收、PR、合并、生产部署未完成。
