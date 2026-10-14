# feat-604 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`，独立于设计作者；skill：`change-design-reviewer`
- reviewer_target: `main db8a7321ad544660984b3bbef34e15374aeabc8d`，base `ee03471d6`
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖首文档、完整设计、原型、delta-spec、M1 骨架及证据。
- started_at: `2026-10-14T11:05:38+08:00`
- completed_at: `2026-10-14T11:13:11+08:00`
- duration: `PT7M33S`；计时从首次显式时钟记录开始，此前的 skill、spec 和原型预读未计入。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

页面的职责和主要阅读顺序成立：账号以身份和资料为先，团队资格与电脑管理不混入资料提交；策略先展示实际容量，再解释和维护尚未执行的预设。两处尚未收口的交互会使下游按原型实施后无法兑现手机操作与失败反馈，需修订后复审。

### Coverage 与证据

**独立体验观察。** 本轮先实际渲染并走查 [prototype.html](prototype.html)，再核作者的对齐表。观察了桌面账号与策略全页、390px 未加入团队账号、320px 待批准账号、管理员容量展开、普通成员只读预设；实际执行显示名编辑、模拟失败、取消失败模拟后重试，以及策略长表单编辑/失败/滚动。身份、分组标题、值与解释的关系可直接读懂，320px 内容改成自然单栏，成员行换行后仍能辨认名称、用量和状态。失败草稿确实保留；保存结果的可见性和手机保存条存在下列问题。作者的代表画面可复查于 [账号桌面](M1-settings/evidence/prototype-account-desktop.png)、[策略窄屏](M1-settings/evidence/prototype-policies-narrow.png) 和 [只读窄屏](M1-settings/evidence/prototype-readonly-narrow.png)；发现的交互由本轮直接操作取得，不能从这些静态正常画面推导通过。

**现有产品对照与证据边界。** 独立 Chrome 标签创建失败，未接管用户正在操作的标签，也未修改生产数据。随后在作者提供的隔离真实栈 `http://127.0.0.1:19765` 登录本次测试账号，独立查看 `/settings/account`、`/settings/nodes`、`/settings/policies`：账号重复 ID、电脑完整行和顶部孤立的设置链接；策略没有分组说明，容量在保存动作之后；电脑页已有返回、宽内容区、清楚的标题、青绿动作及较轻的表面层级。观察与冻结源码一致，支持本次沿用导航和视觉语言、改进内容职责的理由。这是冻结前端的隔离构建观察，不能证明线上部署版本。误抓的 `baseline-policies.png` 已由作者移除，本轮未将它当作策略基线；[walkthrough](M1-settings/evidence/design-walkthrough.md) 对其边界的说明有效。

**现状与组装入口。** 核对 `src/IM/frontend/src/app/router.tsx`、`app/shell/app-shell.tsx`、`app/shell/user-menu.tsx`、`features/me/me-page.tsx`、`features/settings/settings-page-shell.tsx` 及两页实现。路由实际组装现有 AccountPage/PoliciesPage，settings shell 透传；账号依赖 `/me` 和电脑详情查询，profile 更新会重置 draft；策略容量独立查询且只向管理员开启，普通成员当前使用禁用表单。设计对这些问题和改动落点的判断有依据。

**职责与复用。** 本地草稿、校验、反馈与响应式呈现应由两页持有；会话身份留在 AuthStore，服务数据留在 React Query，权限和字段验证继续由 IM 服务负责。复用 `getAccount/updateAccount`、`getPolicies/updatePolicies`、既有 membership/电脑/模型路由和 scoped CSS，足够承载当前变化；不引入全局草稿、设置框架或表单引擎，避免两页变化扩大全站维护范围。`AccountProfile.owned_node_ids` 已能提供数量，去掉账号页的电脑详情查询有直接依据。未发现扩展 DSH 或跨包依赖的设计。

**接口与权限。** 核对 `apps/im-server/src/identity-routes.ts`、`control.ts:902–936`、`media.ts:69–102` 以及实际消费者搜索。六项 policies 目前只存取 settings 表，执行模型属于 Agent/Node 设置，上传边界来自 media 的独立限制；“仅保存预设”不是虚构运行能力。管理员容量的 service/owners 读取与 policies PATCH 分开，非 active 资格、普通成员写权限和个人空间边界继续沿用现有服务。账号保存保留 locale/default_entry_node_id 并同步 AuthStore 的数据流闭合。

