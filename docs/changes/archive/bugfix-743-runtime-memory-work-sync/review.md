# bugfix-743：Review

## 范围与版本

- 独立实现审查：executed_base `116df2253`，初审 validated_at `082d62fe`，复审 validated_at `088d104d`。
- `e5f0856f` 只把现有 PA 竞态 fixture 接到状态读取入口，10 项 PA 测试重跑通过；实现/契约判断保留。目标分支新增 bugfix-744 首文档，不改变受审实现。
- 入口：普通和 PA 的锁定 DSH profile、Node 私有 RPC、Global Work 日志与原生轨迹读取；未动中心 Work 传输协议和页面。

| 问题 | 执行者和证据 | 判断 |
|---|---|---|
| 历史保留与驻留边界 | 实施方隔离性能对照；独立代码审查核对工具展示定点读取、旧投影保留和归属删除。见 [探针](M1-runtime-work/evidence/isolated-probes.md)、审批和工具存储恢复用例。 | 通过。合成历史未增加候选的启动驻留；原始日志和 presenter 格式保留。 |
| 主子游标、慢读、重连、配对 | 独立审查复跑真实 DSH 子进程分页断线；真实冷中断探针，Work 保留一条中断结束。stdio 慢写入测试核实不提前生产下一页，控制独立分派，关闭拒绝未决操作。 | 通过。局部运行证据包含大正文跨页、权限负例以及只读已变化冷日志。 |
| 停用、重连和权限 | 独立代码审查核对正常根页的生命周期检查；本地原生停用/删除测试和 Node lifecycle 用例分别验证冷读取、带 revision 的 cleanup receipt 及同次机器启动的替换进程。 | 通过所列组合证据；未做一次独立的完整停止、断线及 UI 走查。 |
| Delta 校对 | `/root/code_review` 在 `088d104d` 对照设计、实际断线和冷中断证据。 | aligned。 |

## Findings 与关闭

- C1：真实冷中断时 fallback 记录仍为 running，Work 丢弃原生结束。修复只让 Work 保留最后一次物理尝试的原生 interrupted 证据并映射为中断；复跑实际强杀/重启，两次恢复只生成一条 interrupted，checkpoint throughSeq 17 / replayFrom 18。
- C2：根持久屏障失败后，子通知可能清除根 pending。恢复正常事件同时检查根与子；独立复跑子通知触发根重读，根仍失败时 pending 保留。
- C3：根页回复绕过正常生命周期校验，跨停用返回仍可消费 Inbox。恢复请求与回包的生命周期校验；冷停用页依旧走 supervisor 的 revision-scoped 入口。定向测试确认停用后拒绝晚到的根页。
- C1–C3 均经 `/root/code_review` 在 `088d104d` 独立复验关闭；相关两个测试文件独立复跑 18 项通过。

## 证据边界

隔离真实子进程由受控 provider 驱动，验证存储、协议和产品投影，不评价真实模型决策质量。没有接触生产运行数据、部署或重启生产。原生冷观察仍可能解码一份完整日志；不改变未完成子任务的继续执行机制。

## 最终复验

- 传输补审：`/root/design_review` R4 和 `/root/code_review` 定向复核 `eac2f5b5`，无新增 findings，前述结论保留，delta aligned。挂起子历史读取期间，根取证可以返回；共享 stdout 本身背压时仍按同一有限队列等待。慢写入测试和真实 Node/DSH Work 断线所在两个文件共 7 项通过。
- 真实中心链路：`apps/im-server/tests/e2e/work-production-chain.test.ts` 通过。用分页原生事实夹具驱动真实 PA Work 投影、持久日志、HTTP uploader 与 IM 服务，验证完整参数/结果、关联子轮、用量、重启分页和重复传输。
- `7928ed38` 与 `52032883` 只迁移尚沿用旧 RPC 的测试夹具：根/子 Work、恢复后的稳定性检查及停用分页。独立实现结论保留。最终 effective_base `116df2253`，effective_through `52032883`；随后规范合并、记录与归档没有产品差异。
- 构建、TypeScript、iOS 共享运行时检查、文档完整性、Python 135 项、ruff 及 Web 1,105 项通过。iOS 原生应用文件未变。
- 后端本地等价检查：第一次全量 204 个文件通过，22 个文件包含 29 个失败（并行期间机器负载很高，多个能力检查/fixture 超时，另有需要迁移的旧 RPC fixture）。针对 22 个文件低并发复跑后，19 个文件整文件通过，余下三条在单独运行最终实现时通过：Global worker provider、ordinary Global capability，以及迁移到停用冷页后的 legacy Schedule。未将第一次全量记为全绿；远端 CI 重新执行整套。
- 已退出隔离子进程并移除其临时 runtime home，无生产部署或重启。开发 worktree 保留至 PR 合入；脱敏数值和复现脚本另存本机报告。
