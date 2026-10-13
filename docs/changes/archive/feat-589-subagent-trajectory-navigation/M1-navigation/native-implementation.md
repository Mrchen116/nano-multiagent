# 单个原生派生视图实施记录

2026-10-13，取代旧双视图交付路线。设计门禁为 design-review Round 3；旧运行事实仍沿用，旧 UI 验收不作为新 UI 证据。

## 实现与边界

- 本仓 `@nano/trajectory-ui` 从官方 39 个源文件等价导入后独立维护，保留表格、时间线、折叠、搜索、请求与记录检查器。版权、许可和原始摘要保留。
- Viewer 只装配此插件，通过窄 navigation face 提供运行事实与公开 Session 补页。旧 execution-view、navigation-model 和其专用 renderer 测试删除；新的原生显示模型和补页 hook 测试承接相同行为，transport 测试保留。
- 行内发起动作和独立后台发起行由 run 事实驱动；本次范围是本地投影，不改官方全局 target。工具及实时输出的范围由原生请求/来源坐标决定。
- 同一原生组件切换本次与历史；原生时间模式各自推导范围，精确 seq 成员避免相邻时间条被误选。用户手动选择后停止自动接管。
- 父 frame 原地保留；书签增加 runId 维度，子 frame 固定 observer 重读身份。权限与图片读取继续使用原载体。

## 已执行验证

- RED：新执行投影测试先因尚无 navigation-model 失败；实施后 2 files / 8 tests passed，覆盖继承/后续 epoch、partial、工具坐标、后台插入、精确时间选区、同会话重连和软失败重试。
- `pnpm build`、`pnpm typecheck` 通过；`pnpm test` 为 65 files / 206 tests passed。
- 前端 `npm run test`：90 files / 840 tests passed；前端 build 通过。
- Python 非 E2E：56 passed / 31 deselected。Ruff check 通过；单个契约文件格式已修正并复查。
- 实际 bundle 样式错位确认为分开构建的 CSS module 短类名重叠（158 个）。本包保留描述性模块类名后仅共享既有全局 markdown 类，浏览器表格与时间线恢复。不是修改原生组件布局规避。
- 非管理者真实 Work 入口已进入后台技能复盘 fork（#447–#470），可切历史并定位本次输入，原生详情显示对应内容。完整独立产品验收另见本轮 acceptance。
- 作者观察三屏实际产品：1280 原生详情（本地截图）、820 历史中高亮本次（本地截图）、390 详情与关闭入口（本地截图）。窄屏沿用原生覆盖式详情，范围操作可达；来源链在宿主保持，原生 UI 只有一套。

## 隔离服务

保留 `http://127.0.0.1:63084/settings/agents/nav589?view=work&work_view=trajectory`，只读测试账户 reader589b / reader589b-pass；管理员 nano / nano1234。用户明确要求交付后继续运行，不能按默认清理规则关闭或移除 worktree。

同步 main b75ae90fa 后，隔离 IM 按新任务协作迁移命令 dry-run/apply/verify：0 棵图、0 节点、28 条消息保留，备份位于本机临时目录。仅测试库发生迁移，生产未变。随后用本 worktree 构建产物重启 IM，健康检查成功；原节点和真实 DSH 历史仍保留。

最终静态/产品门禁、截图和 CI 尚待本轮收口，以上测试不代替真实体验验收。

## 最终同步与 W2 修复

最终同步 `origin/main=36f2cad9e`，产品快照 `fb3ec48d3`。main 增量只涉及 profile 链接维护及部署路径；没有改变本次运行事实、权限或轨迹 UI。同步后首次窄测试使用了旧 integration/lib，重建后 profile、真实 run 与 UI 共 4 files / 15 tests 全过。

独立静态 Round 3 发现较早后台发起行会混入原生末 50 条窗口；修复仅将呈现下界改为当前显示 nodes 的首 seq。真实注册 bundle 探针先红后绿，并验证加载更早历史后该入口才重新出现。Round 4 code review 与 verifier 已通过，corrected-delta aligned。最终产品报告与远端 CI 另行记录。

本轮真实运行中使用专用测试聊天启动 12 轮只读 shell 子任务；对隔离 Node PID 78214 在17:01:15–17:03:05执行 SIGSTOP/CONT，DSH未重启，已有记录保留。该控制仅用于验证中断与恢复，生产未受影响。

## 交付门禁

独立产品验收 Round 3：15 Scenario 全部 pass，最终 `fb3ec48d3` 显示窗口修正已在重建后的真实服务局部复验。静态 Round 4 code review 无 finding、verification PASS；canonical 已归并单原生派生视图契约。随后仅保存报告、证据并整体归档，未改变产品源码；上述门禁保持有效。远端 CI 结果随 PR 交付。

用户要求保留试用，因此保留本 worktree、隔离 IM 63084 和其 Node/DSH 进程；设计临时 HTTP 服务已关闭。试用只读账号 reader589b 保持 active；资格失效用的一次性 reader589c 已停用。没有生产部署或自动合并。


## 用户反馈修正：完整会话中的自动选区

用户明确要求进入子执行等同于切换会话后在原生时间轴选中对应段。旧的本次投影与历史切换理解失效。本轮移除 scopeSnapshot，进入 run 后通过公开 Session API loadThrough(0) 加载完整历史，确认 hasMore=false，再在全量坐标中应用原生选区；继承前缀与其他 epoch 保持可见且淡化。当前执行下拉框随导航栈 push/pop 同步，显式选择则切换会话并重置栈。

验证：历史加载、实际注册 bundle 完整时间轴和宿主 active-session 回调均先取得 RED 再 GREEN。轨迹 UI 6 tests、宿主 19 tests、实际 fork bundle probe 1 test 通过，trajectory-ui typecheck 和 frontend build 通过。实际 63084 服务点击技能复盘后显示完整背景时间轴与 #447–470 选区；继承行保留且 data-timeline-focus=outside，顶部当前执行同步为技能复盘，返回发起点恢复父级。未修改运行时或生产服务。


### 最终主干同步

`96f5ac497` 合入 `74bfff7f7`（feat-587/588），仅三处文档冲突，保留空间权限、双方导航索引及各自契约。轨迹 UI/宿主导航实现未改变。重新完成 pnpm build/typecheck、前端 build、trajectory/tenancy/control-work 3 files / 12 tests 与 docs-check。测试数据库副本先执行新迁移，8 users / 3 agents / 29 messages / 20 work sessions 数量不变，nav589 仍在 company:default；随后更新隔离 IM，保留既有 Node 与 DSH。真实 reader589b 重新加载并从主轨迹进入技能复盘，仍完整加载历史、显示 #447–470 原生选区且顶部执行同步。生产服务未操作。


最终同步发现 W3：公司 owner 同时保留私人空间时，节点有效性不能替代 company Agent 的运行资格。轨迹 browser prepare 与持续 valid 均复用既有 agentAvailable 检查；不关闭仍服务私人资源的整个节点。新增混合节点回归先确认 company observer 未关闭的 RED，再验证现有/新建 company 观察被拒绝、私人空间重新登录后 session/page 仍可读取；相关 3 files / 13 tests GREEN，IM build/typecheck 通过。该修正兑现既有 auth-tenancy 停用边界，无新增用户能力。
