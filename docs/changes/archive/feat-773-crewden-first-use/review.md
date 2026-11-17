# feat-773: 收尾审查与验证

## 范围与用户验收

- 用户选择快速开发并持续实际试用；最终原话为“我觉得差不多，做收尾吧”。首文档与 as-built design 在实现后形成，未补造事前设计审查或独立产品验收。
- 独立 reviewer：`/root/final_code_review`，`gpt-6.1-sol / high`。首轮完整审查 base `d7f0e60173c9c3feafbec7d251364537da70478b` 到实现 head `a6badf9b0`，24 commits / 129 files，另含本 unit 未提交文档。两轮 closure 核对本轮明确的修复 dirty diff，最后判定 corrected delta aligned、无存活 findings。
- 视觉与旅程复用同一聊天中的用户验收、截图/录像及本机 `output/playwright/` 阶段证据。新建账号、头像创建表单的部分画面使用浏览器响应 fixture；真正安装、绑定、当前候选创建 PA 与模型回复的证据单独区分。

## Round 1 — 完整 code / Context 审查

1. **P2 CONFIRMED**：首次设置将 pending binding 当作可打开的聊天；能力查询或配置未完成后刷新缺重试入口，可能跳入尚不存在的会话。修复：用服务器创建标识、绑定名字与原电脑恢复同一次操作；未确认完成显示重试和错误反馈。刷新恢复测例覆盖失败后留页、成功后导航。
2. **P2 CONFIRMED**：PA 固定入口/欢迎页忽略手动聊天标题；配置提交还会覆盖存储的手动标题。修复：入口采用会话标题，配置提交仅同步 `title_is_custom=0`。延迟回执测试同时覆盖默认标题更新与手动标题保留。

上述两项包含基线已有部分，但与本次恢复和标题契约直接相关，已一并闭合。候选写入前失败时没有已接受的头像记录：同浏览器同请求草稿可恢复，跨浏览器不承诺恢复未接受的选择，边界写入 design。

其余官网/认证入口、创建与头像投影、聊天首屏/群详情、会话 reader 与授权主体分离，与 delta 对齐；未发现权限扩大。头像为 nullable additive schema 且不进入运行配置指纹。

## Round 2–3 — 修复复核

Round 2 确认原始两项 closed，指出新分支把已创建但运行时 `unavailable` 的助手误当 pending，并提醒不得把不同请求的本地头像草稿用于服务端恢复。作者改为依据 `creation` 区分已完成和未完成，用绑定名字满足恢复校验，仅 request key 一致时回送本地头像。

Round 3 静态 closure 确认这些问题均 closed，最终 delta aligned、无存活 findings。新增测例涵盖 unavailable 仍可进入既有私聊、空本地名字恢复、同/异 request key 的头像隔离。无新增设计决策或全量视觉重验。

全量前端检查另发现并修复共享测试初始化回归：`HTMLElement.prototype.scrollIntoView` 遮蔽原测试在 `Element` 上的 spy，且在 node-only 环境不存在；改为有 Element 才在其原型 mock。退出登录断言更新为实际 Welcome back 标题。相关 48 项测试通过。

## Context 证据与限制

独立 reviewer 亲读原始 DSH 轨迹，受保护副本留在本机 `output/final-close/context-evidence/`，不提交：

- 候选安装 PA session `4b0000f0-04b4-4c16-81bf-95ce41d035ce`，2026-11-17 14:21 JST：seq 9 包含 PA 来源指引，seq 10 包含未设置 ROLE 时当前任务优先提示；seq 14/22 请求边界、seq 17–21 Inbox 及 seq 25–26 发送回执对应真实首次任务，未继续追问职责。
- Daily PA session `dbc6d6f5-700f-421d-b2b2-b699987cdfc1`，seq 53–59 以 observer 读取主人和 E 私聊，保留作者与原话；seq 60 判断无需介入。该轨迹生成于最终会话名改动前。
- 新名称进入 Inbox wake/check/read 由确定性的运行端口回归证明；不称为真实模型推理证据。现存轨迹没有证明新名称的真实模型消费、请求转发前主动查来源、ROLE Skill 实际加载以及确认后保存/回读，也未取得独立 provider 出站 JSON；本次不扩展为这些既有能力的重新验收。

## 检查与资源

- 最终前端全量：126 文件 / 1230 测试通过；之后 pending 恢复末轮修正另跑 onboarding 15 项通过。前端构建通过，已有 bundle size 提示；critical audit 通过，仍报告 14 项非 critical 依赖告警（本轮未改依赖）。
- 后端 build/typecheck、打包原生 interactive runtime 检查通过；PA 配置/回执修复的 2 文件 30 测试通过。
- Python 非 E2E 136 项通过，ruff check/format、docs-check、完整 diff whitespace 检查通过。
- 后端默认并行全量：245 文件中 238 通过，1405 测试中 1395 通过；7 个 DSH 相关文件的 10 项失败为超时、capability inspection deadline 或 FS recovery teardown RPC closed。同一源码下以 `pnpm exec vitest run --maxWorkers=1` 串行重跑这 7 文件，28 项全部通过（73.75 秒），未改超时或运行实现。失败与并发条件相关，但未证明底层根因；保留原始失败和串行通过记录，不声称默认并发全绿。
- 已停止 daily IM/Gateway（52855）与安装候选预览/Node（60124），核实监听端口释放；删除独占的 `output/crewden-full`、`output/crewden-home/runtime`、`output/playwright/crewden-app/node-video`，保留截图、录像、摘要与两份必要轨迹。停止本任务 `crewden-full-review` tmux；未动其他任务/生产服务。
- 开发 worktree 在 PR 审查期间保留，责任归本聊天；合并后按工作流清理。没有合并或生产部署授权。本地安装候选已验证不代表公开旧版 v1.0.3 已升级或发布。

## 收口

用户验收、独立 full/closure、canonical 归并与适用验证完成，整套 unit 归档；实现修复提交 `0ecde14e8`。PR 目标 develop，远端 CI 在 PR 中追踪；没有自动合并或部署。归档后仅路径与验证结果补记，已审代码和契约语义保留。
