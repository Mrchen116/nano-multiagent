# feat-654 — 产品验收报告

> 对齐：[spec.md](spec.md) / [design.md](design.md) Runbook for Reviewer
> Round 1 · mode=full · revalidation_mode=full
> Validation snapshot: `d2cad8d59bb7025cacdd546d7fc9e0949fe13916 → a75a88781758515ab2644386c997c1d6503d8f42`
> 实测日期：2026-10-25，Asia/Shanghai；独立 reviewer。

## Verdict

**pass**。7 个必验 Scenario 全部通过；0 blocking / 0 major，1 条非阻塞 unit 外 Side Finding。Highest Required Action: pass；无需重新验收。

## 环境与证据边界

- checkout：`/Users/czj/.codex/worktrees/feat-654-daily-acceptance/nano-multiagent`；开始时 HEAD 精确为 validated_at，分支 `codex/feat-654-daily-acceptance`。
- 主现场由 caller 持有：`output/feat654-live`，IM `http://127.0.0.1:50036`，节点 `wt-feat654-live-59057`，专用主人 nano。四角色及群/私聊以 `.e2e-daily.json` 和公开 API、真实 Web 共同核对。
- 构建复用：`/tmp/nano-feat654-build.log`、`/tmp/nano-feat654-web-build.log` 均成功。构建元数据标记当时 HEAD d2cad8d59，caller 明确构建时本轮 fixture 已在 working tree；本轮版本没有 apps/packages/src 产品源码差异（reviewer 核对该范围 diff 为空）。进程命令指向该 checkout 的 `apps/im-server/lib/main.js`、`apps/node/lib/cli.js`，daily 脚本使用 a75 工作树。没有把构建元数据冒充 a75。
- reviewer 另起 `output/feat654-review-fresh`，IM `http://127.0.0.1:51194`，节点 `wt-feat654-review-fresh-61956`；结束已通过 e2e-down 停止，见 `output/feat654-review/fresh-stop.log`。未停止 caller 主现场。
- 本轮仅操作隔离账号、群和临时配置，未换工作模型、未关闭审核、未使用生产渠道。P/E/Q 为 Sol high，PA 为 Astra medium；实际 owner 配置 Auto enabled、Codex、dangerously_skip_permissions=false，独立审核模型 Luna，见 `approval-config.json`。low 是运行时受支持时的选择，不声称另有静态 effort 参数。
- 本地原始证据统一位于 `output/feat654-review/`，不提交截图、凭据、日志或 runtime。以下相对证据名均指该目录。
- 复用 caller 的同根重启/独立根真实进程回归：`tests/e2e/test_daily_acceptance_environment_e2e.py` 与 `tests/e2e/test_worktree_stack_lifecycle_e2e.py`，5 passed in 57.80s，运行于 a75。原始结果在 caller 工具输出，未单独落盘；pytest 临时目录已被后续轮换，不宣称它仍完整。仅将其用于同根重启及旧 lifecycle 边界；本 reviewer 独立观察了新副本和完整协作结果。

## 用户旅程体验

在真实 Web 1280×720 登录后，聊天侧栏同时显示“研发日常”和独立 PA 入口。群标题下直接列出主人、P/E/Q；Agent 列表共有四位，PA 单列在“My personal assistant”，P/E/Q 显示职责名称，用户无需靠 ID 猜分工（`agents.png`、`pa-entry.png`）。设置页可读职责、模型、推理档位与 Codex，工作模型与独立审核模型通过设置和启动清单分别核对。

通过真实聊天输入向 P 交办普通消息，再通过真实 @ 菜单选 E、Q，均取得公开交付。P 把固定反馈转成三项可观察标准；E 写入实际共享文件并说明文档自查与应用测试的区别；Q 读取真实产物及原始资料后按文件行号作出独立判断。群消息保留作者、时间和 View Work，Q 的表格将原反馈、文件证据、判断并列，阅读和核对连贯（`group-result.png`、`q-result.png`）。本轮验证的是模板中的文档交付协作，不把虚构待办应用本身标为已实现或通过测试。

PA 的汇报把各角色、产物、验证状态并列，带可跳回原消息的链接，能帮助主人直接判断工作完成到哪一层；本人独立比较了群消息与 PA 汇报，内容一致（`pa-result.png`）。PA 无需加入团队群即可查询主人来源，本轮没有向群发送或委派。

## Reference Artifacts Reviewed

N/A。design 明确没有客户端代码或 UI 布局变更，没有 prototype/reference must-match。已独立观察实际 Web 桌面体验；未声明 iOS 视觉通过，本轮共享业务无 iOS 特有要求。

## 问题清单

