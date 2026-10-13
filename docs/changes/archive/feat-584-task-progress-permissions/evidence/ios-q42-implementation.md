# Q42 原生实施与验证

## 范围与基线

PR #338 原 head c72ef882d；合并主线 b7e367cc0（仅 feat-589 文档）后，Gate 2 Round11 Approved。此次原生总览/层内卡片使用状态图标、负责人身份、紧凑空组和浅色边界；详情正文优先、结果强调、子任务进度及收起的审计信息；创建/编辑统一持续标签、内容高度和明确保存，状态/负责人使用独立 sheet，负责人支持搜索/未分配/真人与 Agent。

冲突使用 baseline/draft/fresh 三方比较：远端独改与本地独改并存，同字段冲突必须明确选择；再次 409 重新比较。原 API revision 和 request_key 继续保护写入。父页面轮询在编辑/详情 sheet 活跃时暂停，避免权限撤销时先于编辑器销毁草稿；详情关闭保留总览已加载页数。权限仍由服务端执行，未改后端/Web/Agent/迁移。

## 回归证据

- 原版 build、40 tests（27 XCTest+13 Swift Testing）通过，日志 `/tmp/nano-feat584-ios-q42/baseline-build.log`、`baseline-test.log`。
- 失败复现：在原 TaskDraft 重试序列中，远端把 description 改为 `Remote clarification`，本地只改 result；发出 patch.description 仍是空字符串。`conflict-red.log:184` 断言失败，4 tests 1 fail。
- 修正后最窄 TaskContractsTests：6 tests 通过，`conflict-green.log`。保护独立字段合并、同字段显式选择、负责人清空、本地结果/变更说明保留、相同改动不冲突、连续冲突和以最新 done 状态校验返工原因。既有三项契约测试继续保留，无样式镜像测试。
- 首次全量原生：43 tests（27 XCTest+16 Swift Testing）通过，`native-test.log`；随后对轮询/草稿保持修正的 generic Simulator build 成功，`journey-build.log`。最终冻结版本再执行必要验证。
- 工作树 `git diff --check` 通过。

## 运行环境与产品证据边界

隔离 IM62306，由 worktree 当前后端构建启动；前后端协议与原PR相同。Simulator `Nano feat584` UUID7CB77F12-2282-4AA0-BCC9-D368A4DD1122；新 App 安装路径 `/tmp/nano-feat584-ios-q42/ios/Build/Products/Debug-iphonesimulator/NanoIM.app`。账号 nano/nano1234 仅隔离测试使用，中文身份与会话、三层六状态任务、51分页根任务位于 `/tmp/nano-feat584-ios-q42/fixture.json`。停止使用 `scripts/e2e-down.sh --wt /tmp/nano-feat584-ios-q42`，不操作生产或另一个 feat578 模拟器。

目前原生视觉/交互 **未验收**：准备读取新版时 CUA 报 Mac locked，已请求用户解锁。编译和单测不替代实际验收；待用户解锁后完成走查、保留截图，再独立产品验收。本页后续追加实际来源和结果，不追认未执行步骤。

## 冻结版本检查（7c8ad1ade）

- `frozen-test.log`：27 XCTest + 16 Swift Testing = **43 tests passed**；6 项 TaskContracts 全通过。
- `release-archive.log`：**ARCHIVE SUCCEEDED**，生成 arm64 未签名设备 IPA；不代表真机运行/签名验收。
- `docs-check`：248 maintained Markdown sources / 64 required routes；`git diff --check` 通过。
- 独立 code review Round 4 PASS，无源码发现；delta/corrected-delta 已对齐，Q42-V1 明确保留真实模拟器证据门禁。
- 用户已解锁。CUA 可读取原生画面并通过 AX 元素点击，但坐标点击暂报 `noWindowsAvailable`；工具会话重建后仍未恢复。已请求用户把专用模拟器放到当前桌面并打开任务页，以便继续原生验收。

## 作者原生画面走查（7c8ad1ade，部分）

在 iPhone 17 / iOS 26.4 的真实 App 中，用户打开底部任务标签后，作者通过 CUA 搜索「完成首次」、进入详情/编辑、打开成员面板，验证无匹配搜索、搜索 E2E 并选择 Agent、切换待确认状态。成员与状态选择只更新编辑草稿。

