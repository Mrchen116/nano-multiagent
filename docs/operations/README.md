# Operations

本目录负责运行当前系统：启动日常使用的 IM、Gateway 与 Web IM，管理 Gateway 持久实例，观察运行状态，并在故障时收集证据和恢复。开发环境、测试命令和 worktree 临时服务由 [`../development/`](../development/) 负责。

## 从哪里开始

| 任务 | 先读 |
|---|---|
| 个人生产：mini 唯一 IM + 本机/mini 双 Gateway | [`prod-fleet.md`](prod-fleet.md)；执行部署用 skill [`prod-fleet-deploy`](../../.claude/skills/prod-fleet-deploy/SKILL.md) |
| 第一次启动本机 IM + Gateway + Web IM（开发主链路） | [`local-stack.md`](local-stack.md) |
| 编写 Gateway 配置，执行 start / stop / restart | [`gateway.md`](gateway.md) |
| 配置飞书通道或 `web_search` provider | [`gateway.md`](gateway.md) |
| 页面打不开、节点离线、Gateway 启动失败或通道异常 | [`troubleshooting.md`](troubleshooting.md) |
| 在 worktree 内为开发或 E2E 启动隔离服务 | [`../development/worktree-runtime.md`](../development/worktree-runtime.md) |
| 核对 Gateway 或 IM 应该表现出的 current behavior | [`../specs/gateway/`](../specs/gateway/spec.md) / [`../specs/im/`](../specs/im/spec.md) |

## 使用边界

Operations 文档回答“当前系统怎么运行、怎么观察、出问题怎么恢复”；`docs/specs/` 定义系统应该表现出的行为；日志、状态文件和页面状态证明某一次运行实际发生了什么。三者发生冲突时，保留本次运行的原始证据，再按 [`../README.md`](../README.md#冲突怎么处理) 的规则判断是实现故障、文档漂移还是环境问题。

日常操作遵循三条原则：

1. 对 Gateway 的每次启停都显式确认使用的是哪一份 config；同一 config 只对应一个后台实例。
2. 判断可用性时组合进程、`.gateway-state.json`、`gateway.log`、IM 节点状态和真实用户路径，单个旧 PID 或历史日志不能证明服务仍在运行。
3. 关闭整套服务时先停 Gateway，再停 IM，让 Gateway 有机会收拢任务并关闭连接；配置、凭据、数据库和日志按本机运行数据管理，不提交仓库。
