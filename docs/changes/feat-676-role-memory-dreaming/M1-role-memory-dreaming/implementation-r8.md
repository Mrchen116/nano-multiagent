# R8 实施与证据交接

2026-10-29；本文件是本轮实施记录，不代替独立门禁。设计基线为 main
`452e26373`，恢复已有 `unit/feat-676` 并保留之前实现/报告。旧逐 step 协议的相关验收失效。

## 本轮实现

- 前台 root/child 正式文档只读；明确手动保存/旧备份导入统一进入 Dreaming。
- 每轮固定 Global/child 上界，按原始文本容量连续处理；成功批次分别提交，失败后的下一轮冻结新上界。真人长消息按原 messageId、正文 hash、Unicode 偏移续读。
- 第一层任务独立提炼、同源版本复用与替换；继承背景保留原来源，不当新增证据。提炼与正式文档整合分别记录，空结果退役旧摘要。后代仅作为所属任务的受限原始回查。
- 原生维护会话空 seed；使用自己 notes/history/new_context 恢复，source_history 通过共享包的公开只读投影查询业务历史。IM info/read/search 绑定业务父身份、当前资格和历史时间范围，不领取 Inbox、不改未读。
- 普通文件 staging + finish 形成真实差异计划，正式库按 hash/回执原子应用。保留部分成功、冲突退役和版本记录补偿；取消不重放未应用计划。移除总步数/总时长配置。
- `migrate_dreaming_protocol.py` 对已有 document 状态作显式离线转换：保存原库/状态/配置，补齐已完成游标，保留启用基线、撤销与回执，退役旧计划和 JSON 偏移，不重置新协议进度。旧 legacy 搬迁脚本仍单独使用。

共享包固定发布为 `dsh-agent-context@0.3.0-rc.6`；公开新增 createHistoryView。
上游源码 `fa2b47d470b5cd51f569b678da17fb3b4f43188d`，
PR <https://github.com/Mrchen116/dsh-agent-context/pull/3>；32 项上游测试、类型/构建和 CI 通过。
匿名下载 SHA-256 `5d9d4e7a1e6e2f1f12e9c40c52738331065d547417ad83954a516a3a81074596`；
固定 release URL 加 lock integrity，不覆盖原包。仓库未启用 Release immutable，不能把固定 URL 冒称 GitHub 已锁定发布。

## Prompt 原文与适配

Codex 原版提炼主体保持逐段内容；修改运行主体、finish 输出接口、原生继承/恢复边界。
原文与最终两个 prompt 的逐行差异见 [prompt-adaptation.diff](prompt-adaptation.diff)。
运行分发来源说明及 Apache LICENSE/NOTICE 位于
[随包 provenance](../../../../packages/dsh-integration/assets/dreaming-provenance.md)。
Muse 四份原始说明用于用户目标变化、关系、互动失配与主动性条件维度，落到已有角色文档，不创建平行调度或自我修改系统。

## 回归处置与已完成证据

| 范围 | 处置与理由 | 本机证据 |
| --- | --- | --- |
| dreaming-runtime / incomplete | rewrite-merge：删去旧逐项读取/覆盖声明，保留未 finish、读失败后写入、轨迹暖/冷读及实际请求边界 | `/tmp/feat676-core-native5.log`，相关26项通过 |
| dreaming-recovery | rewrite-merge：移除私有 model/freeze spy，改为公开 start/recover + 已持久计划/真实文件回执 | 同上，7项通过 |
| memory-sources | keep + 扩展：认证、配对、修订/碎片、继承条件及逐消息 Unicode 续读 | 同上，11项通过 |
| dreaming-task-runtime | 新 seam：原生 continuable fork → 提炼/整合失败复用 → 同 child 续做替换 → no_signal；维护换窗、原始回查；超过旧24步/1ms配置仍完成 | `/tmp/feat676-native-no-signal.log`，1个连贯旅程通过 |
| dreaming-cycle-runtime | 新 seam：真实运行时多批成功/失败，再冻结包含新消息的重试目标；已提交前缀不重读 | `/tmp/feat676-cycle.log`，通过 |
| dreaming-history | 新 seam：业务 source_history 的授权过滤、时间/窗口/ID、Unicode分页、外部cursor拒绝、原身份IM绑定、选定任务后代 | `/tmp/feat676-history3.log`，3项通过 |
| 两类离线迁移 | keep + 新协议状态 seam：未完成计划、完成未提交游标、原文保护、中断重入和新进度不重置 | `/tmp/feat676-migration2.log`，14项通过 |
| 扩大回归 | dsh-integration全目录、product-contracts、PA global-agent与IM work | `/tmp/feat676-expanded-tests.log`，68文件307项通过 |
| 构建 | 全仓构建完成；随后 integration 增量构建用于新增测试 | `/tmp/feat676-full-build.log`、`/tmp/feat676-core-build9.log` |

新增测试属于不同真实 seam；不为文档每句或内部拆分另建机械覆盖。上述 native fixture 的 LLM 返回受控，不能证明真实模型理解。

## 初步真实模型自检（独立验收尚待）

