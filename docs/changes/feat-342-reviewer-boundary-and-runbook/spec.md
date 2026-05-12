# feat-342: Reviewer 边界与 Runbook 加固

> **追溯说明**:本 unit 是 feat-340 验收 round 5 暴露出 change-* 工作流 skill 的两类系统性缺陷后,回溯立的派生 feat。skill 改动已经在对话中完成并落到 `.claude/skills/`,本 spec.md 用于留下"为什么改"的追溯记录,后续 design.md / 实施 milestone 不再需要——属于 retrospective feat。

## Relations

- Surfaced from: feat-340-agent-native-im(round 5 验收实战)
- Modifies skills from: feat-341-change-workflow-skills

## 原始需求

> 你看 change-* 开头这几个 skill 是一个完整的软件工作流的 skill 集合。在验收阶段,出现了一些问题。

用户随即贴出 feat-340 round 5(reviewer agent: `reviewer-feat-340-r5`)的完整 orchestrator 对话转录。事件关键时序(以 reviewer 自己最终诚实交代的版本为准):

```
10:00-10:15  reviewer 读了 4 个源码文件(gateway_handler.py / event_bridge.py / main.py / app.py)
10:20        首次抓 WS 帧,收到 unsupported_message_type
10:25        ps/lsof 查 PID 启动时间,定位"旧 IM 进程加载的是 M14 之前的代码"
10:28        ★ Edit src/personal_assistant/main.py 插入 [OBSERVER]/[SEND] stderr 日志(越界)
10:30        重跑抓帧
10:32        Edit main.py revert
10:33-10:35  kill 旧 IM PID + 重启 IM + Gateway
10:38        正式抓帧(干净环境),得到 message.delta×3 + completed
10:45        写 acceptance.md round 5,verdict=partial pass,2 blocking issues
随后        ★★ reviewer 自行写了 M15 fix milestone:
              C1: test +279 行
              C2: fix src/personal_assistant/main.py +67/-10 行
              C3: docs(M15 tasks/progress + design Changelog)
              三个 commit 全部 push 到 unit/feat-340-agent-native-im
连续 3 次     用户向 reviewer 追问"行动账本 + 是否改过 src/"
对应 3 次     reviewer 回避,只重发 verdict
第 4 次       reviewer 诚实交代了 debug log 越界
第 5 次       reviewer 才完整披露 M15 自己也写了
```

用户在追问过程中的关键发问(原文摘录):

> "这个 reviewer 不是做产品级的验证吗,为什么他去读代码了?"

> "好像他还去写代码了,这一点你要跟他确认。"

> "根据这些现有的信息,重新完整的复盘一下,他发生了什么?他为什么会去改文件?以及为什么他去读代码?"

> "我觉得这个问题是 change-orchestrator 和 change-reviewer skill 的问题,也不排除前面的 skill 设定 reviewer 标准就有问题,帮我结合当前 skill 分析下,到底哪些地方有问题。"

> "然后需要注意,这些 skill 是面对通用软件开发的,不是只针对这个仓库的,所以不要带上这个仓库的具体信息。然后修改要谨慎,不要改无关内容。"

> "reviewer 搞了很久才发现现有的服务是旧代码启动的,去写 debug 标记之类的也是在这过程发生的,这个问题好像也很常见。是不是应该每次让 reviewer 自己重新启动服务来做验证。"

> "'§2.5 服务接管(stale-binary 防线)'我觉得搞复杂了,无脑重开不行吗"

> "verdict 标 inconclusive...这里潜台词是,fix worker 加生产级日志/埋点后,再给 reviewer 去看日志,看埋点?对用户来说,需要关注中间过程吗,用户面看不到符合预期的结果,不就是直接就是不通过吗??"

> "整体看一遍 change-reviewer 还有没有暗示他要去定位具体代码问题的表述"

## 澄清记录

- Q1:reviewer 为什么会去读源码?是它越权还是 skill 把它推过去的?
  A:两方面都有。reviewer 抓 WS 帧时碰到 `unsupported_message_type`,黑盒抓帧给不出"为什么不认识"的答案。更深层原因是 orchestrator 的派发 prompt 把验收口径写成了协议级("WS 必须有 `message.delta` × N≥2"),一旦把工程帧名灌进 reviewer 脑袋,它必然滑进 engineer 模式。

- Q2:reviewer 改代码的边界是 skill 没写清,还是 reviewer 自己判断失误?
  A:两条都有缺口。change-reviewer §0 原文只写"不修任何东西",没枚举 `Write`/`Edit` 工具与 git 黑名单;reviewer 把"加 stderr debug log 后 revert"自我归类为"不算修"。skill 缺硬规则。

- Q3:reviewer 还把 M15 fix milestone 自己写完并 push,这是同一类问题吗?
  A:同一类。skill 没说"reviewer 严禁 commit/push 非报告类 commit",orchestrator 也没有"派发前/后 commit 基线对比"的越界检测。两个 skill 互相留口子。

- Q4:reviewer 等 fix worker 加生产级日志 / 埋点后回来"看日志验证",这个反射对吗?
  A:不对。reviewer 只对用户面负责。用户面看不到符合预期 → 直接 fail。让 reviewer 去看日志/埋点等于把它推回 engineer 模式。

- Q5:reviewer 之前花了 20+ 分钟才定位到"旧 IM 进程跑的是 M14 之前的代码"。这是普遍问题吗?
  A:是。跨进程长 daemon 项目(后台服务 / 网关 / IM)很容易出现 stale-binary——已有 PID 加载的是旧代码,但 reviewer checkout 了新分支以为接的是新代码。不解决这个,reviewer 抓到的"现象"全是假的。

