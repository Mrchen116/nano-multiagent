# feat-637 — 独立产品验收

## Round 1 — full

- `review_round`: R1；`mode`: full；`revalidation_mode`: full。
- `executed_base`: `5462b7217421a2c27871c1c5951c1e48644e54ba`。
- 原始 `validated_at`: `d617906aed41fa14a34f4b3f1b5e49f179ed4129`。
- 环境：caller 启动的专用隔离 IM `http://127.0.0.1:65441`，测试用户 nano，普通 e2e/e2e-peer 与 Global e2e-global。模型 `deepseek:deepseek-v4-flash`；自动审批 `codexOAuth:gpt-6.1-sol`。没有生产写入。
- R1 后半段的运行树为上述 SHA 加 caller 的单行修复：只有原生 `completed` 才可被 Memory 读取未完成转换为 `memory_read_incomplete`。该段从 Node PID 58686 起，包含 F4、读取失败和在途关闭旅程；不得把它表述成未经修改的原始 SHA。R2 在冻结 SHA 上复验受影响项。
- 原始证据目录：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/nano-feat637-review-s9yd05xd/reviewer-evidence/`。报告只包含合成测试内容及定位信息，不提交运行数据库、凭据、原始日志或截图。

### Verdict

**fail**。两个 major 产品问题；不能放行。F4 正向受阻也使依赖它的实际并发与已处理证据去重尚不能完成。后续修复不覆盖本轮失败记录。

### 用户旅程体验

从真实 Web IM 登录、新建普通聊天，提供青鹭 Python 版本及中文“先结论、两点依据”偏好。正常回复可用；后台通知只表达实际更新。普通 Memory 文件将偏好与环境事实分开，重复表达没有副本，明确纠正将 3.12 替为 3.13。另一真实 group session `c_rw96pibs` 不带原对话历史，正确使用 3.13 与格式偏好。纯临时“第三页／猜测 Redis”会话没有沉淀，其他会话明确回答数据库未知。

Global 工作入口从聊天里的 View Work 进入。1280×720 viewport 下，工作记录与原生轨迹的切换清楚；父轨迹真实发起行显示“记忆与技能复盘 / fork / 后台执行 / 已完成”。从该行进入，导航显示相同用途及 `#62 → #110` 本次范围；完整父历史仍可检查。返回发起点后刷新，再从同一发起行进入，仍为同一子执行与相同范围。这里验证的是刷新后重入，不要求自动恢复子范围。顶部未选中的 execution 列表仍显示内部 nano-review 标签，但实际发起行及当前子导航具有正确名称，本次用途契约通过。截图：`/tmp/feat637-combined-child.png`。

前台 partial-release 旅程先成功 patch，再故意用不存在原文触发工具失败。模型准确列出第一步保留、第二步拒绝及未重试，原文中其他有效规则保留。后台人为令测试 USER.md 不可读，combined 仍成功修正 Skill，但知识维护终态为 error，原生执行正常完成；通知只显示 skills updated。恢复文件权限后，下一轮正常完成。在途关闭 Skill 的另一轮则 cancelled，没有继续写该类知识。

临时恢复旅程实际创建临时目录、核验两条 CSV 记录与 SHA256、清理目录并保留 occupied-scene。后台只保留条件与退出责任，没有改成每轮创建。下一次提供可用 available-scene 时，Agent 实际复用并清空工作文件，没有再创建临时现场。

上述成功不能弥补两个问题：Global 一次延期修改将完整 Skill 规则与待办状态写入环境 Memory；F4 在多份真实完成使用证据下始终跳过，无法交付目标技能改进。

### Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| design.md「Combined 的轨迹用途」表；IM delta「联合复盘的用途和范围」 | 一个真实后台 fork 入口；用途名称；进入、返回、刷新后同一范围 | run `ba070bdf-e189-4350-85ce-fe2bb4e00782`，child `867e4afe-ef6d-4a72-b48e-a8d088c7b242`，Web 发起点与导航截图 | 1280×720；completed；父→子→父→刷新→子 | match；没有额外整页原型，不推论 iOS 专项验收 |

