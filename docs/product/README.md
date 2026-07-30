# Product

本目录负责产品层长期事实：nano-multiagent 为谁解决什么问题，以及跨实现版本仍应成立的产品与体验原则。

## 与相邻知识的边界

| 问题 | 权威位置 |
|---|---|
| 产品是什么、如何最短开始使用 | [`../../README.md`](../../README.md) |
| 产品定位、目标用户和长期原则 | 本目录的 `vision.md` |
| Web IM 的稳定体验原则 | 本目录的 `web-im-principles.md` |
| 四个包怎样分工和部署 | [`../../SPEC.md`](../../SPEC.md) |
| 某个包当前应该表现为什么 | [`../specs/`](../specs/README.md) |
| 准备改变什么 | [`../changes/`](../changes/readme.md) |

产品原则说明“为什么”和长期取舍，不复制页面字段、API、状态机或实现结构；这些可观察行为由 current specs 维护。产品原则变化需要建立对应 change，并同步核对受影响的架构和行为契约。

## 迁移中的来源材料

| 文档 | 状态 | 用途 |
|---|---|---|
| [`../需求.md`](../需求.md) | Legacy source | 早期产品需求、竞品判断和范围设想 |
| [`../IM前端蓝图.md`](../IM前端蓝图.md) | Legacy source | Web IM 早期信息架构与视觉交互设想 |

来源材料用于还原语境，不能覆盖 README、SPEC 或 current specs。稳定结论完成对账后进入本目录，原稿转入 `docs/archive/product-source-materials/`。
