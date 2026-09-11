# feat-552 实施与验证记录

实施方式：用户授权的 change-orchestrator-simple；精简重复台账和大规模 code review，保留相关回归、真实产品旅程与聚焦改动的独立检查。

- Unit branch：`codex/feat-552`。
- 实施基线：`origin/main=2fd84b9ac2b1949947ac899b3de7fea1488731ef`。
- Gate 2：[design-review.md](design-review.md) Round 5，Approved，0 CRITICAL / 0 WARNING；17 个受审输入哈希未变。相对审查代码基线的新 main 只合入 JPEG 修复及旧 active 文档清理，无权限代码交叉。
- 现场：专属 unit worktree 与独立 Python 3.12.9 虚拟环境；主 checkout 的既有改动保留。

## 基线验证

2026-09-12，在任何产品修改前运行 Auto gate/config/Broker/dispatch/allowlist/result projection 及 Bash unit/integration 相关套件：148 passed。按本次新增/删除文件计算的整仓文档检查：0 issues。

## 实施范围与测试策略

- M1：共享策略/默认规则、来源投影与实时登记、拒绝计数/入口分流、子任务继承、Bash 语法和命令参数等价检查。
- M2：PA Inbox/send_message、共同 runtime 场景装配、global wake、Heartbeat/Cron 来源和交互接入。
- 优先更新已有 gate/config/Broker/result-projection、Bash、runtime/child、PA 入站与调度测试；新风险放在最低能暴露它的模块/集成边界，不重复保护同一失败原因。
- 固定 CC 规则/语法迁移需有完整映射和差分证据；协议层 fixture 与真实模型旅程分别记录，不能互相替代。

当前状态：实施中，尚未形成新机制验收结论。
