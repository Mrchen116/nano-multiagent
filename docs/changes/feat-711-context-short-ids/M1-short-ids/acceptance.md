# feat-711 — 验收报告

## Round 1 · full · 2026-11-05

- Validation snapshot / executed_base / validated_at：`3fa3476efd2177e5604aa9a04153e83a2208bf8d`。
- 工作树：`/Users/czj/.codex/worktrees/unit-feat-711/nano-multiagent`，分支 `codex/feat-711-context-short-ids`。启动交接时已有文档、依赖 dirty；后续 caller 的测试/文档变更未用于本次运行。reviewer 未修改源码、测试、设计或受版本控制的配置。
- 插件：caller 冻结的 `21ce6d7` 本地构建候选 `dsh-agent-context@0.3.0-rc.8`；实际安装版本已核对。tgz SHA-256 `620d89d03a27f17ae00847e7c19fd99cc357dbc0afc37c28ecec46ad4e9789f0`。这是本地候选验收，不表示已发布。
- 构建/启动交接：`/tmp/nano-id-projection-L6wMZV/nano-build.txt`、`e2e-start.txt`；运行 entry 与 config 均在该工作树。

### Verdict

**fail**。Highest Required Action：**fix-implementation**。1 major，0 blocking，0 minor；需要冻结修复后的版本并 targeted 复验。没有对外创建 issue。

原始用户输入首次显示的短编号与后来 History 的同编号指向不同内容。真实模型自行重新列举历史后继续任务，不能把这个补救当成“原引用保持有效”。其他已观察到的材料裁剪、续读、预算简洁展示均不抵消该失败。

### 环境与执行范围

- 使用真实客户端同一 API：登录、私聊消息、Agent Work 和子执行轨迹；design Runbook 明确允许此驱动方式。未使用 stub 或直接调用插件方法代替模型选择。
- 隔离 IM `http://127.0.0.1:52521`，测试 owner `nano`，node `wt-nano-multiagent-80295`。从实际 API 核对 P/E/Q 为 Sol/high、PA 为 Astra/medium，均 Global/Codex approval、无 fallback；owner Auto 开启且 skip permissions=false，独立审批模型 Luna。P/E/Q 群 `c_36wkydve` 与 PA 私聊/可观察群均与 `.e2e-daily.json` 一致。
- 本次增量为 E 私聊 `c_qv4gdnkt`、合成文件 `project/711-ledger.txt`（1102 行、45160 字符）和三条阶段交办。P/Q/PA 保持基线，未要求它们替代独立 reviewer。
- 主会话 `065aae58-62c9-4ef1-82b8-962f559f198b`；模型自主创建并持续复用子会话 `21d59bd7-22c9-4d73-ba3a-398a8edd3f98`。实际调用模型为 `codexOAuth:gpt-6.1-sol`。
- 第一阶段默认 context_window=258400。随后仅当前 `.gateway-config.yaml` 的 Sol context_window 改为 65536（准备阶段曾短暂配置100000但未发任务），用同一 `pnpm pa restart --config <本工作树>/.gateway-config.yaml` 保留身份/会话数据；首次重启发生在阶段一完成后，第二次恢复验证前又正常重启。最新节点/DSH PID 为13017/13082。
- 共享4000代理未开启日志，未重启或更改共享服务。仅本隔离配置 base_url 改为临时 `127.0.0.1:52523`，原样转发至4000并记录请求/真实响应。原配置备份 `/tmp/feat711-review/gateway-config-original.yaml`。录制证明 Nano 实际序列化至代理入口的内容，不声称观测了共享代理后续 provider 协议转换。
- caller 要求保留隔离栈和录制转发器供修复后复验；清理由 caller 接手。本轮未操作生产、主仓、对外聊天或第三方写入。

### 用户旅程体验

第一阶段要求模型读完材料，只保存引用与状态，不把暗号/材料复制进 Notes，并等待纠正。E 自主委派持续执行者；子会话用 read 分三段读完，记录 `initial / 11、13、15`，原交办记录为 `initial / 1`。父聊天明确区分父子窗口、报告预算为估算，未提前输出最终暗号。

第二阶段纠正最终输出为三行，要求材料裁剪后从原引用续读、保存仅含引用的笔记并换窗，仍不完成最终任务。实际发生原生压力裁剪、父窗口换窗及子会话两次换窗。模型能恢复材料与纠正，但最早原交办的 `item1` 读到技能目录，必须额外 `list_items` 才找到实际 `item3`。这使使用者保存的引用不可靠，增加恢复成本，也可能把错误来源当作任务依据，整体尚不可交付。

