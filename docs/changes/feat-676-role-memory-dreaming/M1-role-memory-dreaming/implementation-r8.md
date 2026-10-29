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