**需求、delta 与 milestone。** S1–S3 对应身份编辑、空间资格及电脑摘要，S4–S5 对应实际容量与只读预设，S6–S8 对应本地草稿和独立查询反馈，S9 对应中英文及桌面/手机体验；两项发现分别影响 S7/S9。delta 镜像正确 canonical target `docs/specs/im/auth-tenancy.md`，全部为新增消费者行为，没有用 ADDED 偷换现有 Requirement，也没有删除需保留的 Scenario。M1 单一交付范围无并行冲突；`M1-settings/.gitkeep` 存在，无预填 tasks/progress。三个 must-match 均投影到 reviewer 用户结果和 worker 原型对照/验证证据。

**验收前置。** 本次仅 IM 与 Vite，角色、容量 fixture、服务失败均可在临时数据库/进程中构造，不依赖 Gateway、LLM、外部账号或物理 iPhone；当前隔离栈已证明所需浏览器与基础服务可用。runbook 指定隔离端口、DB、随机 secret、进程记录及停启/健康入口，符合这两页的实际依赖。原型不接后端，真实持久化、权限、refetch 和服务失败仍须实施后验收。零电脑、容量满额/未知、加载错误、后台 refetch 和英文新布局仅有设计决定，未在本轮原型中实际触发，不能算已验证。

### 历史问题闭环

无历史 Round。

### Issues

#### R1-W1：保存失败反馈与当前提交位置脱离

- 位置：[design.md](design.md) 关键决策 4、原型对齐契约“编辑反馈与恢复”；[prototype.html](prototype.html) 第 18–19 行。
- 证据：320px 管理员策略页修改模型后，勾选“模拟保存失败”，滚动到末尾并保存。草稿保留，但错误只插入页面标题下面的 `#feedback`，保存区仍显示“有未保存的修改”。本轮实际画面中失败提示完全在屏外；只读 DOM 几何复核为 viewport 高 720px、提示 top 约 `-1191px`、保存按钮 top 约 `613px`。账号窄屏保存也复现同类位置脱离。
- 用户代价：用户已完成提交却无法从当前操作位置判断请求失败，必须自己回到页首寻找结果；辅助技术 alert 不能替代可见反馈。若按原型对齐，S7 的“失败可重试”和 must-match 的“保存结果可感知”只剩草稿保留。
- 所需收口：在设计与原型中明确保存区可见的失败/重试反馈关系，保留草稿且不依赖用户主动回到页首；在长策略表单的手机提交位置实际触发并观察。无需真实后端或新增全站通知机制。

#### R1-W2：手机原型未呈现承诺的滚动与保存条上下文

- 位置：[design.md](design.md) 关键决策 6、手机 must-match；[prototype.html](prototype.html) `.preview-mobile` / `.save` 与第 18 行的 shell 组装。
- 证据：320/390px 演示仍显示桌面顶栏“nano IM / 聊天 / 任务 / 智能体”，缺少实际 Web 手机端既有底栏。preview 容器仅约束宽度、`overflow:hidden`，随内容增长且没有受限高度的内容滚动区。本轮在 320px 策略表单滚动到运行预设时，保存按钮 top 约 `1333px`，高 720px 的当前视口内没有保存条。真实 `app-shell.tsx` 手机端隐藏桌面顶栏、保留四项底栏，`global.css` 为底栏保留 56px 与安全区；这正是设计承诺不覆盖的相邻区域。
- 用户代价：手机最重要的操作可达性目前只能靠一句“sticky bottom”推断，现有原型演示的是另一种滚动行为。实施者无法从 must-match 对照判断保存条何时可见、与真实底栏及剩余内容如何相处。
- 所需收口：保留现有移动导航的静态背景即可，但须在限高手机视口内表达正确的滚动区域与底栏关系，并实际滚动验证编辑、保存和末尾内容可达。无需重设计导航或实现其他页面。

### Recommendations

- **R1-R1（可选）**：容量明细可以补一句范围说明。当前 `media.ts` 汇总全服务占用，但 `owners` 仅返回权限允许的账号，明细之和不一定等于服务总量；原型的 6.5GB 与两位成员明细也不相等。标明这是“可见账号用量”，可减少管理员寻找差额的疑惑，无需扩大容量读取权限。
- **R1-R2（可选）**：`design.md` 的现状入口路径应写为实际的 `src/IM/frontend/src/app/shell/user-menu.tsx`；当前写成 `components/shell/user-menu.tsx`。这是引用修正，不改变本轮职责判断。

### Author Resolutions

