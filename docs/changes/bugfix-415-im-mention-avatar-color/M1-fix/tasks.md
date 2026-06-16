# bugfix-415-M1 Tasks

## 目标

修复 @mention 候选 picker 和新建群聊弹窗里 agent 头像颜色与其他界面不一致的问题。

## 退出标准

1. `mention-picker.tsx` 第 89 行 Avatar 传 `color={colorForAgent({ display_name, agent_id })}`
2. `new-group-modal.tsx` 第 105 行 Avatar 传 `color={colorForAgent({ display_name, agent_id })}`
3. 新增回归测试：断言两处 Avatar 底色与 `colorForAgent` 输出一致，防止「漏传 color」再次发生
4. 前端构建/类型检查通过（npm run build）
5. 修复/验证两段回填到 fix.md

## 测试策略

分类：bug-regression（历史 bug 修复，必须补 regression case）

两处调用点的回归方式：在现有 mention-picker.test.tsx 和 new-group-modal.test.tsx 中，渲染组件后查询 `.chat-avatar-face` 元素的 background 样式，断言它等于 `colorForAgent({ display_name, agent_id })` 的输出。这样，若未来某调用点又漏传 color，测试会报红（因为回退到 initials 种子会产生不同颜色）。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 添加 regression 测试（Red） | TODO |
| R2 | 修复两处调用点传 color（Green） | TODO |
| R3 | 回填 fix.md + progress 收尾 | TODO |
