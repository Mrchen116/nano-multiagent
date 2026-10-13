# feat-588 M1 — 产品验收报告

> 对齐：[spec.md](../spec.md)、[design.md](../design.md) 与 `change-reviewer` 共同体验标准。
> Round: R1 · mode: full · 2026-10-13 11:48–12:17 Asia/Shanghai。
> Validation snapshot: `7083a0936a9ad6afa92fc2f5d7ac127ff8178d57 → eff9d6daf0b44cd6d1297e08500697e97561fa69`。

## Verdict

**fail**。1 个 major、0 个 blocking、0 个独立 minor；Highest Required Action：**fix-implementation**。R1-01 影响内置厂商身份、重启后一致性和再次添加服务的目录辨认。其余必验旅程已真实执行，不需要因这个集中问题重做全部旅程。

本报告判断的是固定版本的真实客户端与独立测试环境，不以 Gate 2 R4 的设计批准、作者的成功记录、API 200 或无溢出代替产品验收。主会话在本轮收尾时另行提交报告并开始小修，checkout HEAD 已前进；caller 确认运行产物仍为 `eff9d6daf`，没有重建/重启。这里不把新 HEAD 当成实际验过的版本。

## 环境与证据边界

- Worktree：`/Users/czj/.codex/worktrees/feat-588-model-services/nano-multiagent`，branch `codex/feat-588-model-services`。开工 HEAD 等于 validated_at；初始仅 `.runtime/`、`output/` 未跟踪内容，均保留。
- 专用 IM：`http://127.0.0.1:57165`；账号 `nano` / Test User；空电脑 `API Demo Mac`，node `wt-feat588-review-12696`。没有使用用户试用端口 52267、旧 fixture 18489/18490、生产或主仓运行环境。
- Runtime 根 `R = .dsh-runtime/feat588-review/`；浏览器/截图根 `E = output/playwright/review588/`。下文路径均相对本 worktree。截图、日志、配置不提交。
- API 18493/18494 严格校验本次测试凭据，并转发真实推理；DeepSeek 与其他模型名称是测试别名，实际上游为本机代理的 `codexOAuth:gpt-6-luna`，**没有宣称真人 DeepSeek 厂商推理或所有厂商认证均通过**。未读取/修改真实用户厂商凭据或 LLM_PROXY。
- 安装候选 manifest/归档固定为上述 SHA，由专用 IM 提供；精确 GitHub asset URL 在安装时经 caller 预置 curl shim 映射到本地候选字节。真实脚本、校验、依赖安装、Node setup、浏览器绑定、启动与重装均执行；**不是实际 GitHub Release 发布或匿名公网下载证据**。该边界与 design 的发布后验收安排一致。
- 初始 `/health` 可达而 Web 路由跳到未运行的前端端口。caller 为专用 runtime 挂载冻结 dist/trajectory 产物后恢复，没有重建 DB；这是验收环境准备问题，不计产品缺陷。
- 第二隔离 owner：`review588-other` / Review Other Owner，`u_143c6yy1`。仅用于无电脑状态和跨 owner 只读权限核对。

## 用户旅程体验

### 首次 API 接入 → 真实助手回复

从已绑定空电脑的 `/onboarding` 进入模型步骤，默认即内置提供商/API 表单；订阅登录位于下方折叠区，没有开发者代理发现结果抢占入口。目录实际显示约 40 个 provider。选择 `deepseek`，保留其默认协议，使用高级 URL override 指向 18493，选择测试支持的 `deepseek-chat`、显示名 `Daily Chat`，填写测试凭据并点击 Test and save。真实验证成功后 Continue 才可用。

继续创建 `Review Assistant`（`assistant-4123d88b`），模型明确显示 `Daily Chat · deepseek`，起步建议是草稿；改写并发送“17加26等于多少”，真实回复“17加26等于43”。会话 `c_j1jrvl3u`，没有把预置文案当回复。证据：`E/onboarding-390.png`、`E/first-real-reply.png`、`E/catalog-before-restart.yml`。

首次向导保留已有的步骤条和较大说明区，手机需要纵向阅读；模型连接主路径明确，表单和结果在同一位置。日常管理采用更紧凑的页面，避免把首次向导的较大介绍区带进高频设置。首次回复之后出现的上游后续步骤异常另见 Side Findings，不归因为连接验证或配置保存失败。

