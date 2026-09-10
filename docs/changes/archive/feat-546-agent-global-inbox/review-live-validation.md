# Review 修复的真实链路复测（2026-09-10）

入口：[逐项复核](review-followup.md) · [实施记录](M1-global-agent-inbox/progress.md)

用户要求补跑真实模型和渠道。以 `664eb2e8a` 为起点创建独立 IM/Gateway、节点、workspace、数据库和测试 Agent；所有模型调用为 `deepseek:deepseek-v4-flash`，飞书使用专用测试 Bot 与同 App 授权用户。HTTP/WS 代理只控制断连及确认延迟，SQLite trigger 只注入指定记录失败，没有替换模型回答或渠道投递。

## 已完成的实际验证

| 场景 | 实际操作与结果 | 本地证据文件 |
|---|---|---|
| 飞书断连回复与记录失败 | Gateway 断开 IM 时收到真实飞书消息；模型从 Inbox 取得 `local:` 地址，恢复连接后用原地址回复 `EXTERNAL_OK_67f3ea=42`。实际 IM/飞书投递后强制工作记录写入失败，工具仍返回成功；平台只有 1 条 Bot 回复，Inbox 已消费 | `external-evidence.json` |
| 无 MIME 文件 | 实际上传文件并核对下载字节；三成员群聊消息省略 MIME，模型经 Inbox 读取到文件描述、正确回复文件名，无 image part，只有 1 次公开发送 | `file-upload-evidence.json` |
| 本地分页跨重连 | 断连时开始查询/读取，重连后沿原游标读完 3 个缓存会话和 4 页正文，包括长消息尾部及后续记录；保留 `received_only` 与权限确认时间 | `local-pages-evidence.json` |
| 在线分页中断 | 在线取得列表/正文游标后断连，各遇到 1 次 `source_unavailable`；恢复后各重试同一个游标并读完，没有从头重置查询或切换数据源 | `online-pages-evidence.json` |
| 权限确认迟到 | 真实模型请求写测试 workspace 的 `.gitconfig`；浏览器点 Allow once，文件在确认到达前已写入。页面显示“决定已发送，可能已生效”的提示；延迟解除并重连回放后自动显示 Allowed/Completed | `permission-evidence.json`、`permission-file-before-ack.json` |
| Cron 注册失败、手动与定时执行 | 首次强制工作注册失败，运行记录为 `failed/submit_failed`，无 Kernel run；恢复后手动和定时任务各完成 1 次独立真实模型运行、各投递 1 条结果。未来周期起点不再提前触发 | `cron-r2-evidence.json`、`cron-r2-registration-failure.json` |
| 原失败 Session 恢复 | 在保留原始错误历史的同一 Session 中继续追问；真实模型成功读取 Inbox、清理测试任务并回复 `RECOVERED_OLD_HISTORY_0910` | `cron-old-history-recovered.json`、`cron-original-overlap-order.json` |
| 并发建群 | 修复后通过实际 HTTP 同时提交 24 个请求，全部 201、24 个独立 ID、各有完整 3 人参与者列表 | `concurrent-create-after.json` |

附件验证覆盖文件上传、消息描述分类和模型读到文件名，未把“模型下载并理解文件正文”算作已测。权限延迟为 25 秒，超过 Gateway ACK deadline，实际同时覆盖了重连回放恢复。分页中的 Bash gate 只控制断网时间。浏览器实际检查了附件群聊与审批提示/终态。

## 实测新增发现与修复

1. **周期起点被忽略。** 持久任务中存在 `anchorMs=4102444800000`，但 parser 只读取间隔，导致手动执行后下一个 tick 又提前定时执行。现在以显式起点对齐，仅处理最近一个未执行周期；无起点任务和 Heartbeat 行为不变。公开 Scheduler 测试先失败后通过，真实手动/定时复测通过。
2. **后台通知拆开工具调用与结果。** 原 Session `sess_b8429b7070ed3df0` 中，`12:00:57.248` 的工具调用、`12:00:57.410` 的 Cron 通知和 `12:00:57.665` 的工具结果依次落盘；随后追问因 tool result 不紧邻 tool use 被拒绝。现在模型输入物化时把匹配结果放回工具交换中，JSONL 仍保留实际到达顺序。单工具/并行工具落盘重载测试先失败后通过；保留原错误 JSONL 的真实同 Session 追问已经恢复。
3. **并发创建会话交叉提交事务。** 同时创建两个实测会话时收到 500，日志为 `cannot commit - no transaction is active`；并发请求再次出现外键异常。创建入口此前在线程池运行，与共享 SQLite 连接的其他事务交叉。现在这段短事务与 Gateway 写入一样在事件循环执行；并发 HTTP 回归通过。本次修复范围为该创建入口，没有把它表述为所有数据库并发路径均已验证。
4. **一次性任务入队后被提前删除。** 模型创建了 `deleteAfterRun=true` 的定时任务；调度器入队后立即删除定义，执行器随后记录 `job_not_found`，没有 Kernel run。删除职责现保留在 CronRunner 成功提交 Kernel 之后，调度器只记录已处理的到期时间。真实 Scheduler→执行服务→CronRunner 测试在修复前失败，修复后覆盖成功删除及提交失败保留任务。

## 最后一项复测的审批状态

重新创建一次性 Cron、令其在主会话 Bash 执行期间完成、随后继续追问的实测，在 `review-cron-overlap-r4-0910` 的 `cron add` 处被自动审批拒绝：审批把来自 Inbox 的请求判断为未经用户明确确认的持久化操作。该任务未创建，未运行等待命令，也未声称完成；已向用户请求明确授权，当前不计入通过。

这不影响上表中已完成的手动/定时真实运行，以及保留原错误 Session 的恢复验证；但一次性删除时点修复的真实重跑仍待该授权。

## 验证与证据边界

最终代码的 Python 非 E2E 全量 **3728 passed**；上一轮前端 **78 文件 / 739 tests** 和生产构建通过，本轮未修改前端。代码复核由实施者本人完成，没有另计独立审查。

真实请求审计保存在本地 `output/review-live-20260910/final-request-audit.json`，逐 Session 列出模型、原始请求目录、工具调用与工具结果紧邻检查；包含失败尝试，不能用请求总量代替成功场景数。上述 JSON 证据同目录保存，原始模型请求在 `LLM_PROXY/logs/session/`；日志、认证资料、数据库和截图不提交仓库。该记录只覆盖此次列出的故障与观察，不代表生产全场景验收。
