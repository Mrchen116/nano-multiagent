# feat-720 — 实施验证与独立审查状态

本文件由实施 owner 串行归集。**当前未完成独立实施审查，未通过发布验收，不可据此发布。** 设计审查记录见 [design-review.md](design-review.md)；历史直接驱动验证见 [M1 evidence](M1-page-actions/evidence/real-driver-checks.md)。

## 版本与有效范围

- 当前实现/测试版本：`a1fab20f4b1df6f17998cda55395281e3877e654`，分支 `codex/feat-720`；等待固定配置独立实施审查，尚非发布冻结。
- 集成的 develop 基线：`eeaea47921806936da20e78c9ed96167716f5037`。最终交付前仍须重新核对目标分支增量及证据有效性。
- `a1fab20f4` 修复等待驱动 probe 期间资格失效仍会 prepare 的竞态，并按行为拆分 browser-control/lifecycle 测试。原隔离 daily 进程从 `4804e785e` 启动，未为此重启；不能据新 package build 把旧运行进程当作新版本产品验收。
- Gate 2 R7 只批准 `9612ea5d1` 的设计，不是实现或真实旅程批准。
- 本轮自检均由实施 owner 执行，不冒充独立 reviewer。

## 已完成的 owner 验证

| 范围 | 结果与边界 | 本机原件定位（不入库） |
|---|---|---|
| 修复前有意义失败 | 8 failed / 43 passed，覆盖主窗口丢失后错误采纳弹窗、窗口错误吞掉、异步消费轮次锁、混合窗口归还、销毁并发、缺少 Inbox 原始时间 seam | `/tmp/feat-720-red-tests.log` |
| 截图目录、驱动诊断、错误传输回归 | 分别先复现 symlink 越界、输入文本出现在空响应诊断、原生工具仅传 `Error.message` 导致附加证据不可见，再修复 | `/tmp/feat-720-screenshot-red.log`、`/tmp/feat-720-driver-red.log`、`/tmp/feat-720-error-evidence-red.log` |
| 窄测试 | `4804e785e` 的 browser、approval-sources、PA inbox：98 tests / 9 files 全通过，单 worker、禁止文件并行；不是根目录完整 CI | `/tmp/feat-720-browser-suite-final.log` |
| Inbox→BrowserControl 接线 | `3da5cb40d` 的 browser-control：30 tests 全通过，包含 native/PTC × root/child；系统 wake 单独不启动，live 完整真人 Inbox completion 后才可启动 | `/tmp/feat-720-inbox-browser-integration.log` |
| 构建与类型 | 受影响 DSH/PA typecheck、顺序 workspace build 通过；后续完整链中 workspace build、Node installer candidate、workspace typecheck、evals tsc、iOS runtime check 均已进入后续阶段，未见该阶段错误 | `/tmp/feat-720-typecheck-final.log`、`/tmp/feat-720-build.log`、`/tmp/feat-720-backend-ci.log` L1–51 |
| 文档/Python 静态 | 文档完整性、ruff check、ruff format check 通过；新增本报告后另跑 `git diff --check && ./scripts/docs-check` 通过，最终归档后需按最终版本补验 | `/tmp/feat-720-tooling-static.log` |

窄测试命令：

```sh
pnpm exec vitest run packages/dsh-integration/tests/browser-*.test.ts \
  packages/dsh-integration/tests/approval-sources.test.ts \
  packages/personal-assistant/tests/inbox.test.ts \
  --maxWorkers=1 --no-file-parallelism
```

### 中断后的分组 CI 补验与有效性

2026-11-08 +08，旧完整链在异常共享负载下中断：workspace build → Node installer candidate → workspace typecheck → evals tsc → iOS runtime check 已进入后续阶段；根 Vitest 原始输出 `/tmp/feat-720-backend-ci.log` 止于 L386，`capabilities.test.ts` 6 项中 2 项失败、无最终栈或总汇。旧链仍记为中断，不把后来补验改写为旧链 exit 0，也不增大 timeout 或跳过失败。

父级后续明确分配单组非 GUI 验证窗口；在 `5bc1cfbc2` 代码不变时顺序完成：

