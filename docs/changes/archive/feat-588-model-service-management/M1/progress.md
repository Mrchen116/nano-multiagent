# M1 实施记录

## 基线与范围

- Gate 2：UI 重做后的 design-review Round 4 Approved，0 CRITICAL / 0 WARNING。
- 实施分支：`codex/feat-588-model-services`，前置 PR #337 `7083a0936`，同步 main `6275f271d`。
- main 新增 bugfix-585 为节点连接恢复、presence reconciliation；没有改变本 unit 的模型 setup/DSH public seam、配置存储或 installer 设计。实施基线已合入，Gate 2 的职责与接口判断 retained；后续真实离线恢复在该组合树验收。
- 主 Agent 负责模型服务、前端、集成与收尾。首轮独立安装分发任务负责 install/build/release 及其最窄测试，不修改模型文件；后续修复统一主 Agent。

## 测试策略

- Node model-setup 既有新增/失败用例 rewrite-merge，增加编辑保留凭据、多模型/同名 wire ID、版本冲突/依赖保护及共享队列交错。开发者代理自动发现已退出普通产品路径，其专用测试删除；保留可手填自定义 loopback 行为。
- DSH integration model-setup 保留真实锁定 runtime/HTTP 与 OAuth 取消；扩展 credential/profile stage 回滚、真实目录及旧连接不受 probe 影响，不在 mock 层重复整个用户旅程。
- IM onboarding owner 双侧与安全投影测试 keep/extend；安装行为由 installation 子任务维护，不与模型 owner 测试重复。
- Web 共用编辑器测试承担草稿/厂商身份/revision 的交互回归；真实浏览器负责信息组织、移动布局、首次及日常管理到真实回复。
- fixture、截图和录像保留外部 artifact 路径，实际结果记入 evidence，不提交本机运行数据。

## 实施与作者验证

- 已实现 DSH 动态目录、Node 独立 probe 与提交/回滚、持久化共享队列、同名上游模型的服务限定引用、IM 安全投影和常驻/首次共用编辑器。新增与编辑不扫描开发者代理配置。
- 安装分发首轮交付见 [release-distribution](evidence/release-distribution.md)，没有发布 GitHub Release 或部署。
- 本地 backend 串行全量 67 files / 205 tests 通过；Python contract 54 passed / 31 e2e deselected；前端全量 89 files / 842 tests 通过。测试命令与日志在本机 `.runtime/feat-588/`；早期并行 runtime 资源竞争的超时以串行全量及窄复核收口。
- 作者已在真实浏览器配置两服务、同名上游模型、多模型，更换 URL/key 后同一助手回复；相关图片保留到外部 artifact。后续独立验收以自己的实际结果为准。
- 用户试用反馈触发 UI 设计重做；独立设计 R3/R4 闭环后重排实际页面，具体视觉/操作和证据见 [UI redesign](evidence/ui-redesign.md)。此次改变触及 Web 布局与授权反馈，后端验证 retained，相关 22 Web tests 和构建通过。
- 用户要求测试服务保持运行：52267 是用户试用环境，不能为独立验收清空或重启；独立验收另建隔离栈。

## 独立审查后的修复

- 静态 R1 在 `eff9d6daf` 发现旧 YAML 内联凭据按服务数组下标绑定：删除 A 后，仍使用 B 的同一会话发送 A 的 key。新增真实 DSH/HTTP 回归先复现失败，再将环境变量名称固定到不可变服务 ID 的完整 UTF-8 hex；移除其他服务不再改变绑定。
- `/tmp/nano588-legacy-red.log` 保留失败的实际 Authorization 对比；`/tmp/nano588-legacy-green.log` 为 providers/model-setup/configuration/integration model-setup 四文件 15 tests 通过。独立复验尚待最终批次冻结。
- 文档检查通过（252 maintained sources / 64 routes）；Ruff check 与 format check 通过（82 files）。
- 产品 R1 另发现内置厂商标签在改名/重启后被服务名覆盖；主会话以真实 DSH 冷启动目录红测确认后移除 native profile 的产品标签覆盖。四文件 11 tests 通过，原因与回复后上游 502 的独立取证见 [product R1 triage](evidence/product-r1-triage.md)。

## 最终门禁与交付

- Code review R3 `[]`，verifier R3 PASS / 0 CRITICAL / 0 WARNING / 0 SUGGESTION，`validated_at=6309714219ba8cc1432e5e1752a94b50a7d8ad35`。W1 与厂商身份问题均关闭；corrected-delta aligned。
- 产品 R2 PASS / 0 blocking / 0 major / 0 minor，`validated_at=1580bdfb0627e9e9cc614dd3e6a41a63e58c2d47`。R1 完整旅程 retained，R2 实际重验厂商改名/刷新/冷重启/删除后目录及同一助手真实回复。手机证据是浏览器窄屏，不是物理设备验收。
- 两次最终静态/产品验证的 `executed_base` 与 final-sync `effective_base` 都是 `b7e367cc08a642133dea28e372816cd79038818d`。最终 fetch 无新增 main 提交；相对原基线新增 main 仅 feat-589 需求文档。有效源码在上述验证后没有变化，报告提交、canonical 归并与整体归档不影响运行语义，门禁 retained 到 PR 的最终 head（PR body 记录其 `effective_through`）。Gate 2 R4 的布局与职责契约也未改变。
- 已将独立校正的 IM MODIFIED/ADDED、Gateway ADDED delta 归入 current specs，同步入口数量与文档地图。`pnpm -r --if-present build`、`pnpm typecheck` 和安装候选构建通过；Ruff、文档检查、`git diff --check`、前端 critical audit 通过，audit 为 0 vulnerabilities。保留此前全量与本轮针对真实缺陷的窄回归证据，不重复无关全量。
- PR 依赖仍开放的 #337，以 `codex/feat-587-first-run-onboarding` 为 base；不能先于该前置变更合入 main。未自动合并、发布 GitHub Release 或部署；S9 按设计允许的精确下载 fixture 验证，公网匿名 Release 下载仍需正式发布后验证。
- 用户要求保留的 52267 试用服务与本 worktree 保留。独立验收栈和作者临时原型由主会话清理；用户明确结束试用后再清理 52267/18489/18490 并归档 worktree。

## 同会话图标反馈收口

- 用户要求移动端“我的”其他入口沿用模型服务的细线风格；将桌面既有 SVG 提取为共用组件，七个入口统一 18px / 1.7 stroke，移除 emoji 和图标底色，公司成员使用独立双人图标，退出保持红色。导航、权限、状态和 API 未改，无 spec delta。
- 源码提交 `c6b4455e158a32f71e179de19477ad65b2432158`；`1bb8ff98e` 仅清理文件尾空白。MePage / AppShell 两文件 8 tests、TypeScript/Vite build 和变更范围 diff-check 通过。
- 独立静态 R4 PASS / code review `[]`，旧模型服务与安装门禁 retained。仅补充手机与桌面菜单视觉复验，原 S1–S9 证据不重复执行；最新结论见 [acceptance](acceptance.md)。
- final fetch 的 main 仍为 `b7e367cc08a642133dea28e372816cd79038818d`；图标一致性未改变 Gate 2 的布局和职责设计，其余后端/安装/安全验证 retained。最终报告与进度记录不改变运行语义，effective_through 以 PR body 最终 head 为准。
