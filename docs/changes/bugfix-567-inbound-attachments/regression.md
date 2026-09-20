# bugfix-567 — 回归验证

> 对齐: [incident.md](incident.md)
> Validation snapshot: `c5f1d5620 → 30dac3b37a5f8a4c28059f003299f119f661c859`

## Round 1 — 2026-09-19

Mode: full。独立 reviewer 通过真实 Web IM 同一 HTTP API 登录、上传、发送和读取终态；未读产品实现定位，未修改产品/测试/设计。IM `127.0.0.1:55354`，node `wt-unit-bugfix-567-6458`，测试身份 `nano`，新建 `review567-single_thread` 与 `review567-global`，两者真实模型 `codexOAuth:gpt-5.6-sol`。进程为 caller 在该 validated_at 启动的 IM 6493/Gateway 6582；启动时间及 config 路径已核对。服务清理由 caller 负责。

### Verdict

fail。global 混合有效图片旅程的最终答案与实际图像不符，major 1，highest_required_action=fix-implementation，needs_re_review=true。本报告不为后续修改后的版本背书。完整消息证据见 [product-round1.json](M1-fix/evidence/product-round1.json)。

### 复现验证与回归旅程

| Scenario / 来源 | 实际输入与结果 | 结论 |
|---|---|---|
| 普通文件伴随文字 / incident | single_thread `c_xv6h3133`：上传 `review.txt` text/plain，正文 `FILE_BODY_HIDDEN_567`；消息 `754c3e5a9c0844be8c96c86b2c56c708` 要求只回复代码块 TEXT_567_OK。回复 `8a87f5715fa54da98aef8894f3b1cbec` 仅含该代码块，无图片损坏提示。 | pass |
| 文件描述与未读取 / incident | 同会话 `54dc8984f7f9450fb406ac0a02d46afa` 要求不读取/下载，仅说文件名、类型、来源和读取状态；`d3aa716350f9448da3fa2d73f045f53f` 正确列出 review.txt、text/plain、当前会话附件相对路径，并明确“未读取或下载附件内容”。 | pass |
| 混合有效图片与普通文件 single_thread / incident | `131f192e3be2443b94290e7e9860c1ad` 同条上传 320×200 白底红矩形 PNG + TXT，问颜色形状及文件是否读过；`b678c285f52647a88daf9a6038b18a7a` 回“图片中央是红色矩形。普通文件名是 review.txt，正文尚未读取。MIX567”。 | pass |
| 历史缓冲附件失败 / incident | 群 `c_xuhzvlxu` 的 `17e43c51d7db4ab2b41d3e6f2fff9b96` 无 mention，含文字口令松鼠567、history.txt 与字节为 `not an image` 的 broken.png；后续 mention 消息 `a4c22487a4764a7893f22eb4761cff62` 正常触发，回复 `b93641949ec04e5c926ec7becd3ff1a4`：“松鼠567。历史附件未读取。” | pass |
| 当前异常图片明确停止 / incident | 同群先缓冲背景口令海鸥568（`779b21294a4d4f14a5824a1b64f555e0`），再 mention 并附坏 PNG（`7d1104af67fd42b0809c5e1c518faf46`）。回复 `6eae2ab2b4464da09352c3a4387a5741`：“这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。”没有假装看过图片。 | pass |
| 解析失败后的缓冲保留与恢复 / incident | 紧接 `74db32747ac345b08de1990dc33285fd` 请求不再看坏图、回复上一条背景口令；`513f4379cafb4ea8848b1b148f0b8af9` 回“海鸥568。正常恢复。” | pass |
| 普通文件 global / incident | `c_3rm0dek3`，输入 `4a5ed65a056546c39ec212878b3e1ff7` 与同样 TXT；约52秒后 `0aff18ba2d7242b9bcaa2947823308a1` 仅回复 TEXT_567_OK 代码块。 | pass |
| 混合有效图片与普通文件 global / incident | 两条输入 `b9343a40a6864f05824df486109a6a13` / `0bfe4b552dce49359049ad030abe4ca0` 均是320×200白底红矩形 PNG + TXT；终态 `6de24c39c7734c4bb59a3af272c09545` 却分别说“红色正方形”“蓝色圆形”，与实际图像不符。 | fail |
| 历史局部失败保留有效图片 / incident | 群 `c_33v0s3d3` 背景 `de8b60e82d20434aab0fa5d696a22c0b` 同含蓝色正方形 PNG、坏 PNG、TXT与熊猫569；提问 `cedc0c434eb24ad793bf72c08f37ca78` 后回复 `6a2025cf585844788eb4397a043cc390` 准确指出熊猫569、蓝色正方形，坏图与TXT均未读。 | pass |
| 内核拒绝接收、后来消息保留、已接受内容不重复 / incident | 公共 API 不提供确定性内核拒绝/精确 admission 时点控制。核对下列窄自动化证据；真实群旅程独立覆盖图片准备失败后的保留。 | pass（自动化补充） |