### 日常新增、多模型、同名模型和编辑

通过“Me → Model services”进入常驻页面；桌面用户菜单也有单行模型服务入口和独立图标。电脑名/在线状态在标题下同一上下文行，编辑时选择器禁用。添加 `Team API` 自定义 Chat Completions 服务：18493、`deepseek-chat` / `Daily Chat` 与 `nano-demo-model` / 长显示名。两个服务的同一上游 ID 并存，助手设置清楚列出 `Daily Chat · My preserved draft` 与 `Daily Chat · Team API`，可分别选中。

重新编辑已存服务时 API Key 为空、有“leave blank to keep”说明，非敏感字段保留，内置厂商只读。坏 key 验证失败、表单保留原草稿，原助手仍回复 19+28=47。清空 key、只改服务名可真实测试保存；更换到 18494 并轮换 key 后，同一助手在原会话回答 23+29=52。`R/api-fixture.log` 记录 `/v1/chat/completions`、真实 wire ID `deepseek-chat` 以及 18494/rotated 的调用，没有把 Nano 稳定引用误作 wire ID。

服务列表在 1440×1000、768×1024、390×844 实际看图：白底单层列表、名称最突出、厂商/模型次要、编辑与移除同行。两项服务、电脑和添加/订阅入口在手机首屏可辨认。长模型名换行，长服务名占两行但不挤压动作。表单桌面参数合理双列，手机一列；提交在自然末尾，不遮字段。证据：`E/list-1440.png`、`E/list-768.png`、`E/list-390.png`、`E/long-service-390.png`、`E/custom-editor-1440.png`、`E/editor-768-clean.png`、`E/editor-390-top.png`、`E/editor-390-bottom.png`、`E/desktop-menu.png`。

局部间距比原型稍宽，英语说明也更长，但当前页面的主次和操作成本合理。发现的身份问题不是风格偏好：内置 provider 标签会被服务自定义名称替代，见 R1-01。

### 失败、取消、两页冲突、离线与恢复

- 错误 key：测试失败提示紧贴提交区，原值/草稿可见、可重试；同一助手之后仍有真实回复。`E/bad-key-390.png`。
- 取消：使用延迟测试凭据开始验证，点击 Cancel verification 后显示“Verification cancelled without saving. Your draft is preserved for retry”，保留输入，不假报保存。`E/cancelled-390.png`。
- 两页冲突：A 页打开旧版本并写 `My preserved draft`；B 页成功保存 `Latest page B`；A 页提交被拒，草稿没有覆盖最新配置。Compare latest configuration 显示两边服务名、URL、模型；只有显式 Reapply my changes after review 后才能再次保存。`E/conflict-390.png`，03:59–04:05 UTC 浏览器快照可追踪前后状态。
- 离线：编辑草稿改为 `Offline retained draft`，仅对专用 `.gateway-config.yaml` 执行 Node stop。UI 显示 Offline、Computer unavailable、Check connection again 和 Connection guide，保存禁用且表单仍保留。再 start 同一 config，恢复 Online 后要求 Compare latest configuration；没有悄悄替换草稿。选择 Use computer configuration 后回到电脑已保存值。
- 刷新/重启：服务名、URL、模型、凭据可用性、助手 stable ID 和已选模型保持；重启后的原助手继续得到真实回复，未重新创建。厂商显示名发生漂移，因此 S8 的身份一致性部分失败。`E/offline-draft-390.png`、`E/provider-label-after-restart.yml`、`E/list-after-restart.yml`。

恢复操作能表达“哪个值已保存、哪个只是草稿”，用户无需阅读日志。错误、冲突提示使用了两段有重复含义的说明，但操作仍可理解，不另报风格问题。

### 删除依赖与继续使用

先尝试移除在用内置服务，确认后明确列出 `Review Assistant` 和直达助手设置链接，服务没有消失。将助手主模型改为 `Team API`、把旧服务模型设为 fallback 后再次删除，仍被依赖检查拒绝。移除 fallback 并保存助手后，原确认操作可成功移除服务；另一个服务不受影响。同一助手、同一聊天回复 31+42=73。

