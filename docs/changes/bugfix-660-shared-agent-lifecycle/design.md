# bugfix-660: 共享进程内 Agent 生命周期 — 技术方案

> 对齐: [incident.md](incident.md)

## Changelog

## 现状分析

### 涉及范围

`apps/node/src/runtime-partitions.ts` 和 `main.ts` 管理 DSH host、初始化和消息路由；`agent-lifecycle.ts` 管理持久意图与确认。`packages/dsh-integration/src/index.ts` 连接原生 Session 与 Nano Task、Cron、模型策略、知识和 Workflow。IM、PA 与 Web/iOS 已具备停用状态、权限和入口。

### 既有约束

只通过 DSH 声明的公开 exports 使用运行时；不 fork、patch 或 private import。普通 Agent 共享一个 DSH host，已有 PA host 安全边界保留。停用不能杀死共享 host。保留历史、资产、上下文语义、主人权限与显式恢复旧 Task 的要求。

### 可复用能力

- 用 DSH `ctx.agents.create/resume` 返回的 `AgentHandle` 持有产品 root Session；`cancel` 停当前执行，`dispose` 释放 owner scope、Session 与受管 Job/终端。已用锁定安装版本完成同进程 A/B + 真实 Bash 验证，证据见 incident。
- 用 `ctx.subagents.drainContinuableDescendants` 关闭 root 下的持久子树，并由 root scope 释放一次性子 Agent；取消前先封住该产品 Agent 的新执行入口。
- 改现有 SessionController 接入：保留公开只读查询与轨迹能力，用公开子类覆盖 `resolveAgent` 委托给持有 handle 的 Session owner。Nano create/fork 路径直接交给该 owner；fork 使用公开 `buildForkSeed`，不复制 DSH fork 算法。
- 用现有 IM/PA 持久生命周期意图、revision、Task suspension、消息边界、Web/iOS UI。Node 的执行门禁与 native 回调按可信产品 agentId 检查，不再按 partition 的第一个 Agent 判断。
- 改 Native Cron、Task driver、模型恢复、Knowledge、Workflow 的停止范围；复用已有 `disposeAgent`、Session cancel/stop 等接口，不停止共享 service 本身。
- 不用 #406 新增的 control host、逐普通 Agent home、迁移脚本和单 Agent 强制退出进程兜底。历史通过所在共享 host 的只读 Session 查询，PA 的只读请求仍到原 PA host。

### 相关历史

#406 / feat-657 的产品体验保留，运行分区方案被本设计取代。#404 的 Work 增量恢复和 #407 的 Context Engineering 要求保留。本 unit 不部署，不迁移生产数据，不发布包。

## 架构总览

普通 Agent 的 DSH root Session 均由一个 host 承载；Node 的持久生命周期按产品 Agent 记录。native Session owner 保留每个 root 的公开 handle；可信 binding、原生 parent 链与 descendant reader 将每个执行映射到产品 Agent。PA 仍按 binding/epoch 独立 host。停用针对 owner 子树与 Nano 内部该 owner 的工作，不针对 host。

## 关键决策

**保持前端与产品协议，修正执行所有权。** UI 不新增交互，继续 displaying stopping / disabled / stop_unconfirmed / enabled。`process_instance_id` 标识承载它的 host；共享同一值是正确结果，不代表 Agent 独占进程。Node ready 后报告 host 内每个 Agent 的当前状态。

**以公开 AgentHandle 释放执行，不只 cancel，也不自建进程杀手。** 创建和恢复 root 的并发请求在 owner 内合并；停用先关闭 admission，等待已有创建结束并清理其 handle。原生子 Agent 根据 parent 链属于同一产品 owner，native pre-step/tool 与 schedule 输入检查该 owner。启用后按需恢复新的 handle，旧 inbox 用持久 fence 清理；不保留已 dispose 的对象。

**生命周期状态与恢复 fence 按 Agent 隔离。** `RuntimeLifecycle` 初始化为 agentId 到 revision/disabled/disabledThroughRevision 的映射。cold Session fence 仍以 Session 标识记录，owner cleanup fence 改为 agentId；只清该 owner 的持久模型/知识/Workflow/定时恢复，不能清空 B 的 pending 工作。停用期间 reject 自动入口；启用不补跑错过的 schedule、不自动恢复旧 Task。旧 revision 输入和迟到输出继续被 Node/PA 与 native 两层拒绝。

**清理失败如实保留未确认，禁止影响 B 的兜底。** Node 以现有超时（5 秒）显示 stop_unconfirmed，后台清理可继续；重试合并或重新检查相同 owner 的清理。没有 per-Agent SIGKILL、host shutdown 或 provider 全局 dispose。只有受管清理完成且持久 barrier 成功才上报 disabled。整 host 崩溃仍走已有整 host 恢复语义，不将进程隔离作为本需求保证。

## 接口与数据流