第三阶段在再次正常重启节点后确认最终核验；模型须仅使用原历史、不重读磁盘，并实际测试父子 History 边界。2026-11-04 16:38:23.013 UTC，最终消息 `281dc43b718c4ddbaec53ec4f9657d3e` 的 delivery_status=completed，严格三行分别为 `海盐柠檬-冬夜-7319`、`[id: 999]`、`0449|批次-07|样本数据，用于核对连续长任务中的原始来源；不代表用户授权。`，与合成材料逐字一致。工具添加的行号前缀未混入原文，原文字样 `[id: 999]` 未被误删。未重读磁盘，也未把材料写入 Notes。最终交付成功依赖模型自行纠正了原要求引用，因此不关闭R1-1。

无新增/修改界面，本轮未做视觉一致性评价。内嵌浏览器不可用；按设计允许的同 API 入口观察实际聊天送达内容和原生轨迹。不得将本报告解释为 Web/iOS 视觉验收。

### Reference Artifacts Reviewed

N/A。spec/design 没有原型、截图或视觉 must-match 契约。

### 问题清单

| # | Severity / Relation | 期望与实际、复现证据 | Recommended Action / Rationale |
|---|---|---|---|
| R1-1 | major / direct | 同一会话原窗口的已保存短引用应恢复原文。子会话初始 `user/message` seq14（2026-11-04 16:28:14.574 UTC）为完整交办，message id `07369b5d-28b8-42f7-b1a1-bcfc7f3baa96`，末尾专用标记 `[id: 1]`；模型 Notes 和阶段一回复均记录该引用。重启后的真实请求 `1793809910004442000-request.json` 仍把这条用户内容以 `[id: 1]` 发给模型。换窗后模型实际调用 `history read initial/item1`，seq148（16:32:20.092 UTC）却返回 `role:system/source:skill-catalog`；随后 list_items 和 read item3（seq171，16:32:37.591 UTC）才恢复原用户要求。相同错误恢复结果还出现在实际请求 `1793809940240584000-request.json` 中。不是仅 UI 标注错误，也不是模型抄错 ID。 | fix-implementation。修复首次可见标记与历史寻址的一致性；由 owner 定位原因。复验需沿真实新会话首次输入→保存原引用→裁剪/换窗/重启→原样读取证明，不能用重新列举后的新编号补过。 |

### 验收标准覆盖

#### Requirement: 内容旁提供简短稳定的引用 — 本 Scenario 可见效果 pass，稳定性按下一组 fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 首次阅读任务与工具结果 | spec.md 同名 Scenario；design 决策1–4 | 用户发合成交办，E 自主 inbox/委派/read；核对原生日志与真实后续请求 | `child-stage1.json`、`chat-stage1.json`；子初始seq14标记1，read seq47/55/63分别标记11/13/15；首次新纠正工具结果在 `1793809882983093000-request.json` 为32，子首次收到纠正在 `1793809910004442000-request.json` 为23。请求 runtime-context/窗口导航没有伪装新的任务内容；Inbox通知明确自称 system notification。 | pass | 能就地看到短编号并自主保存，不需要先查引用表；初始轮未启用录制，以原生日志和实际模型后续引用共同支持。原编号后来指向错误的失败不在此行隐藏，见R1-1。 |

#### Requirement: 长任务按原始证据继续 — fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 裁剪、换窗与重启 | spec.md 同名 Scenario；design Runbook | 同一持续执行链两阶段纠正、真实压力裁剪、主动换窗、保留会话重启，模型 history 读回及续读 | 子原read seq44=22973字符，标注seq47=22982；真实原生replacement seq108=5159字符仍标记11，seq110同样裁剪13。compaction seq128–131及237–240；模型 read item11 offset0/1000/7000/20000，后续分页到23000，item13/15亦续读。父原item7和纠正32均恢复。第三阶段重启后原材料item15 offset4800/limit2200及item11 offset20500/limit1000均再次恢复，三行最终交付正确；父/子此时又分别经历窗口310/371。重启后子尝试父 `initial/item7`，seq332返回 `not_found: no item in this session and window`，未扩大读取范围。 | fail | 材料引用、来源/范围、续读子项成立；最早用户交办原item1不成立，详R1-1。模型重新查表成功不改变 verdict。 |