编辑 Team API 去掉仍作主模型的 `deepseek-chat` 也被明确依赖拒绝；取消草稿、改为去掉闲置 `nano-demo-model`，真实验证后成功保存。证据：`E/dependency-block-390.png`、`E/fallback-dependency-1440.png`、`E/model-dependency.png`、`E/replies-after-rotation-and-migration.png`。

### 订阅授权、电脑归属与安装

展开 Codex 次要区并启动授权，真实获得 device code、Open authorization page 与 Cancel verification；三宽度实际截图均显示它局限于下方授权区，没有扩散成全页横幅。随后取消，没有真人登录/订阅授权，也没有改 API credential。证据：`E/oauth-1440.png`、`E/oauth-768.png`、`E/oauth-390.png`。

第二 owner 的模型页只显示 Connect a computer first 与连接入口，不显示 Test User 的两台电脑。使用该浏览器真实请求携带的当前身份，对已知 node 的 setup(status) 做辅助只读请求，返回 404 `node_id not found`。未用无效 token 的 401 充当跨 owner 验收证据。证据：`E/other-owner-empty.png`、`E/no-computer-390.png`。

从 57165 获取实际 `/install.sh` 并在指定 install root 执行，manifest 固定 `eff9d6daf…`、SHA-256 `76f184bba686ea13f86e2cfa6ab405d15ff8862b23b20411fa7b264b8e54452d`，URL 为固定 tag asset。旧 `/install/nano-node.tgz` 实测 302 + no-store，Location 同一固定 URL，无包体。脚本经真实校验和依赖安装后出现当前 IM 的绑定链接，浏览器确认 Test User 后生成 `computer-2603ac39` 并启动 Node；autostart disabled。重新运行提示 already connected，配置 SHA-256 完全不变。

下载失败与错误 hash 均退出码 1、明确提示重试；没有选择 latest 或转经 IM 包体。另在已真实安装的 root 暂时移开缓存 `.installed` 标记以强制执行下载分支，分别注入下载失败/损坏字节，配置、安装 CLI、package.json 哈希前后相同，随后恢复标记。证据：`R/reviewer-install.log`、`R/reviewer-reinstall.log`、`R/config-before-reinstall.sha`、`R/reviewer-existing-install-negative.json`、`R/reviewer-corrupt-existing.log`、`R/reviewer-download-existing.log`、`R/release-downloads.log`。真实匿名 GitHub 下载仍是正式发布后的独立工作，不属于本轮完成声明。

## Reference Artifacts Reviewed

实际渲染并查看 `prototype.html` 的列表和编辑区，证据 `E/reference-prototype-390.png`、`E/reference-editor-390.png`；设计文字与 must-match 契约均已阅读，没有引用作者走查结论代替当前判断。

| Reference / required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|
| design 原型契约第 1 行：紧凑电脑上下文；服务名称主层、类型/模型次层；无大卡套列表；手机同行动作 | list-1440 / list-768 / list-390 / long-service-390；offline-draft-390；no-computer-390 | 1440/768/390，多服务、长名称、离线、无电脑 | 布局与主次 match；R1-01 导致重启后厂商身份 deviation |
| 第 2 行：单一编辑区、紧凑方式切换、连接/模型分组、自然末尾提交、key 留空保留、已有厂商只读 | custom-editor-1440 / editor-768-clean / editor-390-top / editor-390-bottom；catalog-before-restart.yml | 三宽度，内置/自定义、多模型、空 key、长名称 | 交互与组织 match；只读 Provider 的值受 R1-01 影响 |
| 第 3 行：API 反馈贴近表单；Codex 授权局限其连接区；草稿恢复可辨认 | bad-key-390 / conflict-390 / cancelled-390；oauth-1440 / oauth-768 / oauth-390 | 错误、冲突、取消、授权码等待 | match；实际完成取消/对账，首次仅测试成功后可 Continue |
| may-adapt：控件与局部间距，保持可读性 | 同上 | 桌面/手机、英文现有语言 | 可接受；未用极小字体换取首屏密度 |
| out-of-scope：演示控制、固定背景 | prototype 与真实客户端对照 | 全旅程 | 真实页面没有演示开关；使用真实账号/电脑/导航 |

## 问题清单