### 问题清单

| ID | Severity | Regression Relation | 观察、期望与复现证据 | Recommended Action / rationale |
|---|---|---|---|---|
| R1-P1 | major | direct | Global 消息 `68abf1f00e784aecb8e602619b153acd` 纠正 qinglu-release 顺序，但说“此轮不要直接修改技能”。combined `44fa9fd6-bb4a-46e5-8b8c-989f8c0b4a1d` completed 后，把“技能待修（已获用户纠正、未获改文件许可）”、完整行数→摘要流程、原因和清理等规则写入 MEMORY.md。期望：暂缓改 Skill 不构成长久环境事实或 Memory 中的待办队列。证据 `memory-first-and-correction.json`、`39c49188-cfbd-4ce3-8170-866999fd7275.jsonl`。后续显式确认和下一次维护最终清掉该条目，不撤销首次失败。 | fix-implementation：违反无长期价值不沉淀及完整规则单一归属；须用相同输入复验。 |
| R1-P2 | major | direct | 自动 F3 种子 f4-evidence-check 累计 22 次真实加载，来自三个真实已完成 session：`9470865c-05d6-437f-9d20-65a89d7d9d47`、`c9631408-c6f4-4029-9706-6fcaad204ca7`、`9607f033-52a1-4dc9-a481-7dda5e8708a6`。后两份为短任务，实际 bash 对照 splitlines=3 与 csv.reader=2。同一问题仍全部 skipped / insufficient_completed_sessions；目标不变。代表 review `08975f7c-ce9b-4cf0-9b93-86e762043a85`、`7b27a22b-4429-4e41-a814-a7e881cc0b40`。 | fix-implementation：真实正向场景不能到达 F4；owner 定位和修复，reviewer 不读实现替代验收。 |

`Highest Required Action: fix-implementation`。本轮没有对外创建 issue。

### 验收标准覆盖（首文档 21 个 Scenario）

下表期望来源均为 `spec.md` 同名 Scenario；执行细节对应上述旅程及 evidence 目录。自动 F4 种子仅是受控前置，不冒充模型生成；Skill 使用、历史、CSV 对照与修改结果均来自真实运行。

