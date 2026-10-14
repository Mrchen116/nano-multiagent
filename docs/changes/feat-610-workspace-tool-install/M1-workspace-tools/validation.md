# M1 validation

- implementation tree: `33ef0d76d342a10c411ccbc0828f82d0d564e810`
- executed_base: `9182699fca58d42fbf166f3de7445c635dcb3527`

## 回归保护与处置

既有 `packages/dsh-integration/tests/capabilities.test.ts` 保留：静态两层扩展、显式空集、配置热变更与 PTC 执行限制仍适用。新增 `workspace-tools.test.ts` 归属 workspace 安装生命周期，使用真实锁定 DSH 子进程和确定性模型，经原生工具调用验证先加载失败→修正重装→同一轮实际调用、同 workspace 第二聊天、跨 workspace 实际拒绝、禁用静态工具/空集、另一个坏 bundle 不破坏好工具、重启恢复与持久停用、重新启用/移除。该风险此前没有安装链路保护，没有重复测试框架或私有方法。

开发过程先确认新测试在未实现版本失败：Agent 工具列表缺少 `plugin_manager`。安装核心复用原生服务；未复制 package-manager、patch parser、Agent Loop 或模块缓存处理。

## 检查结果

| 命令 | 结果 | 证据边界 |
|---|---|---|
| `pnpm build`、`pnpm typecheck` | passed | 本地构建和类型检查；不代表生产部署 |
| `pnpm test` | 84 files / 313 tests passed | 包括原生子进程生命周期；模型 fixture 不能替代真实 LLM 产品验收 |
| `python -m pytest -m 'not e2e' -q` | 56 passed / 31 deselected | standalone tooling / architecture |
| `ruff check .`、`ruff format --check .` | passed / 82 files formatted | Python gates |
| 前端 `npm ci`、`npm audit --audit-level=critical`、`npm test` | 0 vulnerabilities；94 files / 881 tests passed | 未改变客户端；常规前端回归 |
| `PYTHON=<main>/.venv/bin/python ./scripts/docs-check` | 239 Markdown / 64 routes passed | 修正 delta 中复制的相对链接后通过，无契约语义变化 |
| `git diff --check` | passed | diff 格式 |

独立静态审查、corrected-delta 和真实 IM+Node+DSH/LLM 产品验收结论分别见 unit 的 code-review、verification 与 acceptance 报告。隔离真栈使用 worktree 专用身份、workspace、运行数据和随机端口；不触碰生产配置或服务。

## 安装版包管理器补充

收尾发现安装器把 pnpm 安装在私有 tooling 目录，LaunchAgent PATH 不含它。将真实 DSH 测试进程 PATH 设为空目录，并通过 initialize 传入可信 packageManager：修复前 install_bundle 返回 exitCode=127 / spawn pnpm ENOENT；接通原生 ProfileContext.packageManager 后，同一完整安装/失败修复/隔离/重启测试通过。Node 已安装 release 测试通过实际执行 installer 所用私有 pnpm 路径验证 resolver；源码 release 保持默认。

- `pnpm build`、`pnpm typecheck` passed（本轮含安装版接线）。
- `pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts apps/node/tests/node-updater.test.ts`：2 files / 4 tests passed。
- 红/绿证据：`/tmp/feat610-pinned-pnpm-red.log`、`/tmp/feat610-pinned-pnpm-green.log`。
- 产品验收在原核心实现 `33ef0d7` 已完成 7/7 场景；新增接线仅改变安装版的原生包执行命令，源码真栈语义未变。
- 隔离 Node/DSH 两次重启后由 `e2e-down.sh` 按 lifecycle 状态正常停止；IM 随同停止，端口54267与PID505/511已确认不存在。

## 最终集成与门禁有效性

