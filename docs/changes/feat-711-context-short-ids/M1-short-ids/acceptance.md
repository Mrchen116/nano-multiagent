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
