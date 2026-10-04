# bugfix-577 — 回归验证

> 对齐：[incident.md](../incident.md)、[design.md](../design.md)
>
> Validation snapshot: `1daf6676debe129088d9bd0612b489d1eba0301a → e6b202cb87c4deb4e9f9763d5c78e59d28576dba`

## Round 1 — 2026-10-05

- mode: full；revalidation_mode: full；review_round: 1。
- 独立 reviewer：review_577_product。只写本报告，未修改实现、测试、配置，按 caller 指示不提交。
- HEAD 已实读等于 validated_at。开始时仅 caller progress/code-review 与隔离 runtime 为 dirty/untracked；没有用 caller 成功叙述代替产品判断。
- 真机：iPhone 15 Pro Max / iOS 26.4，经 iPhone Mirroring；截图画布 696×1532。手机截图状态栏时间 00:20–00:29。
- 主屏/Safari：`https://jmacbook-air.tailbf614e.ts.net:8443/`，独立账号 nano；从未登录 `/login` 安装 `577 HTTPS`，Open as Web App 开启。未触碰生产 `IM Frontend` 图标。
- 独立 HTTP 读取入口确认 assets 为 `index-BQ9vVzWe.js` / `index-C57yOulR.css`，与 caller 冻结构建交接一致。桌面用 caller 允许的 `http://127.0.0.1:18779/` Vite 入口，同一冻结源码及隔离 IM；它不是手机 HTTPS 构建 URL。
- Reference Artifacts Reviewed：incident、design（含原型对齐契约/runbook）、prototype.html 真实渲染、current `web-chat-ux.md`、`auth-tenancy.md`、`task-graphs.md`、worktree-runtime。

## Verdict

**fail**。Highest Required Action：**fix-implementation**。1 个 major 产品问题，1 个 blocking 验收证据缺口；needs_re_review=true。未创建外部 GitHub issue。

主屏登录后的四入口导航、无浏览器栏、登录/搜索输入宽度、未聚焦聊天布局均改善且实际可用。但主屏聊天 composer 聚焦后，详情标题/返回上移并进入系统状态栏区域，违反 R3 / 原型 must-match。真实软件键盘及手动缩放尚未验证，不能把镜像硬件辅助条或桌面尺寸测试作为替代。

## 复现验证

### I1 — 主屏聊天聚焦后标题与返回进入状态栏

- Severity：major；Regression Relation：direct（直接命中本 unit 用户结果，未据此声称实现因果）。
- Recommended Action：fix-implementation。
- Action Rationale：design must-match 要求详情返回、输入及发送完整；输入期间的顶部关键操作仍被系统安全区侵入。
- 期望：聚焦消息输入后，详情标题和返回留在状态栏以下；用户可继续输入、发送或返回。
- 实际：未聚焦时返回约在截图 y=217、e2e 标题 y=205；聚焦底部 composer 并粘贴两行文字后，返回约 y=110、标题约 y=99，时间/状态图标与标题区域重叠。右侧发送按钮和两行文字完整，无全局底栏。不是 Safari 地址栏重新出现，也没有观察到横向放大。
- 精确复现：未登录 Safari HTTPS `/login` → 分享/添加主屏 `577 HTTPS`（Open as Web App）→ 主屏图标启动 → nano 登录 → Chat → e2e → 点击底部 Message e2e 输入框 → 粘贴 `577 review draft 一行\n第二行 retained`。
- 直接证据：本 reviewer CUA 截图，00:26「Verify composer focus and multiline draft」：标题在灵动岛/时间同一顶部区域；此前「Open chat detail after input」：header 正常。随后「Inspect layout after ending composer input」：点击硬件输入辅助条 Done 后恢复正常 header 和高度，草稿不丢。
- 该现象只以硬件焦点/浏览器自动滚动下的实见结果报告；未测真实软件键盘，不推导其表现或定位根因。已立即交给 caller，未自行 debug/修复。

### I2 — 必验真机输入/缩放证据未收口

- Severity：blocking；Regression Relation：unclear（验收缺口，不是已证明的产品缺陷）。
- Recommended Action：fix-implementation（先解决 I1，再补齐同版本真实设备验收；不要求为工具缺口修改产品）。
- Action Rationale：incident 与 design 明确禁止用镜像硬件输入代替软键盘；必验项 inconclusive 即不能 pass。
- 实际：镜像只有硬件输入辅助条；`pressKey("Eject")` 返回 keyNotFound，没有产生软件键盘。caller 在收到 I1 后明确暂不安排用户实体手机测试，避免让用户验收已知失败构建。正常手势缩放也未取得真机证据。
- 后续：修正后在同一设备完成软件键盘输入/发送/收起/滚动及正常手动放大恢复；主屏详情真正刷新、mention 高亮和群设置跨页也需补齐。