| 实际原生画面 | 对照结论 |
|---|---|
| 详情（历史图片 `q42-native-detail.png`，按用户要求不随 Git 交付） | 会话、任务标题、状态/头像、描述/结果、子任务进度、收起的审计信息；编辑为底部主操作。信息顺序符合原型。 |
| 编辑（历史图片 `q42-native-editor.png`，按用户要求不随 Git 交付） | 持久字段名、紧凑状态/负责人行、内容随长度展开；不再依赖无标签多行框。 |
| 负责人（历史图片 `q42-native-assignee.png`，按用户要求不随 Git 交付） | 真人头像/身份与 Agent 图标、当前勾选、搜索、未分配和关闭入口；半屏可展开。 |
| 状态（历史图片 `q42-native-status.png`，按用户要求不随 Git 交付） | 六状态完整行、当前勾选与明确的保存提示。 |

这四张画面是实际模拟器截图，不是原型。尚未覆盖保存/取消、409 和余下完整旅程：CUA 坐标动作在用户切到当前桌面后仍失败，已请求明确授权 XCUITest 或由用户继续手动操作。未将部分走查记作产品验收通过。

### 恢复坐标点击后继续走查

用户关闭另一个模拟器后，CUA 坐标点击恢复；没有使用 XCUITest。取消编辑弹出「放弃本次修改？」确认，点外部继续编辑，待确认/Agent 草稿仍在。原生多行输入的 setValue/typeText/paste 未能改动文字，因此本次冲突走查使用已实际选中的状态、负责人，不声称输入过新结果。

同行通过隔离 API 把同一任务从 doing 改为 paused，并独立修改 description。作者从 App 点「保存」触发真实 revision 冲突：比较页（历史图片 `q42-native-conflict.png`，按用户要求不随 Git 交付）明确显示状态双方值、保留的负责人、纳入的远端说明，确认按钮在未选择时禁用。选择「我的修改：待确认」后点「确认并保存」，App 回到详情，状态待确认、负责人 E2E Agent、远端说明和原结果同时存在。只读 API 二次确认持久化字段；此 API 读不替代上述 UI 过程。

独立 reviewer 接管完整受影响旅程，键盘/滑动与未走到的场景仍待独立结果。

## 用户调整与最终交付边界

用户明确要求「那就跳过ios验收」，后续不再继续 UI 操作。独立 Round 5 为 partial / inconclusive，真实状态冲突、连续冲突、选择面板与部分层级已观察；创建保存、完整文字输入、权限恢复、分页末页、窄屏/大字体等仍未验，不称原生完整 PASS。代码审查 PASS、43 tests 与 Release archive 的有效性保留。

用户另要求从分支强制删除旧 UI 图片证据。当前 unit 的 81 张图片（10,090,630 bytes）均移出 Git，历史链接改为名称与文字观察；本地副本保留在 `/Users/czj/.codex/artifact-backups/feat584-q42-local-images`，独立 reviewer 本轮截图仅在 `/tmp/nano-feat584-ios-q42/`。PR 独有历史将整理为以主线 b7e367cc0 为父的单个提交，避免新增图片 blob 仍被本分支引用；已有主线历史中的21张图片与 GitHub 对旧对象的保留/回收不由此清除，不声称 GitHub 已立即回收空间。历史报告中的原 SHA 保留为实际执行溯源，最终提交与7c8ad1ade的产品源码一致。

按已核对的 PID/UUID 停止本次 IM/Node/DSH、58449 原型服务及 Nano feat584 App/模拟器；`e2e-down` 保留本地隔离运行记录，不向 Git 提交任何运行数据或凭据。

历史清理已执行：以 b7e367cc0 为父重建单个 PR 提交，重建前后完整 tree 相同；`git rev-list --objects HEAD ^origin/main` 中本 unit 图片对象为0，当前 tree 中本 unit 图片文件为0。`git diff 7c8ad1ade -- apps packages src tests scripts` 为空；最终索引修正后 docs-check（248/64）及 diff-check 通过。本地主线工作区的已有修改未操作。
