# bugfix-660: 撤回 feat-657 的逐 Agent 进程架构

## Relations

- Reverts: PR #406 / `1219d903b1ba851cf49631fe37e5d52b49e8474c`
- Related: [feat-657](../archive/feat-657-agent-disable-switch/spec.md)

## 原始报告

> 赶紧的去看DSH的实现。基本上我是一定要推翻你前面这个设计。

> 我们本身不就是在DSH上面做的吗？这些能力我们不是都可以直接复用了吗？

> 刚刚已经不小心合入了你的错误代码，你看怎么收拾吧。

Agent 对本次处置的解释：先完整撤回 #406 的产品代码、测试、依赖与 current 契约，恢复它第一父提交的行为；保留其他已合入工作以及原始交付记录，明确旧设计已撤回。停用开关暂时撤下；基于共享 DSH 的停用实现属于后续重新设计，不在回退中夹带新实现。不部署、不发布、不删除生产数据。

## 现象 / 复现

#406 将普通产品 Agent 从共享 DSH 运行进程改为各自独立进程，并增加零产品 Agent 的 control 进程、独立 home 和离线数据迁移。启用的 Agent 均常驻，增加内存与启动管理开销。该架构已经合入 main，但用户否定其必要性。

2026-10-25 核对：远端 main 为 `1219d903b`，其第一父提交为 `befcbab3a`，包含 #407；Air 的 prod-main 和 Mini 的生产主仓均为 `46cfb9b95`，现有服务启动时间早于 #406 合入。本轮未执行部署或数据迁移。回退保留 #407，不回退整个 main 到旧日期，也不改写 Git 历史。

## 根因

feat-657 的真实产品目标是持久停用一个 Agent，清理它的子 Agent 与后台执行，阻止自动唤醒，并在重新启用后保持旧任务暂停。设计把实现这些产品规则与每 Agent 一个操作系统进程绑定，未充分复用 DSH 已有的生命周期能力；验收证明了所选实现能工作，却没有证明昂贵架构的必要性。

对 Nano 锁定安装的 DSH `0.2.1-alpha.1` 实测，同一 Context/运行进程里的 A、B 可以独立取消；A 的 `AgentHandle.dispose()` 终止其真实 Bash Job，B 与 B 的 Job 继续运行。普通 `cancel()` 只停止当前活动，不等于持久停用；Nano 仍需持有和使用 DSH 的生命周期能力，并管理自己的归属、停用状态和唤醒入口。上游 `drainContinuableDescendants` 还明确提供按父 Agent 清理子树的公开接口。证据位于本地 `~/.codex/reports/dsh-session-isolation-20261025/`，源码基线 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；相关 339 项上游测试在补齐原生构建后通过。

本次是单一、机械回退，不选择替代架构；以 #406 第一父提交的产品树为比较基线。必须保留之前已有的共享普通 Agent、PA 隔离、模型配置、聊天、Work、Task 与 `/stop` 行为，保留数据库和历史资产。原始停用需求继续有效，但撤回期间不宣称已经提供持久停用功能。

## 修复

使用 `git revert --no-commit -m 1 1219d903b` 生成逆向变更；产品源码、测试、锁文件和 current specs 与 `befcbab3a` 完全一致。保留 archive 中 feat-657 的全部交付证据，给 spec/design/deployment-prompt 加撤回说明，不恢复旧活动目录。生产未采用此版本，因此不执行数据迁移或数据库回滚，也不删除已存在数据。

## 验证

- 源码与 current specs 的逐文件 Git 比较：与 #406 第一父提交 `befcbab3a` 无差异；#407 的 Context Engineering 变更保留。
- 本地回归、独立审查和远端 CI 在交付阶段记录实际结果；不能把机械回退等同于已经重新验收所有用户旅程。
