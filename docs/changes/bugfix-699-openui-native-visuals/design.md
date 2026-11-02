# bugfix-699: As-built Design

> 本文在实现后按实际 diff 整理；Agent 视觉自验已完成，用户确认仍未完成。

## 实现范围

- Base / executed_base: `95c6b3deb07c03e9edd3b78375cd0ae29e87558e`
- Branch: `codex/openui-native-visuals`
- 受影响：Web InteractiveCard、生成指导及其生成资产。

## 最终结构与决定

- 删除 interactive/theme.ts；InteractiveCard 保留上游 ThemeProvider 的 scope/portal 支持，使用其默认 light theme，不注入 Nano token。
- 删除卡片、文字控件字体与图表等额外皮肤覆盖。宿主仅保留聊天空间、只读可读性、状态提示以及 row/wrap 的最小列宽，避免手机挤成不可读的多列。
- catalog.tsx 的 additionalRules 改为上游默认视觉与按参考自主组合；鼓励匹配密度、尺寸和真实图标，保持轴单位及示意流程/定量图表的区别，不能伪称不支持的 HTML/CSS 或组件可用。
- 短常驻 policy 同步改为上游默认视觉与自主组合，避免在加载 Skill 之前仍要求 Nano theme。
- 生成链不变：catalog.tsx → scripts/generate-interactive-ui.ts → integration prompt.md 与 PA nano-interactive-ui/SKILL.md。两条消费入口同时更新，组件 schema、工具、动作权限和持久化不变。
- 未增加参考场景专用组件或固定模板；酒店和看板仅为本轮验证输入。

## 兼容、风险与回滚

- 历史卡片源码及私人状态不变，读取时获得上游默认视觉。
- 官网定制示例不等于固定版本默认组件；依靠通用组合尽可能接近，具体限制在验证中披露，不承诺像素等价。
- iOS 原生视觉不在本轮，生成指导的组件语义仍来自共享目录。
- 回滚本次源码与生成资产提交即可恢复原主题；无需数据迁移或安装包发布。

## 验证定位

见 [validation.md](validation.md)。实际浏览器截图和原始模型/运行材料留本机 output/；不提交私人原图、凭据或 runtime。

## Canonical 影响

必要 delta 见 [specs/im/web-chat-ux.md](specs/im/web-chat-ux.md)。用户确认前不归并、不归档。
