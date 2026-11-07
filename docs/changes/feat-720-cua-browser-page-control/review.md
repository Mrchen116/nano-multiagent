# feat-720 — 实施验证与独立审查状态

本文件由实施 owner 串行归集。**当前未完成独立实施审查，未通过发布验收，不可据此发布。** 设计审查记录见 [design-review.md](design-review.md)；历史直接驱动验证见 [M1 evidence](M1-page-actions/evidence/real-driver-checks.md)。

## 版本与有效范围

- 当前冻结的实现/测试版本：`3da5cb40df9dc0795e4d29507029cb97051c256e`，分支 `codex/feat-720`。
- 集成的 develop 基线：`eeaea47921806936da20e78c9ed96167716f5037`。最终交付前仍须重新核对目标分支增量及证据有效性。
- 运行代码最后变更：`4804e785e3d90aae40931d3c9ac90a7036b32b52`；`3da5cb40d` 仅增加 native/PTC × root/child 的接线测试。
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

### 完整 CI 的受负载污染中断

2026-11-08 +08，本机共享负载异常，其他执行者实测 load 达三位数，父级要求暂停本组及新增重型验证。该轮顺序命令为：workspace build → Node installer candidate → workspace typecheck → evals tsc → iOS runtime check → 根目录全部 Vitest（单 worker、无文件并行）。

原始输出 `/tmp/feat-720-backend-ci.log` 止于 L386：`capabilities.test.ts` 6 项中 2 项失败，其中首项用时 40007ms，末项 17642ms；没有最终失败栈、总汇或进程退出码。恢复核查时原生后台作业已不存在，亦无 Vitest/CI shell 进程。仅清理了经本 worktree 二进制和 `nano-review-lifecycle-*` 临时 cwd 双重核实的本轮孤儿 DSH 子进程。

**该轮整体记为中断 / 未完成，不判完整 CI 通过，也不把受负载污染且未有完整诊断的结果直接判成实现回归。** 不为消除红色输出而改测试或增大 timeout。恢复重型验证须由父级协调单组窗口；待资源可用后，先取得完整失败诊断，必要时作基线对照，再完成适用完整 CI。Python 非 E2E 测试、前端测试/审计及最终归档检查也尚未完成。

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
- 完整 CI 未完成，且当前重型窗口暂停；不新增全量运行。
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
