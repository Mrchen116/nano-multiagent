# 聚焦代码审查

按用户明确要求简化大规模 code review：一名独立 finder 合并检查 correctness、删除行为和跨文件调用边界；只对具体候选派另一名独立 verifier。没有七角度并行 fanout、重复实现审查或假想边界的修复循环。

- 初始审查范围：`2fd84b9ac2b1949947ac899b3de7fea1488731ef..acbf06f9be8cad5fd98175f028f785b7cc8dc85a`。
- finder 检查来源投影、持久化/live 恢复、父上下文及 follow-up、计数/分流、hook 结果传播、PA 工具接线和 Bash AST/参数校验，提出 1 个具体候选。
- 定点 verifier 独立复现并确认；修复后同一 verifier 只核验 finding closure 与修复增量。
- 当前有效代码结论对应 `0fbc85b7b9db8f6ae3f1fd724718c0d1af1c095c`。这份报告不代替尚未完成的全局产品真实旅程验收。

## C1：模型 fallback replay 丢失输入来源（P1，已关闭）

模型首次调用在真实输出前失败，PA fallback 通过 `replay_last_user(origin=HUMAN)` 重放输入。旧重放代码只取历史正文/结构化内容，丢弃已持久化的 context_origin/context_parts；新的 loop 来源推导遂把系统通知或 Agent 消息当成真人输入。真实 SDK + scripted provider 的隔离复现中，首次主请求有系统来源模板，重放 classifier 却出现裸 `{"user":"Automatic event: publish release"}`。

该调用是现有 PA fallback 的真实接线。拒绝重放的 guard 仅覆盖已产生真实输出，不能防住首个请求无输出的失败。候选经独立验证为 CONFIRMED；不声称脚本 provider 证明了真实模型必然错误放行。

修复 `0fbc85b7b`：重放使用原消息正文和 metadata 恢复输入；将既有 stranded pending continuation 的恢复逻辑放到共享的 core message_context helper，保留每段原来源、同轮真人标记、委派上下文以及图片数据。没有根据失败后的调度枚举重新猜来源。

- system、agent、mixed 三个真实 SDK 接线回归：先 3 failed，修复后通过。
- 实施者相关 replay/runs/approval 检查：58 passed。
- 独立 closure：原复现重跑后仍保留系统来源模板；replay、registry executor、approval context 相关 16 passed，diff check 通过；该问题 closed，修复增量未发现同类回归。

当前存活 finding：

```json
[]
```
