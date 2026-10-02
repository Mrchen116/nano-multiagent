# M1 实施交接

状态：本地实施与集成完成，独立 code review 已通过；产品与 verification 仍有必验现场缺口，详见同目录最新 acceptance/verification 轮次。未归并 canonical spec、未归档、未上线。

## 实现

公司成员批准/停用与管理员边界；持久 refresh 轮换、会话 epoch、单次 WS ticket；入口限流和有界 WS；设备持有证明、本机确认、整机交接及中断恢复；公司范围任务与按群活动入口、保护原聊天来源、真实人类删除授权和幂等回执；受保护附件读取、SSRF 限制、上传配额及失败附件草稿；单进程 public launcher 与日志脱敏。源代码、集成 fixtures 和脚本均在本提交。

## 验证

运行位置：本 unit worktree。Python 使用主仓 .venv，PYTHONPATH=src。

- `pytest -m 'not e2e' -n 4 --dist worksteal -q`：4090 passed，27 warnings，98.25 s（/tmp/feat572-python-final2.log）。随后仅 PA 绑定轮询改为 2 s、备份恢复测试隔离目录修正、群提及删除解析窄修复；相关绑定 11 passed、独立目录恢复 1 passed、公司任务/PA bridge 18 passed。
- frontend `npm test -- --run`：788 passed / 85 files（/tmp/feat572-ui-final.log）；后续新增容量错误翻译测试后 chat-workspace 54 passed、bind 2 passed，`npm run build` 通过。
- Ruff check/format、git diff --check 通过；contract + company + public launcher 167 passed；docs_check 246 maintained / 75 routes 通过。
- `npm audit --audit-level=critical` exit 0，已有 2 low / 3 moderate / 2 high，无 critical；未升级依赖。
- 群聊真实 `<mention .../> 确认删除 Child` 原先被 fullmatch 拒绝，先取得 red，再只移除前导结构化 mention；命名确认仍来自已持久化真实用户消息。裸 yes 不构成命名删除授权。
- 备份恢复测试先证明独立恢复目录缺 message-images 时附件 404，再连同数据库复制私有目录后通过，旧人类/机器凭据失效且重新登录可读取相同附件字节。

真实本地产品证据见 [evidence](../evidence/product-20260930/README.md)，发布/恢复草案见 [public-rollout](../public-rollout.md)。有效证据可复用，无需为角色交接重复全量。

## 授权前的退出标准记录

R6 真实公网域名、免费配置、真实恢复发布现场：需要设计明确要求的当次上线授权；尚未操作 Cloudflare 或生产部署。
R7 真实飞书：专用 E2E Bot 正由 unit-feat-569 使用，未停止其他任务或抢占长连接。
独立 reviewer 应逐项记录 pass/fail/inconclusive，不把自动化覆盖当作真实旅程通过；必须保留这两个缺口。不能据此归档或创建 Ready PR。

## 复审修复批次

- 慢附件响应在发送 response headers 前释放公司准入锁，网络 send 限时；慢消费者不再阻塞停用提交。实际 ASGI 背压与并发停用回归通过。
- 设备确认链接统一使用配置的 public URL；跨主机存量节点登记只接收 Gateway 导出的公钥与指纹，不搬运私钥，操作已补入发布文档。
- 删除回执查询忽略七天前结果，写入时有界清理到期删除回执；create/apply 重试行为保留。
- 全局 Agent 删除从同 agent/session/run 的 `inbox_read_committed` 收集完整读取的人类消息；入口持久化 IM 消息身份，provider ID 仍用于模型来源展示。历史同步、其他运行、未提交或只读部分消息不授予删除资格。IM 仍逐条核对真实人类消息、聊天权限和明确命名范围，模型参数不增加确认字段。
- 实时连接共享现有 transport 状态，显示重连/冷却倒计时和重新登录入口；429 遵守 Retry-After，1013 使用冷却。认证错误改为关联表单的简短红字，与原型一致。

窄验证：公司网络/绑定9 passed；删除回执/公钥登记13 passed；global Inbox/bridge/company tasks31 passed；实时流/App/认证30 passed。全量与独立 targeted 复验结果待下节记录。

## 复审追加的真实回归

- 停用后附件后续分块：200000-byte ASGI 下载，首块65536后停用，旧响应不再发送剩余134464；先red后green。
- 同连接FIFO：先排队heartbeat，再到达HTTP所需config回执，原接收循环timeout；有界串行worker与继续读回执后43窄测通过，实际配置更新跨进程旅程通过。ASGI取消时回收两个owned任务并注销连接，15项断开/任务测试通过。
- 自演化技能：真实stub旅程暴露旧机器凭据PATCH真人配置401。收窄成仅本机Agent技能追加入口，跨节点/真人/吊销/并发版本及原工作模式回归45 passed，真实自演化Skill创建、启用及新会话使用1 passed（20.58s）。
- 既有压缩旅程失败：当前实现与本 unit 开始基线7340a7805独立源码快照均复现summary_records=0；请求记录显示摘要调用得到空的末尾user文本。本unit未改kernel，保留该side finding，不称完整E2E全绿，不扩展内核修复。基线日志/tmp/feat572-compaction-baseline.log，当前/tmp/feat572-gateway-e2e-closure.log。
- 前端全量792 passed/1原测试选择器歧义，收窄查询后Agent edit5 passed；已搬迁超过400行的新测试，测试规范及搬迁用例4 passed。