1. IM 保存主人意图，PA/Node 关闭 A admission、暂停 Task 并使授权失效；向 A 所在 host 发送含 agentId、revision 的 lifecycle RPC。
2. native 标记 A disabled，新 Session、pre-step、工具、Cron、Task 与自动恢复均检查 A；用 binding/root lineage 找 A 的 live roots 和 descendants。
3. 先 cancel A 全部 live 执行；并行停止 A 的 Nano 自动驱动、关闭 continuable subtree，随后 dispose A 的 root handles。清理覆盖创建中的 root，等待 DSH 受管 Job/终端退出和 Session 持久化；不遍历全局 Job 并误杀其他 owner。
4. native 记录 A 的 cold cleanup fence 后确认；Node 按 revision/node epoch/host instance 更新状态。失败返回未确认，重试不重启 host。
5. 重新启用只打开 A admission，应用最新配置及 skip-missed 定时策略；旧 Task 保持 suspended。新消息按公开 resume/create 获得新 root handle。
6. 初始化先装配 bindings/config 与所有 lifecycle 状态，再开启 Cron/Task/模型等恢复入口。全部 Agent 停用时 host 仍提供配置、历史、Work、模型设置；历史读取不调用 resolveAgent/create/resume。
7. Node collection RPC 仍要求 scoped runtime port；一个普通共享 host 内的 facts/pending 可包含多个 Agent，但逐条按可信 owner 过滤禁用状态，ACK 只作用传入身份。审批、Session 和观察者路由保持原来的可信映射与 generation 防护。

### Context 消费与验证

Consumer 是普通 root、子 Agent、Schedule、Task、模型续跑和知识/Workflow 的 LLM 请求。修改创建/恢复的 owner 生命周期，不改变 preset mount、tools/skills/system prompt、cwd、历史 seed 或模型选择。创建/恢复均在公开 factory setup 内 mount 原有 preset，绑定在任何自动消费前可见；fork 保留原有 snapshot/idMap/seed 语义。启用后的新消息必须实际读到原历史与配置，A 停用不改变 B 的模型输入或 schedule/task 上下文。验证使用真实 LLM 日志、产品消息与 root/child 证据；仅类型或内部 mock 不代替实际交付。

## 契约层增量 (delta-spec)

- Gateway service lifecycle：[delta](specs/gateway/service-lifecycle.md) 替换共享目录升级场景；保留停止、历史和权限保证。
- IM、PA Task、Web/iOS 体验无新增契约；沿用 feat-657。`SPEC.md` 的拓扑归并为 ordinary shared + PA scoped，删除 control/per-Agent migration 描述。

## 风险与回退

DSH 未受管外部进程/已接受的外部副作用不承诺撤销。清理失败只影响 A 的确认，不能扩大至 B。Session factory 接入改变恢复入口，需覆盖 create/resume/fork、Schedule 与冷历史。发生问题可回到已验证生产 `46cfb9b95` 或 #406 前共享版本，保留运行数据；不能把 #406 逐 Agent 进程方案当作无需迁移的回退。

## 一次性部署迁移

无。本会话已确认生产未部署 #406、未执行拆分。继续沿用现有 ordinary home 和 PA home，不增加迁移脚本或启动兼容分支；未知已拆分环境不属于本轮部署授权。部署时仍需按既有生产流程核对版本与目录，生产部署不在本 unit 执行范围。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 本 unit Node + IM + Web | `./scripts/e2e-down.sh --runtime-root /tmp/nano-bugfix-660` | `./scripts/e2e-up.sh --profile daily --runtime-root /tmp/nano-bugfix-660`（按脚本 help 补齐隔离端口和配置） | `.e2e-daily.json` 内端点与真实消息 |

**Review 驱动方式**：端到端真栈，从 Web 入口走停用/状态/重试/启用/历史和旧任务恢复；并行 A/B 的后台 Bash 与子 Agent 用真实执行证据。客户端实现无变化，已有 iOS 界面证据保留，仅在实际改动原生 UI 时重新原生验收。

**验收前置**：使用仓库 daily P/E/Q + PA 和已有测试 LLM 配置，主 Agent 交接实际运行命令、隔离端口、配置、证据和 `.e2e-daily.json`，不接触生产。先验证模型可用，再做真实并行任务、停用和重启。只清理本 unit 服务。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-shared-lifecycle | 共享 host 的 Agent 生命周期修正 | 无 | 单阶段 | Node partitions/main/lifecycle；DSH owner、native lifecycle、Task/Cron/model/knowledge/workflow；相关 tests/specs，保留 IM/PA/UI | [worker] 锁定 DSH 公开 exports，普通 A/B 同 PID，A cancel+dispose 后 A Bash/终端/子树停止而 B 继续；create/resume/fork、cold history、自动入口与 fence 回归通过；实际 LLM 验证恢复历史和 preset 不退化；移除新迁移及独立进程层；[reviewer] Web 停用/重试/启用、历史、旧 Task 显式恢复可用；离线意图重连与重启不唤醒 A，B 正常；全部停用后管理可用；确认失败不虚报且不重启共享 host |
