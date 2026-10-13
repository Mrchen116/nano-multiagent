# bugfix-598: 技能禁用状态与新版页面入口

## Relations

- Related: [refactor-593](../refactor-593-skill-denylist/motivation.md)

## 原始报告

> tmd，把禁用名单显示成了启动，禁用应该是灰色的啊
>
> 这个做个快速修正，然后提pr

## 现象 / 复现

截图中 daily-journal-write 为绿色，但当时持久配置的 explicit_denylist 包含该名称，运行时拒绝加载。截图缺少 #345 新增的默认启用提示。重新加载生产页面后，新版选择器能正确显示禁用项为灰色；当前源码未复现颜色反转。另已将该 Skill 从生产禁用名单移除，独立 DSH 加载验证成功，此配置操作不包含在本 PR。

## 根因

#345 将 skills 字段从允许名单迁移为禁用名单，旧页面代码会继续将该数组当作启用项。当前新版组件已正确求补集，不应再次反转。已确认页面 HTML 响应没有显式缓存策略；不能证明截图具体来自 HTTP 缓存还是一直打开的旧页面。本修正要求入口每次加载重新获取，防止刷新时复用旧入口，同时直接保护禁用灰色/启用绿色的既有契约。不引入自动刷新正在编辑的页面；已打开的旧代码需手动刷新。

## 修复

仅为前端 HTML 直达与 SPA fallback 加 no-store，脚本/CSS 返回策略不变。选择器现有求补集逻辑保留；扩展其已有测试验证真实灰色/绿色样式，详情页测试验证禁用名单保存及重新挂载。current spec 明确颜色、计数和入口缓存契约。

## 验证

- 修前 frontend.test.ts 在缺少 Cache-Control 断言失败；修后通过，覆盖 /、/index.html、Agent 配置页、/chat 与普通 JS。
- 相关 Web 27 项测试通过，包括禁用灰色、名单外绿色以及保存后重新打开；页面测试使用 API mock，不能替代生产用户实际重试。
- 生产新页面已观察到取消 ongoing-work 后为灰色；该草稿未保存并已刷新丢弃。
- 旧截图具体的旧代码来源未证实；本 PR 不会热替换已运行的旧代码。无模型、技能内容或生产配置修改。
- Web 全量：92 files / 860 tests passed。
- pnpm build、pnpm typecheck 与 Web build 通过。
- 后端全量：272 passed / 1 failed（既有 approval.test.ts 审批场景，本次未修改相关代码）；单独复跑该文件 5/5 通过，保留首次全量失败事实。
- 独立 code review：无 findings。docs-check 首次发现新增 Requirement 的入口计数未同步，已修正。
- docs-check、change unit 归档检查与 git diff --check 通过。