| 范围 | 实际结果 | 本机原件定位 |
|---|---|---|
| 原 capabilities 失败重跑 | 6/6 通过，首项 12.53s、末项 5.374s。该窗口未复现旧失败；不因此证明负载是唯一根因或不存在间歇竞态 | `/tmp/feat-720-capabilities-isolated.log` |
| 根 Vitest 剩余集合 | 190 files / 784 tests 全通过，exit 0；复用 33 个版本不变且完整通过文件的 464 tests，覆盖当时全部 223 files / 1248 tests。不是单次 fresh `pnpm test` 全量 exit 0 | `/tmp/feat-720-root-remaining.log` L3720–3726；逐文件版本与来源 `/tmp/feat-720-root-coverage-manifest.json` |
| Python 非 E2E | 134 passed / 1 failed / 28 deselected；唯一失败为本分支新增 browser-control 测试 475 行超过 400 行。未豁免，后续按生命周期行为拆分 | `/tmp/feat-720-python-ci.log` |
| 前端 | 113 files / 1078 tests 全通过、pretest interactive assets 检查通过、exit 0；`npm audit --audit-level=critical` 通过，但仍报 11 个非 critical 漏洞（4 low / 2 moderate / 5 high），不声称零漏洞 | `/tmp/feat-720-frontend-ci.log` L57、L7562–7568 |

### 后续启动门禁竞态：有意义红测与最小修复

owner 静态核对发现 `ensureInstance` 在初次在场判定后 await `driver.probe()`，随后直接 prepare；该等待期间祖先轮次可能过期、关闭、换轮或被 sibling 的真窗口归还消费。无 GUI deferred-driver fixture 在修复前取得 **4 failed / 5 passed**：前三种错误地成功启动，第四种已越过 prepare 后才返回窗口歧义，均不是预计的资格拒绝（`/tmp/feat-720-launch-race-red.log`）。

`a1fab20f4` 在 probe 后、prepare 前无额外 await 地重验同一祖先 session/turn seq、当前在场与消费锁；不借用后来的真人轮次。晚拒绝不调用 prepare 或对未准备 label 调用 end_session，finally 释放预留槽。既有生命周期/并发/冷却测试迁至 browser-lifecycle，browser-control 378 行、新 lifecycle 175 行；不改测试上限。

修复后 **10 files / 106 tests** 全通过（browser 全集、approval-sources、PA inbox，单 worker/无文件并行），包括晚拒绝零 driver call、槽位可被新合格请求使用、等待期间 sibling 消费锁；`/tmp/feat-720-launch-race-green.log`。受影响 DSH typecheck/build、`NANO_TEST_BASE_REF=origin/develop ...pytest tests/contract/test_test_naming_and_size_contract.py -q` **2 passed**、`git diff --check` 均通过。该窄测不替代真实桌面验证。

以上根/前端/Python 的分组证据具有各自版本边界：旧全集不是 `a1fab20f4` 的 fresh 全量证明；新增源码已补受影响窄测与构建，最终 sync、独立审查后须再判断哪些结果有效。Python 原失败已由未放宽规则的窄重验修复；最终归档检查尚未到可运行阶段。单组重型窗口已释放，未经重新协调不新增重型全量。

## 已观察到的真实产品链

本轮从 `4804e785e` 构建的代码启动隔离 daily 栈，独立端口、数据库、Gateway config、runtime home、workspace 和节点身份；`3da5cb40d` 无运行代码变化。只使用 headless Playwright 操作本栈 Web IM；**没有调用本轮 browser_read/browser_act、没有 CuaDriver prepare/click，也没有操纵物理桌面**。

1. 在真实 PA 设置页看到 `browser_read` / `browser_act` 默认均未选中。禁用态的真实 PA 回复为“当前不可调用 browser_read 与 browser_act，没有启用浏览器能力。”；该轮没有浏览器或替代工具调用。另建的隔离 single-thread 测试 Agent 同样观察到两项默认未选中。
2. 通过同一设置 UI 显式选择并保存后，仅发送可用性查询；真实测试 Agent 列出两项能力，未调用浏览器。此项只证明设置可发现/启用，不证明实际浏览器动作链。
3. 真实 PA 原生轨迹的 Inbox `read` call seq25 / 原始 result seq26 保留了真人消息原始 `created_at`，同时带本地化展示时间，participant/user 身份未变；恢复后追加的替换结果不作为新的 live 完成来源。此项证明原始时间已跨 PA→runtime 投影，但不是 browser gate 实际启动或 provider 输入验收。

定位：worktree `.e2e-daily.json` 为本栈清单；默认态 snapshot 为 `.playwright-cli/page-2026-11-07T18-17-54-499Z.yml` L302–303；本轮提取的 PA 轨迹 `/tmp/feat-720-pa-session.jsonl`。以上均为本机测试产物，不提交日志、截图、配置、数据库或认证内容。

## 发布阻塞与待补验