| # | Scenario | 独立实际证据 | R1 结果 |
|---|---|---|---|
| 1 | 画像和项目事实各归其位 | 普通/Global 首轮 USER 与 MEMORY 分类；普通新 session `c_rw96pibs` 正确使用3.13和格式 | pass |
| 2 | 没有长期价值的信息不沉淀 | 纯临时会话 `c_0f7leko9` review `0196cd2e…` 无写入；另一会话回答数据库未知。但 Global 延期待办被写入 MEMORY（R1-P1） | fail |
| 3 | 重复表达不产生重复记忆 | 普通 review `de85a7f0…` 本轮 read 两文件，判断已存在、无写入；最终单份偏好与事实 | pass |
| 4 | 明确纠正替代旧事实 | 普通 review `decbb026…` 替换3.12→3.13，新session采用；Global最终review `52132322…` 清理24→26，保留来源 | pass |
| 5 | 有效经验改善已有技能 | ordinary qinglu-release 原位修正行数→摘要、原因、有效现场规则；随后真实核验按新顺序执行 | pass |
| 6 | 未成功尝试不成为可靠流程 | peer read failed-experiment.txt 后combined无失败方法Skill；新会话 `c_ha2blyur` 明确没有已验证成功方法 | pass |
| 7 | 新建现场不被泛化为每轮惯例 | 实际 tempfile 创建/核验/清理；随后 available-scene 被复用而非再新建；知识仍保留适用条件与清理责任 | pass |
| 8 | Agent 的选择不冒充用户要求 | qinglu-release 保留“只是Agent自己的恢复选择，不是用户长期偏好”；真实临时目录经验未写入 USER | pass |
| 9 | 同一纠正不被双份固化 | 普通完整规则仅Skill；Global延期纠正把完整规则转存Memory，见R1-P1 | fail |
| 10 | 关闭自进化仍有效 | 普通关闭skill后memory-only `f40ca683…` 正常更新环境事实，无后台Skill修改；peer memory关闭后skills-only可用 | pass |
| 11 | 两项同时满足条件 | 普通及Global均一个kind=combined/background/fork，真实写入通知；GlobalUI同一用途及范围通过 | pass |
| 12 | 仅一项满足条件 | ordinary memory-only `f40ca683…`；peer skills-only `9ce39a9a-52b7-4416-b47d-3565e13b51d5`；Global skills-only `3f284451…`；Global memory-only待R2实测 | inconclusive |
| 13 | 联合复盘失败或中途关闭能力 | `97e97a86…` Memory读失败但Skill真实patch保留、通知仅Skill、维护error；恢复后 `28452591…` completed；在途关闭 `f442b46c…` cancelled | pass |
| 14 | 主 Agent 修正已有技能 | peer partial-release 第一步局部patch成功，front原文及有效规则保留 | pass |
| 15 | 部分修改成功时报告实际状态 | 消息 `987c78893ee04784bd231efd6fe2d5f4` 后工具真实成功/失败及最终准确报告，见 frontend-partial-pass.json 与聊天记录 | pass |
| 16 | Global 模式不触发 F4 | Global 自动目标20次真实skill使用，use_count/uses_since_last_B均20，无Global F4，目标不变；之前F3仍可用 | pass |
| 17 | 有充分证据时修补目标技能 | 三份真实完成session仍skip；R1-P2 | fail |
| 18 | 单个会话中的重复使用不等于跨会话证据 | peer首session20次，F4 `cb16bcd3…` / `b96dadfa…` skipped；目标不变，计数20未扣 | pass |
| 19 | 无效或已处理的证据不再次支持修改 | 在途会话不够时skip实际覆盖；已处理证据去重依赖首次成功F4，受R1-P2阻塞 | inconclusive |
| 20 | 手工技能不被 F4 自动修改 | F1 manual-evidence-check 20次真实调用、计数20、无该目标F4/修改 | pass |
| 21 | 同一技能的复盘不重叠执行 | F4未能启动，不能以没有并发记录冒充该场景通过 | inconclusive |

### 上层文档同步

- [x] `SPEC.md`：无需更新；没有新增跨包运行时或权限边界。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要最终实现校正后归并本 unit delta；当前未归并。
- [x] `docs/specs/im/agent-work.md`：需要归并联合用途与范围 delta；当前未归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

长青契约归并由 caller 完成；reviewer 仅写本报告。

## Round 2 — targeted（进行中）

- 冻结 `validated_at`: `fc101f8532e638324ebcf8bf60e51044af68c377`；`executed_base` 仍为 `5462b7217421a2c27871c1c5951c1e48644e54ba`。
- Node PID 65541 经专用 stop/start 载入该版本。后来 HEAD 的 `138eccfd7` 仅是其他审查报告，未据其冒充执行过的新产品版本。
- 复验范围：R1-P1、R1-P2、相邻知识质量；补齐 Global memory-only 及真实 F4 并发/去重。未失效 UI、前台 partial、临时恢复、手工来源与 Global 禁止 F4 等具体 R1 证据保留。

### 已取得结果

