# feat-700 Validation

日期：2026-11-02。本轮验证公共页面与 case 建档，不是正式能力评分。用户确认待完成。

## 代码与边界

- Node v24.22.1：evals TypeScript 检查通过；Node/integration 构建通过。
- `pnpm exec vitest run evals/ui packages/dsh-integration/tests/observation-only.test.ts packages/dsh-integration/tests/runtime-profile.test.ts`：5 文件、9 tests 通过。目录折叠窄改后重新执行 evals/ui 4 tests。
- docs-check：282 maintained Markdown sources、68 required routes 通过；git diff --check 通过。
- runtime dependency contract：13 tests 通过。无 DSH private import、内核 fork 或第二套执行循环。
- 已有 runtime-profile 测试 keep，保护普通执行与恢复未退化；新 observation-only 在真实公开 RPC seam 保护归档不触发绝对路径恢复副作用；导航延迟关闭回归在 DOM seam 保护切换 case 不被旧观察流覆盖。检索现有 tests 未有这两种失败原因的同因保护。
- catalog/server 测试保护固定材料接线、已有证据不冒充新执行和本地读取 capability。截图与单次原件哈希仅保存在 ignored output，不进入永久测试。

## 实际页面

- 公共入口：<http://127.0.0.1:59335/10545764-3b0f-4a2c-82d7-edd83324bac9/>；viewer 状态 `output/capability-eval-viewer/state.json`，日志 `output/eval-ui-viewer.log`，运行在 tmux `capability-eval-ui-final`。
- CUA 实际查看酒店照片固定输入、酒店/看板用户参考原图、会议选择步骤和五项判定；页面明确显示已有独立现场不是重新运行结果。
- CUA 打开 Memory 冷答题与 Dreaming 第 1 批，确认原生轨迹加载、真实请求和工具记录可读。默认折叠阶段后两项能力与三个 UI case 同屏可见；展开可访问18阶段。截图 `output/eval-ui-evidence/common-viewer.png`。
- 原 Memory 归档 `longmemeval-window-one-case-20261030-005908` 的 agent-work、analysis、run、trial-summary 共439文件，读取前后 SHA-256 无变化；清单与比较在 `output/eval-ui-original-{before,comparison}.json`。
- 默认页面仅建档，零模型调用。已有 Memory 轨迹仍包含原实验自己的错误和结果，未修改或重新判分。

## 保留服务与边界

按用户“测试完不要关服务”的明确要求，公共 viewer 和原三个产品服务保留，开发 worktree 保留。关闭公共 viewer 可按 state.json 的本轮 pid 发 SIGTERM，只释放它自己的观察流和 DSH；不会停止以下已有产品服务：

- 会议：<http://127.0.0.1:50985/chat/c_f904c9b5844a>，`output/runtime-openiui`。
- 酒店：<http://127.0.0.1:51193/chat/c_4718644999af>，`output/runtime-openiui-clean-hotel`。
- 看板：<http://127.0.0.1:51507/chat/c_b101f7e09046>，`output/runtime-openiui-clean-dashboard`。

这些是上一轮独立上下文现场；看板手机图表过小等已知问题没有冒充修复或通过。本轮不提供正式自动运行/评分，fresh-context 是已记录的执行前协议，尚未交付自动隔离器。未提交运行数据、日志、密钥、PID或截图缓存。

## Dataset v2 四例增补

- 用户同意新增 activity-budget；会议原样保留，检查真实确认消息及 Agent 回复。新 case 自然任务不点名 UI、不附界面参考，包含固定报价、初始选择、40→50人容量变化及自行前往的操作检查点。
- Node24：evals/ui 3文件4 tests及evals TypeScript检查通过；独立窄 patch review `[]`。仅扩充材料，不重跑产品运行时测试。
- CUA 实际打开四例目录和新增 case，核对固定输入、从零上下文、步骤、判据及“未运行”状态。截图 `output/eval-ui-evidence/activity-budget-case.png`，不冒充候选完成或正式评分。
- 当前公共入口更新为 <http://127.0.0.1:63351/609d5ed3-d53b-4919-a454-20b407ed6541/#activity-budget>，tmux `capability-eval-ui-v2`，日志 `output/eval-ui-viewer-v2.log`；最新 pid/url 仍在 `output/capability-eval-viewer/state.json`。旧版公共 viewer 已替换，原三个产品预览不停止。开发 worktree 和更新后的服务保留。

## Dataset v3 自然广告分析替换

- 用ad-analysis替换activity-budget，仍4题；固定候选输入只包含自然业务问题与本地CSV，无UI、图表、交互或组件要求。合成数据12行9列、两周三个地区两个渠道。
- 依据用户最新纠正，分析、计算、业务归因不评分。使用按真实发布调用携带interactive.source的是/否记录，主观视觉质量单列，加载Skill或写代码不冒充使用；未跑/轨迹缺失未判定，调用失败与呈现失败区分。没有新增评分执行器或模型裁判。
- evals/ui 3文件4tests、evals TypeScript通过；server测试覆盖CSV读取、缺token拒绝、未登记附件与路径越界拒绝。原三个case无变更。独立patch/closure审查 `[]`。
- CUA实际查看四例目录、固定业务输入、附件下载入口、操作与判据；点击下载入口无页面错误，HTTP测试确认CSV读取，未宣称实际候选完成。截图 `output/eval-ui-evidence/ad-analysis-case.png`。
- 当前入口 <http://127.0.0.1:64734/96c2a32c-6937-447d-8983-b6bf72243188/#ad-analysis>，tmux `capability-eval-ui-v3-final`，日志 `output/eval-ui-viewer-v3-final.log`；pid/url仍在 `output/capability-eval-viewer/state.json`。旧公共viewer已替换，保留最新服务、原三个产品预览与开发worktree。
