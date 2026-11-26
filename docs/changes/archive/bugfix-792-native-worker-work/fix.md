# bugfix-792 恢复 DSH 一级 worker 的工作记录和原生轨迹

## 原始报告

> 工作记录现在DSH的worker反而看不到，外部的反而看得到。另外DSH的worker完全可以给原生轨迹

> 对，其实之前就支持的，但是支持外部worker的时候灯下黑了。改错了

[Issue #552](https://github.com/Mrchen116/nano-multiagent/issues/552)

## 现象和定位

PA 和普通 Global Agent 派出的 DSH worker 有轮次及 Token，用户从派工关系和主记录无法进入子执行，原生查看器也过滤该会话。基线 36af1a86b 的目录和原生轨迹回归用例均复现失败。3995e74e4 将一级派工收窄到关系展示，bf7a1e720 恢复了外部 CLI 的明细。DSH worker 自身的持久 Session 和可信父子关系仍存在。

## 期望与验收

- 在派工关系、活动弹窗、主记录的 start、send 及来源回传中打开同一个 DSH worker，检查任务输入、工具参数和结果、助手回复及实际报告的用量。
- IM 保存已同步的工作记录，刷新或执行节点离线后继续可读。具有原生历史的旧派工在节点重新同步后取得明细。
- Web 可在该 worker 的 Work 切换到对应 DSH 原生轨迹。PA 仍只允许主人查看，普通 Global 沿用空间权限，内部 helper 和长期记忆边界沿用原契约。
- iOS 共用服务端的工作记录及跳转身份。外部 CLI 继续查看工作记录。

## 修复和验证

详见[事后设计](design.md)。用户已确认并授权合入，见[审查与验证](review.md)。
