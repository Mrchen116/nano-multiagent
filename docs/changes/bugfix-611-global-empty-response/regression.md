# bugfix-611: 真实模型场景验证

## Claim / Baseline

2026-10-15（Asia/Shanghai），在 `cab844d6c` 上核对全局 Agent 的先回应、必要进度、非空内部收尾、公开静默边界及空响应恢复。模型为 `codexOAuth:gpt-6-astra`，reasoning=medium，经本机 LLM_PROXY 的 Anthropic Messages 入口；DSH 为仓库锁定的 0.2.1-alpha.1。

## Method

- 在仓外临时目录创建独立 DSH home、六个 session、六份 workspace，真实读取/写入合成材料。每个场景以系统 Inbox wake 开始，再由 inbox check/read 获取真人任务；任务本身没有提醒模型先确认或更新进度。
- 使用当前分支真实 RuntimeClient、profile、提示词、工具与原生 retry，模型回答未被 fixture 代写。
- Inbox 产品接口和 send_message 投递端由测试 harness 接收，只允许各场景自己的虚拟目标；不连接真实聊天。权限设为测试用跳过模式，因此不验证审批策略。
- 五个场景全程透传真实模型；empty_retry 场景在读文件后的首次模型请求注入一次合法 Anthropic 空 end_turn，其他请求均透传真实模型。
- 重试使用 DSH 默认 provider 策略（normal，maxRetries=5），没有测试专用的重试循环。
- 临时命令：`node /tmp/nano-611-live/run.mjs resume empty_retry`；`node /tmp/nano-611-live/run.mjs audit no_reply idle blocked`；`python3 /tmp/nano-611-live/evaluate.py`。harness 为本次证据工具，不纳入永久测试套件。
- 以持久 session 事件序号检查 send_message 是否早于 read、进度是否早于报告写入、最终交付是否晚于写入；公开消息另记录真实时间。检查终态、非空内部收尾、重试事件和实际文件产出。

## Result

6/6 通过，每个场景执行一次；本轮没有新增产品代码修复。

| Case | 输入与判据 | 实际观察 | 结果 |
|---|---|---|---|
| resume | 读两份经历/岗位材料，输出三条可信简历要点 | 17.4 s 确认，随后读文件，34.6 s 交付；43.1 s 完成并留下内部说明；公开消息共 2 条 | Pass |
| audit | 逐份审查六份发布材料，找出矛盾并写 audit.md | 20.1 s 确认；67.7 s 报告已发现的风险和下一步；写入报告后 181.2 s 交付，187.4 s 完成；公开消息共 3 条 | Pass |
| no_reply | 读状态并写 checkpoint.md，明确不发任何消息 | 文件真实写入，公开消息 0 条；42.1 s 完成，内部记录遵守不回复要求 | Pass |
| idle | 空 Inbox 的系统唤醒 | 公开消息 0 条；13.0 s 完成，内部说明无待读事项 | Pass |
| blocked | 请求读取不存在的库存文件并计算 | 18.2 s 确认，读文件失败后 27.9 s 说明阻塞并请求文件/路径；33.1 s 完成，未编造计算结果 | Pass |
| empty_retry | 读两份文件后注入一次空 end_turn | 真实 pi adapter 分类为 EMPTY_RESPONSE，原生 llm/retry 一次后模型恢复；公开确认与结果各 1 条，31.1 s 完成并有内部收尾 | Pass |

### 长任务中途公开更新的实际文本

> 已逐份读完 checklist 及其列出的五份证据文件。发现校验和不符、集成回归失败、两节点版本不一致、回滚包失效且逆迁移未实现，以及原型截图被签为用户旅程通过；当前不满足发布条件，正在将逐项依据及补证要求写入 audit.md。

报告实际包含预置的校验和差异、失败回归、节点版本不一致、回滚包过期、缺少逆迁移、原型验收冒充真实验收，并明确材料陈述不等于生产在线证据。

### 空响应恢复

`empty_retry` 的原生事件：step=5、failure.code=EMPTY_RESPONSE、retry=1、maxRetries=5，退避约 499 ms。随后成功送出结果；没有重发早先的确认，也没有把空返回直接判作完成。

## Locator / Cleanup

- [脱敏场景结果及工具顺序](evidence/real-model-cases.json)：输入任务、session ID、公开消息、内部收尾、计时与断言结果，不包含完整系统提示词、凭据或模型内部推理。
- 仓外原始证据：`/tmp/nano-611-live/nano611-<case>-<timestamp>/`，包含请求/响应、原生事件和合成文件。模型代理日志按相同 session ID 定位。
- 两批 RuntimeClient 均执行 shutdown 并等待退出；临时 HTTP 端口 58305、58424 已关闭。临时数据仅用于复查，未提交原始日志、profile 或数据库。

## Limit

这是真实 DSH + 真实模型的集成场景测试，不是生产 Web IM/飞书送达验收。产品 Inbox 和发送出口、权限使用隔离 harness；未覆盖真实审批、生产网络投递、既有超长上下文或所有模型。单次通过不代表模型行为必然稳定。本报告由主会话执行，不代替用户亲自体验或独立产品验收；unit 继续保持 active。
