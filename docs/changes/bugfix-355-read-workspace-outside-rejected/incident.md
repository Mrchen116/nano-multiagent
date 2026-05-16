# bugfix-355: agent Read 工具读工作区外路径被硬错

## Relations

- Refs: refactor-353(本 unit 修正其 spec.md Q1 与 design.md 决策 2 的不一致)

## 原始报告

> 用户在 IM 让 agent 读 `/tmp/sandbox-alpha/README.md`,agent 调 Read 工具被拒,返回 `path is outside repo sandbox | 0 lines`。
>
> 用户反馈(2026-05-16 chat 8ec96b39beaf438fb63437aaa38b9811):
> > 他去 read "path": "/tmp/sandbox-alpha/README.md",path is outside repo sandbox | 0 lines。这符合预期吗?docs/changes/refactor-353-unify-path-sandbox 做了还会有这个?难道是因为 CC 就是这样做的
>
> 用户进一步:
> > 我要确认这个用户体验是 CC 的 auto mode 正常操作还是本代码仓没对齐

## 澄清记录

- Q1: 对齐 CC 时,Read 工具按哪种行为复刻?(我推荐:完全对齐 CC — auto mode safe-allowlist 直接 allow,default mode ask,bypassPermissions 放行但危险目录仍 ask,dontAsk 转 deny;并复刻 SAFE_YOLO_ALLOWLISTED_TOOLS 机制)
  A: 好,和CC一致,我的auto mode就是CC的auto mode

- Q2(初问): 危险目录保护(CC bypassPermissions 下 `.git/.claude/.vscode/shell configs` 仍 ask 的 safetyCheck)要不要本期复刻?(我推荐:本期不做,留作后续 unit)
  A: bypassPermissions模式就是开了dangerously-skip-permissions的模式吗,如果是,那我们也复刻
  - 源码核实回应:CC `permissionSetup.ts:725-727` `if (dangerouslySkipPermissions) orderedModes.push('bypassPermissions')` — 两者等价,CLI flag 即 mode。
  - 但进一步核实发现初问的前提是错的:CC 的危险目录保护(`checkPathSafetyForAutoEdit`)只在 `checkWritePermissionForTool` 内部调用(`filesystem.ts:1305`),`checkReadPermissionForTool` 不调用 — Read 在 bypass 下完全放行,无危险目录兜底。Q2 的初始推荐基于错的前提,作废。

- Q2(修订后): 既然 CC 的 Read 在 bypass 下也无危险目录保护,严格"对齐 CC"=Read 在 dangerously 下完全放行(`.git/config`、`~/.ssh/id_rsa`、`~/.bashrc` 等都直接 allow,不弹卡片)。这跟你"复刻"的本意一致吗?
  A: 对齐CC
  - 注:此答复仅覆盖 **Read** 方向(问题上下文只问了 Read)。Write/edit 方向的危险目录保护未表态,见后续 Q5。

- Q3: 本 unit 范围扩到对 refactor-353 整体权限设计 vs CC 做系统性对照,找出所有差异?
  A: 扩大这次的范围,你要检查上353其他的权限设计是否和CC有区别

- Q4: 本仓要覆盖 CC 的全部 mode(default / acceptEdits / dontAsk / bypassPermissions / auto / plan / bubble)吗,还是只做部分?
  A: 本仓只要做两个模式,auto和dangerously-skip-permissions,完全对标CC这两个,其他模式不做!

- Q5: Write/edit 在 dangerously 下要不要复刻 CC 的危险目录保护(`.git/.vscode/.idea/.claude/.bashrc/.zshrc/.profile/.gitconfig/.mcp.json/...` 仍弹卡片 ask)?
  A: 和CC一致。

- Q6(用户主动指出): `auto_mode_gate.py:777-786` 显式塞 `NOTE: target path '...' is OUTSIDE the agent's workspace` 给 classifier,这个 CC 没有对吧,那也要"复刻"(即对齐 CC = 从本仓移除)?
  A: auto_mode_gate.py:777-786 显式塞"NOTE: target,这个你确定CC没有对吧,那也要复刻
  - 源码核实:CC `yoloClassifier.ts:1487-1495 formatActionForClassifier` 只返回原样 tool_use,无任何 OUTSIDE 包装;整个 yoloClassifier.ts 搜 "outside" 无相关条目;CC 是让 classifier 凭 system prompt 的 "BLOCK — File Write Outside CWD" 规则自己判断。
  - 结论:本期把 auto_mode_gate.py:777-786 的 NOTE 包装移除,对齐 CC。

