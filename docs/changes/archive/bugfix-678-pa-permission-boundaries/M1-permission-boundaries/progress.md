# M1 实施记录

## 2026-10-29 首轮实现

基线 `9bf2b13da`，独立 worktree `unit/bugfix-678`。主 Agent 集成；首轮独立任务为审核执行、消息准入和独立模型重试。未修改生产服务。

已取得的失败复现：任务拒绝隐藏阻断、独立外发计数互相作废、非法审核判定不恢复、事件已拒草稿挡住收敛措辞。对应窄测试通过。迁移新增状态导致旧 Node 导入失去唤醒，已修复导入的已准入状态。

- 审核专项：5 files / 39 tests，通过真实锁定 DSH 子进程验证原生重试、取消、分页、并发及图片请求；图片 provider 是明确声明 pricing 的 fixture。
- Python 非 E2E：113 passed / 28 deselected。
- 初次全量 TypeScript：818 passed / 4 failed。迁移问题已修复；审核人工短时限已调整；knowledge-policy/workspace-tools 受控单 worker 复跑 6 passed。最终全量仍待完成，不能将窄复跑记为全量成功。
- PA 收敛事件措辞：18 passed；unknown 不另起发送。
- 图片格式/hash/副本、迁移备份与回滚窄测试通过；真实用户旅程未验收。

## 已确认能力缺口

锁定 DSH `0.2.1-alpha.1` 的 Pi-AI adapter 没有公开 imageRequestPricing，通用 estimateContent(image) 只计算引用文本。当前 Codex OAuth/Pi-AI 的待发送图片和 native read_image 调查会明确 unavailable。只有 native DeepSeek adapter 声明对应图像计费；当前日常模板走 Pi-AI。不得把 fixture 成功当成 R2/R6 完成。主 Agent 已提出是否扩展现用模型图像预算适配并补设计复审，待用户裁决。

本轮固定日常栈 `.e2e-daily.json`，隔离 IM `127.0.0.1:58487`、node `wt-nano-multiagent-69106`。后续验收前绑定冻结版本并重启自建服务；结束清理。

## 用户纠偏与独立审查修复

用户明确指出图片 token 估算不是其要求，要求按主 Agent 的原生图片转入方式处理。author 修正 design `5789ce9ef`，设计 R4 delta 复审 Approved、0 CRITICAL / 0 WARNING。删除本仓 pricing 前置门槛；同主 Agent 使用 admitPromptContent → followup → 原生 adapter，保留完整待审图的请求核对。无 pricing 的真实 DSH 子进程先复现失败，再通过 full/delta/fresh 图像请求回归。

静态审查 `21b8da0d3` 确认主人通知 ACK 丢失后 unknown 无法恢复。现重复相同 incident 调用时只查询 host publication receipt，确认真实发送后绑定 incident 回执；found=false 不重发，并向模型说明同工具同 incident_ref 的查询方式。窄验证：3 files / 32 tests passed（含20项 PA 测试），证据 /tmp/bugfix678-native-image-green.log。初始red分别为 /tmp/bugfix678-native-image-red.log 和 /tmp/bugfix678-receipt-red.log。

本地前端108 files /1029 tests通过；文档检查、Ruff、iOS交互资源检查通过。第二次全TS 822 passed/2 failed，失败的 knowledge-review/workflow-native 在无并发重构建/前端全量时单worker复跑5 passed（/tmp/bugfix678-runtime-repro.log），暂只确认与负载相关，最终全量仍待独立一轮完成。

## 最终回归与补充真实验证

固定实现 `80941dfd6` 的第三轮全量 TypeScript 已通过：156 files / 826 tests，242.17s。build/typecheck 均通过。R5 真 Luna 预审核后实际等待 >60s 两笔仍可提交、撤回后第三笔 not_sent；R8 副本迁移 CLI 重复执行/verify 及真 Astra 查回已有回执均完成，无重发。详见 [补充证据](evidence/supplemental-validation.md)，明确区分真实模型、host seam 与确定性故障测试。产品 reviewer 正补完其他用户旅程，尚未以这些补充结果替代独立最终裁决。

## 最终同步与归档