| ID | Severity | Regression Relation | 期望 / 实际 / 用户代价 | Recommended Action / Rationale |
|---|---|---|---|---|
| R1-01 | major | direct | 内置厂商身份应独立于用户自定义服务名且重启稳定。DeepSeek 服务依次改名后，重启 Node，列表次行和只读 Provider 都变为 `My preserved draft`。删除该服务再点 Add service，内置目录依然只有 `My preserved draft` 而不再显示 `deepseek`；选择后带出 DeepSeek 模型，证明只是厂商标签失真。用户无法按厂商名称辨认/重新添加服务，影响 S3/S8 和身份 must-match。 | fix-implementation：保持产品服务名可编辑，但内置厂商名称不受该名覆盖。集中修复同一身份来源；复验改名→刷新→Node 冷启动→列表/编辑/再次添加目录，以及原助手一次真实回复。 |

R1-01 复现顺序与证据：

1. 11:56:43 本地（03:56:43 UTC）首次选择内置 `deepseek`，只读/目录基准为 `E/catalog-before-restart.yml`；正常列表见 `E/list-1440.png`。
2. 空 key 改名 `DeepSeek Daily`，轮换 URL/key 后仍可用；双页冲突恢复最终保存 `My preserved draft`。
3. 12:05–12:06 仅停止/启动专用 review Node；编辑草稿仍保留。12:06:40 快照 `E/provider-label-after-restart.yml` 中 Provider 选项已是 `My preserved draft`；12:08:55 `E/list-after-restart.yml` 列表两行重复此名称。
4. 12:09:35 移除依赖后删除该服务。12:15–12:16 再 Add service，目录仍被旧自定义名替代。`E/catalog-provider-after-restart.txt` 与实际看图 `E/catalog-provider-corrupted-1440.png` 直接体现影响，不依赖实现推断。

本轮未改源码、测试、设计或受版本控制配置，没有新派 worker。主会话已另行定位并准备修复，不计作本轮受验版本已修好。

## Side Findings / 执行异常

首次与第二次真实回复后，刷新聊天看到用户消息 `failed`，答复气泡同时存在。独立 UI/API 观察：

| 用户消息 ID / 创建 UTC | 内容 / 对应回复 ID | 刷新后的实际状态 |
|---|---|---|
| `be5944a112d64d3d93c812c0f44dd500` / 03:58:03.692 | 17+26；回复 `cb5edbfe049c45a18cb2546252405547` / 03:58:22.522，内容 43 | user failed，agent completed |
| `4da247c41a9e4a09864a80a6f2333de8` / 04:01:08.553 | 19+28；回复 `6889069aa6e94833887ff5910fcf4eb2` / 04:01:39.494，内容 47 | user failed，agent completed |
| `baf5877670614df286a98d9e1433591f` / 04:02:43.967 | 23+29；回复 `472d57bf3ce141f595516a9854ac1fbf`，内容 52 | user/agent completed |
| `b8f29508c52949848188088ee3327195` / 04:10:08.180 | 31+42；回复 `53ceff62a89b4e4dbdc5a15011785e36`，内容 73 | user/agent completed |

首次完整刷新核对 12:12:25 本地，补充截图约 12:13。会话均为 `c_j1jrvl3u`；证据 `E/messages-after-refresh.txt`、`E/false-failed-after-refresh.png`。后续 41+52=93 的真实回复后再保存长服务名并刷新，消息保持正常，未重现普遍“保存后变 failed”。

**原因证据来自 caller 的只读运行事件核对，非 reviewer 读取实现所得**：DSH session `2734d082-ccdb-4727-a96c-0a9e9201bd8f` turn 1 在 03:59:01.874、turn 2 在 04:02:23.192 的 turn/end 为 error，错误是上游 502 `upstream_empty_stream`，发生在答复已发送后的后续模型步骤；turn 3/4/5 为 completed。故不能称为“已完成 run 被配置保存改坏”，也不能把这次上游错误作为凭据/URL 轮换失败。保留这个易困惑的用户现象与现场，未扩大为本 unit 的第二个实现缺陷。

## 验收标准覆盖

### 首次接入优先呈现普通 API 用户的路径 — pass

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S1 没有本机代理的新用户 | spec S1；design B | 默认 API 表单→真实测试→创建→聊天；onboarding-390、first-real-reply、消息 ID 如上 | pass | 实際收到真实回答；后续 upstream 502 已单列，不冒称整段执行从未出错 |

