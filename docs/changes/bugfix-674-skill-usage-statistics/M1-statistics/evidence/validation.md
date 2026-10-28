# 实施验证

基线：origin/main ff326c351；初始设计 2bca4754e。隔离 worktree，无生产写入。实现后的 commit 与最终门禁见后续记录。

## 测试归属与处置

- 扩展 `packages/dsh-integration/tests/knowledge.test.ts`：新旧统计隔离、75 次调用、样本被其他 Agent 挤出、重开文件、去重与跨 30 天窗口；扩展既有 Global Inbox 真实 runtime 测试，确认 skill_creation=false 仍计数且重启不重计。F4 原维护测试保留，仅更新内部签名。
- 扩展 `apps/im-server/tests/agent-settings.test.ts`：两条公开 API 共用投影，不透出内部聚合，旧 live/snapshot 拒绝与新版离线缓存保留。
- 扩展 Web 现有 Agent 页测试：累计与窗口合计分开、服务端固定 UTC 日期、起点前未知桶；未新建重复 E2E 套件。
- 扩展 iOS AgentContractsTests：解码后的累计/窗口值及图表日期过滤；无导航或系统集成改变。

## 已执行

- Red：新增存储回归在旧实现失败，期望新计数 0、起点 null、无新引用，实际返回旧 999 及旧引用。
- Green：knowledge.test + knowledge-review.test，10 tests 通过；包括 F4、维护 fork 与关闭自进化的真实 DSH 子进程。
- IM settings：20 tests 通过；Web Agent 页：27 tests 通过。
- pnpm build/typecheck/check:ios-runtime、Web production build 通过，使用 Node 24.22.1。前端构建仅有既有 bundle 体积提示。
- iOS 新统计契约测试通过；首次全量测试在旧通用模拟器的图片剪贴板用例失败，尚待隔离基线复核，不据此声称全量通过。

## 设计澄清

`/skills/usage` 真实现有离线契约是 HTTP 503（rpc helper），不是设计分析中误写的 node_online:false。实现保留 503；设置页沿用 unavailable/last_known 语义。此为 current grounding 文字纠正，无新增兼容分支。

原型截图为 gitignored 本地产物：unit 根部 `evidence/prototype-{desktop,mobile,mobile-scrolled}.png`，不提交 Git；设计中含实际观察文字，交付 PR 不将图片链接当作远端证据。