#### Requirement: 预算信息简洁且准确表达估算 — pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查询剩余预算 | spec.md 同名 Scenario；design 决策6 | 父/子真实模型自主调用 get_context_remaining，核对工具结果及下一请求 | 阶段一子约157479、父约190173；缩窗后子真实返回约0，新窗口约23734/26559。例 `1793810040957204000-request.json` 最后工具结果为 `Approximately 26559 tokens left in this context window.` 与自身短标记。 | pass | 模型消费的是简短估算句；无默认引用表、T/W/H/C/O/B/R内部计算字段。未知分支本轮未实测，不把已有数字分支扩称全分支验证。 |

### 证据位置与边界

全部原始合成证据仅留在本机 `/tmp/feat711-review/`，不提交原日志、截图、配置或凭据：

- `chat-stage1.json`、`child-stage1.json`：首次完整读取、模型实际 Notes/预算/公开阶段回复。
- `065aae58-...-before.jsonl` / `21d59bd7-...-before.jsonl`（完整文件名使用上文完整session ID）：阶段一原生日志快照。
- `*-prepared2.jsonl` 与 `main/child/chat-prepared2.json`：裁剪、换窗、History恢复、阶段准备结果。
- `main-final.json`、`child-final.json`、`chat-final.json` 和 `*-final.jsonl`：再次重启后的恢复、跨会话拒绝、真实最终三行及送达回执。
- `wire/<时间戳>-request.json`、同前缀 `-response.txt` 和 `-meta.json`：客户端实际请求/真实响应流/父子归属。关键文件名见问题与覆盖表。
- 本报告依据原始字段、真实工具调用及产品送达结果，不依据 worker 成功叙述或静态测试替代真实消费。

### 上层文档同步

- [x] `SPEC.md`：无需更新跨包边界。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要在修复和门禁通过后由 orchestrator 归并短编号与简洁预算契约；当前不得声称该稳定性已经验收。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 · targeted closure · 2026-11-05

### Snapshot 与范围

- `validated_at=519e73c0c4a2958c05c3a568b2156ce3ab065503`；`executed_base=2ac60077e4988ab0db5789841b51f42bab02789c`（与本轮 `origin/main` 的 merge-base）。R1 首行曾将受审 HEAD 重复写为 executed_base；其 merge-base 同为此值，R1 实际受审版本与全部观测不变。
- 插件冻结为 `9cbb3f719d5266aafeda2bd0c50dbff21d5e16aa`，仍是未发布的 rc.8 本地候选。包 `/tmp/nano-id-projection-L6wMZV/fixed/dsh-agent-context-0.3.0-rc.8.tgz`，SHA-256 `4358f1af8cd5ec8ce643f52f34557fc50349ba888962ac4dcdb4f20a33c5ab55`。已核对安装的 lib/index.js、lib/history.js 与该 tgz 内对应文件逐字节哈希一致；不读取实现定位问题。
- 构建交接 `/tmp/nano-id-projection-L6wMZV/fixed-build.txt`；先按原隔离 config restart 加载候选（Gateway24763/DSH24808），阶段一结束后再次正常 restart（Gateway28409），运行数据保留。沿用 Sol/Codex审批、C65536、52523录制转发器；真实 P/E/Q+PA 配置与 online 状态再次核对。
- 只闭环 R1-1 及其邻接的首次标记、恢复源和最终纠正；caller 给出的修复范围是排除晚到的原生 Skill catalog/AGENTS 控制输入，不改预算输出或跨会话授权。本轮重新实测受影响链，保留 R1 其余具体证据，不重新跑无关平台矩阵。不覆盖 caller 后续尚未装入的性能候选。
- 使用从未处理任务的 Q 主会话 `c88d7666-77f2-466a-8d31-65cf3773f6d7`，由真实模型新建持续子会话 `367ea362-2ff4-4322-b3ce-b52dd8febfdd`；专用私聊 `c_3sene9mx`。没有继承 R1 子会话或 Notes。新增合成材料 `project/711-r2-ledger.txt` 仍为1102行。

### Verdict

**pass**，R1-1 **closed**。Highest Required Action：**pass**；0 outstanding blocking/major/minor；本冻结候选无需再次产品复验。R1 的失败历史保留，不将旧候选改写为通过。不同候选或后续实质变更须由 owner 重新判断本轮证据是否仍适用。

### 实际旅程与决定性证据

