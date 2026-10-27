# perf-666 — 产品验收报告

对齐 [motivation.md](motivation.md) 五个 Scenario。独立 reviewer 按 change-reviewer 执行；未读取变更实现定位根因，未改源码或测试。

## 当前结论

**pass（Round 3）**：全部五个 Scenario 已有通过证据；Round 1 渐进显示缺口由真实 Responses 逐片路径补验关闭，Round 2 余额不足保留为已记录的环境限制。没有未关闭的产品验收阻塞项。详见末尾 Round 3；不将前两轮失败历史覆盖为成功。

## Round 1 — 2026-10-27

Validation snapshot: `a78e9498560f6943e934bc29a68e0ac9918270f1 → 25c6d866fb2423fdb0e2d941deabe48a33dd7f76`。

### Verdict

**fail**。4 个 Scenario pass，1 个 fail；1 major 阻塞项。两次真实普通私聊最终正文完整有序，但均只在完成前出现一次全文 delta，未达到“文字渐进显示”。不据此认定本次变更导致回归；调用方补充上游单片条件的归因需与本报告独立观察区分，后续须补齐真实渐进输出证据。

### 环境与范围

- 隔离 IM：`http://127.0.0.1:63180`，账号 nano，node `wt-nano-multiagent-47934`。
- 核对 checkout HEAD 与指定版本一致；PID 47973 的命令指向本 worktree `apps/im-server/lib/main.js`。复用 caller 已核实的构建版本，未重启服务。
- `.e2e-daily.json` 阵容为 P/E/Q + PA；普通私聊增量 `perf-stream`，`single_thread`，`codexOAuth:gpt-6.1-sol` / low。普通私聊 `c_1blssfbq`、群聊 `c_5q26ny3h`；新增 Global P 私聊 `c_jym307ap`。
- 客户端无变更，按 design Runbook 以客户端同一 HTTP/WS API 代驱动：登录、ws-ticket、sync/resume、会话发送/读取、contacts 翻页与详情。未评价未实测的 Web/iOS 视觉，不要求新原型。
- 隔离 DB 增加 110 个 active 真人联系人、私人 owner/Agent、suspended 公司 owner/Agent，及 3 条 watchdog 前置消息。真人 fixture 使用现有测试账号的密码哈希，仅留隔离 DB，不输出凭据。数据库只用于准备前置，判定来自真实服务 HTTP/WS。
- 原始证据：`/Users/czj/.codex/reports/perf-666-product-acceptance-20261027/`。`events.json` 按 canonical event_id 去重（两段观察窗口有重叠连接）；`contacts-and-watchdog.json`、`messages-*.json` 和 `stream-summary.json` 保存结果。未触达生产/Feishu，未向真人外发。服务由 caller 统一关闭。

### 用户旅程体验

用户可读取完整有序的长答案，刷新历史后正文与 WS 终态相同；群聊只见最终答案，Global 显式交付也只形成一次正文。联系人搜索、翻页和详情可稳定找到同一对象，无权对象不出现且详情拒绝。停滞回复有明确失败反馈并保留已有内容，持续活跃长运行没有被误杀。

未满足的实际体验是长回复正文的等待过程：60 行约 64 秒后一次出现 2,028 字；180 行约 249 秒后一次出现 9,130 字。中间有存活事件但没有正文增量，故不能称为渐进显示。此处记录真栈结果，不把最终完整性等同于流式体验通过。

### Reference Artifacts Reviewed

N/A：无客户端源码变化，无 prototype / must-match 视觉契约。读取 motivation、design Runbook、current auth-tenancy、conversations-messages、gateway-relay、routing-delivery 与共同体验标准；不以实现者测试成功叙述代替验收。

### 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 | major | 两轮普通私聊仅一次全文 delta，随后 44ms / 36ms 内 completed；没有可观察的渐进正文 | 阻塞“长回复逐步显示并完成”。caller 核实真实模型逐片输出前置后补验；本报告不推断实现根因 |

### 验收标准覆盖

