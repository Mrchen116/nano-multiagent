# M1 实施与验证证据

## 当前实现

同一 unit 串联个人账号/资源空间、同源电脑安装包、空 Node 启动、模型 setup、Web 四步向导及首次真实聊天。初轮独立实施负责 IM 空间边界与 Node/DSH 模型 seam；主 Agent 负责集成、安装器、Web 和后续修复。完整门禁尚待独立审查与产品验收。

## 已验证

- 全新隔离安装目录：从 `http://127.0.0.1:18489/install.sh` 获取实际发布包，校验 SHA，安装锁定依赖，浏览器确认后启动 Node。无需仓库路径、YAML 或预建助手。
- 初次慢速确认触发真实 429：`prepare` 每秒调用与浏览器共用 60/min 来源桶；现改为 3 秒并遵循 Retry-After。已有 device-binding 行为测试先失败、修复后通过，同时仍证明丢失 commit 响应可恢复、旧 owner runtime 保留。
- bootstrap 最低层测试证明同源重跑身份与配置不变、不同服务独立、私有文件权限，跨服务指定既有配置拒绝覆盖。
- IM onboarding API 测试在路由接入前 404、接入后通过，覆盖本人资源、他人节点拒绝、异步归属变更拒绝、凭据不回显、未发布安装包明确 503。
- 真实 Node ModelSetup → DSH → 本机代理 → `codexOAuth:gpt-6-luna` 验证成功；浏览器随后真实创建 global 助手 `assistant-31e4dd7c`，工作目录自动分配。首聊 `c_uacc7xc9` 收到真实模型回复，按建议起步任务询问目标、截止时间/固定安排与可投入时间；刷新后历史保持。
- Integration 测试通过真实锁定 DSH 的公开 settings/credentials seam，验证失败回滚、冷重启后 key 保留和实际 Agent 回复。原生 OAuth device-code notice/cancel 经受控 interaction 验证，未宣称真人 OAuth 登录完成。
- Web onboarding 3 个行为测试通过：连接失败禁止跳步且不保存 key、创建重试保留 Agent ID 和安全默认值、重新打开已有首聊不覆盖草稿。Web build 通过。
- 初轮 IM 套件、公司/认证 Web 窄测试、11 个 DSH 依赖架构契约通过；最终全套结果在交付前补齐。

## 证据与限制

所有运行数据位于 worktree `.dsh-runtime/onboarding-e2e/`，IM 仅监听 18489；Node identity、config、DSH home、workspace 均隔离，安装演示禁用登录自启。截图和最终录屏保存在本地 `output/playwright/`，不提交数据库、凭据或媒体。

现有本机代理 DeepSeek profile 的流式 SSE 返回未标注 encoding 的压缩字节，被真实 DSH 拒绝；非流式成功不代表可用。该外部代理未修改/重启，验收改用其已验证的 Codex ingress。

## 测试维护

保留/扩展现有 identity、control、device-binding、company-access、auth-form-experience 与 iOS SessionTests；旧注册等待批准断言改为个人 onboarding。新增 bootstrap、setup、onboarding 和 tenancy 测试分别持有首次安装、公开运行时配置、跨进程入口与跨资源空间隔离风险；无为单次录屏创建永久测试。

## R1 修复与本地 CI

独立静态审查的三项发现均在本 unit 范围内并阻塞交付：公司 Work 失权导致同节点私人 journal 无法推进、首次 discovery 缓存使后启动的代理不可发现、Node 官方包解压失败后的部分目录被误认为完整。主 Agent 为每项补充可复现的失败测试后集中修复：不保存/发布失权 Work 内容但推进共享 journal；每次 setup 状态重新做限定范围发现；官方 Node 在临时目录完成解压、Node/npm 校验后才写完成标记并提升目录。3 文件 12 测试通过，既有 Work/trajectory 2 文件 6 测试通过。

独立产品走查还发现已连接模型可再次点击并得到误导失败、助手创建后掉线仍显示 ready。主 Agent 将已有连接明确标注并允许继续，掉线按真实节点状态回到恢复步骤。对应前端行为测试先红后绿。既有绑定测试补充真实 transfer 标记，保留接收确认覆盖；普通绑定路由断言更新为电脑连接文案。相关 3 文件 11 测试通过。

本地检查（完整基线 `59650f196` 与上述修复的受影响回归合并作为证据）：

- 后端全量：63 文件、178 测试通过；修复增加 3 个行为测试，相关套件另跑通过。
- Web 全量：88 文件、830 测试中 827 通过，3 个失败均为绑定旧文案/缺少 transfer fixture；修正后相关 3 文件 11 测试全部通过，其中新增 2 个恢复测试。无忽略或删除失败测试。
- Python standalone/architecture：54 passed、31 e2e deselected；Ruff check 与 82 文件 format check 通过。
- `pnpm build`、`pnpm typecheck`、Web `npm run build` 通过；Web critical audit 为 0 vulnerabilities。
- iOS：独立模拟器 27 XCTest + 10 Swift Testing 全通过；Release arm64 archive 成功，无签名。仅说明构建/模拟器证据，不等同真机安装验收。测试专用 simulator 已删除。
- 最终 sync `origin/main=b70d4a7bd80b4424fea430e507390c5dde7c0a05`，较审查基线未推进。