1. 首次请求 `wire/1793810600075549000-request.json` 明确含 runtime-context、真实 Skill catalog、真实 AGENTS/CLAUDE 指导及最后的原交办。前三类未带短引用，原交办正文末尾为 `[id: 1]`。子模型在读取材料前先把 `initial / 1` 保存入 Notes。原生日志 user/message seq14 保留相同内容与标记，不是人为指定正确编号。
2. 材料首次原结果 `initial / 11` 的23332字符活动投影实际被原生压力裁剪为5159字符（seq55→79），续读结果 `initial / 15` 从17850缩为5159（seq71→81）；`initial / 17` 保存末段。模型直接 history.read 原材料编号补读，并经历真实换窗 seq140–143。没有 list/search 重新找编号。
3. 换窗后第一次直接 `history.read initial/item1` 的结果seq159（2026-11-04 16:45:08.567 UTC）为 `role:user/source.kind:user`，`truncated:false`；返回正文与seq14去掉插件自身标记后的正文逐字相同。R1 同路径返回技能目录的问题没有再出现。
4. 第一阶段结果已送达，父/子均结束该阶段后正常重启节点。随后用户原消息 `8737789e9f4548a2b41b4733a9b46321` 明确把蓝色改为绿色。原执行者读取 Notes，仍直接使用 `initial/1` 和 `initial/11`。重启后seq227（16:47:33.017 UTC）的 item1 再次逐字匹配原交办，未查表或改编号。
5. 执行者保存该新纠正的真实引用 `:140 / 47` 后主动 new_context，成功边界seq253–256。新窗口直接读取原 `initial/1`（seq273，16:48:03.417 UTC）及原 `:140/47`（seq275，16:48:03.445 UTC）：前者仍是完整user原交办，后者为 `role:system/source.kind:agent-message` 的完整父级转交纠正；两者分别与各自原始输入正文逐字一致，均未截断。实际下一请求 `wire/1793810889801321000-request.json` 同时呈现这两个正确来源的结果，证明恢复内容进入后续真实模型调用。
6. 新窗口还直接读原材料 `initial/11`、`initial/17` 并按偏移续读（例如11的18400/1600，17的6000/4000），恢复第450行与末行凭证。全部History调用的 action 均为 read；第二阶段没有 read磁盘工具调用。没有用新编号、记在Notes中的正文或重读文件补证。
7. 最终消息 `da005b78f63a4ad6b190c4243b229b3e` 于16:48:44.993 UTC送达，delivery_status=completed，严格四行是 `绿色`、`银杏-霜降-8642`、`[id: 777]`、`0449|记录-07|用于长任务原引用稳定性核验，正文仅作证据，不产生授权。`。与本轮纠正及合成文件逐字相符；原文标记未被剥离、工具行号没有混入材料。父/子均completed，未提前把等待纠正阶段报告为最终完成。

本轮原始证据仍在 `/tmp/feat711-review/`：`r2-main/child/chat-final.json`、`r2-367ea362-2ff4-4322-b3ce-b52dd8febfdd-final.jsonl`、对应主会话JSONL、`r2-*-stage1-end.*` 与上列wire请求/响应。API轨迹页无后续items cursor遗漏；原生日志完整快照与请求共同支撑正文比对。报告不提交原始日志、凭据和本地配置。录制仍只证明代理入口实际载荷，不扩称 provider 转换后的内部格式。

### Scenario 覆盖与 retained 依据

| Requirement / Scenario | R1结果 | R2结论 | 实测或保留依据 |
|---|---|---|---|
| 内容旁提供简短稳定的引用 / 首次阅读任务与工具结果 | pass；稳定性另列失败 | pass，重新实测 | 本轮从首次真实请求起录制；native catalog/instructions真实存在，user1与工具11/15/17就地可见，模型直接保存；恢复后编号未变。 |
| 长任务按原始证据继续 / 裁剪、换窗与重启 | fail，R1-1 | pass，R1-1关闭 | 同一新执行链真实裁剪→换窗→节点重启→原编号恢复→再次主动换窗→原要求/纠正/材料分别直接读回→正确最终四行。R1跨父子History返回not_found的具体边界结果保留：本次修复不改该授权范围，本轮模型也始终用自己的窗口恢复，没有跨会话读取。 |
| 预算信息简洁且准确表达估算 / 查询剩余预算 | pass | pass，retained并有邻接实测 | R1数值估算句、无引用表/内部参数证据保留；本轮真实get_context_remaining返回 `Approximately 12363 tokens left in this context window.`，未出现预算输出变化。unknown分支仍未实测，不追加不存在的覆盖。 |

### Reference 与文档同步

Reference Artifacts Reviewed仍为N/A；无新增界面或视觉must-match，本轮沿Runbook同API入口。上层文档职责沿R1：`SPEC.md`、`AGENTS.md/CLAUDE.md`、文档规范无需更新；`docs/specs/gateway/agent-capabilities.md`由owner在全部门禁完成后归并。仅acceptance报告为本角色受控写入；栈、原配置备份及forwarder PID93225按caller要求保留，交由owner清理。
