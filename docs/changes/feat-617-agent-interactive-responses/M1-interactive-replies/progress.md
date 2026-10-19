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

## W3：独立验收修复

产品 Round 1 在 `aaa6bfc24` 完成完整真实旅程，报告见 `../acceptance.md`。A1 离线提交缺少待处理提示成立并阻塞；A2 选择摘要显示内部值成立。`0a7b187a8` 为修复前实现基线（随后 `613f33765` 仅验收报告）。修复仅增加 pending 消息提示、收到 relay 回执后的消息刷新，以及从公开卡片选项生成的 display_value；原始 value 与不可变历史继续保留。提交卡片用中性“选择已提交”，实际业务结果仍由后续 Agent 回复说明。

先复现三项红测：选项标签缺失、待处理提示缺失、收到回执后仍未清除提示；修复后 IM 2 suites / 18 tests、前端 4 suites / 162 tests 通过。`pnpm typecheck`、前后端构建通过。产品 A1/A2 定向复验、静态 patch 与 verification closure 后执行最终同步、归并、归档和 PR CI；616 未修改。

## W4：交付收口

最终实现候选 `a211d7643`，产品 Round 2 报告提交 `2183e3870`；产品 PASS、静态 code-review `[]`、verification PASS / 0 CRITICAL / 0 WARNING，三份 delta aligned。A1/A2 与 C1 均关闭；单选/多选、离线恢复无需刷新、正常提交与后续模型结果均有独立现场证据。完整 Web 最终 99 suites / 899 tests 通过；归档前 docs-check 249 maintained Markdown / 64 routes; post-archive docs-check 237 maintained Markdown / 64 routes, archive gate passed. 其余本地 CI 使用 W2 中有效结果，修复相关 IM18/Web162 与前后端构建/typecheck 已追加覆盖。

Final sync 通过 HTTPS fetch 与 GitHub main API，`origin/main` 仍为 `cc47abe3f92eebbf8f9d3fb1b1e221d95625599d`，无 main 增量。产品首次 full 在 `aaa6bfc24`、targeted 在 `a211d7643`；静态 full 在 `0373d8fec`、后续 closure/patch 在 `aaa6bfc24`/`a211d7643`。报告逐项保留未受影响证据；最终归并与归档只改变契约归属、路径与交付记录，不改运行代码或门禁判据。effective_base 为上述 main，effective_through 使用 PR 所列最终 head，原 executed_base / validated_at 保留在独立报告。

三份产品 delta 按已审内容归并到 canonical specs，整个 unit 归档。feat-616、主 checkout 既有修改及生产环境未改动。临时 W1 Vite 与遗留 DSH 进程已清理；隔离产品实例与测试数据保留供用户评估 617，完成评估后由本 worktree owner 清理；主仓原型预览未改动。原生 App / 外部渠道只有文本边界回归证据，未声称真机或外部现场验收。


## 2026-10-19 用户实测后的范围纠正

原 PR #366 / cf4b17f00 的表单切片未满足通用 Intelligent UI。用户普通知识问题实际仅得到文字，授权恢复 OpenUI 能力，并要求无交互提示的指定原话和跨领域实测、禁止专用答案/组件。unit 恢复 active；原证据保留但不外推为本次目标通过。spec/design/delta/prototype 已按新边界修订，待独立 Gate 2；产品代码尚未修正。


## R3：按用户反馈恢复完整 OpenUI（实施候选）

- 用户明确要求保留 OpenUI 能力，以普通“给我讲解下冒泡排序”实测，禁止交互暗示与题目专用实现。R4 design closure Approved；原表单验收不代替此次验收。
- 保留全部 82 个上游组件，新增的第 83 个仅为旧 ContinueButton 兼容；保留原生动作、计算、条件/Each、Query/Mutation/toolProvider。宿主工具为当前会话读取和当前用户继续对话，不隐式开放本地文件或任意系统调用。
- 私人状态使用原生 store；请求按独立幂等键保存，提交后可继续探索；原生 message/context 与可见点击文字分离，完整 state ref 与 Form 局部状态合成；手写输入保持原文与冻结重试键。增量 source 经 mergeStatements 存成完整新版本，发布幂等比较原始输入。
- 定向红绿：旧库拒绝 Button/Query，提交后草稿锁死，patch 无 root；修复后 22 项 source/messages 通过。真实第一轮模型样本暴露 Select 数字绑定使当前标签为空，保留失败消息；通用字符串绑定指导与按声明类型校验覆盖初值和 Set，无题目专用分支。
- 真实浏览器：Global 原话在 17:56 生成步骤/柱状图/重置；18:06 再发同一句（先取消旧状态附带）生成显示正常的版本。普通 Agent 原话“给我讲解下单利和复利的区别”生成输入/下拉/曲线/动态金额，2万元、10% 显示26000/26620与差620；刷新保留。自然语言追问保存当时参数；提交后仍可调至3万元，前一快照仍为2万元。后续完整证据与独立验收待补。
- 验证：前端99 suites / 905 tests；IM与PA交互22 suites / 108 tests；pnpm build、Web build通过。日志分别 /tmp/feat617-native-final-web-tests.log、/tmp/feat617-native-im-tests.log、/tmp/feat617-native-build-3.log、/tmp/feat617-native-web-build-4.log。最后只加发布原始输入断言，interactive-messages 11项再次通过。
- 本 worktree 保留数据重启：IM健康且Node ready；旧会话/历史/草稿未重置。主 checkout、feat-616及生产未变。隔离浏览器 Slider 在 jsdom 组合测试耗时异常，真实浏览器验证 Set 2→3、手动3→4正常；未替换或裁剪 Slider。


### 2026-10-19 18:16 完整原生实测与 W2 修正

完整实测源和失败样本已保存在 [新作者走查](../evidence/native-browser-review.md) 与 native-model-samples.json。普通原话跨领域自主生成、原生重置/刷新、同卡两轮手写快照与回答均实测通过。完整backend96/373、Python62与typecheck通过。独立静态W2同次native请求WS/POST双增revision已先红后绿：统一权威读回版本，保留当前编辑，2 suites/16 tests。等待冻结版本独立closure与产品完整新轮报告；未宣称门禁完成。


### 2026-10-19 18:18 产品复验失败重试修正

独立产品 reviewer 在真实模型新卡片的第二次手写请求中中断POST，发现Send被可访问树判为disabled。确认button本身不需要禁用，原因是附件dropzone的aria-disabled向子控件继承。改为data-disabled，仅禁用文件drop行为，不向整个输入区施加禁用语义；未知请求的正文/状态/key仍冻结。回归用实际Send按钮点击代替直接form submit，并断言无禁用祖先，先红后绿；附件禁用仍拒绝drop。3 suites/18 tests通过。前一版全Web99/907通过；本修复后再跑最终Web。origin/main final fetch仍cc47abe3f，无main增量、无重合变更；所有门禁base保持cc47abe3f。