### Issues

- R1-P1：Severity=major；Regression Relation=direct；Recommended Action=fix-implementation。global 混合图/文件请求虽收到回答，但两个实际相同的红矩形被说成红色正方形、蓝色圆形，不满足“有效图片进入模型并可基于内容作答”。复现及消息ID见上表/JSON；single_thread相同生成图片回答正确。此为用户结果判断，未读实现定位原因。需要用单条独立global旅程复验并由owner调查。

### 自动化测试增量与边界

已核对 [validation.md](M1-fix/evidence/validation.md)：基线相同命令 10 failed/10 passed，修后20 passed；更广 focused 70 passed。测试内容核对：`test_unaccepted_group_input_keeps_buffer_for_next_request` 参数 image/submit；`test_accepting_snapshot_does_not_consume_later_background`；`test_rejected_steer_fallback_does_not_repeat_accepted_background`；resolver 空内容、oversize、corrupt、download exception 及 scoped credential 测试。此类确定性时序/权限补充不冒充真人 HTTP 故障注入。

普通文件类型矩阵 CSV/PDF/Office/archive 用自动化补充，真人旅程使用 TXT。没有客户端界面改动或 must-match 原型；未做视觉 UI 验收。真实代理没有 mock。TXT正文 sentinel 从未要求被读取；该验收证明用户可观察的未读取说明，不以模型自述证明底层无读取副作用。

测试驱动第一版曾把空 running 气泡当稳定结果提前前进；其后重新 GET 终态确认三条 single_thread 回复 completed，报告只引用终态快照。global第二条文件说明最终约144秒后正确返回；混合请求曾并发到达，驱动一度把另一条user消息当新增结果，已以最终agent快照纠正，未作为成功证据。首次群 mention 用错属性（`type=agent id`），未触发回复，不计为产品失败；按现有测试 helper 的 `type=user target_id` 在新群重跑成功。

### Reference Artifacts Reviewed

- incident.md、design.md 与其中 Runbook for Reviewer。
- docs/development/worktree-runtime.md、docs/specs/gateway/relay-protocol.md。
- change-reviewer skill、handoff、regression 模板。
- 公开 OpenAPI、tests/e2e/critical_paths/_im_client.py 与 _im_ws.py（测试驱动）。
- M1-fix/evidence/validation.md 及上述测试断言（仅核对自动化覆盖）。

### 上层文档同步

- [x] SPEC.md：无需更新，架构边界不变。
- [x] docs/specs/gateway/relay-protocol.md：需由 orchestrator 在收尾归并本 unit delta。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## Round 2 — targeted，2026-09-19

Validation snapshot: `30dac3b37 → 800f4dfe3ef818dbbf4db0fd2e1ca322dbdf8089`。caller 仅重启隔离 Gateway 到 PID13964，启动于05:24:52Z；IM6493未变。reviewer 核对 HEAD、进程命令与 node 在线心跳05:24:55.492352Z晚于 caller 的 generation floor。新建 `review567-r2-global` 和 `review567-r2-single_thread`，同真实视觉模型。

受影响项为历史 inline 失败描述与 global 混合附件；Round1 single_thread TXT/来源说明、普通上传坏图错误及恢复、确定性 admission/消费验收继续引用原证据。Feishu indexed图文由自动化补充，本轮未声称外部Feishu真人验收。

- 历史 inline 坏图 targeted：`c_aiqhtew5`，背景 `0956e2a8aca64f71a5aa0215ceac41fd` 含熊猫569、蓝色正方形PNG、坏 inline data:image PNG 与 TXT；请求 `3ec7701b67d1432f8dfcb9b5a7620891`；终态 `0112f3c37fcd43a0a4aeec0e088db09c` 正确回答熊猫569、蓝色正方形，明确坏图未读且内容损坏、TXT未读且入口未自动解析。**pass**。未在此真人旅程制造巨型payload；省略巨型inline说明由新窄红绿测试证明。
- 全新 global 单条混合：`c_lheq3l87`，输入 `4f49220c1907450380ff41a8fe09e4d5` 只发一次红矩形PNG+TXT，约46.2秒后终态 `73b6ebd71c6a4ddcb870bcc622694215`：“我当前只收到图片占位信息，无法可靠判断中央的颜色和形状。普通文件名是 review.txt；其正文尚未读取。MIX567”。**fail**。单条请求排除了前轮并发驱动干扰，有效图像用户结果仍未出现。

### Round 2 Verdict

