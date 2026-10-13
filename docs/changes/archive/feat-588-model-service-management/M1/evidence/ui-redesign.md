# UI 反馈闭环

2026-10-13 用户实际试用否定旧页面的视觉与组织，并指出现有 Skill 已要求 UI 设计。旧版的原型“无溢出/可操作”证据不能支撑体验通过，作者已撤回其 UI 完成度判断。新的 design/prototype 经独立 Round 3 找出手机悬浮保存遮挡、电脑归属可切换两项问题，修正后 Round 4 Approved，0 CRITICAL / 0 WARNING。后端事务/权限及分发边界未因本轮改变。

## 实际产品走查

服务为本 worktree 的隔离 IM `http://127.0.0.1:52267`，测试账号 nano，原测试电脑和数据保留。仅重建 Web 静态产物，未重启 Node、IM 或改写已有服务配置。

- 1440×900：单一页面标题与新增同组；电脑归属为紧凑上下文；服务按名称、类型、模型读取；菜单模型入口取消多行说明并区分电脑图标。
- 390×844：两项服务和新增/订阅入口同屏；编辑、低强调移除同行；无需大头像、标签背景和重复章节标题。
- 真实编辑：打开日常助手 API，密钥不回显，填写模型显示名称仅保留草稿，实际点击/聚焦后字段完整可见，取消后回到原列表且电脑解锁。没有保存这些演示更改。
- 768×1024：新增自定义 API，连接和模型两组清晰，API 地址/协议合理双列；取消未改变真实模型配置。
- 真实订阅授权：在此前操作结束后发起一次测试登录，等待真实 DSH 授权页链接/代码；反馈位于订阅区域，两个服务仍在其上方。随后取消本次测试操作，按钮恢复；没有完成账号授权。
- 取消反馈按 API 草稿/账号连接/移除区分，避免没有草稿时仍提示草稿保留。

截图已由作者实际查看，外部根目录：`/Users/czj/.codex/visualizations/2026/10/12/01a130c5-e6d4-7b60-aad8-33ac995ff4ef/feat-588/`。代表截图：`ui-after-desktop.png`、`ui-after-mobile.png`、`ui-after-menu-desktop.png`、`ui-after-editor-mobile.png`、`ui-after-focus-click-mobile.png`、`ui-after-add-tablet.png`、`ui-after-authorization-mobile.png`。用户原截图保存为 `user-ui-before-desktop.png` / `user-ui-before-mobile.png`。缓存不提交。

## 验证边界

相关 models/onboarding/Me/shell 4 文件 22 tests 通过，前端 TypeScript + Vite 构建通过。最后仅调整取消文案后再跑 models tests 和构建。以上为作者自检，独立产品验收仍在本 unit 的 M1 acceptance 中记录，不能以设计 Gate 2 或本文件代替。未部署生产。