## 回归测试

| 来源 / Scenario | 实际旅程与证据 | 结果 |
|---|---|---|
| R1 登录、搜索与聊天聚焦后保持完整布局 | 主屏用户名 nano、密码输入；Chat 搜索 e2e、Find Agent 搜索 e2e；登录/搜索焦点前后右边界完整，主屏两行 composer 与发送按钮完整。截图00:22–00:26。聊天顶部另见 I1。 | fail（聊天顶部）；登录/搜索宽度子项 pass |
| R1 手动放大与 mention 镜像 | 未进行真机 pinch；单聊未建立 mention token，普通两行文字渲染正常不能证明高亮对齐。 | inconclusive |
| R1 输入后跨页继续使用 | Agent搜索→e2e Config→Overview→Chat，宽度正常；Overview为既有占位，未误认新增工作能力。未进入群设置及真实工作详情。 | 已覆盖子项 pass；完整项 inconclusive |
| R2 从未登录安装进入完整应用 | 独立安装577 HTTPS→登录→Chat→Tasks（空任务态）→Agents→Me→Agent详情→Chat详情；全部入口可点击，主屏无Safari域名/工具栏，安全区下方四tab完整。截图00:21–00:26。 | pass（未聚焦状态） |
| R2 已登录再次启动与刷新 | Home→Spotlight→577 HTTPS图标重新打开，保持登录和聊天详情，真实回复可见。主屏Cmd+R无可观察加载，不宣称已刷新。Safari点击系统刷新有空加载→详情恢复→返回列表成功。 | 重启 pass；主屏详情刷新 inconclusive |
| R3 软件键盘弹出/收起 | 未出现软件键盘，Eject不受支持，caller暂缓用户物理测试。硬件焦点出现I1；Done恢复。 | inconclusive（软件键盘）；硬件焦点 fail |
| R3 草稿与发送 | 两行草稿→Done→返回列表→重进e2e，文本完整；点击可见发送按钮后输入清空，00:27收到真实Agent回复；详情无全局tab。 | pass |
| R4 普通Safari浏览器栏 | HTTPS私密Safari独立登录，登录字段/列表/聊天边界完整；composer输入Safari 577 draft及Done后发送可见；系统刷新→详情→返回成功，四tab在系统底栏以上。截图00:28–00:29。未独立穷举手动收起系统栏状态。 | 已覆盖子项 pass；完整状态矩阵 inconclusive |
| R4 桌面原有布局、草稿、收发 | 1440×900双栏，输入desktop 577 unsent→Tasks→Chat→e2e草稿恢复；发送577 desktop check. Please reply only OK.并收到OK。 | pass |
| R4 375/430/600真实浏览器 | 375×812与430×932聊天返回/输入/发送及四tab完整；375/430/600登录和注册表单真实输入/滚动聚焦，提交按钮可达，未提交注册。600×960最终稳定截图无裁切。 | pass（布局辅助证据） |

## 原型 must-match 对照

原型与产品均由 reviewer 使用真实 IAB 渲染，而非DOM存在推论。原型 URL `http://127.0.0.1:18778/prototype.html`；外层尺寸 1440×900、375×812、430×932、600×960，查看短可用区域及键盘占位+两行草稿状态。原型长页全页截图记录在本轮 CUA 输出；手机图片亦在同轮直接截图输出中，未提交截图缓存。

| 区域 / 状态 | 原型与产品对照 | 结论 |
|---|---|---|
| 登录/注册输入及提交可达，375/430/600 | 原型短区域登录下半部需滚动；实际登录字段/提交在完整卡片内，注册375聚焦密码后页面滚动且Create account可见，430/600亦完整。沿用teal操作与卡片层级。 | match |
| 列表四入口与安全区，375/430/iPhone | 原型四tab底部保留；产品375/430及真机主屏/Safari四入口均可见且实际切换。 | match（已覆盖状态） |
| 详情返回/输入发送、键盘开关、375/430 | 原型键盘占位时返回仍在内容头部；375/430桌面产品返回/发送完整，无全局tab。真机主屏硬件焦点返回侵入状态栏，真实软键盘未测。 | **mismatch / inconclusive**，I1/I2 |
| 1440桌面与样例差异 | 原型三列为外层演示；产品维持真实桌面sidebar/chat及顶部导航，发送和草稿通过。样例文本、外层控件不要求进入产品。 | match（may-adapt / out-of-scope正确区分） |

## 自动化测试增量

本 reviewer 未改测试、未运行源码定位或重跑 worker 自动化；产品结论只来自上述真实客户端。自动化增量与执行结果由 implementation/code-review 证据负责，不能代替此报告的实机未通过项。

