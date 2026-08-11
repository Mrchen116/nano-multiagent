# bugfix-528-M1: 移动端底部导航图标升级 — Tasks

> 对齐：`../fix.md`

## 目标

以真实移动端底栏和品牌色为基准，用 ImageGen 探索统一的 Chat、Agents、Me 图标语言，并规范化为 20–24px 下清晰的产品 SVG；路由、标签、未读 badge 和导航行为保持不变。

## 退出标准

- [x] 三枚图标属于同一圆角几何体系，inactive / active 只继承底栏产品色，不再出现彩色 emoji。
- [x] Chat、Agents、Me 的语义分别可辨认，Agent 不使用机器人脸、玩具或 Demo 风格。
- [x] 三个链接、标签、active 路由、未读 badge 与至少 48px 高触控区域保持正确。
- [x] 相关 Vitest、frontend build、文档门禁、diff check 和真实 `390×844` 浏览器验收通过。

## Roadpoints

### R1 — 真实页面 grounding 与 ImageGen 视觉探索

- 状态：DONE
- 验证：`390×844` before 截图、ImageGen 概念板与生成记录进入 `evidence/` / `progress.md`。

### R2 — SVG 规范化、接入与回归测试

- 状态：DONE
- 验证：AppShell 定向 Vitest 由红转绿，三枚 SVG 继承 `currentColor`。

### R3 — 浏览器与交付门禁

- 状态：DONE
- 验证：真实 tab 旅程、截图、build、docs、diff 与 CI。
