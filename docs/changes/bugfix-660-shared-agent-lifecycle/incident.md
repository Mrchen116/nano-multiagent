# bugfix-660: 复用 DSH 生命周期完成共享进程内的 Agent 停用

## Relations

- Supersedes runtime design: [feat-657](../archive/feat-657-agent-disable-switch/design.md)
- Corrects: PR #406 / `1219d903b1ba851cf49631fe37e5d52b49e8474c`

## 原始报告

> 赶紧的去看DSH的实现。基本上我是一定要推翻你前面这个设计。

> 我们本身不就是在DSH上面做的吗？这些能力我们不是都可以直接复用了吗？

> 刚刚已经不小心合入了你的错误代码，你看怎么收拾吧。

## 澄清记录

Agent 曾先准备完整回退作为恢复检查点。用户明确要求完成正确实现，而非只撤回功能：

> 你现在是只做退回吗？我还需要你按正确的方式完成。其实有一些东西是可以复用的吧，包括前端。

本轮最终范围：保留已经实现的 Web/iOS 停用入口与产品规则，修正底层生命周期接入；撤掉 #406 新增的逐普通 Agent 进程、零业务 control 进程和拆分数据迁移。完整回退提交只保留为本地开发分支的恢复检查点，不交付为最终产品。原来已有的 PA 隔离边界保持，普通 Agent 共享 DSH host。本 unit 因范围扩大升级为 Full，单个 M1 完成接入、回归与真实用户验收。

## 现象与复现

#406 将普通产品 Agent 从共享 DSH host 改为各自独立常驻进程，并增加 control host、独立 home 和离线迁移。功能验收能证明所选实现运行，但不能证明拆进程是实现停用所必需。用户要求复用 DSH 原生能力并保留功能。

对 Nano 锁定安装的 DSH `0.2.1-alpha.1`，已在同一 Context/进程中同时运行 A、B 与各自真实 Bash Job。`A.cancel()` 停止 A 当前活动而保留后台 Job；`A` 的 `AgentHandle.dispose()` 释放 A 并结束其 Bash，B 与 B 的 Bash 继续运行。上游 `drainContinuableDescendants` 提供按父 Agent 关闭和释放子树的公开接口。证据：本地 `~/.codex/reports/dsh-session-isolation-20261025/`；上游源码基线 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，相关 339 项测试在补齐本地原生构建后通过。

## 影响范围

修正 Node 的运行分区、生命周期控制和 DSH integration 的 Session owner 接入。复用 IM/PA 的持久意图、消息与任务边界以及 Web/iOS 界面；只按实现需要调整与进程独占假设绑定的内部字段和诊断含义。原始停用需求、真人权限与历史可读性不降低。

2026-10-25 核对：Air prod-main 和 Mini 生产主仓均在 `46cfb9b95`，服务启动时间早于 #406 合入。本会话没有部署 #406 或执行其拆分迁移。本次沿用生产已有共享 ordinary home 和 PA home；不自动迁移未知的独立分区布局，不删除数据库、聊天、文件或历史资产，不发布安装包。

## 根因分析（RCA）

把产品 Agent 的执行边界与操作系统进程绑定，没有优先使用 DSH 已有的 Agent/Session 取消、子树清理和 owner scope 释放。Nano 当前经 SessionController 创建普通 Session，只取得 Agent 对象；真正可释放的 `AgentHandle` 留在该 controller 的创建生命周期中。应调整产品 Session 的 owner 接入，不能据此认定 DSH 缺少独立生命周期。

#406 随之把 native 禁用标记、生命周期 revision、模型续跑取消、知识/Workflow 停止、定时器和历史处理做成 host 全局动作。在共享 host 中必须按产品 Agent 的可信 Session 归属执行，不能只改回分区 key 或只调用一次普通 Session cancel。

## 修复方向

复用已上线代码里的前端、IM/PA 持久停用与旧任务暂停；执行层通过 DSH 公开接口持有普通 Session 生命周期、关闭指定子树及其受管资源，并将 Nano 自身恢复入口限定到目标 Agent。取消 #406 新增的进程和数据布局层，不新增第二套执行循环或进程树管理器。

## Requirements

### Requirement: 停用只影响目标 Agent

#### Scenario: 共享运行时并行工作
- **WHEN** 主人停用正在执行任务、子 Agent、后台 Bash 或终端工作的 A，B 同时执行
- **THEN** A 的全部受管执行停止并被阻止再次唤醒，B 的任务、后台工作和运行进程保持；不会为停用 A 退出或重启共享 host。
- **AND** 只有 DSH 清理完成才确认已停用；无法确认时显示未确认与重试，不虚报成功，也不杀死共享 host 作为单 Agent 清理的兜底。

### Requirement: 现有停用体验保持

#### Scenario: 真人操作与旧任务
- **WHEN** 主人在 Web 或 iOS 停用、查看状态、重试、重新启用 Agent
- **THEN** 沿用现有入口、状态与权限；停用时 Task 暂停、待授权失效，重新启用只接受新工作，旧任务只在真人明确恢复后执行。

### Requirement: 停用持续生效且历史可用

#### Scenario: 重连与重启
- **WHEN** Agent 停用后节点重连或重启，或节点离线时收到停用意图
- **THEN** 在恢复业务前应用最新意图；消息、Heartbeat、Schedule、Task、模型续跑、知识复盘与 Workflow 都不能重新唤醒目标 Agent；其他 Agent 正常恢复。

#### Scenario: 所有 Agent 停用
- **WHEN** 主人查看历史、Work、配置或模型服务设置
- **THEN** 仍能读取和管理非执行配置，不为历史读取恢复停用 Agent；历史与资产保留。

### Requirement: 回到已有共享运行布局

#### Scenario: 多个普通 Agent
- **WHEN** 节点启动多个普通 Agent
- **THEN** 它们共享原有 DSH host，不增加每普通 Agent 一个进程或单独 control host；原有 PA 隔离保持。
- **AND** 现有生产共享 home 可直接沿用，无需 feat-657 的历史拆分迁移；升级不重建身份或删除已有数据。