#### Requirement: 普通私聊回复保持完整且顺序正确 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据与实际结果 | 结果 |
|---|---|---|---|---|
| 长回复逐步显示并完成 | motivation.md 同名 Scenario；current gateway-relay | 真模型 ordinary single_thread 私聊分别请求 60/180 条编号中文建议，观察 WS 后读取历史；以 current 不变性对照 | `stream-summary.json`：消息 `8846f16d2dd24a9cab43445b4230c5e9` 2,028 字、编号 1–60 恰好一次；`baa3754bb911497d931eca24996d6d27` 9,130 字、编号 1–180 恰好一次；delta 拼接等于 completed；但各只有 1 次全文 delta，分别在 04:10:05.447Z / 04:14:52.229Z 出现，44ms / 36ms 后完成，未渐进 | fail |
| 群聊与显式回复维持原行为 | motivation.md 同名 Scenario；current routing-delivery/gateway-relay | 使用客户端规范 `<mention type="user" target_id="…"/>` 点名普通 Agent；Global P 明确要求使用显式发送 | `events.json` + 两会话历史：群聊回复 `0922bec078dd4800bb083fec6e91af2f` 327 字，包含 GROUP666_BEGIN/END，0 次正文 delta，最终 completed；Global 消息 `baaef704c26649a09d3354342309af06` 仅 `EXPLICIT666_OK` 一次，无结束哨兵/重复答案。前两条普通 @文本未触发，不作为群聊通过依据 | pass |

#### Requirement: 聊天超时判断保持原语义 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据与实际结果 | 结果 |
|---|---|---|---|---|
| 活跃和停滞回复 | motivation.md 同名 Scenario；current gateway-relay liveness | 隔离 DB 准备 8 分钟前 running 消息：近期活动、停滞有正文、停滞空正文；真实服务默认 30s 扫描/120s 阈值收口，通过 HTTP/WS 验证 | `contacts-and-watchdog.json`：active 仍 running 且正文保留；stalled failed 且原文后追加 `relay idle for 120s with no new event`；empty failed 填充同一反馈。`events.json` 04:09:45Z 两条 relay.failed；active 的活动停止后于 04:11:45Z 也正常失败。真实 180 行 run 在约249秒内持续 heartbeat 并最终 completed，未被误杀 | pass |

#### Requirement: 联系人搜索和访问边界不变 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据与实际结果 | 结果 |
|---|---|---|---|---|
| 连续翻页与搜索 | motivation.md 同名 Scenario；current auth-tenancy | 建立固定联系人数据，经客户端 contacts API 连续翻页、human/agent 筛选、Unicode 大小写搜索并逐项打开详情；按 current 不变性和已知 fixture 集合对照 | `contacts-and-watchdog.json`：all 50/50/16 共116唯一项，human 50/50/11 共111项，agent 5项；搜索 `école` 匹配显示名 ÉCOLE 的110人，分页50/50/10。各列表 user_id 有序，无重漏；110 fixture 全数出现；116个详情 status200且与列表对象完全一致 | pass |
| 不可见对象 | motivation.md 同名 Scenario；current auth-tenancy | 同一登录用户查询其他私人 owner/私人 Agent，以及 suspended 公司 owner 的公司 Agent，列表及直接详情交叉核对 | `contacts-and-watchdog.json`：`perf666-private-owner`、`u-perf666-private`、`u-perf666-disabled` 均不在列表，详情均404 `contact not found` | pass |

### 上层文档同步

- [x] `SPEC.md`：无需更新，跨包边界无增量。
- [x] `docs/specs/`：无需更新，本 unit 承诺行为不变；渐进输出缺口不可通过改写 current 标准放行。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — 真实逐片模型前置补验，2026-10-27

Validation snapshot 不变：`a78e9498560f6943e934bc29a68e0ac9918270f1 → 25c6d866fb2423fdb0e2d941deabe48a33dd7f76`。产品及服务未重启/修改；caller 在本隔离实例新增普通 Agent `perf-stream-incremental`，`deepseek:deepseek-v4-flash` / high，私聊 `c_o5rdh8g3`，记录于 `.e2e-perf-666.json`。

**Verdict: fail（必要前置阻塞，未关闭 Round 1 问题）。** caller 提供的只读归因指出首轮 Sol 代理先收集完整响应再单次输出；这是 caller 的上游诊断，不替代 reviewer 的渐进输出证据。本轮独立请求 50 条建议后，真服务于 `04:16:59.408Z` 发布消息 `7f36572d2cb749639b202d1096a96a8a` 的 `message.completed`，`delivery_status=failed`，正文明确为模型 `402 insufficient_balance_error / Insufficient Balance`，0 次 delta。