原生 OAuth 真人账号登录、Linux/WSL 实机和生产部署未作为本次已完成证据。真实模型路径采用本机现有代理的 Codex ingress；官方 Node 自动下载路径由独立产品走查在隔离目录实际执行。

### 重装升级与首聊状态诊断

产品 reviewer 在第二次安装时遇到发布版本切换，启动最终超时。主 Agent 只读定位到自有 DSH profile 的两个 bundle symlink 仍指向旧 release，而新 launcher 从新 release 运行。用隔离空 home + 原旧链接重现 `web_fetch already registered`；不读写生产凭据。`prepareProfile` 现只对自己生成的两个符号链接比较并更新目标，不删除其他配置。链接更新行为先红后绿；同一旧链接实验经重新 prepare 后真实官方 DSH initialize 成功。安装发布版本变化属于首次安装/重复命令的真实交付场景，本 unit 内关闭。

reviewer 首条用户消息的 failed 并非离线测试导致：Node 持久事件 `turn/end seq=48` 在 `2026-10-12T17:06:13` 记录上游 `502 upstream_empty_stream`，发生于已显式发送回复之后。第二轮 `seq=80` 为 completed；IM 两条 Agent 回复均 completed。该既有执行回执语义如实保留上游错误，不把已发出回复伪装为整轮成功，也不把它判为离线 UI 回归。外部 LLM_PROXY 未修改。

## R2 定点恢复修复

独立静态复验发现两个直接恢复缺口。第一，创建后的同一向导组件已经固定在 ready 步骤，之后设备离线没有重新计算；现在实际节点离线优先于手动步骤，新增“创建成功后不刷新、节点掉线”的行为测试先红后绿。第二，撤销公司资格时若完全丢弃 session 注册，随后授权的新 owner 接收整机后无法延续 journal；现在只保留 session 身份与父子关系，不保存、投影或广播失权期间的内容。真实数据库交接序列测试先出现 scope_not_allowed，修复后证明新 owner 的公司和私人事件均可继续，失权标题不可读。

产品复验发现任务工具仍把所有计划描述为 company-shared，导致私人助手拒绝保存用户明确要求的私人计划。工具说明现与已经实施的固定资源空间一致：私人 Agent 的计划归本人，公司 Agent 的计划归公司；加入团队不发布私人计划，讨论 target 不能改变范围。此修复不改变权限或工具执行协议，实际计划创建由独立产品复验覆盖。

## 完整新用户录屏

在 `00dd42398` 发布物上，从全新账号与空安装目录实际完成注册、两种安装入口、复制手动命令、下载与安装、浏览器绑定、已发现代理的真实模型测试、用途/名称/目标引导、创建助手、发送可编辑的首个任务及刷新后保留真实回复。IM/Node/配置/身份/运行数据全部隔离；模型调用使用已有本机代理，未预填或伪造助手回复。最终消息的 relay 与 receipt 均为 completed。

原始完整视频 452 秒；交付版仅以 2 倍速编码全部画面，226 秒。中文章节字幕和最终真实聊天画面已经抽帧人工检查。录像中的终端展示页明确标注为辅助展示，呈现真实 installer stdout，绑定 token 已隐藏。保存于外部交付目录 `feat-587/new-user-flow-full.webm` 与 `new-user-flow-2x.mp4`，不提交媒体或运行数据库。后续 R2 补丁影响掉线恢复、Work 恢复和任务工具说明，未改变这段首次成功旅程，保留录像证据。


## R3 真实交付修正

产品 reviewer 在冻结发布包 b1a70198 上证实私人计划 tg_021a12df 已通过普通请求保存，不再要求公司共享确认；同页掉线与同电脑恢复也已通过。但执行以 completed 结束时仅产生 Work 内的“已保存”草稿，没有调用 send_message，聊天未收到结果。此真实失败作为交付修正的红证据，不能以工具成功代替用户收件。

主 Agent 核对 global-mode 提示后，修正“工作完成无需额外 public completion”这一过宽表述：直接真人请求的答案/结果先通过既有 send_message 发回来源聊天，已送达后才无需重复完成消息；背景无可行动结果仍静默。没有修改工具、路由、自动审批或静默终态机制，也没有隐式公开私人草稿。此类模型行为以独立真实复验为绿证据，不增加只断言提示字符串的测试。

## 最终门禁与归并

产品 R4 在 `f881314a469e97178cd91e59a308c0d3625404d9` 的真实发布包上完成私人保存请求，任务 `tg_6bd77847` 成功且原聊天 `c_rprqeogj` 收到与之匹配的真实完成消息；#5 关闭。结合前轮有效证据，S1–S12 全部通过，0 未关闭阻塞。独立静态 R4 在同一实现树 PASS、0 CRITICAL/0 WARNING，七份 corrected delta 全部 aligned；通信窄测试 2/2 通过。

