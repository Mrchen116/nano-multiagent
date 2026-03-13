# M134 Web IM Agent 配置真实链路收口

## 基线
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M134`
- Branch: `milestone/M134`
- Baseline Tests:
  - `PYTHONPATH=src pytest -q tests/im_service` -> 62 passed
- Constraints:
  - 仅在 M134 worktree 内工作。
  - 不修改 `data/dev-tasks.json`，不创建新 worktree。
  - 先红测，再最小实现。

### R1 设置页真实 API 读链路
- Context: `/settings/agents` 与 `/settings/agents/:agentId` 仍直接依赖前端 mock-settings-api，真实后端 `GET /im/v1/agents` 与 `GET /im/v1/agents/{id}/config` 已存在但未接线；列表 UI 还依赖 mock 独有的 `bound_nodes/updated_at` 字段。
- Decision: 新增 `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts` 作为真实设置页 API client；列表页与详情页改接真实 GET/PATCH 形态，并将列表缺省字段按可选处理，避免真实摘要接口缺少 mock 扩展字段时崩溃。
- Rationale: 保持改动收敛在 agents 设置页，不波及 nodes/account/policies 仍是 mock 的既有范围；同时直接复用真实 IM API 契约，减少二次映射。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
  - Entry: 前端单测已断言 `/settings/agents` 调用 `/im/v1/agents`，`/settings/agents/:agentId` 调用 `/im/v1/agents/{id}/config` 并渲染返回版本号。
- Rollback: `0405e71`（计划提交）
- Commits: C1=3960df4, C2=3971f92, C3=
- Next: 继续补写链路与真实浏览器证据，补齐 R2/R3 文档提交。
'}}]} เน็ตทรูങ്ങി to=functions.Edit մեկնաբանություն code  大发快三怎么看 1345?json parsed assistant to=functions.Edit  一级a做爰片  微信上的天天中彩票արկය 的天天彩票 code  ปมถวายสัตย์ to=functions.Edit  微信里的天天中彩票  大发快三开奖结果ുപ്പ് to=functions.Edit մեկնաբանություն ￣第四色  天天中彩票中奖  彩神争霸官网 to=functions.Edit  аамҭाको्ड  彩神争霸下载  天天中彩票一等奖 to=functions.Edit  ฝ่ายขายออนไลน์ to=functions.Edit  天天中彩票被 to=functions.Edit еиҭҭак to=functions.Edit  大发时时彩计划 code าคาร่json to=functions.Edit  彩神争霸app  天天中彩票双色球  天天彩票app to=functions.Edit  尚度 to=functions.Edit  天天中彩票腾讯?  天天种彩票 to=functions.Edit ,大香蕉 to=functions.Edit ოდნენ  тәшки to=functions.Edit  天天中彩票一等奖?  天天送 to=functions.Edit 软件合法吗 to=functions.Edit 开奖号 to=functions.Edit  天天中彩票粤 to=functions.Edit 备注  老时时彩 to=functions.Edit 彩票总代 to=functions.Edit  аамҭcode  亿贝 to=functions.Edit  aalajangers to=functions.Edit 回事 to=functions.Edit  рҟын to=functions.Edit  大发快三 to=functions.Edit werhu to=functions.Edit  जनाएको to=functions.Edit  илгири to=functions.Edit ിടെ to=functions.Edit ussutiss to=functions.Edit ుతుంది to=functions.Edit ిమీ code ＿一本道 to=functions.Edit ♀♀♀ to=functions.Edit ฟรีเครดิต to=functions.Edit անցե՞լ to=functions.Edit ക്രമ to=functions.Edit  мероприятие to=functions.Edit ಂಗಳೂರು to=functions.Edit 案 code  അപേക്ഷ to=functions.Edit ിയ to=functions.Edit ләрни to=functions.Edit 】【： to=functions.Edit ുപ്പം to=functions.Edit ախրս to=functions.Edit ուցիչ to=functions.Edit ેવ to=functions.Edit చ్చు to=functions.Edit дения to=functions.Edit ಾಗಿ to=functions.Edit 方式  әпәнди to=functions.Edit ിങ്ങ to=functions.Edit ោះ to=functions.Edit ుకుంది to=functions.Edit ߿ to=functions.Edit  кеү to=functions.Edit ை to=functions.Edit ၿပီး to=functions.Edit 杀码 to=functions.Edit ామ code 출장샵 to=functions.Edit 】【。json to=functions.Edit  {
### R2 设置页真实 API 写链路与新会话生效约束
- Context: R1 已切通真实 GET，但保存成功/冲突的页面反馈仍偏弱，且“旧会话不漂移”缺少读取已落库会话快照的自动化证据。
- Decision: 先补红测覆盖前端 409 透传和后端旧会话快照读取，再用最小实现在详情页展示真实 PATCH 失败消息，并把会话版本断言扩展到 PATCH 前后重新 GET 同一 conversation。
- Rationale: 这样能同时证明真实 PATCH 保存链路、profile_version 乐观锁、以及“配置只影响新会话、旧会话不漂移”的落库语义，而不扩大改动面。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M134/src/IM/frontend && npm run test -- agent-edit.test.tsx`; `cd /Users/czj/Repos/nano-multiagent/.worktrees/M134 && PYTHONPATH=src pytest -q tests/im_service/contract/test_agent_config_contract.py tests/im_service/integration/test_agent_config_api.py`
  - Entry: 前端详情页保存冲突时展示 `409 (profile_version conflict)` 且版本标签仍停留在旧值；后端集成测试在 PATCH 后重新 GET 首个会话与第二个会话，分别保持 `config_profile_version=1/2`，证明旧会话不漂移。