| Scenario | 本轮证据 | 结果 |
|---|---|---|
| 长回复逐步显示并完成 | `round2-events.jsonl`；真实模型因余额不足失败，不能验证渐进或完整性；Round1 fail未关闭 | inconclusive |
| 群聊与显式回复维持原行为 | retained：Round1 真栈证据，未改产品/原Agent配置 | pass |
| 活跃和停滞回复 | retained：Round1 真服务收口与长运行证据 | pass |
| 连续翻页与搜索 | retained：Round1 固定联系人集合与116项详情证据；新增测试Agent不使该历史集合验证失效 | pass |
| 不可见对象 | retained：Round1 非法访问真实HTTP证据，资格数据与产品未改 | pass |

新增阻塞：需可用的真实逐片模型前置。未尝试充值、修改外部模型账户或扩大授权。观察脚本已停止，无自启服务需关闭。

## Round 3 — 可用真实逐片路径定向补验，2026-10-27

**Verdict: pass。五个必验 Scenario 均通过；0 个未关闭产品问题。**

### 版本与前置

实际运行产品仍为 `25c6d866fb2423fdb0e2d941deabe48a33dd7f76`，executed_base 仍为 `a78e9498560f6943e934bc29a68e0ac9918270f1`。checkout 此时为 `54b1214c8d52dc1645df3b526756b9b2d2353a2a`；独立核对两 commit 的 changed paths 全为 docs，不将新 checkout 冒充已重启的产品版本。

caller 通过正常产品 setup API 在原隔离实例新增 custom 服务与普通 Agent `perf-stream-responses`，私聊 `c_1dbq8zsh`，同一真实 `codexOAuth:gpt-6.1-sol` 模型，经 `openai-responses` 协议连接既有本机代理。manifest 为 `.e2e-perf-666.json.responses`。产品、代理及运行服务未修改/重启；无充值、购买或生产改动。此配置变化只改变验收前置，不替代实际观察。

### 实际旅程与决定性证据

请求 50 条中文读书笔记建议，以 RESPONSES666_BEGIN/END 标记首尾，每个编号恰好一次。真实消息 `4cf11105b8ba46919c69762930dd8685`：

- 04:21:15.877Z 首次正文增量，至 04:22:09.391Z 共 **270 次 message.delta**，跨越 **53.514 秒**；在完成前持续有新正文，确认渐进交付。
- 04:22:09.581Z `message.completed`，最终 **1,868 字**，编号 **1–50 完整、顺序正确且各出现一次**，首尾标记完整。
- 按接收顺序拼接 270 次 delta **严格等于 completed 全文**；通过真实 HTTP 重新读取的历史正文也严格相同。末片先于 completed，未出现重复正文或缺尾。
- 自启观察脚本正常退出；未启动额外服务。服务仍由 caller 统一清理。

证据目录同前：`responses-events.jsonl`、`responses-summary.json`、`messages-c_1dbq8zsh.json`。这证明用户侧实时正文与最终交付，不声明未实际测量的吞吐指标、慢 ACK 性能或视觉布局。

### 必验 Scenario 最终覆盖

| Scenario | 本轮裁决与证据 | 结果 |
|---|---|---|
| 长回复逐步显示并完成 | 本轮真实逐片输出270次、跨53.514秒；拼接/终态/历史严格一致，50条无重漏。关闭Round1唯一major缺口及Round2前置阻塞 | pass |
| 群聊与显式回复维持原行为 | retained：Round1普通群聊0草稿delta + 完整最终正文，Global显式发送一次，无哨兵/重复；产品与原Agent配置未改 | pass |
| 活跃和停滞回复 | retained：Round1真实服务watchdog与249秒活跃运行证据；产品未改 | pass |
| 连续翻页与搜索 | retained：Round1静态fixture集合50/50/16分页、Unicode搜索110项及116详情一致；新增独立测试Agent不改变原受验集合证据 | pass |
| 不可见对象 | retained：Round1私人及停用公司对象列表不可见/详情404；资格与产品未改 | pass |

上层文档更新判断保持Round1结论：无需修改current行为契约。原Sol转换路径的单片输出与DeepSeek余额不足保留为真实环境限制，不称为本次产品回归；本轮通过来自独立的真实渐进结果，而非caller归因说明。
