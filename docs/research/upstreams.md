# Upstream Reference Repositories

这些仓库用于比较实现、验证设计假设和诊断行为。它们是研究输入；引用结论时仍需记录实际查看的 upstream commit，并回到 nano 当前代码和规范核实。

| 参考项目 | 本地路径 | 主要参考面 |
|---|---|---|
| Claude Code | `~/Repos/opensource-hub/claude-code` | agent core、coding agent harness |
| Codex CLI | `~/Repos/opensource-hub/codex` | coding agent core，与 Claude Code 对照 |
| openclaw | `~/Repos/opensource-hub/openclaw` | 多 channel 个人助手、heartbeat、cron、identity/soul |
| hermes-agent | `~/Repos/opensource-hub/self-evolution/hermes-agent` | 自进化、skills、子 agent、多终端 |
| opencode | `~/Repos/opensource-hub/opencode` | 多 provider/客户端、hook、共享 agent 内核 |
| Better Harness | `~/Repos/opensource-hub/better-harness` | Repository Harness 的工作循环、环境、反馈、门禁与变更安全 |

## 记录一次比较

研究页至少记录：

```text
recorded_at: <date>
nano_commit: <full sha>
upstream: <name>
upstream_commit: <full sha | not recorded>
scope: <files / subsystem / question>
current_landing: <nano code/spec/workflow | pending review>
```

本地路径只负责可发现性，不代表当前 checkout 就是历史研究使用的版本。缺少历史 upstream commit 时保留 `not recorded`，并限制结论的可复现性。
