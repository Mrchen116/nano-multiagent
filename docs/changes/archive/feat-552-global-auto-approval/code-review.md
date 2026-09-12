# 聚焦代码审查

按用户明确要求简化大规模 code review：一名独立 finder 合并检查 correctness、删除行为和跨文件调用边界；只对具体候选派另一名独立 verifier。没有七角度并行 fanout、重复实现审查或假想边界的修复循环。

- 初始审查范围：`2fd84b9ac2b1949947ac899b3de7fea1488731ef..acbf06f9be8cad5fd98175f028f785b7cc8dc85a`。
- finder 检查来源投影、持久化/live 恢复、父上下文及 follow-up、计数/分流、hook 结果传播、PA 工具接线和 Bash AST/参数校验，提出 1 个具体候选。
- 定点 verifier 独立复现并确认；修复后同一 verifier 只核验 finding closure 与修复增量。
- 初始完整审查及 C1 closure 对应 `0fbc85b7b9db8f6ae3f1fd724718c0d1af1c095c`；后续代码增量的有效性见下方 patch 审查。本报告与独立产品验收、实现对账分别记录。

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

## Patch review：人工否决、超限类别及隔离启动修复

范围 `21537b980..b218d31e4`，只检查本次五文件增量及其必要调用上下文。一名独立 finder 合并逐行、跨文件、删除 guard 和修复层级检查，未提出新候选，因此没有无目的的二次 finder 或 verifier。

- 显式 `user_deny` 正确优先于此前触发人工入口的分类故障；诊断 metadata 仍保留。
- 已有 `ModelError.details` 为字典，读取其标准 provider 错误字段未新增异常路径。
- `e2e-up.sh` 的 Global journal 清理与新建 IM 数据一致，位于服务存活检查之后；不改变生产启动脚本。
- 独立验证：20 项相关单测、`bash -n` 和增量 diff check 通过。未启动或清理服务、未修改源码；实际重启入口另由产品 reviewer 验收。

本报告有效代码结论更新到 `b218d31e4e27bb2fdad8cbd27bc33e3f92adc817`；完整范围中其余代码沿用上述已通过结论。存活 findings 仍为 `[]`。

## Patch review：写入目标事实

范围 `7c9f5ee37..10bf12c44`，仅检查真实 Cron finding 的修复增量及必要调用上下文。独立 finder 无新 findings（`[]`）：权限检查的 cwd 与实际执行上下文一致，敏感路径仍先经硬检查；存在性只是检查时点事实，仍需分类且执行阶段保留 Read-Before-Write。33 项相关测试及增量 diff check 通过，没有把已不存在的旧测试路径计为通过。

本报告有效代码结论更新到 `10bf12c44`；其余完整范围及两个先前 patch 的有效结论保留。真实 Cron 入口 closure 由独立产品验收报告记录。

## Patch review：普通工作区 Write/Edit 直接放行

2026-09-12，复用原独立 finder `feat552_focused_code_review`，仅审 `ab80c695a` 上的本次未提交增量及调用上下文。沿用用户已授权的聚焦检查方式，未重跑大规模扫描。

结论 `[]`：HookContext 的 session workspace/cwd 与执行器一致；传入与解析路径均检查敏感目录，二者都在 workspace 内才提供 acceptEdits hint；gate 在 deny/ask 后、仅 Auto enabled 时消费；没有按工具名免审。独立临时验证 6 组同名 override，passthrough 仍进入 classifier，deny/ask 均阻止。相关 135 项和 diff check 通过。没有候选需要二次投票，不以此替代真实 Cron 验收。既有完整范围与历史 patch 结论保留；本次改变的行为及旧证据替代范围见 [补漏证据](evidence/workspace-file-fastpath.md)。

审查代码随后原样固定为 `b9a61941a`，`validated_at=b9a61941a`，`executed_base=effective_base=2fd84b9ac`；后续仅报告/契约同步时保留该代码结论。

同一 finder 仅对 `b9a61941a..1cf086696` 的 macOS 系统路径别名补充检查，结论 `[]`。归一匹配完整 `/private/var`、`/private/tmp` 段，敏感检查仍在先，真实目标仍须位于 root 内；独立运行 22 项 gate 用例通过，覆盖别名与双向跨界符号链接。最终 `validated_at=effective_through=1cf086696`；执行和有效 base 仍为 `2fd84b9ac`，原审查结论继续有效。