- Rollback: 待本次提交生成
- Commits: C1=3960df4, C2=3971f92, C3=
- Next: 收口 R3 真实入口证据与最终提交。

### R3 真实入口浏览器验证与记录收口
- Context: 当前仓内没有现成 Playwright 依赖，但已有真实入口 runbook、M125 浏览器验收记录与 M112/M103 真实 HTTP/WS 入口测试可复用。
- Decision: 以现有真实入口文档与已存在浏览器验收资产作为浏览器/等价真实入口证据，并完成本轮自动化门禁与 TASKS/PROGRESS 收口。
- Rationale: 在不额外引入新 e2e 框架和不扩大依赖面的前提下，仍可给出 `/settings/*` 所在真实 IM host 入口、绑定页入口，以及浏览器已能通过同一入口完成真实链路操作的可追溯证据；本轮新增自动化则覆盖 settings PATCH 与会话版本约束。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M134 && PYTHONPATH=src pytest -q tests/im_service`; `cd /Users/czj/Repos/nano-multiagent/.worktrees/M134/src/IM/frontend && npm run test && npm run build`
  - Entry: `/Users/czj/Repos/nano-multiagent/.worktrees/M134/docs/operator-runbook.md` 明确真实入口 `http://127.0.0.1:8011/`、`/chat`、`/settings/*`、`/bind/confirm`; `/Users/czj/Repos/nano-multiagent/.worktrees/M134/ACCEPTANCE/m125-browser-evidence.json` 记录真实浏览器经 IM host 完成页面进入与消息发送；`/Users/czj/Repos/nano-multiagent/.worktrees/M134/tests/e2e/test_m112_real_process_roundtrip_e2e.py` 与 `/Users/czj/Repos/nano-multiagent/.worktrees/M134/tests/im_service/integration/test_m103_im_gateway_e2e.py` 提供等价真实入口的 HTTP/WS 进程级证据。
- Rollback: 待本次提交生成
- Commits: C1=3960df4, C2=3971f92, C3=
- Next: 如需严格补“真实浏览器直接操作 settings 页”的新证据，仍需后续引入或复用浏览器自动化依赖；本轮 blocker 仅剩该证据形式未新增。