### 常驻入口支持管理电脑上的模型服务 — fail

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S2 已完成首次设置后再次管理 | spec S2；design A | Me/桌面菜单→模型页；电脑选择/离线恢复；第二 owner 无电脑+跨 owner 404；desktop-menu、no-computer-390、offline-draft-390 | pass | 入口可达，不用重做安装/助手；不误报离线为空配置 |
| S3 使用内置服务商目录 | spec S3；design B | 真实动态目录、DeepSeek 默认协议+高级 URL 实际调用；改名重启删除后再打开目录；catalog-before-restart 与 catalog-provider-corrupted-1440 | fail | 首次连接成功；R1-01 使后续目录厂商不可辨认 |
| S4 添加自定义服务及模型 | spec S4；design B | 自定义多模型真实测试、同 wire ID 分服务、助手菜单分开选择；custom-editor-1440、list-*、迁移后真实73回复 | pass | 协议/地址/key/model 均真实填写；不同服务未覆盖 |

### 编辑可恢复且不意外破坏现有助手 — fail

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S5 编辑已有服务 | spec S5；design B | 空 key 保留、改名、18493→18494+key轮换、同助手52回复；api-fixture.log、replies-after-rotation-and-migration | pass | 凭据不回显；stable引用/助手/会话不重建 |
| S6 保存失败与并发修改 | spec S6；design C | 坏key、慢测试取消、两页冲突、专用节点离线/恢复与草稿对账；bad-key-390、cancelled-390、conflict-390、offline-draft-390 | pass | 失败未替代旧连接；旧页须显式对账才可保存 |
| S7 移除服务或模型 | spec S7；design C | 主/备用服务依赖、在用单模型拒删、迁移后服务可删、闲置模型可删；dependency-block、fallback-dependency、model-dependency | pass | 明确助手依赖与链接；另一服务和原助手继续可用 |
| S8 持久与界面一致性 | spec S8；design A/B | 刷新/Node重启，配置/模型/助手选择保留；三宽度实看和真实手机操作；list/editor/oauth三宽度、provider-label-after-restart | fail | 核心持久和布局通过；R1-01 违反重启前后厂商身份一致性 |

### 安装入口与程序包分发分开，保持版本配套 — pass

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S9 从当前 IM 安装配套电脑端 | spec S9；design 安装分发/F | 固定 manifest、302旧路径、真实脚本安装/绑定/启动/重装、下载/哈希失败保留现有安装；reviewer-install/reinstall、existing-install-negative、release-downloads | pass | 按明确允许的运输 fixture 验收安装生命周期；匿名 GitHub 公网下载未执行，不视为已发布 |

M1 reviewer A/B 受 R1-01 阻塞，C/F 通过。worker D/E/G 的实现层测试、独立代码审查、CI 不由本报告替代。未出现需要把必验项标成 not-applicable 或以缺证据降级通过的情况。

## 上层文档同步

- [x] `SPEC.md`：无需由本次产品 reviewer 更新；跨包责任边界未在本轮验收中发现新增决定。
- [x] `docs/specs/im/agents-nodes.md`、`docs/specs/gateway/agent-capabilities.md`：需在 unit 收尾由 orchestrator 根据最终实现归并本 unit delta。当前已读 canonical 仍描述前置 onboarding，不能用 active design 冒充 current。
- [x] 安装操作说明/正式发布证据：需在正式发布部署阶段补匿名下载与对应 manifest 提升记录；本轮不发布、不部署。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 现场保留与复验交接

caller 要求保留现场供统一修复核对：专用 IM、review Node、安装 Node `computer-2603ac39`、安装目录、数据库、截图和运行日志全部保留，不调用 e2e-down，不动模型 fixture。review Node 的重启由原 PID 13085 切到 PID 25496；安装 Node 本轮启动时 PID 23222。临时原型 HTTP 57169 和仅本轮创建的浏览器可关闭。

R2 建议仅覆盖 R1-01：同一内置服务自定义改名→刷新→专用 Node 冷启动，核对列表厂商、只读 Provider、新增目录均仍为真实厂商；确认服务自定义名、URL/key/模型/助手引用保持，再用原助手真实发一轮。保留 R1 其他完整旅程，不扩大为重复全量验收。