- **V2 ≥2 次真窗口后前台归还，是发布阻塞**；V3 ≥3 次独立启动采样及 V4 弹窗半边仍缺。本轮不能用“未测但已披露”替代。
- 老版 V1/V5/V6 是直接驱动 / orchestrator workspace 证据，不是本轮真实产品节点等价性证明。仍需真实 IM→Node→DSH→驱动→结果→read_image 链路，以及默认关闭、身份、审批拒绝、无人值守、Global/native/PTC 与子 Agent 的代表性场景。
- 物理桌面实验已向父级提交具体影响与有界窗口请求（最多 3 次独立启动、2 次 popup/归还），**尚未收到真人时间窗口许可**；不能把桌面锁定、用户空闲、通用继续开发或工具启用当作该许可。不得接用户已有 Chrome/profile/登录态。
- 分组 CI 已补齐旧版本根/前端覆盖并定位、修复 Python 超长测试失败；当前有新的启动竞态修复与窄验证，最终版本证据有效性尚待 sync/独立审查收口。重型窗口已释放，不自行新增全量运行。
- 独立实施审查、Context 实施审查、corrected-delta 与产品旅程结论均未取得。所要求的固定模型/effort 在原生派发接口中无参数，已由父级协调；不能把 inherited 配置或 daily Q 自动当作等价独立审查。

## 待独立审查核实的生命周期差异

这是 owner 静态自检发现的潜在契约差异，不是独立审查结果；父级明确要求保留到独立 Context 审查，**不授权直接删承诺或新增 Memory 屏蔽机制**。

原句：

- spec L181：`画面截图只是本次任务的临时证据，只保留有限时间，不向用户承诺长期保存，也不作为记忆内容。`
- design L117：`截图不进 Memory/Skill/Dreaming。`
- design L341：`页面内容不长期持久化、不跨会话继承：实例结束即丢页面状态；截图只是临时证据（TTL 1 小时、最多 20 张，只在写入时清理 + 启动期有界补清，不随 Agent 销毁删除），不写 Memory/Skill，不进 Dreaming 材料。`

须区分四类数据，不以“工具结果被保留”直接推断“图像字节进入 Dreaming”：

| 类别 | 当前源码事实 | 结论边界 |
|---|---|---|
| ① 截图文件 / 像素编码字节 | `browser/screenshots.ts` L75–94 写 workspace PNG，L97–134 只清该目录匹配文件；`browser/control.ts` L183–203 / L257–279 只返回路径和尺寸，不返回 base64。已安装 `dsh-tool-fs@0.2.1-alpha.1` 的 `read_image` 后续另调用 `attachments.saveImage`，返回文本与 normalized attachment ref；`dsh-attachment-local@0.2.1-alpha.1` 将归一化图像持久到 `DSH_HOME/attachments/v1`。 | 源 PNG 的 TTL 不等于清理独立附件对象；本轮尚无产品截图/读取/过期实验，未观察该功能的实际附件存续。静态持久化路径不是像素进入 Dreaming 的证据。 |
| ② 路径 / 元数据 / 工具结果文本 | `control.ts` L196 / L278 返回路径尺寸；`trajectory-attachments.ts` L20–31 / L53–58 保存来源元数据而非字节。`memory-sources.ts` L128–170 与 `memory-source-view.ts` L6–48 不排除这些普通工具；前者 L56–70 / L238 将非 text 块渲染为 attachment JSON 文本。 | 当前 normalized image 块只含附件引用元数据，Dreaming 取材代码不因此解引用像素。不能从结果保留推出图像字节入模。 |
| ③ 页面正文 | `control.ts` L183–194 / L257–277 返回有界正文与 `text_after`；`memory-sources.ts` L133–170 / L238 不排除此文本；`dreaming.ts` L339–346 和 `dreaming-agent.ts` L105–110 以 text 输入提交材料。 | 资格、启用基线、cutoff 和预算允许时，页面工具文本可进入 Dreaming 材料；本轮没有实际 Dreaming 输入或保存页面原文的观察。 |
| ④ 可能提炼的长期事实 | `dreaming-agent.ts` L42–62 / L73–84 无 `read_image`；原始输入是 text，普通合格页面文本与 Agent 的文字结论可被取材，所检源码未有 browser-specific 排除。 | 没有证明已禁止从这些合格文本提炼事实，但也没有证明实际提炼/保存发生，更不等于原始页面或像素已经写入正式记忆。 |

详细精确安装源码定位已补进同一中性审查包 `/tmp/feat720-review-package.md`。这只是只读源码核对，不是删除审计、真实 Dreaming 验收或人类隐私意图判断；聊天搜索未找到同句不构成撤销已有 spec/design 的依据。契约与机制的最终判断交独立审查，必要隐私取舍由父级再处理。

## 独立审查结论

**Pending。** 当前没有可以登记的实施 Approved / 产品旅程 Approved；未归档、未创建交付 PR、未合并、未部署生产。待授权、资源与审查配置条件满足后，沿同一事项和 worktree 继续。