- Q6:解法是"reviewer 每次重启所有服务"还是更精细一点?
  A:无脑重启清单内服务。判断 stale 的成本远高于直接重启(5 秒 vs 20 分钟);清单由 design-author 在 design.md 强制段 `§Runbook for Reviewer` 给出,reviewer 不需要读源码猜该启动什么。

- Q7:验收标准本身要不要禁止协议级描述?
  A:要。reviewer 的真值只能是"用户能看到/听到/敲到什么"。orchestrator 在派发 reviewer 时必须只透传首文档已有的用户可观察标准,严禁手写"WS 帧 X / API 字段 Y / 函数 Z 被调"塞进 prompt。

- Q8:这些 skill 给的是通用软件开发,还是只服务本 repo?
  A:通用。所有改动里禁止出现本 repo 特定的文件路径、服务名、产品名。

## 用户场景

**主角色**:在任意软件项目中使用 change-* skill 套件跑工作流的开发者(用户调起 `change-orchestrator`,后台派发 worker 和 reviewer)。

主路径:

```
人:启动 orchestrator
   ↓
orchestrator 派 worker 实施 milestone
   ↓
orchestrator 派 reviewer
   ├─ reviewer 按 design.md §Runbook 无脑重启服务清单(消除 stale-binary)
   ├─ reviewer 走真实用户旅程
   ├─ 用户面看不到 → 直接 fail(不去读源码 / 不加日志 / 不改代码)
   └─ 报告 §行动账本 + §环境声明 主动披露做了什么
   ↓
orchestrator 校验 reviewer 越界
   ├─ 派发前/后 commit 基线比对
   └─ 出现非报告类 commit → 强制 revert + 作废 verdict + issues 转 fix worker
   ↓
人:看到 PR
```

边界路径:
- reviewer 发现 design.md 没有 `§Runbook` 段 → 立即停下,要求 orchestrator 回 design-author 补,**不允许**自己读源码猜启动命令
- reviewer 想"加一行 debug log 跑完就删" → skill 硬规则判违规,污染过的环境抓出的证据无效
- reviewer 自作主张写 fix 代码并 push → orchestrator 自动 revert + 把 reviewer 的工作整轮作废 + issues 转独立 fix worker 实施(不复用越界代码)
- orchestrator 想在派发 reviewer 时写"WS 必须有 X 帧" → skill 禁用清单明示禁止,验收口径只许从首文档透传

## 验收标准

每条都从"使用这套 skill 的开发者能观察到什么"角度判定。

- [ ] reviewer 接到派发包后,**永远不会**对源码、测试、配置发起 `Write`/`Edit`/`NotebookEdit` 调用——包括"先临时改后 revert"的场景
- [ ] reviewer 在 unit 集成分支上**永远不会**产生除 acceptance.md / regression.md 报告外的 git commit
- [ ] reviewer 走旅程前,无脑按 design.md `§Runbook for Reviewer` 重启服务清单内的全部服务;清单外服务不碰
- [ ] design.md 模板含 `§Runbook for Reviewer` 强制段;design-author 自检和门禁 2 都校验该段已填(或显式"无常驻服务");缺失会导致 reviewer 卡住并要求回头补
- [ ] reviewer 写报告时,产出的 acceptance.md / regression.md **必含** `§行动账本`(按 READ/RESTART_SERVICE/BROWSE/CAPTURE/SHELL_MUTATION/SENDMESSAGE 分桶 + 计数)和 `§环境声明`(PID/端口/commit hash/临时文件)两节
- [ ] 用户面看不到预期结果时,reviewer **不会**自己去读源码 trace、加日志、抓内部协议帧——直接判 `fail`,在报告里写"期望/实际/步骤"
- [ ] orchestrator 派发 reviewer 时,prompt 里**只**透传 unit_id / unit_dir / branch / review_round / mode 字段,不会出现"WS 帧必须有 X / API 必须返回 Y / 函数 Z 必须被调"等协议/接口/实现级描述
- [ ] orchestrator 在 reviewer 回报 DONE 后,会自动做 commit 基线比对;发现非报告类 commit 时执行 `git reset --hard` + `push --force-with-lease`,作废本轮 verdict,issues 转独立 fix worker,review_round 不递增
- [ ] reviewer 判定问题归属时,只看"症状所属用户能力域 vs 首文档范围",不去定位代码模块/文件;判不准时默认 in-unit + fix-implementation
- [ ] 上述全部 skill 内容**保持通用**:不引用具体仓库的文件路径、服务名、产品名、模块名

## 范围与非目标

**在范围**:

- `.claude/skills/change-reviewer/SKILL.md` §0 / §2.5 / §4.2 / §6 改动
- `.claude/skills/change-reviewer/assets/acceptance.md` + `regression.md` 模板加 `§行动账本` + `§环境声明`
- `.claude/skills/change-orchestrator/SKILL.md` §0 / §5 / §6.2 / §6.6 改动
- `.claude/skills/change-design-author/SKILL.md` §5.1 / §6 / §8 改动
- `.claude/skills/change-design-author/assets/design.md` 模板新增 `§Runbook for Reviewer` 段

**非目标**:

- 不改 change-spec-author(它原本的"验收标准只写用户视角"规则已经够好,问题在传递链路不在 spec)
- 不改 change-impl-worker(worker 边界没暴露问题)
- 不引入 harness 层的工具拦截/沙箱(`Write`/`Edit` 在 reviewer 角色下硬拦截)——留 follow-up
- 不对 feat-340 已经被 reviewer 越界写出来的 M15 commit 做事后追溯;由 feat-340 orchestrator 按 §6.6 自行处置
- 不做 skill eval / benchmark
- 不做跨语言 / 跨开发环境的服务启停脚本标准化(`§Runbook` 段只规定字段,具体命令由各 unit design-author 自填)
