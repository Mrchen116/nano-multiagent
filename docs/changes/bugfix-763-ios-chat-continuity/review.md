# iOS 聊天连续性实施审查

- 独立审查者 `review_763` 对 `4491692c6` 与工作区修复审查，基线 `9f900ff3ba355414cb442f9211c3a8e17e391428`。已确认访客权限待核实期间隐藏历史、Earlier 控件及多余的辅助反馈。现有会话短断线恢复后补做失败的会话详情读取。
- P2 读取结果次序已关闭。旧请求失败不能覆盖同范围的新成功。回归 `testLateTimelineFailureDoesNotReplaceNewerSuccessfulRead`。
- P2 降级存储访客临时读取失败已关闭。访问资格仍待核实的访客不从已加入列表的缺席推出撤权，保留历史与分页游标。回归 `testNetworkOnlyVisitorHistorySurvivesAnotherFailedAccessCheck`。
- 独立复审批准上述修复，delta 与实现一致。原生体验和性能状态以 [实施证据](M1-continuity/progress.md) 为准。

## 原生旅程与性能

独立审查核对了短断线宿主时间、长断线恢复、详情与前台回到历史、键盘和多行输入框、状态栏回顶、远距 Latest 和迟到 Earlier。当前候选补跑十张交互卡片的原生展开与收起，通过。短断线期间保留焦点的输入草稿、图片或流式段落单独改高、新远程消息到达时阅读历史尚未分别实测。

D5 整体验证仍不充分。混合卡片暖滚动的首轮和同条件复测在 CPU 与峰值内存门槛两侧，部分手势主线程样本与请求时间不能解释差异。四组 Latest 均到达真实尾部，已取得外层尾行几何的 handler 时延。新挂载卡片的真实内容首次可见时刻与最后一次高度变化后纠正时延未被独立测出。没有证据确认原始真机卡顿根因或滚动性能提升。

| Gate | validated_at | executed_base | effective_base | effective_through |
| --- | --- | --- | --- | --- |
| 原生单测与独立代码复核 | `6dee4f33b` 与对应受审工作区 | `9f900ff3b` | `be23e8fc7` | `109cf5652` |
| 原生旅程与性能矩阵 | `6dee4f33b` 产品源码，`d6df16c9e` 包含分页竞争的旅程验证更新 | `9f900ff3b` | `be23e8fc7` | `109cf5652`（性能仍未定） |

集成增量只有 Agent 运行恢复、回执及 Gateway relay 路径。本轮原生 fixture 与代码复核无这些路径参与，保留其有效范围。保留 active unit 及待归并 delta。Draft PR 汇总候选，归档检查预期提示 unit 仍 active。
