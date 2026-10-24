# refactor-655 一次性部署提示词

此文件不授权生产操作。只有用户要求部署包含本 unit 的版本时执行；先验证代码和归档证据已具备，再按 prod-fleet-deploy 管理服务。

## 适用状态

旧 Node 仍生产 node.report/usage.read，旧 IM 提供累计 metrics；Work journal/ACK 已存在但处理位置与 descendant catalog 仅内存。目标为累计链退役、工作记录 checkpoint 与小型关系元数据持久化。适用于该版本首次升级的 Node 和 IM，不能只更新其中一端。

## 执行顺序

1. 记录现有 Node/IM 版本、运行目录及真实 PID，备份各 Node SQLite、Inbox SQLite、DSH home 与 IM SQLite。保留本地配置、用户数据及无关修改；备份和凭据只进入受保护本地记录。
2. 按正常维护边界停止旧 Node，然后更新 IM 与各 Node。同一机器不得并发打开两份写运行时；不清空 usage_reports、usage_metrics、usage_receipts，也不清空 journal/ACK。
3. 初次缺少 Work checkpoint 的历史由新实现受控补建，保持新输入和必要控制可用；页面显示已有记录及补齐状态。记录首次补建完成，不把它的成本算作后续普通重启。
4. 主/子任务真实产生工具开始、完成、失败及 Token；验证 Work 保存和增量更新、聊天、Workflow 预算及原始详情。等待 journal/ACK 追平后重启，记录正文读取次数和事件处理量；不变完成历史不应再正文重建。
5. 中断后按已有 checkpoint/ACK 继续；记录 journal 身份、处理位置与 ACK 的核验结论，避免人为重置导致重复全量恢复。

## 完成与恢复

完成需工作记录与统计重启前后一致、补传后无重复或缺口、普通重启无完成旧历史正文扫描，所有目标节点版本一致。失败时停止新 Node，成套回滚 Node/IM 到记录版本；新增元数据可保留供问题取证，旧累计历史表仍可读取。若需从备份恢复，恢复同一时间点的原生日志与产品库，不混用任意断点。未确认问题保留现场，不删除生产原始数据。
