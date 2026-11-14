# bugfix-767 交付审查

## 版本

| 字段 | 值 |
|---|---|
| executed_base / effective_base | `9f900ff3ba355414cb442f9211c3a8e17e391428` |
| validated_at | `483160f760e75e9eac74addc67eaa11cf17d21de` |
| effective_through | 最终交付提交，代码与上述冻结版本相同，仅归档和证据更新 |
| 独立审查者 | `/root/review_recovery`，gpt-6.1-sol / high |

## 独立审查与闭环

首轮审查 `81974720d` 发现两项 P2。无状态 TIMEOUT 也可能来自供应商明确 SSE error，且无条件等待阻止健康备用接替。真实 DSH HTTP probe 复现后，`ac486dac9` 收窄本地 watchdog 识别并接入既有备用链。最终 HTTP 回归覆盖此分类边界。

第二轮审查 `ac486dac9` 发现两项 P2。备用交接的第二次发布检查失败会终止逻辑任务，第一次检查挂起会阻塞取消。`dfb17289d` 引入可取消发布检查及检查失败退避。对应旧版两项红测失败，修复版四文件 27 项通过。

第三轮审查 `dfb17289d` 发现一项 P2。新的交接检查重试也影响明确供应商错误，可能使没有聊天绑定的子任务永久等待。`483160f76` 复用同一本地 watchdog 判定，将新增持续等待限定到对应交接。新增 provider-check-error 真实 HTTP 回归在旧版失败。

第四轮对 `483160f76` 执行 closure 与 corrected-delta，P2 全部 CLOSED，最终契约 aligned，无新增阻塞问题。根与各级子 Agent 接线、退避、取消、工具完成边界与原任务恢复均核实。独立审查读取冻结版本测试证据并对争议路径执行真实 DSH / 本地 HTTP probe。

## 非阻塞观察

P3，既有 `/stop` 文案使用 DSH maintenance 的 idle 状态，可能在实际已取消备用等待后显示“当前没有正在执行的操作”。取消和任务终止实际有效，本次不扩展此既有文案问题。

## 验证边界

真实 DSH 使用隔离 home/workspace 与模拟模型服务。SIGSTOP/SIGCONT 仅暂停测试进程，覆盖暂停超过 idle watchdog、连接故障交替及原任务恢复。本轮没有实体合盖或生产恢复验收。原始生产故障的电源日志和 native 轨迹用于根因定位。

## 验证结果

- 最终代码 `483160f76` 的四个定向文件共 28 项通过，包含 root／两级子暂停恢复、socket 断开、三种模型协议、Dreaming、备用链、临时发布检查故障和取消。
- 旧实现暂停恢复红测、初版两个备用链分类红测、二次检查／取消红测、供应商故障检查红测均取得预期失败。
- 全仓构建、类型检查、iOS 共享运行时检查通过；Python 135 项通过，Ruff 检查与格式通过。
- 后端全量 1367 通过、3 项超时；失败的三个文件以单 worker 重跑，共 17 项全部通过。
- 前端构建及 critical audit 通过；前端全量 1196 通过、2 项超时，单 worker 重跑原失败均通过，重跑期间另一项超时再单例通过。保留本机负载相关波动记录，远端 CI 另行核实。

## 后续生产观察

用户补充新消息 `6eade39e15244ee9b9055f66147210bf` 入 Air Inbox seq946 后未被读取。只读核对确认旧实现仅持久入箱就发 node sent；这是用户要求纠正的回执语义缺陷，按 bugfix-768 修复。root work_recovery.pending=1，运行时内 root 已进入 turn413 step0，但持久化 cursor 停在19623，内存 session seq19626；writer.chain/draining 均 pending。原生 FS 请求798个未结算，而四个 libuv worker 与主事件循环空闲。该存活但无文件系统进展故障按 bugfix-769 修复；不能用本 unit 的模型流重试测试代替其恢复证据。调试 inspector 已关闭，临时诊断引用已移除，生产进程未重启。
