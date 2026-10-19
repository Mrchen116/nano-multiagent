# M1 交互回复实施记录

2026-10-19，独立 `.worktrees/unit-feat-617` / `unit/feat-617`，基线 cc47abe3f。按用户最新指示，只实施 617；616 由另一 Agent 继续，接入由用户在验收 617 后决定。

## W1：固定版本真实模型起点

- 依赖：OpenUI react-lang/lang-core 1.0.1，react-ui 0.18.1。前端现有 Zustand 5 保留；OpenUI UI/headless 声明旧 peer 范围，检查其使用的是 create/createStore/useStore/useShallow/subscribeWithSelector，均为当前公开 API，采用仅针对这两个包的 npm peer override。安装、Renderer 编辑/恢复/按钮回传测试及真实浏览器通过；未降级整个聊天状态库。
- 初始默认 DeepSeek 路由返回 HTTP 402 insufficient balance；无前端结果。改用已配置 `codexOAuth:gpt-6.1-sol`。随后用户明确要求主模型 6.1 sol、审核模型 6 luna，隔离配置已设为此组合，完整真栈的实际请求核验仍待完成。
- 首轮三个交互样本语法通过，但草稿被放进 placeholder，无法直接编辑。补充 value 参数指导后重跑四类样本，原始响应、token 用量、耗时见 `../evidence/openui-model-samples.json`。修订后草稿/提醒/行程分别约 13.88/18.66/31.61 秒；纯文字 9.76 秒且 source=null。
- 浏览器入口是本 worktree 临时 Vite harness；实际编辑草稿为“林悦，改为周日上午10点在断桥见。”，点击回调包含该修改和静态 action_id，刷新恢复。390×844 可操作；提醒单选和行程字段均实际打开。临时截图 `/tmp/feat617-openui-draft-mobile.png`、`/tmp/feat617-openui-itinerary-mobile.png`。这只证明库与生成起点，不代替完整消息链验收。
- 永久窄测试：catalog.test.tsx（真实 Renderer 编辑、恢复、动作）；interactive-source.test.ts（受约束源码与状态边界）；interactive-messages.test.ts（身份、CAS、提交幂等、正文保真、替代和离线排队）。先观察未实现时红测，再完成已覆盖行为；当前前端 1、IM 16 通过。完整产品验收与回归待实施完成后执行。

## W2：集成与当前验证

公开消息、完整 source 校验、不可变替代、每人私有 CAS 草稿、选择提交与 relay 原子入队、幂等重试、Relay/Global Inbox 上下文、fork 只读、Web Renderer 与普通输入附带选择均已实施。用户补充的 Agent Features `intelligent_ui` 默认启用开关已接通能力注册、配置页、DSH Feature 提示和 PA 发布限制。

- 完整 backend 初跑：95 suites / 366 tests passed，workspace-tools 安装测试在并发下超时；未改实现，单 worker 重跑该 suite / 1 test passed（53.24s）。
- Web 全量：99 suites / 893 tests passed。增加 Features 用例后 agent-detail-page 23 tests passed。
- 最新功能窄测：5 suites / 31 tests passed；原生 DSH communication-native 2 tests passed，实际跨进程验证默认提示、关闭消失、重新启用恢复。
- `pnpm build`、`pnpm typecheck`、前端 production build 通过；architecture 13 passed。生成资产由前端 `pretest` 执行一致性检查。
- 真栈 `http://127.0.0.1:58769`，own node `wt-unit-feat-617-88927`；普通 `e2e`、Global `e2e-global`。模型配置为主 `codexOAuth:gpt-6.1-sol` / 审核 `codexOAuth:gpt-6-luna`。隔离数据和密钥均不入库。
- 早期真实生成暴露：单线程模型空终结导致回复错误；生成提示要求明确非空 `NO_REPLY`，仅在已确认交互交付的该 turn 抑制其重复投影，并补回归。Global 早期 DSL 使用未声明局部变量；提示补足 `$` 声明、静态具名表单与完整 source 校验错误反馈。重试的新草稿与行程已真正交付。
- 浏览器已验证 Features 默认勾选→关闭保存→刷新保持关闭→重新勾选保存；草稿编辑成“周日下午2点北山街”，附带手写“先别发送”后，持久化原文与快照齐全，普通 Agent 正确理解新时间地点并保留不发送限制。Global 已交付步行/骑行及出发时间卡片。
- side agent 的默认 E2E 工具名单和 Global 预设修复在本需求内纳入，证据见 `../evidence/e2e-config-validation.md`。

完整独立静态审查、产品验收与最终归档/CI 尚待完成。尚未创建 PR、合并或部署；616 未修改。
