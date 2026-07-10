# feat-379-M3 progress

## 初始化

- 基线测试: 2 failed / 328 (token-chip R8-3 + policies-page — 与本 M3 无关的既存失败)
- 既存失败 commit: a7b02d1e (M1 结束)

---

## C1 — 红测 (5ad7038a)

4 failing:
- agent-detail-page.test: 3 new M3 tests (BehaviorCard 不存在)
- agent-edit.test: 1 (System Prompt label 被移除)

## C2 — 实现 (169392b2)

变更文件: im-agent-config-api.ts, agent-detail-page.tsx, agent-create-page.tsx, agent-edit.test.tsx, agent-create.test.tsx, i18n/en.json, i18n/zh.json

最终测试: 2 failed / 334 (仅剩既存 token-chip R8-3 + policies-page)

`npm run build`: tsc 0 error，vite build success (535kB bundle)

browser self-test: IM (127.0.0.1:53163) + Vite (127.0.0.1:53164) 起服务，
Vite proxy → IM login 200，注册账号成功，API 链路通。
无 agent 节点在此测试环境中（纯 IM，无 Gateway），Behavior card 在 agent detail
页面需有 agent 配置才可见，单元测试已覆盖三态 checkbox + collapsible preview。

---

## C4 — 视觉证据补全 + i18n fix (Fast-lane)

Fast-lane 省略 §0.4 三提交，理由：reviewer 退回补视觉截图，属于 evidence 补充而非新功能实现。

**额外 fix**（浏览器自测发现）：
- `feat.label_i18n` / `feat.help_i18n` 直接渲染 i18n key 字符串的 bug → 改为 `t(feat.label_i18n)`
- en/zh.json 补充 `feature.memory_curation` + `feature.skill_creation` label/help 翻译

**完整链路 browser self-test（ephemeral 端口）：**
- IM: 127.0.0.1:54157，Gateway: wt-feat-379-M3 节点，Vite: 127.0.0.1:54158
- Gateway config 用 worktree 本地副本 `.gateway-config.yaml`，node_id=wt-feat-379-M3，不污染主仓
- 登录 → Settings→Agents→test-agent detail 页面，Behavior card 渲染正常

**截图证据（ACCEPTANCE/m3-behavior-card/，viewport 1440x900）：**

| 文件 | 展示内容 |
|------|---------|
| r01-behavior-card-full-1440.png | Behavior card 全貌：Custom Instructions textarea + Features 区块（Memory Curation + Skill Creation，均 disabled，灰色）|
| r02-behavior-card-policy-preview-collapsed-1440.png | Features + Group Reply Policy + `▸ Preview full system prompt`（折叠态）|
| r03-preview-expanded-1440.png | `▾ Preview full system prompt`（展开态）+ preview 区域 + 提示文字|
| r04-behavior-card-with-preview-1440.png | Behavior card 整体（含展开 preview）的完整视图|

**与 design ASCII mockup 对照：**
- checkbox idiom：复用 `appearance:none` + `:checked` 样式，无新 Switch 组件 ✓
- aria-expanded 折叠：`<button aria-expanded>` + `▸/▾`（a11y tree: `[expanded]` 已验证）✓
- custom_prompt textarea：Optional，placeholder 显示，label 正确 ✓
- Features 三态（disabled）：`[checked][disabled]` = default_on=true + available=false，灰色 opacity-55 ✓
- Group Reply Policy：preserved ✓
- tooltip：`title` attr 实现（native tooltip，hover 时浏览器显示）✓

**NOTE**：两个 feature 在测试环境均 `available=false`，截图仅覆盖 disabled 态。
checked/unchecked 态通过 agent-detail-page.test.tsx resolveEffectiveFeatures 单测覆盖（11/11 通过）。

**测试（C4 后）：** 332/334（仅 2 pre-existing），build 0 error
**服务已清理：** .im.pid / .gateway.pid / .vite.pid 全部 kill + 删除

---