- Q7: web_fetch / web_search / agent 三个工具本仓多丢进 SAFE_TOOL_ALLOWLIST,比 CC 宽松(CC 这三个不在 safe-allowlist,而是走各自独立的 checkPermissions:WebFetch 看 preapproved host + hostname rule,Agent 走子 agent 权限继承,WebSearch 独立)。本期严格复刻(A)、移除但不复刻(B)、保留现状(C)?(我推荐 C)
  A: Q6 严格复刻,工作量不是问题。
  - 注:用户称为"Q6",实际答的是本编号 Q7(选项 A = 严格复刻)。
  - 结论(初版):本期把 web_fetch / web_search / agent 从 SAFE_TOOL_ALLOWLIST 移除,各自补 checkPermissions:
    - WebFetch — preapproved host 表 + hostname rule 引擎
    - WebSearch — 独立 checkPermissions
    - Agent — 子 agent 权限继承
  - **design 阶段 D2 修正(2026-05-16)**:重读 CC `AgentTool.tsx:1692-1709` 发现 CC 外部用户的 AgentTool **本来就是所有 mode 都直接 allow**,"子 agent 权限继承"是我杜撰的描述。S3 实际跟 CC 外部用户行为已对齐,**不算 gap,从本期范围移除**。Q7 答复对 web_fetch / web_search 仍生效(S1 + S2)。

- Q8: S1 / S3 工作量明显比 R/W 大一个量级(基础设施级新增),本期一个 unit 一锅炖,还是拆 sub-unit?
  A: 不用,design再拆

## 现象与复现

### 直接触发面(用户报告)

1. 启动 Gateway + IM(`auto` mode,默认配置)
2. 用户在 IM 让 agent 读工作区外文件,例:`请读 /tmp/sandbox-alpha/README.md`
3. agent 调 Read 工具,`tool_input.file_path = "/tmp/sandbox-alpha/README.md"`
4. **期望**:Read 工具返回文件内容(对齐 CC `auto` mode 下 Read 在 safe-allowlist 直接 allow)
5. **实际**:Read 工具返回 `path is outside repo sandbox | 0 lines`,LLM 据此误判文件不存在或目录为空

### 延伸触发面(audit 期间发现,见 audit-vs-cc.md)

- 用户在 `dangerously-skip-permissions` 模式下让 agent 改 `~/.bashrc` 或 `.git/config` — 当前**沉默地发生**,跟 CC 的 "bypass-immune safetyCheck" 不一致(应该弹卡片仍 ask)
- 用户在 auto mode 下让 agent `WebFetch` 抓未审核的外部域名 — 当前**直接 allow 跳过 classifier**,跟 CC 的 "WebFetch 走独立 preapproved host + hostname rule" 不一致
- ~~用户在 auto mode 下让 agent 派子 agent — 当前**直接 allow 跳过权限继承**,跟 CC 的 "AgentTool 走子 agent 权限继承" 不一致~~ **(2026-05-16 design D2 修正:'子 agent 权限继承' 是初版杜撰描述,CC 外部用户的 AgentTool 本来就是无条件 allow(`AgentTool.tsx:1708`),`USER_TYPE === 'ant' + mode === 'auto'` 才走 classifier 且被外部 build DCE 移除。本仓 `agent` 在 SAFE_TOOL_ALLOWLIST 跟 CC 外部行为一致,不是 gap)**
- 用户在 auto mode 下 agent 写工作区外路径 — classifier 拿到的 prompt 被本仓加塞 `NOTE: target path ... is OUTSIDE` 前缀,跟 CC 的 classifier 凭 system prompt 自判不一致(影响 classifier 行为可重现性,不是直接用户感知)

## 影响范围

### 谁受影响

- 任何在 `auto` mode 下用 Read 工具读工作区外路径的用户 — 100% 触发 R1,LLM 拿不到内容
- 任何使用 `dangerously-skip-permissions` mode 期望"完全放行"的用户 — Read 工作区外仍硬错(R1),违背 mode 的语义承诺
- 任何使用 `dangerously-skip-permissions` mode 让 agent 改配置文件的用户 — W1 缺位,危险写入沉默发生
- 任何在 `auto` mode 下用 WebFetch / WebSearch / Agent 工具的用户 — S1/S2/S3 安全姿态过宽,缺 CC 应有的独立 checkPermissions

### 多严重

- **R1**:高频可见 bug,直接堵住"读工作区外文件"这条核心路径,LLM 误判进一步污染后续推断链
- **W1**:静默风险面,危险写入用户无感知,prompt injection 持久后门攻击面
- **S1/S2/S3**:安全姿态比 CC 宽,理论上提升 prompt injection 风险面(WebFetch 抓恶意 host、Agent 派恶意子任务等)

### 是否有数据损坏

无。R1 是读失败,不写;W1 至今为止主要是"潜在"风险面,无已知用户数据损坏报告。

## 根因分析（RCA）

### 直接根因(per gap)