- R1-W1 — accepted：失败与成功反馈移入保存条，输入后恢复未保存状态；design 决策 4 明确反馈必须与当前操作同时可见。320px 长策略页实际保存失败截图见 [手机保存失败](M1-settings/evidence/prototype-mobile-save-failure.png)，草稿/保存/失败/底栏在同一视口，无需返回页首。
- R1-W2 — accepted：手机原型改为限高 flex 容器、独立 main 滚动，隐藏桌面顶栏并保留现有四项底栏背景；在 320px 实际滚动、修改与提交，保存条位于内容区底部且不覆盖导航。design 决策 6 同步。
- R1-R1 — accepted：成员折叠区改为“可见账号用量”，说明权限范围内明细不一定等于全服务；不扩大数据读取。
- R1-R2 — accepted：user-menu 路径修正到 `app/shell/user-menu.tsx`。
- 补充基线：冻结 db8a7321a 的前端 git archive + npm 锁定依赖构建，本次测试管理员在隔离真栈看到的旧页见 [账号](M1-settings/evidence/baseline-account-isolated.png)、[策略](M1-settings/evidence/baseline-policies-isolated.png)。截图只包含本次专用测试数据，不是生产部署证据。

## Round 2

### Metadata

- reviewer: `/root/design_review`，沿用 R1 独立 reviewer；skill：`change-design-reviewer`
- reviewer_target: `main ef2304bbde34f79d2ceebf213cf3ba6e0288cfbc`；previous_target: `db8a7321ad544660984b3bbef34e15374aeabc8d`
- review_mode: `closure`
- mode_reason: 冻结差异限于 R1 两项反馈/手机上下文问题的修正、容量范围消歧、入口路径和证据补充；首文档、delta-spec、职责边界、共享接口与 M1 退出标准未变，无需扩大为新的 full review。
- started_at: `2026-10-14T11:16:32+08:00`
- completed_at: `2026-10-14T11:19:06+08:00`
- duration: `PT2M34S`
- retained_from: `Round 1`；需求覆盖、现状组装、接口与权限、架构复用、delta 归并目标和验收前置不受本轮差异影响，沿用 R1 的独立核查与隔离真栈观察。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1 两项问题均关闭。保存失败的说明与当前操作位于同一个可见保存条，手机原型也呈现了有界内容区与既有底栏的关系；本轮修订已足以指导实施。

### Coverage 与证据边界

本轮独立核对两个冻结版本间的完整 unit diff、R1 Author Resolutions、design 决策 3/4/6、原型 footer/submitDraft/main/shell、walkthrough 和三张新增截图。[手机保存失败](M1-settings/evidence/prototype-mobile-save-failure.png) 是 author 在 320px 限高容器中修改长策略表单并提交失败后取得的真实渲染画面；本 reviewer 独立查看像素，明确看到 `test-model` 草稿、红色失败说明、放弃/保存按钮与四项手机底栏同时在场，桌面顶栏已不在产品手机区域。图像证明这一失败状态与空间关系，不能单凭它推导完整滚动序列或失败后成功重试。

本轮子会话的旧 IAB、创建新 IAB、绑定主会话现存标签均报告浏览器不可用；未接管用户 Chrome，也未声称独立重新执行 R2 交互。闭环结论由本轮独立图像判断、冻结源码、明确设计约束和 author 的实际操作记录共同支持。R1 已独立执行的编辑/失败/重试及现有产品对照按上述 retained 范围保留；真实客户端持久化、权限、refetch、中英文及不同手机尺寸仍按 M1 退出标准独立验收。

新增 [账号隔离基线](M1-settings/evidence/baseline-account-isolated.png) 与 [策略隔离基线](M1-settings/evidence/baseline-policies-isolated.png) 的画面和本 reviewer 在 R1 直接查看的隔离旧页相符，替代了不可复查的会话截图引用；它们仍只证明本次专用测试构建，不能用于生产部署结论。

### 历史问题闭环

| ID | Author Resolution | 本轮核实证据与判断 | 状态 |
|---|---|---|---|
| R1-W1 | 失败与成功反馈移入保存条，输入后恢复未保存状态 | design 决策 4 明确反馈与当前操作同时可见；`submitDraft` 修改 footer 内的 `#status`，失败为 alert 且保留草稿/保存按钮；新增手机失败截图直接显示结果与操作同屏，不再依赖回页首 | closed |
| R1-W2 | 手机改为限高 flex 容器、main 独立滚动，保留既有底栏背景 | `.preview-mobile` 具有限高，main 为可收缩的 overflow-y:auto 区域，底栏 flex-shrink:0，保存条在该内容滚动区内；截图直接显示窄屏的失败保存条位于底栏上方。design 决策 6 同时约束末尾字段及导航不得被覆盖，给实施和真实产品验收留下明确判断依据 | closed |
| R1-R1 | 明细标为“可见账号用量”并说明不能与全服务直接求和 | design 决策 3 与原型折叠区文案同步；仅说明既有 service/owners 范围，不修改读取权限或接口 | closed |
| R1-R2 | 修正 user-menu 路径 | design 现状入口已改为 `app/shell/user-menu.tsx`，与 R1 核实的真实组装位置一致 | closed |

### Issues

无新增 CRITICAL / WARNING；无 still-open 历史问题。

### Recommendations

无新增建议。