无阻塞问题。Side Finding 1（minor，Regression Relation=unrelated-existing；Recommended Action=out-of-unit）：P 设置页 Group Reply Policy 显示 Only when mentioned，公开 config 为 `always`，实测普通群消息已触发 P；PA 设置页也显示 Only when mentioned，而公开 config 为 `manual`。期望显示保存后的真实策略，实际显示与值不一致。证据 `p-config.txt`、`pconfig.json`、`pa-config.txt`、`paconfig.json`。本次无客户端变更，职责、模型、审核及主旅程均不受阻；caller 同意作为非阻塞 unit 外观察保留。未读实现追因，也未另发 GitHub issue。

## 验收标准覆盖

### Requirement: 固定可辨认的日常协作阵容 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据与实测结果 | 结果 |
|---|---|---|---|---|
| 打开新环境 | spec 同名 Scenario | 真浏览器登录、Agent 列表、群和 PA 私聊、公开配置 | `agents.png`、`pa-entry.png`、`group.json`、四角色 config JSON；群是主人+P/E/Q，PA 不在群；职责明确 | pass |
| 按职责完成一次工作 | spec 同名 Scenario / design runbook | 真群发消息、E 文件交付、Q 实际读取、reviewer 回读 | P 结果消息 `a5ecc24a88ea49b79f2b37ce73c0bab4`；E `4a0d6c84365c47c9a5dec32d2b72a458`；Q `f10aa60aca4d408d901d51749a56295e`。`messages.json`、`e-work.txt`、`q-work.txt` 保留证据；Q Work 展开显示完整文件1–91行读取。产物 SHA256 `55a33c096a9f491b83520ef110b1a68a46e69d0bca5617791d72069597bd9e34`，覆盖三条反馈 | pass |
| 识别模型与审核配置 | spec 同名 Scenario | 清单、公开 config、浏览器设置与隔离 owner 配置对照 | 四角色模型/effort 与默认一致，均 Codex，无主模型 fallback；独立 Luna，Auto 开启且未跳过权限。`p-config.txt`、`pa-config.txt`、各 config JSON、`approval-config.json`。未使用模型覆盖 | pass |

### Requirement: PA 具有真实个人助手关系 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据与实测结果 | 结果 |
|---|---|---|---|---|
| 主人私聊与团队上下文 | spec 同名 Scenario | 主人从 PA 私聊询问群内 P/E/Q 真实进展 | `pa.json`、`sources.json`、`group.json` 确认 active binding、未排除群来源且 PA 非成员。请求 `e2a188a37bfe4b7eb37df22cb9555fd0` 后，回复 `4314b7007cab43d081fdb5647bc2f4f4` 精确汇总 P/E/Q、文件路径、文档通过和应用未实测边界，并链接三条真实结果消息；`pa-messages.json`、`pa-result.txt/png`。群最终9条消息中无 PA 发言，未将查询变成群内委派 | pass |

### Requirement: 每个需求复用同一基线并保持隔离 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据与实测结果 | 结果 |
|---|---|---|---|---|
| 新需求独立启动 | spec 同名 Scenario | 主现场已有真实聊天时独立启动第二副本，公开 API 查空历史、文件校验 | `fresh-evidence.json`：同阵容和模型，不同 node/PA/group ID，两会话 items=[]，只含三份原始资料；主现场交付文件未进入副本（`isolation-check.json`）。同根重启额外复用 caller 真实进程测试 | pass |
| 在基线上补充需求场景 | spec 同名 Scenario | 在新副本公开 PATCH P description，查询另一副本 | `fresh-config-increment.json` 中 description=“本轮 reviewer 隔离增量：仅此副本”、version=2；`isolation-check.json` 主现场 description 仍为空。主现场新增产物和消息也仅在自己的副本 | pass |

### Requirement: 开发流程默认复用模板 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据与实测结果 | 结果 |
|---|---|---|---|---|
| 准备与交接真实产品验收 | spec 同名 Scenario / design runbook | 按 caller 精确版本/清单/身份交接执行 daily，全链路独立实测；额外启动一副本 | `fresh-start.log` 完整 seed 后 ready、公开 API 四角色/PA/群；初次指定不存在 runtime-root 返回具体 cd 错误且 exit 1，未报 ready，创建目录后正常启动。模板就绪未替代后续模型交付验收 | pass |

## 上层文档同步

- [x] `SPEC.md`：无需更新；无跨包架构变化。
- [x] `docs/specs/<包>/`：无需更新；design 为 no spec delta，产品 API/权限不变。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；正常流程通过现有 skill 路由引用。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；未改变文档体系。
- [x] 开发权威文档：`docs/development/worktree-runtime.md` 固定日常模板段已反映阵容、模型、审核、隔离和交接；`docs/README.md` 已提供入口，相关 change skills 已纳入 daily 约定。
