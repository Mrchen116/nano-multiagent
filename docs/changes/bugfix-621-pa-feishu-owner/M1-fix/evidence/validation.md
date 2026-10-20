# Validation evidence

## 修前真实飞书复现

- Baseline: 0fa706a67 产品代码（文档 HEAD 9fa676f00），2026-10-20 09:53 Asia/Shanghai。
- Method: 专用测试 App 的 user identity 真实发送，经 SDK 到隔离正式 PA；IM/Node/DSH 位于本 worktree。
- Input: `PA621_BASELINE_0953`；平台消息 `om_x100b6258d6ff80b0b099c7ada43a8d5`；影子消息 `7a777f19734042a9984d47121a1eccd0`。
- Result: 输入被当 external 审查并产生“隔离测试是边界探测”的拒绝通知；来源事件仍 pending，Node 输出镜像报 `personal_reviewed_delivery_required`。证明真实链路存在误分类/交付拒绝，不以服务在线推断成功。
- Locator: 本地 `output/pa621-baseline/observations.json`、`gateway.log`（运行产物不提交）。
- Limit: 此基线证明本次测试输入的失败；此前生产 09:10 提醒误拒绝证据见 incident。

## 定向回归

- 初始 4 个新增回归在修复前失败，旧 31 个通过；修复后同组 35 个全部通过。
- External/Global/Inbox/PA 相关组初步 64 个通过，typecheck 全部通过；最终集成验证待以下实测完成后记录。
