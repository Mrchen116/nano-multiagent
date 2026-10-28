# bugfix-674 — 回归验证

> 对齐：incident.md；Round 1；mode=full；2026-10-28。
> Validation snapshot：`ff326c351d104447028f4b185740ab6d6be55de6 → 28b205259d60017679f2844d1fa5280c3ebc8802`。

## Verdict

**pass**。本 unit 受影响的 Web 统计阅读与真实调用旅程可交付，blocking/major/minor 均为 0。Highest Required Action：pass；无需产品复验。

独立 reviewer 使用真实浏览器新建后台 tab，从 Agents 进入 P 的 Skills，完成列表、活动、Q 空态和 390×844 横滚操作；随后通过 Config 切换本机 fixture 提供者并关闭 Skill Creation、Memory Curation，经 Open chat 发出一次隔离指令，返回 Skills 观察计数增加。没有外发、调用真实模型、访问生产或修改实现。

## 验证现场与边界

- 分支：`codex/bugfix-674-skill-usage-statistics`；worktree 为本 unit worktree；daily IM：`http://127.0.0.1:53171`；节点 `wt-nano-multiagent-67359`；专用身份 Test User / nano。
- `.e2e-daily.json` 与页面核对：P/E/Q、PA、研发日常群均存在；模型及审核基线由 daily 配置提供。本轮没有把模板 ready 等同于功能通过。
- caller 交接服务由 `28b205259` 对应实现构建，Vite 提供同树前端。本轮期间 HEAD 更新至 `83fda25a3736983bf7a3882038c534f5ee001a51`；独立核对两者 diff 只包含 E2E fixture 与文档/验证记录，没有产品源码变化，产品结论仍绑定上述 validated_at。
- 实测 viewport：桌面 1280×720、窄屏 390×844。测试后恢复默认 viewport；未停止 caller 的服务。
- 临时增量：P 已有 usage-audit 新统计累计 75、窗口 1、起点 2026-09-01，以及 legacy-only 旧记录；Q 无统计。reviewer 通过产品保存 P profile v2：Default Model=fixture，Skill Creation=false，Memory Curation=false；fixture 仅访问 caller 提供的本机确定性服务。创建隔离私聊 `c_cnpcqmbr`，发出一次调用指令；保留该测试状态供 caller 清理。
- iOS 按 design 的 may-adapt 范围复用编译、统计契约与专用模拟器测试，不宣称 native 界面体验已实玩。跨 Agent、重启、去重、日桶清理、起点前未知和缓存兼容复用最低层回归，不通过批量产品消息重复验证。

## 复现验证与场景覆盖

修前复现来源为 incident：本地 61 次累计但趋势仅 60，共享累计随样本截断；修前红测还观察到旧 999 被当作新统计。修后实际产品列表 75 与窗口 1 分开，追加一次真实 skill 调用后为 76 与 2；旧记录仍为 0 / No new calls yet。

| 来源 / 必验结果 | 实际证据 | 结果 |
|---|---|---|
| incident：关闭自进化仍计数，超过 60 次不丢累计 | 真实 Config 中 fixture 被选中、两维护开关关闭、保存后 profile v2 / No changes；Open chat 发一次指令后 usage-audit 75→76，活动 1→2。规模/重开/去重复用 knowledge 10 tests | pass |
| incident：共享 Skill 按 Agent 独立，样本淘汰不丢统计 | 复用 validation 中 75/65 跨 Agent、较早 Agent 引用淘汰后累计仍保留和 unused 不冒充已使用的回归 | pass |
| incident：旧记录未新调用时不补回旧数 | 桌面及窄屏列表 legacy-only 名称下显示 No new calls yet，USES=0，LAST USED=Never，趋势显示 No new calls yet；调用 usage-audit 后仍保持该状态 | pass |
| incident：首次新统计起点与累计清楚 | usage-audit 名称下 Statistics since 2026-09-01 (UTC)，USES 75→76；活动有同一起点和 total new calls 标签 | pass |
| incident / design：真实 UTC 30 天窗口，不伪装全年历史 | 列表 TREND · 30 DAYS (UTC)；活动范围 2026-09-29—2026-10-28 · UTC，30 个日期格，窗口标签 last 30 days (UTC)，累计 75/76 与窗口 1/2 可区分 | pass |
| design：起点前不标为 0 | 复用 Web 固定 UTC 日期回归（起点前 28 格未纳入，后 2 格已统计）及 iOS 日期过滤契约；真实活动图独立看到 Not included in statistics 图例。本轮 P 起点早于窗口，不将它冒充起点前格的实测 | pass |
| incident / design：窄屏列表及空态可读 | 390×844 初始可读名称、起点、来源、状态、次数；在表格上实际横滚后最近使用和趋势可读，导航及页头保持原位；Q 显示 No skill usage yet；legacy 行显示局部空态 | pass |
| design：热力图周/星期关系、30 格和图例完整 | 桌面及390px截图观察星期 Mon/Wed/Fri、周列、30日格、UTC日期、累计/窗口和未纳入/强度图例，均可辨认 | pass |
| design：两公开入口与旧缓存/在线旧形状隔离 | 复用 IM settings 20 tests：两入口公开投影、无其他 Agent 聚合泄漏、新缓存离线可读、旧缓存及在线旧形状拒绝 | pass |
| design：日桶清理、维护行为与 iOS 数据契约 | 复用 knowledge + knowledge-review 10 tests，跨30日清理保持累计/其他Agent、F4等；iOS专用模拟器26 tests / 5 suites通过且归档成功 | pass |