产品 Round 2 pass（报告4636bc606），verifier Round 3 pass（受验41a315eb9，0 CRITICAL / 0 WARNING），code-review Round 2无finding。最终fetch后origin/main仍为9bf2b13da，无新增上游差异；源码自80941dfd6未变，全部门禁retained。两项MODIFIED与全部ADDED均按已审delta逐字归并current spec，更新area计数与路由后完整归档。后续仅文档归并、状态、相对链接和归档路径，不改变产品行为，不重跑无变化源码全量。

服务已按e2e-down停止并核实无目标PID/58487监听，专用tmux关闭。开发worktree保留供PR审查，未合并且未部署；具体PR/head/远端CI状态以GitHub为准。

### Final sync gate validity

executed_base / effective_base：`9bf2b13da4005631096f2a49223564cd68647c3c`；本次有效集成树 effective_through：`3cfad90d8123302ee25516072ece0ef78dc284d5`。

| Gate | 实际 validated_at | 最终判断 |
|---|---|---|
| 产品 Round 2 | 80941dfd6afcd181536a08da1b0762051ee98b11 | retained；后续仅文档，用户行为/运行配置未变 |
| 代码/Context Round 2 | 80941dfd6afcd181536a08da1b0762051ee98b11 | retained；全部源码与测试未变 |
| 一致性 Round 3 | 41a315eb972616176dbce2b6f3146715b578ed8e | retained；已审delta的全部Requirement逐字归并，脚本逐项相等检查通过，无新delta |

本条记录的提交只补有效性元数据；其后的实际PR head会在PR正文列出并延伸同一文档变化判断。归并后docs integrity通过（317 maintained sources），change unit归档检查通过，git diff --check通过。

## PR #430 用户指定全面 Context 复审与修复

对 `89acdd464` 的完整 PR diff 新派独立 reviewer，确认两项先前门禁未覆盖的缺陷：Inbox 全部 partial 片段被原话保留层丢弃；交互卡片图片已复制到受众会话但 source 仍指向原私聊。完整覆盖和确定性复现在 code-review 的 User-requested full Agent Context review 中，原“无剩余 finding”结论不再代表当前结果。

修复将可信已读消息按会话/消息与 part/parts 收齐为完整单元，跨页保持首次出现顺序；缺片整单元省略并标 incomplete。提交交互卡片时，source 与 content/attachments 使用相同冻结资源副本映射。扩展现有 retained-instructions 与 personal-images 回归，不新增平行套件；真实 Inbox 分页覆盖长文本/附件撤回、读不全警告、重建与继承，真实 IM/SQLite/图像文件 seam 覆盖 PNG/JPEG/WebP 卡片实际持久源码和副本字节。

窄验证 2 files / 10 tests passed，DSH 和 IM build 通过。首次图片测试暴露 fixture 未把 PA 加入目标会话，补齐正常成员关系后通过，不放宽产品权限。受影响 DSH+IM 回归与独立 closure 尚在进行，后续补最终结果；没有新增真实模型调用、浏览器试用或生产操作。

### 2026-10-30 Context 修复收口

独立 closure 绑定 `3e5b63e11f453ad84cc3c84f2e0ddcb09375cfe0`，两项 finding 均 closed、remaining `[]`；原缺陷独立重放3项与永久窄回归10项通过。后续提交只记录报告/验证，不改该源码。既有产品/一致性证据仅对未变部分保留；本次两条 delta 由最低有效的确定性 Inbox/IM seam 验证，不冒充重新执行真实模型或 UI 全旅程。

受影响 DSH+IM 回归100 files / 483 tests：98 files、481项通过，knowledge-policy 与 knowledge-review 各一项在等待异步事实时超时，完整日志 `/tmp/pr430-context-fix-tests.log`。同源码单 worker 对照重跑两文件9项全部通过（14.90s，`/tmp/pr430-context-fix-retry.log`）。这是负载相关假设的支持证据，尚不能证明并发超时的确切根因；未修改这两套测试或知识维护源码，不将两次结果拼成“一次全绿”。最终远端CI另行核实。

DSH/IM build、两包 typecheck、文档完整性（317 sources /68 routes）、归档检查与diff check通过。当前没有自建产品服务；测试子进程按fixture清理。PR仍未合并、未部署，开发worktree保留用于审查。
