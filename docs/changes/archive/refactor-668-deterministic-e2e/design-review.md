# Design Review

## Round 1

### Metadata

- reviewer: 独立 reviewer `/root/design_review`，非设计作者。
- reviewer target: `refactor-668-deterministic-e2e` 的 `motivation.md`、`design.md`、M1-e2e；基线 `687c9c1218c09a3e4c37f0247fa4b07287b1431a`，开始取证时 main 工作区干净。
- review_mode: full。
- mode_reason: 首轮 Gate 2，完整核对目标、现状、方案边界、no spec delta 与 milestone。
- started_at: 2026-10-27T21:39:03+08:00。
- completed_at: 2026-10-27T21:39:36+08:00。
- duration: 33 秒（结论收口记录窗口；此前源码取证未单独计时）。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案允许确定性驱动真实产品链，并将删除旧覆盖的前提明确限定为同一失败原因已有通过验证的替代保护。没有发现会使实施实质走偏的未收口设计问题。此结论是设计可实施性判断，不代表替代测试已实现或已通过。

### Coverage 与证据

1. **需求与基线。** 独立执行 `.venv/bin/python -m pytest tests/e2e --collect-only -q`，实际收集 32 项，其中 critical_paths 27 项、目录外环境测试 5 项。结合 `critical_paths/conftest.py` 的 live fixture 及测试依赖核对 14 项 live 路径。`scripts/e2e-critical.sh` 当前确实主动开启 live 开关。设计将全部 32 项纳入逐项映射，而非只改标题提到的工具、fork 和 restart，符合原始诉求；coverage.md 是实施交付物，不将尚不存在的映射冒充已验证证据。

2. **产品组装与职责。** `scripts/e2e-up.sh:237-285` 启动仓库构建的 IM 与 Node CLI；`apps/node/src/main.ts:110-155` 通过 `RuntimeSupervisor` 初始化真实运行时、恢复 binding、安装消费者并配置 provider；`packages/dsh-integration/src/client.ts:41` 后的客户端经 stdio 管理子进程。`SPEC.md:40` 规定的运行时边界得到保留。HTTP recording 响应属于测试夹具职责，不要求产品新增测试开关、第二套循环或直接依赖 DSH 私有实现。

3. **复用与接口可行性。** `test_agent_config_context_continuity_critical_path.py:227-370` 已支持 script/env 参数、全部 provider URL 重写、真实栈启动、JSONL 请求记录和 finally 清理；`anthropic_sse_compaction_recording.py` 已有真实 SSE 工具调用响应和 tool-use/tool-result 配对观察能力。提取现有共享 helper、仅增加当前场景需要的响应，比引入通用场景 DSL 更符合维护边界。脚本必须根据实际请求与工具结果推进，且断言独立落在真实出站请求、工具副作用和公开结果；这一限制足以排除“fixture 直接宣布成功”的假绿设计。

4. **Context 与恢复。** 设计决策 3 明确普通重启、压缩重启、fork 截断和源/分支隔离各自的保护，检查 messages/system/tools 和工具配对而非回复复述。既有 recording fork 测试实际只验证历史配置与前缀存在，设计已要求补截断与独立性，未将旧测试误称为完整替代。`packages/dsh-integration/tests/history.test.ts` 保护原生 fork/compact/restart，不能单独证明 IM fork 接线；设计保留 IM recording 路径是合理取舍。本次不修改产品 Context 的来源、选择、交付或恢复逻辑，因此不触发完整 Agent Context 设计审查；已核对其验证观察点，不能用 stub 成功外推模型理解与自主规划能力。

5. **协议、工具与跨进程覆盖。** 原生 `communication-native.test.ts` 使用真实 RuntimeClient，但 `product.call` 是测试 handler；`workflow-lifecycle.test.ts` 经运行时进程保护任务/child 生命周期；`personal-assistant/tests/heartbeat.test.ts` 使用替身 RuntimePort。它们分别保护运行时或产品模块边界，不能自动替代 HTTP/WS、IM 配置传播、定时触发后真实交付、`/stop` 入口等全链路风险。设计决策 1、4、5 要求按实际失败原因判断并保留接线缺口的真栈覆盖，因此不存在按名称直接删除的授权。Global J2 去除订单计算与自主规划，保留 Inbox 正文实际消费、同一 child 跟进及真实 dispatch/持久事实，能在不依赖真实模型的前提下保护机制。

6. **失败观察与隔离。** 已检查原 bash 超时、后台通知、stop、subagent failure 测试，它们多处只凭最终文本或完成事件推断工具/失败曾发生。设计要求工具真实执行及下一请求中的 tool_result，可以使替代证据更强；下游应以此要求核实真实失败或取消发生，不能把脚本返回普通文本算作失败分支验证。当前 heartbeat 测试设置 5 秒 cadence 且没有 case 级撤销，设计明确 finally 关闭/撤销。function 级 stub 栈已有 teardown 进程和端口检查，适合复用。无生产数据、模型账号、真实代理或部署动作。

7. **契约、文档与实施出口。** 仅修改测试、fixtures、入口及开发文档，无产品行为变化，no spec delta 与无部署迁移合理。`testing.md` 继续拥有测试策略，catalog 和 fixture README 更新其使用说明，避免形成第二份权威。单一 M1-e2e 范围无并行冲突；退出标准包含 32 项处置、无外部 provider、实际请求/工具结果证据、受影响低层与完整 E2E、本地 CI、独立 code review 和 verification，足以承接设计中的删除前保护要求。

### 历史问题闭环

无；本轮为 R1。

### Issues

无。

### Recommendations

- **R1-R1（可选措辞修正）**：`design.md:19` 的“TS 原生 profile 已覆盖 … heartbeat 和路由”建议改为“已有 TS 原生运行时及产品模块测试覆盖 …”。实际 heartbeat 文件使用替身 RuntimePort，communication 原生测试也 stub 了 product.call。正文已经要求同因证据和跨进程缺口保护，因此这处概括不阻断；实施 coverage.md 应精确写出各保留测试的 seam，避免后人把模块保护误读为 IM 真栈保护。

### 验证边界

本轮只做设计、源码和测试收集审查，没有运行真实 LLM、没有启动产品服务，也没有执行 TS 或真实进程 E2E。新 deterministic fixture 的稳定性、全部替代断言及回归通过状态，留给实施和既定验证门禁取证。本 reviewer 仅新增本报告。

### Author Resolutions

- R1-R1: accepted。按实际测试 seam 修正 design 的概括措辞；不改变架构、范围或退出标准，R1 retained。无未闭环实质问题。