## 上层文档同步

- [x] `SPEC.md`：无需更新；没有改变跨包边界。
- [x] `docs/specs/im/web-chat-ux.md`：需要在最终回归通过后由 orchestrator 归并本 unit delta；本轮 fail，不提前宣称目标已成为 current。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 清理与交接

没有启动/停止任何服务，caller继续拥有IM/Gateway/HTTPS生命周期。00:29手机停在Safari HTTPS Chat列表并明确交还caller，之后未再操作手机。桌面临时viewport已reset，正常产品/原型临时tabs已关闭；最初HTTPS失败生成的data错误页被浏览器URL policy阻止close，已如实告知caller。577 HTTPS测试图标保留用于修复复验，未动生产图标。报告未提交，report_commit=none。

## Round 2 — 2026-10-05（定向复验，实体操作待补）

- mode: full；revalidation_mode: targeted；review_round: 2。
- executed_base: `1daf6676debe129088d9bd0612b489d1eba0301a`；validated_at: `bd170820be5f17f17093189d36290c377b0463ff`。
- delta: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba..bd170820be5f17f17093189d36290c377b0463ff`。已实读 HEAD；读取 design 的 R2 offsetTop/relative top 补偿契约后再操作，未自行定位源码或修复。
- 相同手机/隔离账号/HTTPS 入口，主屏 `577 HTTPS`；实读 HTML assets `index-B4S4bvwT.js` / `index-D5kI87rP.css`。真机截图时间00:41–00:47。本轮继承 Round 1 未受该定向修复影响的桌面、375/430/600与原型证据，没有把旧截图冒充新构建验证。

### 当前结论

**fail（仅剩 mandatory evidence inconclusive，尚非最终复验通过）**；needs_re_review=true。I1 已关闭，I2 尚未关闭。Highest Required Action：补齐同一构建实体软件键盘和手动缩放验收；该动作是证据补齐，不要求针对工具限制修改实现。

| 复验项 | 直接观察 | 结果 |
|---|---|---|
| I1 原路径：主屏详情 composer 聚焦 | 聚焦并输入 `577 R2 draft 第一行` 与第二行 `第二行 retained` 后，header/返回保持状态栏下方约 y=217，发送与两行输入完整。聚焦中点击 Back 成功，重进详情两行草稿仍在。 | pass；I1 resolved |
| Safari 同路径/刷新 | 系统刷新后详情恢复；两行草稿输入、结束输入前后 header 和发送均完整，没有观察到整体横向放大。 | pass（硬件输入状态） |
| 主屏真正冷启动 | App switcher 上划关闭 577 HTTPS 卡片，确认消失；Home/Spotlight 重新启动图标进入已登录 Chat，四入口完整、无浏览器栏。 | pass（真实冷启动；未声称 Cmd+R 生效） |
| 群聊 mention 与跨页 | caller 在隔离 IM 准备的 `577 viewport group` 中输入 `@`，可见候选并选择 e2e，蓝色 `@e2e` token 与输入行对齐。打开 Group settings、返回仍保留 token；打开 Tasks 空态并关闭，同样恢复 token，header/发送安全。 | pass |
| 软件键盘弹出、滚动历史、发送与收起 | 镜像仍是硬件输入路径；交还实体设备待用户操作，未用辅助条或原型键盘占位作替代。 | inconclusive；I2 remains |
| 正常双指缩放/恢复 | 镜像未取得实体手势证据。 | inconclusive；I2 remains |

原型详情 must-match 的 I1 mismatch 已消除；软键盘真实可用性仍不可由当前截图推断。没有重复完整桌面矩阵，也未增加自动化测试。

### 附带发现（非本轮阻塞定性）

主屏 Chat 的 `+` → `Create group` 在两次 fresh screenshot 定位点击后仅关闭菜单，没有显示创建面板或导航。已即时报告 caller；Regression Relation: unclear，尚未证明由本 unit 引入，不进行源码 debug，也未把 caller API 建群当作该按钮通过。现有群设置/mention 的实机验证与此入口问题分开记录，由 owner 判断是否需另立问题。

### 交接

00:47 停在主屏 577 HTTPS → e2e 详情，composer 未聚焦、历史消息可见，明确交还设备 lease。建议实体操作：输入两行、键盘打开时滚动历史并检查标题/输入/发送，收键盘、返回再进入检查草稿，发送测试与查看回复，双指缩放后恢复；Safari 补同样键盘和缩放操作。尚未收到该证据，不提前 final pass。只追加本报告；无产品/测试/配置修改，无服务生命周期操作，report_commit=none。