隔离 daily `/tmp/feat676-daily-20261029`，IM `http://127.0.0.1:50967`，
P/E/Q Sol high、PA Astra medium、独立审核 Luna；未修改生产。
PA 会话 `c_91ae1772dfea`，root `92288720-595f-4666-96e0-30267706dccf`。
合成输入 `4cffa112ae3c43a38e09a3af36858811` 要求仅在当前对话采用虚构旅行条件；
回复 `8e52ba6be22044e3bfc230c6f1f3cc73` 保留5000预算、免费取消、周六下午出发及缺失信息，未泛化永久偏好。
随后明确整理请求 `12a192cf987b40a9a3da23b7de472ff4` 触发
`dreaming-a823e27b-c6d8-4666-9ceb-069c280cb922`，宿主 completed、2/2页保存。
本地材料 `/tmp/feat676-live-evidence/` 及隔离 workspace；没有提交原始模型/用户数据。
这仅是自检，不能代替 S01–S30 独立产品验收。共享代理 request logging 默认关闭，本次没有重启它；真实 wire 捕获另在隔离转发路径补证。

## 冻结版本的本地全量检查

实现候选 `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`：

- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime` 通过；日志分别为 `/tmp/feat676-frozen-build.log`、`/tmp/feat676-full-typecheck.log`、`/tmp/feat676-ios-runtime.log`。
- `pnpm test`：164文件、851项通过，`/tmp/feat676-root-tests.log`。
- Web `npm --prefix src/IM/frontend run test -- --run`：108文件、1031项通过，`/tmp/feat676-frontend-tests.log`。
- Python `pytest -m 'not e2e' -q`：127通过、28未运行，`/tmp/feat676-python-full.log`。`ruff check .` 与 `ruff format --check .` 通过。
- docs-check：326 maintained sources / 68 required routes 通过，`/tmp/feat676-docs-pre-review2.log`；重新打开活动unit后的两条相对链接已修正。
- Web `npm audit --audit-level=critical` 退出0；仍报告11项既有依赖告警（4 low / 2 moderate / 5 high），未擅自升级本轮无关依赖，`/tmp/feat676-frontend-audit.log`。该结果仅表示当前CI阈值通过，不等于依赖无告警。

共享代理保持原状。仅当前隔离环境经 `/tmp/feat676-live-evidence/capture_proxy.py`
透明转发并记录真实 adapter 请求/响应，端口56172；候选构建后 Node pid59025、DSH pid59092，IM保持50967。
捕获文件只写本机私有目录；独立产品reviewer使用该环境，不以stub替代模型行为。

### 独立审查后的定点修复

- F-R8-1：8 天前已保存但 Git 版本记录失败的 completed plan，恢复时保留 staging；补记成功后仍按保留期清理。真实 `.git/index.lock` 造成版本记录失败，解除锁后跨 recover/start 补记成功，随后过期清理通过。
- F-R8-2：直接展开 Inbox 及按原消息 Unicode 分页均保留外层 conversation target/name/delivery/type/channel，消息自身 sender/id 不变；Global 与 child 复用同一 renderer。
- D-R8-1：修正 active spec 三个包源码链接层级；上游源码阅读入口 `stage_one.rs` 更正为该固定版本实际的 `phase1_output.rs`。
- 新回归先得到 3 failed / 17 passed，修复后 20 passed；原生 Dreaming、子任务提炼/续做/换窗和共享原始历史 6 passed，DSH integration build 通过。日志 `/tmp/feat676-review-{red,green,runtime,build}.log`。初次窄测 shell 为 Node 25.8.2（build 给出 engine warning），交付前使用项目 Node 24.22.1 再验。

### 固定上游代码机制核对

按 `8fdf6472955749a731fd9e4b8ffc218e8e80c51d` 阅读 `rollout_input.rs`/相邻测试、`phase1.rs`/`phase1_output.rs`/`prompts.rs`、state `memories.rs` 的资格/更新/成功/无输出路径、`phase2.rs`、`storage.rs`/tests、`workspace.rs`/tests、`workspace_lock.rs`，补齐模板之外的实现依据：

- 原始提炼输入按 human/final/other-agent/commentary/context/tool 近期优先选择，最后恢复时序；问答配对、缺口标记和 Unicode 分块保留。Nano 保留优先级及来源身份，Global 使用连续可提交批次，child 按容量选择合格自身经历及继承背景；Inbox 里的真人正文与外围观察身份同时保留。
- V2 输出仅 rollout_summary/rollout_slug；同 thread 源版本更新替换，no_output 删除旧输出，并在旧输出曾存在时驱动下一次整合。Nano 采用同一语义，用现有 storage domain 的每 child 当前摘要与 integrated 版本分开表示提炼/整合成功位置；不增加 raw_memory。
- 上游 phase2 先排他、同步当前选中摘要、计算 workspace diff，再启动受限整理 Agent；只有完成且产物有效、仍拥有作业权才重置 baseline 和登记选中版本。Nano 复用现有主体排他、冻结 source generation、staging 文件计划与逐文件回执，成功后推进相应来源范围；无需复制 SQL 租约或 Codex 工作区格式。
- 上游 heartbeat 持续续租，循环等待最终 Agent 状态，无总耗时/总步数上限。Nano 删除专属上限，保留输入容量、取消和请求真实错误。上游 summary-only 格式、9KB 输出裁剪与目录布局不照搬；Nano 使用角色入口/正文及既有模型输出预算，差异由已批准 design 和 prompt-adaptation.diff 说明。

- 项目 Node 24.22.1 复验：DSH build 通过，5 文件 26 项通过（`/tmp/feat676-review-{node24,build-node24}.log`）。产品 reviewer 指出 R6 原型的停用提示漏同步，现已同步 Web 中英和 iOS；Web agent-detail 28 项及构建通过（`/tmp/feat676-review-ui*.log`）。此修复仅说明文字，不变更开关行为；真实页面由产品 reviewer 定向复验。