- final sync：origin/main 仍为 `9182699fca58d42fbf166f3de7445c635dcb3527`；无外部推进或冲突。
- 最终源码版本：`d7265f0a3a11a3467d9acb421ad6e45ec4721fbd`；build/typecheck passed；全量84 files/313 tests、non-E2E pytest56 passed/31deselected。未改前端/Python规则，保留此前881项前端与Ruff通过证据。
- 独立设计R4 Approved 0/0；独立code-review patch findings=[]；verifier delta pass/corrected-delta aligned。
- 真实IM/LLM产品7/7通过的validated_at为`33ef0d76d342a10c411ccbc0828f82d0d564e810`；静态审查已确认安装版可信命令接线不改变源码产品旅程，保留该报告。
- effective_base：`9182699fca58d42fbf166f3de7445c635dcb3527`；effective_through：本归并/归档提交（可用`git log --grep='archive feat-610'`定位）。后续只含报告、已校正delta原文归并、目录移动和相对链接修正；没有运行时代码变化，已审源码与验收结论retained。
- 用户要求继续网页体验，因此重新启动同一隔离栈，保留workspace、数据库与配置。服务不会在本轮交付时关闭，worktree保留给用户；后续用户结束体验时按此worktree的`./scripts/e2e-down.sh`停止，再归档worktree。生产未改动。

## 用户网页体验场景

在最终源码d7265f0上重启保留的隔离服务，真实DeepSeek模型自行创作`expense-summary-bundle`三个文件，通过`plugin_manager`安装启用并实际调用`expense_summary`，5条跨月支出得到2026-10的4笔、办公89.90/交通50.70/餐饮48.00，总计188.60元；9月20元正确排除。用户消息`43132288c4de4befa27070feae34444c`、回复`f5084f651ba04857b5473dd4b2f223b0`，聊天`c_pp1ump8j`。未修改白名单、未为安装重启。浏览器已正常登录测试账号并打开聊天，展开Process确认三个write、plugin_manager与expense_summary输入/结果真实可见。服务IM端口54267、Node/DSH启动时PID5181/5187，保留给用户继续体验。

## 配置页反馈闭环

用户实际设置页发现已可调用工具仍显示未勾选。最终源码`4122379c8ef39fc110c553302ea23081830f595f`补齐同一有效集合的source_group/ enabled元数据与只读Workspace tools分组；静态选择保持可编辑，自动工具不进静态默认名单。实际预览另复现晚加载Cron项误归workspace（`/tmp/feat610-late-tools-red.log`），每次Include更新前扩充静态baseline后，重复catalog只标记真正新增工具，原生全生命周期通过。

- `pnpm build`、`pnpm typecheck`、前端`npm run build`通过。
- 窄native3files18tests、前端3files37tests通过；前端交互测试证明只读状态、不发自动工具选择、静态操作payload不含自动工具名，以及Unavailable状态。真实用户配置未改动来做演示。
- 全量native84files314tests（`/tmp/feat610-ui-full-tests.log`）、frontend95files882tests（`/tmp/feat610-ui-full-frontend.log`）通过；non-E2E pytest56passed31deselected；docs-check通过。
- worker真实桌面浏览器截图`/tmp/feat610-review/workspace-tools-settings.jpg`，仅expense_summary Enabled及说明/管理提示；原用户tab未改动。原型草稿因file协议被浏览器策略拒绝而未渲染，没有绕过；以真实授权localhost产品页完成实际视觉对照，草稿不冒称验证通过。
- 独立code-review patch findings=[]、verifier delta pass/corrected-delta aligned；原生执行+持久化7/7旅程retained，新增UI由R2真实浏览器复验补齐。

## 最终 UI 收尾

- 独立设计R5 Approved 0/0，采用真实桌面和390px窄屏实际产品对照；独立产品R2 pass，新第8Scenario与原7项retained。新fork聊天真实expense_summary为3笔40元，配置前后完全相同。Unavailable与表单保存支路明确保留自动化证据边界，不声称真人操作。
- final sync origin/main仍为9182699fca58d42fbf166f3de7445c635dcb3527。effective_base保持该SHA；最终源码validated_at为4122379c8ef39fc110c553302ea23081830f595f；effective_through为最终`docs: finalize workspace tool availability review`归档提交。其后仅报告、已校正IM delta原文归并、索引计数与路径移动，无代码或验收判据变化；各门禁retained。
- 测试服务按用户要求继续运行；不归档或删除managed worktree，用户结束体验后以同目录e2e-down.sh清理，再归档worktree。

归档后发现macOS大小写不敏感路径使`git add docs/specs/IM`未暂存Git实际跟踪的`docs/specs/im`；已按真实Git路径暂存canonical原文归并，并将unit delta目录名改为im。effective_through延至`docs: align canonical IM paths for feat-610`提交；只改变已审契约归并与路径，无源码/判据变化，门禁retained。