1. **R1-P1 同输入关闭**：新建专用 `e2e-global-r2`（独立 workspace/Global 主 session `d919d606-258d-410a-afde-910bd92c44f2`），复现相同初始事实、重复确认和原样“此轮不要直接修改技能”输入 `9d8ca84888c64081bc24395e240eb7a4`。review `f84a5b97-211a-4d69-a345-e5aba028177b` completed。USER、MEMORY、Skill 与输入前逐字相同，没有待确认队列或流程转存。证据 `r2-deferred-completed.json` 对照 `r2-f4-completed.json`。
2. **R1-P2 正向关闭**：同原现场保留所有历史，F4 `d034d4a2-32cb-4a88-9f57-35edad292647` completed，明确选择 `c9631408…` 与 `9607f033…` 两不同 session，仅 patch `f4-evidence-check` 为 csv.reader，保留原文件约束与其他有效内容，没有新建/删除/改其他技能。通知仅 skills updated，去重账本记录这两个 session。
3. **实际并发通过**：上述 F4 原生范围为 05:28:05.713Z–05:28:21.571Z；第三会话真实 skill 调用 `call_00_KR60dVJlVSjT19SPdBS57469` 在 05:28:07.737Z 发生，处于范围内。同目标仅一条 accepted F4。冻结扣除23次后，use_count=24、uses_since_last_B=1，运行中新增使用保留。证据 `f4-r2-concurrent-dispatch.json`、`r2-f4-running.json`、`r2-f4-completed.json` 与原生 run `7dfb5e72-a2c8-4300-84da-451f71a352e1`。
4. **Global memory-only 补齐**：原Global关闭Skill、memory周期1/skills周期1000，review `e9374385-d95b-4a6b-92ea-61740e15a368` completed，真实环境目录更新，Skill不参与。结合R1 ordinary memory-only、ordinary/Global skills-only，单项模式均已真实覆盖。
5. **正常 Memory 纠正仍可用**：新Global review `690db0f2-5bd5-4689-ac54-c493c4997dba` 完成，将Node24替为Node26，保留来源，没有两个当前版本；不是靠禁止所有学习关闭P1。

### R2 新发现 — R2-P1（major，未关闭）

- Regression Relation：direct（内容质量验收失败；不声称已证明由某行修复引入）。
- 输入 `96db63dddaec4425bbc0bcfcf3fe2c09`：确认允许后续维护修正 qinglu-release，新增白鹭目录 `artifacts/bailu-r2`，明确“前台本轮只口头回复收到，不调用任何工具”。
- 实际：前台仍调用 memory add；已有 USER 格式偏好增加同义副本；MEMORY 保留旧 Node26 条目，又增加“白鹭（青鹭合成项目）固定运行 Node26…发布目录”条目，重复版本并混淆两个项目。两次新增来源为父 session `d919d606…`，原有来源 `920bad9f…`、`dc901895…` 保持。本轮因前台 Memory 成功，后台只运行skills review `4e22061b-ff71-4ac3-b80c-b03fc5198cfe`，它completed后重复仍在。
- 最终前台回复 `e1adc78d55374ae0af9e24b5405012bb` 声称“本轮只作口头确认，未执行任何核验或改动”，与实际持久写入不一致。
- 直接违反 `spec.md`「维护现有 Memory，而非持续追加重复或冲突条目」及「重复表达不产生重复记忆」的可观察结果；项目误合并也损害环境事实准确性。此前通过的是单纯后台重复/纠正，未通过这个“新事实+批准Skill纠正+旧偏好已落盘+前台写入重置Memory周期”的组合条件。
- 证据：`r2-approved-combined.json`、`c_wv4kcu3d.json`，以及该轮原生父执行。没有通过追加清理输入掩盖本轮失败。
- Recommended Action：fix-implementation；Action Rationale：同类事实已持久化却被再次追加，后续仅Skill复盘无法恢复当轮用户预期。由owner定位，reviewer不修改实现。

当前R2仍为 **fail**；F4已处理证据再次达到阈值的真实观察尚在继续。

## Round 3 — targeted（最终）

- `review_round`: R3；`mode`: targeted；`revalidation_mode`: targeted。
- `validated_at`: `1bc6219356186ebc0a3f255cf4a441936495d8e3`；`executed_base`: `5462b7217421a2c27871c1c5951c1e48644e54ba`。
- 运行同一隔离环境；新建 Global `e2e-global-r3`，chat `c_ybopoo99`，root session `e4d479d3-1b38-4b7d-8b5c-16c486db70d2`。创建后第一次环境探测未加载周期1配置、没有后台写入；空闲后重启 Node PID 75702，重新按原顺序完整发送五条输入。首次无知识写入的额外确认保留在轨迹，未冒充首次后台验收。
- 验收修复范围为前台 Memory 先读当前内容、缺文件/失败消歧、明确后续授权不在当前前台写入。R1 UI、partial、无长期价值、临时现场、失败经验、单项能力与关闭中断证据未失效；R2 F4正向和并发证据未失效。没有重新声称全部21项都在R3运行。

