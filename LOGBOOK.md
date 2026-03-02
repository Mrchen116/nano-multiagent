# LOGBOOK (经验 / 预防规则)

- 约定：本文件只记录可复用的经验（坑/风险/预防规则/操作手册），不记录每个 Roadpoint 的实现思路与过程性决策。
- Roadpoint 的方案、证据、回滚点与提交哈希请写到：`PROGRESS/<milestone_id>-<简述>.md`。
- 迁移：历史工作记录已归档到 `PROGRESS/legacy-logbook-work-notes.md`。
- Hook 加载断言规则：涉及 `load_hooks_from_directories` 的测试不要写死“已加载模块总数”，应断言关键模块（source/file_path/event）存在，避免内置 hook 增减引发脆弱回归。
- Tool-calling 蓝图与实现错位（“有 tool-calling 设计，但运行仍像单次文本”）的根因：只验证了普通文本 happy path，没有在 CLI/HTTP 真实入口上验证“LLM 首轮返回 tool_call 后必须继续执行工具并二次请求模型”。设计层写了 loop，不代表接线层（runtime-loop-tool registry）真的打通。
- 早期可检测信号：
  - 首轮模型响应携带 `tool_calls`，但请求链路只出现 1 次 `LLM.generate`；
  - 返回 `stop_reason=tool_registry_unavailable` 或 assistant 文本为空；
  - CLI 只看到 `send failed: timed out`，日志/输出里缺失 `trace_id` 和上游错误 message（root cause）。
- 强制防回归规则（测试门禁 + 验收口径）：
  - 门禁 1：必须有一条集成测试使用 mock LLM（首轮 `tool_call`、次轮最终文本），并断言“工具实际执行 + LLM 至少两轮 + 最终 assistant 文本来自工具结果”；
  - 门禁 2：必须有一条 CLI/HTTP 集成测试断言超时失败输出同时包含 `model_error`、`trace_id`、根因 message（如 `root_cause=...`），不能只验“timed out”字样；
  - 验收口径：主链路验证必须经过真实入口（CLI -> HTTP API），不接受仅 unit mock 的“看起来支持 tool-calling”结论。
- 外部依赖优先归因规则（2026-03-02）：当现象只在某上游/代理项目出现（例如同一请求在本项目逻辑正常、但上游返回空 payload），必须先输出“外部项目可复现实锤 + 责任边界 + 修复建议”，默认不要在本项目硬做语义兜底改造。
- 执行动作顺序：先最小复现（同请求直打上游）、再给结论与 owner（哪个仓库哪段转换逻辑）、最后再决定是“转修上游”还是“本项目临时兼容”；未经用户确认不做跨边界策略改动。
