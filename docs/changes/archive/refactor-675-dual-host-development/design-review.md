# refactor-675 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`（独立 design reviewer）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖完整设计、一次性迁移、M1 骨架及开发 Agent Context Mode A。
- started_at: `2026-10-28T11:51:16+08:00`
- completed_at: `2026-10-28T11:53:20+08:00`
- duration: `124s`（正式判断与报告阶段；材料读取在此前完成）
- reviewed_base: `532704f7168e4eb350b3f830d47fbeb701a13731`
- reviewed_tree: 上述 detached checkout 中现有 motivation，以及未提交的 design、deployment-prompt、`M1-development/.gitkeep`；没有受审实现 diff。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

开发入口、生产隔离、两机分工和整数编号方案可成立；一次性迁移漏掉恢复 IM 服务的关键动作，需补齐后复审。

### Coverage 与证据

1. **需求与用户约束。** motivation 的三项不变性均有设计对应：固定生产 checkout/持久数据、Mini 飞书提前拒绝、Air 明确发起部署。保留 spec/design main、同 unit 通常同机完成与现有整数号；冲突按首次成功推送解决，没有新增跨机调度或锁服务。`next_unit_id.py:38–102` 的锁确实位于 Git common dir，不能提供跨 clone 唯一性，设计的远端推送冲突检查补充合理。
2. **E2E 实际入口。** 已读 `scripts/e2e-up.sh` 和 `e2e-down.sh`：up 从脚本确定源码根，支持任意 `--wt`，转换私有 Gateway 配置后会删除目标 DB 并启动真实 IM/CLI；down 会按目标配置停止 Gateway。因此同时 guard 源 checkout 与 runtime，并放在复制、删除和停止之前，落点正确。完整本机 YAML 复用现有 default/daily/feishu 转换，显式 `--main-config` 优先，避免引入第二套配置合并器。缺省配置兼容社区/CI、错误配置失败、Mini `feishu_e2e=false` 在读取凭据前失败都有明确语义。
3. **生产数据与启动依赖。** `apps/im-server/src/server.ts:63–65` 支持 DB/upload 路径覆盖，`media.ts:39` 的图片目录相对 DB；前端与轨迹资源在 `server.ts:271–286`，安装资产入口在 `server.ts:168` 和 `install.ts:10`。设计已包含 DB、图片、uploads、静态资源、既有安装资产、Node、Tunnel venv、身份和 DSH state 的处理。`apps/node/src/lifecycle.ts:345–360` 由当前 CLI 生成并 bootstrap Gateway LaunchAgent，复用该入口合理。迁移仅改路径且保持生产 SHA，未把后续 main 功能一起发布。
4. **一次性部署提示词。** 覆盖适用条件、秘密本地备份、停写后 SQLite backup、附件核对、未知目标拒绝、完成/跳过判据、中断恢复、新写入后的无损回退。临时数据负责功能与失败演练；生产只核对迁移和连续健康，没有生产消息测试或故障注入。600 秒 Tunnel gate 有终点；恢复 IM 的顺序缺口见 R1-W1。生产现场事实采用本轮主 Agent 提供的只读核验，未在本审查中重新登录生产，也未执行迁移。
5. **契约和 milestone。** 本次不改产品工具、业务行为、公共 CLI 或 UI；`no spec delta` 合理，长期事实归 development/operations。唯一 M1 骨架仅 `.gitkeep`，符合设计阶段要求。退出标准涵盖 guard 边界、两机真栈与模型回包、清理、临时迁移恢复、有限生产核对及独立审查；没有把隔离功能验收拖到生产。无前端交互变化，不需要原型和产品 reviewer。
6. **架构与复杂度。** 本机资源解析/防误操作属于开发脚本，生产编排属于部署 runbook，不应进入 PA/IM/DSH 业务包。一个标准库 helper 加私有 JSON，复用既有 E2E、CLI 和 Tunnel 能力，规模适合两机当前需求。生产标记与 protected_paths 是误操作保护，设计未声称其为权限沙箱；未发现有实质维护代价的多余抽象或平台化机制。

### Agent Context Review — Mode A

- **Consumer / Surface：** change-* 开发 Agent 的 AGENTS、按需开发文档、host check 输出，以及部署 Agent 消费的一次性操作提示词。没有产品模型 System Prompt、工具 Schema 或 Memory 存储修改。
- **来源与交付：** 当前 `AGENTS.md` 和 `llm-integration.md:7–27,108–117` 含 Air 绝对路径。设计改成 AGENTS → 权威本机说明 → check/本机文件，提供可发现的参数来源；不将 Gateway 密钥正文输出给 Agent。host 标签只作展示，路径事实来自当前机器检查。
- **更新与恢复：** 机器切换后重新读取配置，旧会话/Memory 路径不被当作当前本机事实；部署状态仍以 prod-fleet 与 live 证据为准。飞书能力拒绝在脚本执行层，不能仅凭提示词默认 Agent 遵守。
- **可验证性：** 两机 reviewer 实际读取入口并运行 check，再用隔离 daily 真栈与模型回包证明配置消费，符合这次开发文档/脚本的风险；不要求为纯文档改动另起业务模型评测。当前尚无实现与 check 输出，以上只是设计可行性判断，不宣称已经交付或模型已正确消费。
- **发现：** R1-W1 同时属于部署 Context 的可行动性缺口；没有额外开发 Context finding。