- **R1**:`safety.py:306-325 resolve_read_path` 沿用 codex-cli 风格的"工作区外硬 raise" — refactor-353 design.md 决策 2 有意保留,但跟 CC 实际 Read 行为(auto safe-allowlist + bypass mode 短路)不一致
- **R2**:refactor-353 调研期把 CC "auto mode + safe-allowlist 直接 allow" 简化误判为 "CC read 默认放行,保持不变",未区分 mode,导致 spec.md Q1 与 design.md 决策 2 双双跟 CC 错配
- **W1**:refactor-353 把 dangerously bypass 设计为 `auto_mode_gate.py:713-717` 早期 short-circuit,跳过所有后续检查;但 CC `permissions.ts:1252-1260` 注释明确写 "safetyCheck is bypass-immune",这层 immune 检查在 refactor-353 调研期被遗漏
- **W2**:`auto_mode_gate.py:777-786` 的 OUTSIDE NOTE 是 refactor-353 实施期"为帮 classifier 做更好的决策"自行加的辅助提示,CC 不做这种加工
- **S1/S2**:refactor-353 实施期把所有 `isReadOnly()=true` 性质的工具简单归入 SAFE_TOOL_ALLOWLIST,未区分 CC `SAFE_YOLO_ALLOWLISTED_TOOLS` 的实际清单 — CC 的 WebFetch / WebSearch 虽然 `isReadOnly()=true` 但**不在** safe-allowlist,各自有独立 `checkPermissions`(WebFetch 看 preapproved host + hostname rule,WebSearch 返回 passthrough 委托上层)
- ~~**S3**:~~ 初版判断"Agent 工具同上,缺独立 checkPermissions 含子 agent 权限继承"在 design D2 阶段被推翻 — CC 外部用户的 AgentTool 默认无条件 allow(`AgentTool.tsx:1708`),不存在"子 agent 权限继承"机制;本仓 `agent` 在 SAFE_TOOL_ALLOWLIST 直接 allow 跟 CC 外部行为一致,**不是 gap**,从本期范围移除

### 为什么这种错能进来(系统性根因)

refactor-353 是本仓权限子系统的**第一次跟 CC 对齐**尝试,调研期主要参考的是 CC 的 mode 入口、classifier 主路径、safe-allowlist 概念;但**没有做工具级 `checkPermissions` 的逐个核对**,导致:

1. **mode-条件性行为被当成 mode-无关全局行为** — CC "auto mode + safe-allowlist 直接 allow" 简化为 "CC read 默认放行",失去 mode 维度
2. **工具级 checkPermissions 被忽略** — 把 `isReadOnly()=true` 直接等同于"放进 safe-allowlist",忽略 CC 给特定工具单独设的权限链路(WebFetch hostname rule、WebSearch passthrough 委托上层)
3. **bypass-immune safetyCheck 被遗漏** — 把 bypass mode 等同于"完全跳过所有检查",忽略 CC 的"bypass 也仍要 ask 的边界条件"
4. **assumption 没经过源码二次核对** — refactor-353 spec.md Q1 / design.md 决策 2 的 "CC 也是这个口径" 声明,如果当时跟着 `permissions.ts` / `filesystem.ts` 源码逐行核对一遍,这些错配会立刻发现

review 时没触发怀疑的原因:权限子系统的对齐验证依赖"对照 CC 源码",而 refactor-353 提供的 "CC 也是这个口径" 叙述本身就是简化版,reviewer 没有独立去 CC 仓核对源码;且本期 audit 是用户在使用中真实碰到 R1 才反向推动的源码核实,如果没有这个使用反馈,这些 gap 还会潜伏更久。

## 验收标准 / 目标状态

> 每条都是用户在产品上能观察到的行为。实现层标准(协议字段、内部 API、单测断言)归 design.md `[worker]` 轨。

- [ ] 用户在 `auto` mode 下让 agent 读工作区外文件(如 `/tmp/foo/bar.md`),agent 能拿到内容并返回给用户;不再收到 `path is outside repo sandbox` 报错
- [ ] 用户在 `dangerously-skip-permissions` mode 下读工作区外任意文件,直接放行无任何弹卡片;读 `.git/.bashrc/~/.ssh/id_rsa` 等也直接放行(对齐 CC,Read 无危险目录保护)
- [ ] 用户在 `dangerously-skip-permissions` mode 下让 agent 改 `~/.bashrc` / `.git/config` / `~/.zshrc` 等危险路径,**仍然弹卡片让用户确认**(不再沉默写入);Allow / Deny 选项与现有 bash 卡片一致
- [ ] 用户在 `dangerously-skip-permissions` mode 下改工作区内任意文件、改 `/tmp/foo/bar.txt` 等普通工作区外路径,跟之前一样直接放行(W1 不能误伤正常路径)
- [ ] 用户在 `auto` mode 下让 agent 调 WebFetch 抓未审核域名,行为按 CC 复刻的 hostname rule 引擎(preapproved → allow;否则按用户规则匹配 / 弹卡片 / classifier);跟之前"直接 allow"行为有可观察的差别
- [ ] 用户在 `auto` mode 下让 agent 派子 agent(`agent` 工具),行为跟修复前一致,直接 allow(对齐 CC 外部用户行为 — `AgentTool.tsx:1708 return {behavior: 'allow'}`,无条件放行;子 agent 自己跑的每个 tool call 仍重新过 auto_mode_gate)
- [ ] 用户在 `auto` mode 下让 agent 写工作区外路径,classifier 的决策跟修复前可重现一致或更准(本仓不再加塞 OUTSIDE NOTE,行为对齐 CC)— 这条是反向不变性:不引入新 ask、不引入新 deny