**fail**；R1-P1 未解决，major 1；Regression Relation=direct；Recommended Action=fix-implementation；Highest Required Action=fix-implementation；needs_re_review=true。本轮新回复明确承认只收到占位信息，尚不能凭此确定源码根因；由 owner 追查真实模型payload。完整输入输出见 [product-round2.json](M1-fix/evidence/product-round2.json)。已通知 caller，没有自行重启或改产品。

报告由 caller 统一提交；report_commit 在本轮写完时未生成。没有对外创建 issue。

## Round 3 — targeted，2026-09-20

Validation snapshot：Nano `fbfa77dfef2c4c3b2eeb6667916ccace8ae3bbd6`；独立 LLM_PROXY `514cd964bb6289d426ddbdbaa7a93200ad67e988`（代理 worktree clean）。本轮只重验 R1-P1/Round2 global 单条混合图像失败及同条普通文件未读说明；其他已通过且未受此代理修复影响的场景引用 Round1/2，不重复冒充本轮实测。

运行身份：最初交接 PID23936 已不存在，reviewer 通知 caller 后由 caller 用 tmux `bugfix567-r3` 恢复；实际 IM `http://127.0.0.1:59643`，PID24658，启动18:15:00+08:00；Gateway PID24737，启动18:15:05+08:00；node `wt-unit-bugfix-567-24615` 在线心跳10:15:36.502656Z晚于启动。代理 PID23777，启动18:13:17+08:00，监听127.0.0.1:4010，cwd为独立proxy worktree。安全提取 Gateway 单个环境变量确认 `NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4010`；未输出凭据。

真实入口：登录本次隔离 `nano` 测试用户，经公开配置 API 新建 `review567-r3-global`，work_mode=global，default_model=`codexOAuth:gpt-5.6-sol`；新会话 `c_go2vcc3x`。上传320×200白底红矩形PNG（红色区域x40..280/y30..170，SHA256 `9633971832d60fbcfb65405ac59d0ed1134b921a5fe76269fb78a0e3b62aa800`）和 `review.txt`（text/plain，正文 `FILE_BODY_HIDDEN_567_R3`）。仅发送一次用户消息 `fc5ed2df3bb547f39facc6121eb9d862`：“图片中央是什么颜色和形状？同时说出普通文件名及正文是否已经读取。最后写 MIX567-R3。”未在提示中告诉模型图形或颜色。

完整公开 API 输入/输出证据：[product-round3.json](M1-fix/evidence/product-round3.json)。本轮未读产品实现定位、未修改产品/测试/配置、未 mock LLM；服务由 caller 清理。

### Round 3 结果与 Verdict

约24.1秒后，终态消息 `85b9f0362f2747aa97b72801d237fb90`（2026-09-20T10:16:17.658928Z，delivery_status=completed）回复：

> 当前消息转录里只显示了图片占位符，我无法可靠判断中央的颜色和形状。普通文件名是 `review.txt`；正文尚未读取（并且我不会读取普通附件）。MIX567-R3

- global 有效图片 + TXT + 文字：**fail**。没有实际识别红色矩形，仍只有占位符说明，不满足 incident 的真实代理端到端图片可见性要求。
- 同条普通文件名、未读说明与文字标记：**pass**。准确保留 `review.txt`、正文尚未读取以及 MIX567-R3；此项不能替代有效图片验收。

**Verdict: fail**。R1-P1 未解决，open issues=1（major）；Regression Relation=direct；Highest Required Action=fix-implementation；needs_re_review=true。虽然同一问题已经历两轮修复，本轮仅观察到用户结果仍缺失，没有足以证明 design 具体矛盾的独立证据，故不机械升级为 revise-design。由 owner 继续核对真实运行链路及修复；本 reviewer 不推断源码根因。

已通知 caller；未外发 GitHub issue。报告与证据按既有交接由 caller 统一提交，report_commit 未生成。

## Round 4 — targeted closure，2026-09-20

Validation snapshot：Nano `fbfa77dfef2c4c3b2eeb6667916ccace8ae3bbd6` + LLM_PROXY `514cd964bb6289d426ddbdbaa7a93200ad67e988`，新代理 process generation。保留 Round3 的真实失败结果；caller 后续指出当时代理 PID23777 启动于18:13:17，早于接线补丁 commit 时间18:14:44，内存仍加载旧模块。本 reviewer 不以 caller 的最小请求成功代替产品验收。

独立运行核对：代理现 PID25542，启动2026-09-20 18:17:24+08:00，**晚于**已核对的 commit 514cd964 时间18:14:44+08:00；监听127.0.0.1:4010，cwd为proxy修复worktree，工作区干净。IM PID24658/59643、Gateway PID24737 保持在线；安全提取Gateway单个环境变量仍为 `NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4010`。node `wt-unit-bugfix-567-24615` 心跳10:17:36.518461Z。

