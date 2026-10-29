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