### 历史问题闭环

首轮，无历史问题或 Author Resolution。

### Issues

#### R1-W1 — 停止 IM 后缺少重新启动与源站健康确认

- severity: `WARNING`
- evidence status: `CONFIRMED`（文档步骤缺失；未运行生产证明故障）
- 位置：`deployment-prompt.md:15–19`，「切换」步骤 1、3、4、5。
- Context Surface：部署 Agent 直接执行的顺序操作指令。
- expected：卸载旧 IM、复制数据并修改启动定义后，重新加载同一 IM LaunchAgent；确认新 cwd/数据路径和 loopback 健康，再启动 Mini Gateway、应用 Tunnel 解释器变更及最终 gate。
- observed：步骤 1 卸载 IM，步骤 3 仅更新 launcher/plist，步骤 4 直接启动 Gateway；直到完成判据都没有恢复 IM 的动作。编辑 plist 本身不会重新加载已卸载的服务。现行部署 runbook:117 明确要求「IM 健康 → … → 受影响 Gateway」。
- 影响：按提示词字面执行时源站持续停止，Gateway 无法连接 IM，后续 HTTPS/节点健康判据也无法完成；执行 Agent 必须在生产停机窗口自行补关键步骤。
- 建议：在更新 IM launcher/plist 后明确 bootstrap 原 IM 服务并验证 loopback readiness、实际 cwd 和 DB/upload 路径，成功后才进入 Gateway/Tunnel 步骤；失败立即进入现有恢复分支。临时迁移演练同时核对这个停启顺序，无需增加生产演练或新 Gate。

### Recommendations

- **R1-R1（可选）**：安装资产现有默认值位于 checkout 的 `dist/node-release/`（`install.ts:10`），可在迁移提示词中直接注明使用现有 `IM_NODE_RELEASE_DIR` 指向独立稳定目录，保留并核对既有 manifest/包哈希；这会使「安装资产保持且不依赖开发目录」更易执行。设计已要求保留既有资产与稳定路径，本项不另作阻断问题，也不授权重新发布安装包。

### Author Resolutions

- R1-W1 accepted：deployment-prompt 切换 3 补齐原 IM LaunchAgent bootstrap、PID/cwd 与 loopback 200 门禁；失败立即回滚，不继续 Gateway/Tunnel。
- 安装资产建议 accepted：同段明确独立 node-release 目录、IM_NODE_RELEASE_DIR 与既有 manifest/包 SHA256 核对，保持既有发布版本。

## Round 2

### Metadata

- reviewer target: `/root/design_review`（与 Round 1 相同的独立 reviewer）
- review_mode: `closure`
- mode_reason: 本轮仅修订 deployment-prompt「切换」步骤 3，关闭 R1-W1 并落实安装资产建议；没有需求、核心边界、接口或 milestone 变化。
- started_at: `2026-10-28T11:54:04+08:00`
- completed_at: `2026-10-28T03:54:37.214Z`
- duration: `33s`
- reviewed_base: `532704f7168e4eb350b3f830d47fbeb701a13731`
- retained_from: Round 1（其他设计内容和实现来源未变）

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

### Coverage 与证据

重读完整 deployment-prompt 和 Round 1 Author Resolutions，复核其停写、恢复 IM、启动 Gateway、更新 Tunnel 与失败回滚之间的顺序。其余需求、E2E 入口、生产隔离、编号协作、no spec delta、M1 骨架、架构复杂度及开发 Agent Context 判断沿用 Round 1；本轮只对部署提示词的局部 Context 可行动性与安装资产路径消歧作增量判断。没有运行生产服务或实现验收。

### 历史问题闭环

- **R1-W1 — closed。** Author Resolution 接受问题；`deployment-prompt.md:17` 现明确以原 label bootstrap 原 IM plist，确认 PID/cwd 与 loopback `/health` 200 后才进入 Gateway，启动或健康失败停止切换并执行既有恢复段。`deployment-prompt.md:27` 仍分别覆盖新路径接受写入前和接受写入后的恢复，未因补充启动步骤丢失无损回滚要求。部署 Agent 可从当前文本取得恢复服务的动作、继续条件与失败方向；原文档缺陷已关闭，不代表生产迁移已成功。
- **R1-R1 — addressed。** `deployment-prompt.md:17` 明确复制既有已发布安装目录到 `~/.nanoassistant/node-release/`，通过现有 `IM_NODE_RELEASE_DIR` 固定入口，并比对迁移前 manifest 和包 SHA256，禁止采用新 build 候选清单。该补充落实原有稳定路径与保持已发布版本的要求，不新增安装包发布或运行时机制。

### Issues

无存活问题，无新增问题。

### Recommendations

无新增建议。