## 修复方向

> 行级实现 / milestone 拆分留给 design.md。下面只列高层方向。

7 个 gap 按 audit-vs-cc.md 的编号:

1. **R1**:`safety.py:306-325 resolve_read_path` 移除工作区边界检查,仅保留 normalize;`read.py:53` 调用方对应调整。Read 决策权完全交给 `auto_mode_gate`(Read 已在 SAFE_TOOL_ALLOWLIST,auto/dangerously 两 mode 下都直接 allow)。
2. **R2**:refactor-353 spec.md / design.md 加 Changelog 行,在 spec.md Q1 + design.md 决策 2 旁加 corrigendum,标注被 bugfix-355 修正并解释 CC 实际行为。
3. **W1**:从 CC `filesystem.ts:57-79` 抄 `DANGEROUS_FILES` + `DANGEROUS_DIRECTORIES` 常量(按本仓上下文裁剪 — 至少 `.git/.claude/.bashrc/.zshrc/.profile/.gitconfig`);在 `auto_mode_gate.py:713-717` dangerously 短路前加 safetyCheck 调用,命中则**降级到 ask**(不 bypass)。
4. **W2**:删 `auto_mode_gate.py:777-786` 的 NOTE 包装,classifier 凭 system prompt 已有的 `BLOCK — File Write Outside CWD` 规则自判。
5. **S1**:`web_fetch` 从 SAFE_TOOL_ALLOWLIST 移除;新建 preapproved host 表(从 CC `WebFetchTool.ts isPreapprovedHost` 抄初始清单)+ hostname rule 引擎;`WebFetchTool` 加 `checkPermissions` 走该引擎。
6. **S2**:`web_search` 从 SAFE_TOOL_ALLOWLIST 移除;给产品级 `WebSearchTool`(`personal_assistant/tools/web_search.py`)加独立 `checkPermissions`(逻辑对照 CC `WebSearchTool.ts:101+`)。design 阶段需决定 checkPermissions 落在产品层还是平台层。
7. ~~**S3**:`agent` 从 SAFE_TOOL_ALLOWLIST 移除...~~ **(design D2 阶段撤销 — CC 外部用户 AgentTool 默认无条件 allow,本仓现状已对齐,非 gap,本期不做)**

## 范围与非目标

### 在范围

- 上述 R1-R2-W1-W2-S1-S2-S3 七个 gap 的代码修复 + 文档修订
- `auto` 和 `dangerously-skip-permissions` 两个 mode 的行为对齐到 CC
- 相关单测口径迁移(从 ToolError 文案 → hook decision / safe-allowlist 短路 / 各工具 checkPermissions 输出)
- e2e 实测:IM 下 agent 读工作区外文件、写危险目录、WebFetch 抓未审核 host 等关键路径

### 非目标

- **其他 mode 不做** — `default` / `acceptEdits` / `dontAsk` / `plan` / `bubble` 全部不在本仓范围(Q4 用户硬声明:"本仓只做 auto 和 dangerously-skip-permissions 两个模式,完全对标 CC 这两个,其他模式不做!")
- Read 的危险目录保护不做 — CC 也不做,严格对齐
- CC `additionalDirectories` / `additionalWorkingDirectories` 配置持久化不做(refactor-353 Q2 已声明非目标,本期继承)
- CC `transcript_classifier` 之外的特性(如 `acceptEdits fast-path`、`dontAsk transformation`)— 因 mode 范围已锁定,这些 mode 自身就不做,相关 fast-path 自然不做
- 本仓引入 CC 有而本仓没有的工具(Grep / Glob / LSP / TodoWrite / Sleep / Workflow / EnterPlanMode / ExitPlanMode 等)— 不在本期范围;后续真引入这些工具时再单独决定是否进 safe-allowlist

## 参考文件

- `docs/changes/bugfix-355-read-workspace-outside-rejected/audit-vs-cc.md` — refactor-353 ↔ CC 系统性对照表,7 个 gap 的源码引用与一致性判断,本 incident 的事实基础