最后一次 origin/main 同步仍为 `b70d4a7bd80b4424fea430e507390c5dde7c0a05`，无 main 增量。各门禁 executed_base 与 effective_base 均为该 SHA；code review/verification/product validated_at 均为 `f881314a469e97178cd91e59a308c0d3625404d9`。后续仅报告、七份已核 delta 的 canonical 归并、入口数量/职责摘要、使用说明与整体归档，无产品代码变化；结论 retained 到最终交付树，PR 记录解析后的 effective_through SHA。Gate 2 同理保留：恢复和明确交付义务不改变已审用户范围、接口、显式投递机制或权限。

最终本地 Web 全量 88 文件/833 测试全部通过；root build/typecheck、Web build 已通过，最后提示改动后重新 root build 与通信回归通过。较早的后端全量、Python/Ruff、iOS 模拟器/Release archive 和其后定点回归保留，未因文档归并重复无关全量。录像已有真实成功 send_message，新的交付提示仅纠正后续私人保存请求，不使原视频失效。

canonical 只归并七份已核对的 delta；更新包入口计数与现行说明，README 区分已有 IM 用户和自托管者，Gateway/local-stack 记录安装与安装包发布。全部 unit 文档整体归档后提交 Ready PR；未自动合并或部署，生产与主仓无关 dirty 内容保持原状。

最终文档检查通过：260 个 maintained Markdown、64 条 required routes。检查发现 active delta 中一个沿用 canonical 相对位置的 gateway-relay 链接；已仅修正指向，归档时随目录深度调整，不改契约。`git diff --check` 通过。

## 588 集成后的完成复核与新版录像（2026-10-13）

PR339 已合入本 587 分支，集成点为 `77622d2152fe7e1bb2966fb656adf9e41613aed6`，其树与 588 最终 head `0247eb0e610bbf366f37b34f41015430cdaff8f7` 完全相同。该 head 的 CI run 38349265822 三项成功证据保留。独立静态复核 R5 对齐全部需求/里程碑后提出两处 current 文档偏差；一次修正 README、Gateway、安装发布 runbook 和入口后，R6 在 `22aa42c62af979671366d2a1ebc2644f1d7618e0` PASS，0 CRITICAL / WARNING。独立产品 R5 在集成运行时 PASS、0 阻塞/major，逐项保留或重验 S1–S12；原 S6 开发者代理发现由 588 的 API 优先契约明确替代，不再宣称旧路径通过。

新版录像在上述确认之后，以另一个全新账号“林舟”、空安装根和独立 IM 18497 开始。实际完成中文注册、两种安装选项及复制、无预装 Node 的手动安装、网页绑定、添加自定义 API 并真实测试、命名“小澄”并创建助手、修改首个任务草稿后发送。任务请求是建立每天阅读 20 分钟的习惯，未在请求中指定底层工具；真实助手在原聊天提出三个相关问题。会话 `c_e5j6ws6w`，助手 `assistant-a5154775`，节点 `computer-bd19e4ec`；用户消息和助手消息均 completed，relay `7a2b580820314ff09102b7873609a98c` 的 status / receipt_status 均 completed。录像止于首答，没有刷新章节；刷新/重装/离线恢复由独立验收报告覆盖。

原始视频 509.12 秒、1280×900，交付 MP4 为全程 2 倍速约 254.6 秒，未删去安装等待或失败步骤。画面与最终首答已抽帧核对。媒体保存在本地交付目录 `feat-587-integrated/new-user-flow-full.webm`、`new-user-flow-2x.mp4`，不提交媒体、账号、凭据、日志或数据库。终端是明确标注的辅助输出页，呈现实际安装 stdout。程序包为固定版本/哈希的本地候选：只将精确 GitHub asset URL 的运输替换成本地相同字节，其余官方 Node 下载与安装真实执行；这不代表已发布 Release 或通过匿名公网下载。自定义测试 API 将请求转发到已有代理的真实 Codex 推理，不代表第三方厂商账号认证。

最终同步 main 到 `82b4c13201dccd12ac72bb2a79c4dd99aa233c49`，新增内容仅为独立 feat-589 的设计/证据文档，无运行时代码和本 unit 行为变化。门禁 executed_base 保留 `b7e367cc08a642133dea28e372816cd79038818d`，effective_base 更新到该 main SHA；后续报告和 current 文档校正不改变集成运行时，各有效门禁 retained。同步后文档检查 248 sources / 64 routes 通过，diff check 通过。新版录像这轮最终执行完成；独立产品 R5 中首答送达后的上游 empty_stream 失败仍按其报告保留，不用本轮成功覆盖历史观察。

用户要求停在 merge main 之前：PR337 继续 OPEN，未合并 main、发布 GitHub Release 或部署生产。用户原试用服务及无关工作区内容保持原状。