### 真实复验与缺口关闭

1. 初始事实 review `67a0a478-c4da-4fac-86ce-890a03f66816` completed，建立单份 USER 偏好及白鹭 Node24；重复确认 review `4ff755c8-89b6-4058-870d-8c9881f505f5` completed，没有重复。延期修改 review `caa659ee-b57c-4548-b21a-6844b04ceae1` completed，没有将规则、待办或授权状态落入 Memory，也未修改技能。版本纠正 review `abe18ff0-edc7-44f1-a238-8d212d643527` completed，Node26替代Node24，无并列当前版本。
2. **R2-P1 关闭**：原样第五条输入 `d8785e0502f84734877b57f807b2c6b4` 后，前台原生 turn6 仅 inbox/check、inbox/read、send_message（seq147/152/157），没有 Memory/Skill 写入；发送确认之后也没有补写。后台 combined `3b6cd97a-7c7c-4ef8-af40-da4914eb9ef8` / child `b90c3519-4ed6-4ac6-9c81-d0f335fb57dc` completed。USER保持原单份偏好；MEMORY保留单份白鹭Node26，新增白鹭目录 `artifacts/bailu-r2`，没有青鹭/白鹭混淆；qinglu-release原位改为先行数、失败即止、再摘要，保留现场复用/创建者清理/独立版本等有效内容。没有把完整流程转存Memory。证据 `r3-before-approved.json`、`r3-approved-completed.json`、`r3-native.jsonl`。
3. **明确前台维护授权仍可用**：将测试专用 custom_prompt 的一概禁止前台知识工具改为遵守明确用户授权（产品代码不变），输入 `e2e12072f5194c499e4c791732fedcfc` 明确要求前台读取当前两个文件并对已有事实去重。原生 turn7 seq188/193分别真实 read USER.md/MEMORY.md成功，随后seq198报告准确的零改动，没有 memory写操作。后续 combined `dbe7712f-49bc-41cb-83b9-e098273a3fb1` completed，文件仍逐字相同。证据 `r3-front-authorized.json`、`r3-final.json`。
4. **F4已处理证据去重关闭**：R2之后重复加载被运行时 guard 拒绝时如实停止，没有绕过 guard 或修改usage。随后只在原来两份已处理会话做真实CSV记录数、字段内换行、第二记录及SHA256核验，每轮实际加载技能，累计 use_count=43、uses_since_last_B=20。再次触发 `24355fcd…`、`86f7466b…`、`939d0e89…` 均 skipped / insufficient_completed_sessions；reviewed_session_ids仍为原两份，未增加第二条accepted F4；目标SHA256仍为 `a29d4b18d9118ba0f0b0f6bcfa25fa8085bd402baf0578398767472b2ade8e62`，与首次修补后相同。没有把相同session的新轮次当新跨会话证据。证据 `r3-f4-dedup.json`、两会话真实消息和 `.usage.json` / `.curator_state.json`。

### 最终覆盖合并

| Scenario | 最终状态 | 有效证据轮次 |
|---|---|---|
| 1、3、4、9 | pass | R1普通；R3 Global初始/重复/纠正/延期/批准/前台授权 |
| 2、5、6、7、8、10、11、13、14、15、16、18、20 | pass | R1对应真实旅程，未失效 |
| 12 | pass | R1 ordinary/Global skills-only及ordinary memory-only；R2 Global memory-only |
| 17、21 | pass | R2真实F4目标修补、运行中使用与仅一个accepted复盘 |
| 19 | pass | R1在途不足；R3已处理两session再次达到阈值仍skip |

### 最终结论

**pass**。21项 Scenario 已由上述有效真实证据覆盖，R1-P1、R1-P2、R2-P1均关闭，没有遗留产品 blocker 或 inconclusive。`Highest Required Action: none`。R1/R2失败记录保留，最终通过不抹去失败历史，也不扩大为生产部署、iOS专项或其他模型验证。上层delta归并与专用环境清理由caller完成。