最终受影响区域回归：IM service + IM unit + contract 763 passed（32.09s），Ruff 与 docs_check 251 maintained/75 routes 通过。其余 Python 基础批次4095 passed，唯一行数规则失败已经搬迁测试并4项复验；未机械重跑未受影响区域。

## 最终冻结版本回归

生产实现保持 `7df455679`。最后全量发现两个旧测试桩仍预期机器 PATCH 完整配置；已对齐本机技能追加 POST 路由，明确仅 `profile_version`/`skills` 两字段，保留静态 Agent 失败隔离和运行中配置边界断言。相关6项通过，无新增生产修改。

- 后端 `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal -q`：**4099 passed / 27 warnings / 84.53s**，日志 `/tmp/feat572-final-all-backend-green.log`。
- 前端 `npm test -- --run`：**793 passed / 85 files / 35.59s**，日志 `/tmp/feat572-final-all-frontend.log`。
- 以上不包含尚未完成的真实公网/飞书验收，也不覆盖已记录的基线压缩 stub E2E 失败。

## 2026-10-01 授权后的真实飞书修复

用户已授权公网部署并接管原专用飞书 Bot。独立 R7 实测发现外部消息进入后无回复，shadow 恢复以新机器凭据调用真人 `/me` 返回401；这是旧身份查询接线未随机器凭据迁移的真实回归，生产尚未切换。

影子同步改用 `GET /im/v1/gateway/identity`，仅返回经 current_gateway 验证的当前 node_id/owner_id；本机核对 node 后使用真实 owner 调和旧 saga。移除真人 token_getter、`/me` 和全节点列表依赖，写入仍使用当前机器凭据。真人管理接口保持原限制，没有凭本地配置授予权限。

先由真实 API 入口测试和拒绝真人接口的 shadow 恢复测试取得2项 red，再修复。影子、图片离线恢复、入口管线、机器身份与授权边界共 **80 passed / 8.46s**（`/tmp/feat572-shadow-identity-batch-green.log`），Ruff/diff检查通过。需由产品 reviewer 复验真实飞书；此前全量4099/793只作为未失效基线，不能预支修复后现场通过。

修复版本 `821ff6ce1` 后端全量 **4100 passed / 27 warnings / 122.45s**（`/tmp/feat572-r7-identity-full.log`），前端无改动，复用793项通过结果。独立静态审查见本目录 code-review.json；真实 R7 已由产品 reviewer 在 acceptance Round 5 关闭，合并48 pass / 4 inconclusive，仅R6未完成。

用户明确纠正执行范围：全部验收与交付收尾均在独立测试环境，用户合入 PR 后才进行正式生产切换。当前测试部署使用全新账号、数据库、附件目录、JWT、设备私钥及节点 `review572-mini`；真实域名仅路由到测试端口18572，生产8011未迁移。此前误用生产副本的迁移预检不作为验收证据；短暂停止的生产Gateway已恢复，不继续操作生产。

公网已完成域名免费计划核对、专用 Tunnel 与 DNS 路由、受保护 IM 启动配置。发现 Access 登录前置后，已按用户要求撤回该错误配置并恢复原定 `im.nanoim.win`，独立测试页面HTTP200。R6仍须由独立reviewer完成浏览器、恢复及旧凭据失效现场验证；不把首页200当作完整通过。

## 最终真实产品验收与清理

独立验收 acceptance Round 6 已收口：**52 pass / 0 fail / 0 inconclusive**，产品版本为 `821ff6ce1`。真实公网浏览器聊天、图片、任务、Work及物理en0直连HTTPS/WSS通过；停测试隧道后入口不可用，独立副本恢复、四类旧凭据失效、原附件哈希及历史一致、同设备重新绑定和恢复后真实回复全部通过。Cloudflare官方页面免费配置已独立核对。此前R7全部真实飞书场景亦通过。

收口已停止本次Mini测试IM/Tunnel和本机测试Gateway，核对18572/51636无监听、目标PID退出、测试tmux退出；保留隔离原始数据和备份供复核。用户要求的8572原型服务继续HTTP200。正式生产未切换，等待用户合入PR后另行执行生产操作。既有R2 UX1 minor与基线压缩stub E2E限制仍按验收报告保留，不宣称所有无关E2E通过。

## 2026-10-02 上游同步

- 合入 `origin/main` 的 `e4ce08c97`（PR #316 / bugfix-574，自定义工具候选列表）。产品代码自动合并；唯一冲突是 `docs/specs/im/agents-nodes.md` 的对齐编号，保留双方编号及契约正文。
- 合并后工具候选集成、capability payload、SDK behavior、上报器、候选投影及 task graph tool/bridge 相关测试：68 passed / 3.79s；docs-check：235 sources / 75 routes；git diff --check 通过。
- 未手改产品实现；既有独立验收保留，以上游相关测试及本次 PR CI 补充集成验证；不将既有公网验收冒充新合并版本重新实测。未执行生产部署。
