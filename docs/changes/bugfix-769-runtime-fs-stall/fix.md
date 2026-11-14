# bugfix-769 恢复异步文件系统失去进展的执行进程

## 需求与现象

用户要求同时解决新消息入箱后不处理及回执过早。本 unit 负责前者的运行时卡死恢复，回执见 bugfix-768。

生产 Air DSH 的 JavaScript、stdio 和配置预览仍响应，但 root 的持久 writer.chain/draining 永久 pending，新消息 seq946 无法取得唤醒确认。Inspector 观察数百原生 FSReqPromise；sample 显示四个 libuv worker 空闲。具体原生缺陷尚未证明，不能声称修复了 libuv 或实体合盖本身。

## 根因及最小修复

已证明的产品缺口是 supervisor 只恢复退出进程，无法处理仍活但异步文件操作不再完成的 DSH。增加独立 runtime.health RPC，实际 await 本地目录 stat，避免仅 ping 将该状态判健康。宿主每15秒探测，单次30秒无完成后终止失效执行进程及其所属工具后代（包括DSH自行创建的独立进程组），沿既有退出恢复重新加载持久会话；不按模型/工具耗时判定。只保留一个在途探测。定时器观察到明显时钟跳变时，给原探测完整新宽限，避免睡眠耗时导致立即误杀，也不累积新的挂起RPC。

退出及shutdown清理健康timer；连续失败继续使用已有三次上限，成功完成健康探测后重置预算，因此长期运行中的独立故障不会耗尽进程整个生命周期额度。已完成外部副作用不会凭空变成可重复操作，恢复只依据既有持久身份及日志，不提供exactly-once承诺。

## M1-fix 验证与审查

确定性计时测试覆盖正常健康、永久pending、有界请求、长时间睡眠跳变、关闭；真实DSH子进程通过专用测试插件让异步FS stat停滞而stdio仍活，确认健康失效触发替换且持久输入和后续输入仍可访问。已有进程退出恢复回归保留。独立代码审查由主Agent统一安排。实体合盖、原生libuv故障复现与生产部署不在本轮验证范围。


## 当前验证结果与未完成项

`pnpm --filter @nano/dsh-integration build` 通过。`pnpm exec vitest run packages/dsh-integration/tests/runtime-health.test.ts packages/dsh-integration/tests/supervisor.test.ts` 共8项通过，包含单探测、睡眠跳变宽限、关闭、独立工具进程组回收、既有退出恢复、onReady失败清理，以及真实DSH中FS异步stat停滞后替换进程并把原持久输入和新输入交给受控模型完成。测试使用真实DSH子进程与确定性模型，不代表真实模型判断或实体合盖复现。

更强的 `apps/node/tests/runtime-fs-recovery.test.ts` 通过真实GlobalAgent消费原Inbox消息，停在读取后的下一模型请求，注入FS停滞，确认进程替换；但没有新输入时，恢复后请求数量仍停在2，未达到预期3。该红测确认另一个既有缺口：已读root任务没有自动续跑触发。主Agent继续在本unit内实现原任务/各级子任务恢复，完成前不宣称unit完成。该测试保留原目标，不降低为等待新消息后再恢复。

## 契约增量（待最终合并）

Gateway服务生命周期增加：运行时仍活但异步本地FS探测持续不完成时，节点在有界且睡眠友好的宽限后回收所属执行进程和工具子进程，沿持久恢复路径继续；正常长模型/工具调用不触发该故障判定。健康恢复重置连续失败预算，连续启动/健康失败仍受三次上限保护。

## 原执行恢复补齐

真实 PA 红测证明已读原消息的任务在冷恢复后没有新模型请求。新增恢复 owner 只识别原生 interrupted 结尾，使用公开 agents resume / steer 和持久日志，恢复主及各级 continuable 子会话，在原历史上追加系统恢复通知。子会话先恢复，父提示保留已有委派身份。用户停止按原 turn/start 时间与持久停止边界比较；completed、aborted 和明确 error 不自动重开。一次性 fork 原生未保存可恢复组合，自动唤醒主会话继续原任务并处理异常事实，不能伪造同 ID 恢复。

模块接口是 `InterruptedWork.recover(root, owner)`，对同一 root 并发调用合并；原生持久 Inbox 与 turn 事实承担恢复通知幂等，不另建执行循环或原生事件。跨层验证使用真实 DSH 和受控 provider：已读原任务无需新消息续跑、后续新 Inbox 继续处理、两级子会话沿原身份自动完成、明确失败和取消保留，第二次重启不再唤醒已完成任务。原有依赖“continuable 中断只通知父而不恢复”的轨迹与规模用例改为验证新行为；一次性 fork 的异常通知逻辑保留。
