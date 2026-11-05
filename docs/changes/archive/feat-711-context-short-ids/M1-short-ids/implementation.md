# M1 实施与验证

## 冻结实现

- 插件：`Mrchen116/dsh-agent-context`，`9a2a29078d264311a7d4327e1e4940d0c966f537`，[PR #4](https://github.com/Mrchen116/dsh-agent-context/pull/4)。候选版本 `0.3.0-rc.8`。
- 包 SHA-256：`94cea01fa13425aaa925e51789aea084072e1a24095c89263e889909461ad9a3`。最终 pack 与实际通过最后两项运行时测试的 lazy pack 字节相同。
- Nano 生产适配位于 `3fa3476ef`：审批结构化正文、Task 严格消费回执去掉插件自有标记；Memory 完整步骤边界忽略原生替换副本。后续提交补测试、设计和独立报告。
- 编号依原始日志重建，native Skill 目录和工作区规则不占短编号；无额外索引文件、迁移或进程内权威编号状态。已标记工具及空输入避免重复建图，不改变恢复或计价规则。

## 验证结果

| 范围 | 版本与结果 |
|---|---|
| 插件 | 最终源码 38 tests、typecheck、build 通过；包含控制消息在 pre-step 后提交的重放回归 |
| Nano build/typecheck | fixed 候选通过；性能增量只改变插件内部重复扫描，公开类型不变 |
| 原生控制与最早输入恢复 | 真正启用 skill 目录、AGENTS 和项目根，捕获首次 user1；两次原生换窗/进程重启分别读回工具尾部及 user1 原文，通过 |
| 自动连续执行压力 | 同一未修改的 Task limits 测试，保留 45s 等待和 90s 总超时；最终候选与上项合计 2 tests 通过，67.57s；未放宽阈值 |
| 宿主其他回归 | 审批、Task 同步/回执、停启去重、原文、权限、Memory 边界、子执行者与维护检查通过；见下文全量结果对账 |
| Web | 113 files / 1077 tests 通过；critical audit 门通过，无 UI 修改 |
| Python / 文档 | 135 tests 通过、28 deselected；docs-check、ruff check/format 通过 |
| 原生交互资源 | `pnpm check:ios-runtime` 通过；无 iOS 源码改动 |
| 独立真实模型 | acceptance Round 2 pass，R1-1 关闭。原 user1、更正47在真实裁剪、换窗、节点重启后直接读回；最终交付正确。详见 acceptance.md |

本机 Node 为25.8.2，仓库声明24.22.1/26.12.1；插件远端 CI 使用 Node24。没有为本任务更改引擎标准。

## 全量失败与闭环对账

首次完整 Nano `pnpm test --maxWorkers=2` 在修正过程中运行：213 files、1159 tests，其中207 files /1146 tests通过，6 files /13 tests失败。保留原失败，不将该命令改称全绿：

- global-child-tools 三项、knowledge-review 一项、Task graph permission 六项：脚本 provider 拼接新增标记后不再匹配原单文本命令。仅改 fixture 取原命令 text block，保留副作用/权限/审批断言；前两文件11项、Task graph六项窄复验通过。
- personal-security 一项：全量30s超时，原样隔离重跑26.67s通过，未修改实现或阈值。
- context-short-ids 一项：真实 catalog/AGENTS 激活后，旧候选 user1恢复为 Skill catalog；修正两类控制资格后，通过运行时回归和独立真实模型R2。
- Task limits 一项：旧候选在45s时仍执行第380/384轮；rc.7对照原样55.34s完成整个测试。去除空输入及已标记工具的重复建图后，实际安装最终候选的原测试通过。未通过的复制 integration 实验未加载目标模块，明确不作性能证据。

全量中其余未变范围的通过证据与上述窄闭环分别保留，不重复声称最终树完整全量命令已全绿。远端 Nano PR CI 仍待固定发布包可下载后执行。

## 证据与收尾状态

本机合成原始证据：`/tmp/nano-id-projection-L6wMZV/` 与 `/tmp/feat711-review/`，不提交原日志/配置/凭据。关键命令输出为 `nano-all-tests.txt`、`fixture-closure.txt`、`personal-isolated.txt`、`fixed-runtime-tests.txt`、`lazy-real-tests.txt`、`task-limits-baseline.txt`；真实模型证据见 acceptance.md。

隔离 daily 栈已通过 e2e-down 停止，录制转发器已停止，临时 Gateway 配置已恢复备份。主仓既有未跟踪内容未修改。两个开发 checkout 保留供审查。

发布前状态：rc.8 尚为发布草稿，待用户确认发布；不部署生产。公开下载/匿名 integrity 校验、Nano 固定依赖最终安装、最终 verification、canonical 归并/归档及 Nano PR/CI 尚待该发布完成，不提前宣称交付完成。

## 发布与 HTTPS 接入验证（2026-11-05）

- 用户明确授权“发布 rc.8”后，已发布 [v0.3.0-rc.8](https://github.com/Mrchen116/dsh-agent-context/releases/tag/v0.3.0-rc.8) 预发布版本。tag 对应上述冻结插件提交；没有合并 PR 或部署生产。
- 使用不携带 GitHub 认证的 curl 从 package.json 的公开 HTTPS 地址下载成功；SHA-256 与上述验收包相同，SHA-512 与 pnpm-lock.yaml 一致。
- `pnpm install --frozen-lockfile` 实际从 HTTPS 安装成功；安装包的30个 lib 文件与公开下载包逐字一致。随后 build、typecheck 通过。
- 同一 HTTPS 安装后运行未修改阈值的原生控制消息/首次 user1 恢复与进程重启测试、自动连续执行压力测试：2 files /2 tests 通过，测试执行65.15s。
- 本轮证据在 `/tmp/nano-feat711-rc8-release/`：public.tgz、install.txt、build.txt、typecheck.txt、runtime-tests.txt。先前临时证据目录已被环境清理，已提交的历史报告与结果仍保留；没有把历史失败改称全量通过。
- final sync：origin/main 仍为 `2ac60077e4988ab0db5789841b51f42bab02789c`，与既有门禁 base 一致，无新增主干差异。发布包与先前验收包字节一致，原独立模型验收和代码审查的语义范围保留；最终 artifact gate 见 verification.md 后续结论。

最终 artifact 门禁独立通过（verification Round7），已审 delta 原样归并到 Gateway capability current spec，unit 整体归档供 PR 审查；上述验证后的收尾仅改文档，不改变运行代码或依赖字节。Nano 远端 CI 以本分支 PR 检查结果为准。


## 窗口内编号后续修正 · 2026-11-05

- 用户要求每窗从1开始，并明确“不需要！不用兼容旧版本”；不保留旧编号基数恢复、metadata迁移或fallback。设计R8 Approved；代码R8-P2按需求变更 superseded，非修复。
- 插件冻结 `76e7a421ec9191540ebb0fa3d0279a26c7070c96`，PR https://github.com/Mrchen116/dsh-agent-context/pull/5；原生成功窗口识别共用 windows.ts，新窗 next=1，message.id去重，pending在成功换窗后重新标记，原文形似标记仍保留。40 tests、plugin build/typecheck通过。
- 已发布不可变预发布 rc.9，公开URL已匿名下载；SHA256 `af18a7df4a852fe3c1517f4f30f305a1036ce7d2950f784bc1c4cc0ffab3a296`。正常公开HTTPS安装后的33个lib与下载包逐字一致，pnpm-lock的SHA512一致，详本机 `/tmp/feat711-window-local-public-artifact.json`。不使用开发目录软链或/tmp文件依赖交付。
- 真实模型R4使用全新Agent/UUID会话与空白home，最终正常安装候选包完成三窗、两次进程重启、两个旧窗item1原文分别恢复。详acceptance.md R4；自建进程均退出，未触碰用户52521预览。
- Nano跨进程回归新增每次重启后输入1/工具3，并分别读取不同窗口的item1。正常tar安装全仓build/typecheck、Python135 passed/28 deselected和iOS runtime检查通过。
- 验证环境边界：初次跨仓源码软链导致重复DSH类型身份，build/typecheck失败；已改为正常tar安装后通过。首轮全量随后停止，不宣称完成。
- 正常安装后本地全量发现 global-child-tools 的 PA=true 并发场景失败；三种mode/PA组合独立复验全部通过，未修改该用例或产品代码，全量未完成。保留 `/tmp/feat711-window-local-nano-final-suite.log` 与 `/tmp/feat711-window-local-fork-target.log`，最终CI另行记录。
- 原生disable验证的测试fixture从字面软链路径创建require，无法读取DSH已声明的terminal-bash依赖；改为先公开resolve package.json再创建require。此单行改动不改断言或运行时；原失败1项、修正后原7项通过，日志 `/tmp/feat711-window-local-native-fixture.log`。
- origin/main推进到 `fc447faee`（浏览器凭证稳定性709），已以merge同步；与编号/模型消费链无交集，原相关门禁按受影响范围保留。公共包最终运行时回归与远端CI结果待下文续记。

- 最终交付树 code-review R10 无存活发现，verification R9 targeted pass / corrected-delta aligned；产品R4为全新Agent最终候选包实测。公网安装后真实进程回归1项、宿主审批/Task原文/History与Memory边界5文件22项均通过。新发布包、锁文件和canonical接线已由独立静态审查核对；下一步为Nano PR完整远端CI，不以窄复验替代全量结果。


### Main 稳定 Cookie 接线的 CI 闭环

远端 `41960919057` 完整 TS 回归：214 文件、1163 tests，1160 pass / 3 fail。失败均为 HTML bootstrap 缺失：main709 将浏览器 Cookie 改为稳定 sid.jti，但原 browserSession 和异步预读后的复验仍只 decode refresh JWT，导致被 catch 后不注入 bootstrap。按 main 意图复用 browserCredential 与 issueAccess；末尾在所有 await 完成后再次通过 browserSession 校验，既不旋转 Cookie、不延长 session，也不改 API 授权。未改测试断言，frontend/trajectory e2e/identity 三文件25项通过；独立 code-review R11 / verification R10通过。新完整远端CI需在本次修复提交后再运行，不改写原失败。

用户要求直接查看Web真实轨迹后，已在原52521隔离栈用公开配置API创建全新Agent `window-visible-d71f6826`、空工作区及独立主会话 `75ebed1f-be78-42e8-b788-a771146d0a27`；没有导入R4或P/E/Q状态。当前通过实际Web/IM私聊、公开 /compact 命令及测试节点正常重启补充可见演示，原轨迹保留。该预览服务按用户要求持续运行；演示原始证据仅保留本机 `/tmp/feat711-web-visible/`。

### 用户验收与 bugfix-712 一并归档

上述 Web 实测完成两次手动换窗和两次节点重启，三个窗口首次工具返回均为3，最后用原窗口/5和第二窗口/7分别恢复两段原文，公开回复为 `青岚-6147`、`橙色`、`秋汀-3926` 三行。浏览器实际显示初始系统提示词、运行上下文、压缩记录、Notes 和 History 结果。用户确认“ok”，要求把已集成的 bugfix-712 随当前 PR 交付并归档；见 [712 验收记录](../../bugfix-712-trajectory-history-prepend/acceptance.md)。

CI `41963461005` 的完整结果为214文件/1163项，1161通过、2失败：identity 的真实时钟跨秒令精确30天预期差1秒，task-execution-limits在并发负载下等待超时。两者连同 trajectory-ui 独立复跑5文件23项全部通过，原全量失败保留。本次仅将既有 identity 测试的 Date 固定提前到会话签发前，避免把夹具准备耗时混入30天断言；所有断言及 Task 测试不变，修正后identity13项通过。产品代码和既有门禁覆盖范围不变；归档文档/路径与该测试时钟夹具修正不新增产品设计或 Context delta，保留原独立静态审查结论。归档提交后的完整远端CI仍需另行确认。