## 整体体验与原型对照

Reference Artifacts Reviewed：incident.md、design.md、prototype-desktop.png、prototype-mobile.png、共同体验标准、current IM Skill 统计 API，以及 M1-statistics/evidence/validation.md 的构建/测试记录。

实际页面沿用 Agent 详情的侧栏、一级 Skills 与 Skill list / Agent activity 二级切换。列表六列在桌面同时可读；起点位于名称下方，直接说明这行数字的时间含义。旧记录不画假趋势，空态文案和 0 与新统计行形成清楚对照。活动页把累计放在图上方、窗口合计放在图下方，并各有标签，用户无需把图中的总量误认为全历史。原型并排展示的列表/活动/空态在真实页通过已有导航切换，未改变 must-match 语义。

390px 沿用设计指定的表内横滚：初始视图保留名称、起点及次数，向右滚动后查看最近使用与趋势，页面其余部分不横移。活动图窄屏保留星期/周列、UTC范围和完整图例；Q 的整页空态及 legacy-only 的行内空态均可读。对照原型，没有发现妨碍阅读、比较或返回的本次变化；月份短标签紧邻不影响明确日期范围，无需扩展本次设计。

本地关键画面（均由 reviewer 本轮浏览器生成；属于本机证据，不将链接当作 PR 远端附件）：

- `/tmp/bugfix-674-product-review/desktop-list.png`、`desktop-activity.png`、`desktop-empty.png`
- `/tmp/bugfix-674-product-review/mobile-list.png`、`mobile-list-scrolled.png`、`mobile-activity.png`、`mobile-empty.png`
- `/tmp/bugfix-674-product-review/config-after.txt`：保存后的 fixture、关闭开关与 profile v2。
- `/tmp/bugfix-674-product-review/after-call-list.png`、`after-call-activity.png`、`after-call-activity.txt`：真实调用后76累计/2窗口。

## 自动化证据复用

未新增或重跑重复测试。独立读取了 `/tmp/skill674-knowledge.log`（2 files / 10 tests）、`/tmp/skill674-web-bounded.log`（108 files / 1029 tests）、`/tmp/skill674-ios-isolated.log`（26 tests / 5 suites，TEST SUCCEEDED）与 `/tmp/skill674-ios-archive.log`（ARCHIVE SUCCEEDED）的实际结果。IM 20 tests 与窄 Web 27 tests 依据 M1 已有执行记录复用。初次 daily seed 的 config_apply_pending 记录是环境准备历史；本轮真实阵容、在线详情和计数链已实际可用，不把它记作产品缺陷。

## Issues

无。没有将观测工具选择器差异或确定性 fixture 不发送公开回复归为统计产品缺陷；关键结果通过真实统计入口验证。

## 上层文档同步

- [x] `SPEC.md`：无需更新，未改变跨包顶点架构。
- [x] `docs/specs/im/agents-nodes.md`：需要由主流程归并 unit delta，写入新统计/日期窗口/旧口径隔离的 current 契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

报告由 reviewer 写入，按 caller 指令不提交；未修改源码、测试、设计或停止共享隔离服务。