新建全新 `review567-r4-global`，global模式与真实 `codexOAuth:gpt-5.6-sol` 模型；新会话 `c_klohn5m5`。仅发一条用户消息 `4ea22608a2184c85ab5632c4e4da997c`（10:17:57.814408Z）：“图片中央是什么颜色和形状？同时说出普通文件名及正文是否已经读取。最后写 MIX567-R4。”同条含实际红矩形PNG（与Round3同SHA256，320×200白底，红色x40..280/y30..170）和 `review.txt`，正文为 `FILE_BODY_HIDDEN_567_R4`。未在提示中告诉模型颜色/形状，未读实现、未mock；服务仍由caller清理。

原始证据：[product-round4.json](M1-fix/evidence/product-round4.json)。

### Round 4 结果与 Verdict

18.1秒后，终态 `260784d6fc014eefa7d28ce4e3148913`（10:18:15.651907Z，completed）回复：

> 我这里未获得可辨识的图片画面，因此无法可靠判断中央的颜色和形状。普通文件名是 `review.txt`；正文尚未读取。MIX567-R4

**Verdict: fail**。global 单条有效图像的颜色/形状仍未被识别，R1-P1 未关闭；同条文件名、未读说明及标记为 pass。open issues=1（major）；Regression Relation=direct；Highest Required Action=fix-implementation；needs_re_review=true。进程generation已纠正仍不满足产品结果，不能使用最小proxy请求代替完整产品旅程，也不将失败原因擅自归结到某个实现模块。其他未受影响场景继续引用Round1/2。没有新的设计矛盾证据，不机械升级revise-design。

已将消息ID及实际输出交caller。无外部issue；报告由caller统一提交，report_commit未生成。

## Round 5 — targeted closure，2026-09-20

保留Round3/4失败，补充运行配置解释：caller查得前两轮实际请求Host为127.0.0.1:4000，完整llm catalog的YAML base_url覆盖了进程环境的预期值。因此，Round3/4仅核对环境变量不足以证明真实修复代理参与；两轮用户结果仍是fail，但不能据此否定514cd964正确路由后的效果。本轮显式核对生成配置及匹配代理请求Host。

版本仍为Nano `fbfa77dfef2c4c3b2eeb6667916ccace8ae3bbd6` + Proxy `514cd964bb6289d426ddbdbaa7a93200ad67e988`。隔离IM `http://127.0.0.1:60282` PID26555，18:22:49+08:00启动；Gateway PID26829，18:22:51启动，命令明确指定本unit `.gateway-config.yaml`。reviewer仅提取该配置的base_url，结果为 `http://127.0.0.1:4010`。Proxy PID25542，18:17:24启动，晚于补丁提交时间。node `wt-unit-bugfix-567-26523`在线，心跳10:22:53.068384Z。

全新 `review567-r5-global`，global/`codexOAuth:gpt-5.6-sol`；新会话 `c_dblgj574`，仅一条消息 `48d765723f724dbea6d998f48e273bf9`（10:23:18.372363Z）。同条红矩形PNG（与前轮同SHA256）+ `review.txt`（text/plain，正文`FILE_BODY_HIDDEN_567_R5`），要求颜色形状、文件名/未读状态与标记MIX567-R5；未告知模型颜色或形状。原始证据：[product-round5.json](M1-fix/evidence/product-round5.json)。

### Round 5 结果、真实路由与 Verdict

21.1秒内收到终态 `2d7bb2a2683140d8987aaeb9c98e79c7`（10:23:36.631312Z，completed）：

> 图片中央是红色长方形。普通文件名是 `review.txt`；正文尚未读取。
>
> MIX567-R5

独立核对实际proxy raw证据：在修复worktree `logs/raw/openai_codex/` 下，包含MIX567-R5的 `2026-09-20_18-23-24_814`、`18-23-28_257`、`18-23-32_828`、`18-23-36_642` 四个 `req-anthropic_messages.json`，其对应 `headers-anthropic_messages.json` 的 **client_headers.host 均为 `127.0.0.1:4010`**。只提取Host与文件名写入product-round5.json，未输出或提交其他凭据headers。这证明本轮完整产品请求确实经过正确的隔离代理，不再仅凭环境变量推定。

**Verdict: pass**。图片中央颜色及形状识别正确；普通文件名与未读取状态正确；用户文字标记保留。R1-P1关闭，open issues=0；Highest Required Action=pass；needs_re_review=false（针对本轮指定版本与运行配置）。其他既有通过场景继续引用Round1/2；Round3/4失败和配置原因保留，不覆盖历史。

本轮无产品实现/配置改动、无外部issue；报告与证据由caller统一提交，report_commit未生成。服务由caller清理。
