# Verification Report: feat-572-public-im-protection

> 最终结论见末尾 Round 7：实际产品/实现固定 `821ff6ce1`；R7/R6独立报告均已落盘，产品52 pass /0 fail /0 inconclusive。Verification **pass**，corrected-delta **aligned**，CRITICAL/WARNING为0；code-review沿用pass（`[]`）。正式生产切换不属于本次隔离验收，不将文档/evidence SHA冒充运行版本。前轮失败与问题数保留历史，不代表当前门槛。

> Round 1 · verification_mode: full · executed_base: `7340a7805` · validated_at: `d5de5f9f7abeb33a3ba2959d8ef602ea0b222b96` · branch: `codex/feat-572-public-im-protection`
> 固定版本独立审查；审查者未实施该版本，只写本报告与 code-review/evidence。工作目录为 `.worktrees/unit-feat-572`。后续工作区修复不改变本报告基线。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | R1–R4、W2/W3 大部分有实现与适用证据；R5 有确认问题；R6/R7 未验收；W1 对照证据不完整；W4 迁移流程有缺口 |
| Correctness | 核心公司资格、对象 ACL、持久 refresh、整体交接、公司任务与附件配额有直接实现；发现 HTTP 慢响应持全局锁及绑定 HTTPS 地址错误 |
| Coherence | 架构包边界保持；删除回执有限保留和跨主机旧设备登记未完整落实 |

**Verdict: fail。4 CRITICAL、4 WARNING、0 SUGGESTION。不能宣称 M1 完成、归档或创建 Ready PR。**

`requires_full_verification: false`（这是 full 首验，修正已知问题可按影响范围 closure；若修正扩大共享边界则重新判断）。R6/R7 是真实退出标准未完成，不是推定代码漏洞；当前 canonical 未归并属于正确 active 阶段，不列为实现缺陷。

## Completeness

当前采用简化实施流程，`implementation.md` 是正式交接；不强制额外 tasks/progress 文件。下表只核证据链与契约，真实体验 pass 由独立产品 reviewer 决定。

| M1 退出标准 | 已有证据 | 状态 |
|---|---|---|
| R1：pending→批准→公司，停用覆盖浏览器/机器/缓存 | company_membership 集成、company-access UI；pending/suspended-live/suspend-impact 图；新旧 HTTP/WS 拒绝记录 | 通常路径 covered；慢下载阻塞停用见 C1 |
| R2：管理者边界、确认取消、共享 Work/原对象 ACL | current_company_admin、policies；company_membership 与原 member_permissions/agent_work 套件；ordinary-me/policies-readonly/suspend-impact | covered；不将静态核对称为独立产品验收 |
| R3：两 owner/Gateway、A/B 群同图、活动保留、来源保护及回聊草稿 | two-owner-task-results.json，group-tasks-a/b、group-a-retained、group-empty、task-node-b、protected-root、task-return；公司任务/bridge 窄测18 passed | covered；删除回执窗口偏离见 W2 |
| R4：本机交接、停用旧 owner、旧身份失效、IDs/历史保留及恢复 | device_binding unit/protocol 集成；bind-accept/await-local/complete、handoff-result；恢复11 passed | 新/已登记节点 covered；存量缺公钥跨主机迁移见 W3 |
| R5：冷却、附件逐项反馈/仅文字、容量 admin、慢连接反馈、SSRF/日志 | auth limits/tickets、bounded_socket、message_images、resolver/Feishu source 限制；attachment/capacity-* 与 launcher redaction evidence | partial：C1、W1、W4；真实 Feishu 图片仍 R7 未验 |
| R6：当次授权后真实域名/免费项/恢复/旧令牌 | public-rollout 操作草案，本地恢复集成与 redaction | inconclusive / 未执行；见 C2 |
| R7：专用 Feishu 真实往返、资格/能力、群背景及离线自治 | 实现接线与本地自动化；专用 Bot 被 feat-569 占用 | inconclusive / 未执行；见 C3 |
| W1：所有 must-match 双视口与对照结论、构建/i18n/路由 | product-20260930 截图 + 原型基线；build/788 frontend + 后续54/2窄测 | partial；见 C4 |
| W2：身份矩阵、refresh/停用并发、绑定重放/修订/迁移/恢复 | company_membership、gateway_auth_boundary、device_binding unit/protocol、原 gateway/user-stream 套件 | covered（慢 HTTP 响应未被现有并发用例覆盖） |
| W3：跨 owner任务/群关联/保护来源/删除/配额/SSRF接线，真实Agent | company_task_graphs、message_images、image_attachment_resolver、task_graph_bridge；两真实 Gateway 工具聊天及投影 | covered；回执到期缺实现 |
| W4：检查、架构、版本、备份/恢复及部署配置 | 4090 Python、contract+company+launcher167、Ruff/docs_check/git diff记录；本地独立目录恢复 | partial：已有公钥缺失的双主机迁移流程不可执行；公网恢复发布现场仍 R6 |

## Correctness

13 项 Requirement 的全部场景按同一风险链映射；Q11/Q12/Q16 为最新目标，旧任务 owner/chat 隔离讨论不作为本次契约。

| Requirement / Scenario（首文档位置） | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 公网访问、公开注册、pending/批准、普通人与匿名不能批准/读公司（spec:200–229） | auth_service.register、CompanyBoundary、deps.current_user/company_admin、require-auth/membership | company_membership、company-access；pending截图 | 本地身份 covered；真实公网 C2 |
| 停用既有请求/实时/机器，历史保留，不转移/关闭主机（233–256） | company_service.transition、company route、gateway_sessions.revoke_owner、auth_sessions、bounded_socket | company_membership 含上传撤销竞争；gateway_auth_boundary；suspended-live | slow HTTP download 违例 C1；其余 covered |
| 来源/账号限流、来源不能伪造、共享网络恢复（261–277） | public_boundary.client_source/limits、auth routes、auth_limits、use-auth-cooldown | company_membership throttle/恢复，auth表单 suite | covered；CF 真实路由状态仍 C2 |
| refresh轮换/并发/登出/重启失效（281–292） | auth_sessions.rotate/revoke/valid、auth_service._decode | company_membership 与 auth_service suite；恢复测试 | covered |
| policies admin、新注册不升权、共享Work、原聊天/附件/owner及共用设备（297–318） | deps、policies route、Work API 与原对象权限；agent config mirror窄机器入口 | company_membership、原 member_permissions/agent_work/config suite | covered；没有把 Work 共享反当聊天权限 |
| 本机整体换绑、只知node无权、pending/suspended目标拒绝、停用原owner可交接（324–340） | infra.device_binding、routes.device_binding、PA.device_binding、manifest install_handoff | device_binding unit/protocol、handoff evidence | 功能 covered；HTTPS W1、旧机迁移 W3 |
| 公司共享全图、私聊/无来源图、受保护来源、两Gateway、身份/工具能力、按需读、Feishu主体（346–374） | task_graphs.execute/_project_chats、repository.actor_user、PA bridge | company_task_graphs、ownership、bridge；two-owner/图截图 | 本地 covered；Feishu现场 C3 |
| 全员经Agent维护、明确删除、真实来源、revision不覆盖、写主体边界、外部写（380–407） | task_graphs来源/regex/delete、domain.delete_subtree、receipt、PA可信run上下文 | company_task_graphs 拒绝model confirmed/否定请求/mention确认/回执/稳定ID；窄测18 | covered；到期窗口 W2；外部现场 C3 |
| 群任务入口、A/B同图不同节点关联（412–420） | task_node_chat_activity、record_activity/activity、GroupTaskPanel、task-graphs return_chat | company_task_graphs、task-graphs UI、two-owner截图 | covered |
| 退群不撤任务资格、解散群任务保留（426–432） | 公司图list/get，activity FK仅删除关联，原conversations删除 | company_task_graphs及原group流程 | covered |
| 正常Web/渠道附件、伪造URL/越权引用失败、文本外链保留（437–443） | image_attachment_fetcher保护IM origin/path/无redirect，provider资源API，reply_images文本链接，resource ACL | image_attachment_resolver与message_images、Feishu rich_messages、reply_image_public_sources | 本地接线 covered；真实provider往返 C3 |
| 超限请求/累计配额、文字继续、实时有界且可恢复（448–459） | upload_chunks/put_stream、attachment_storage配额、message-pane failed chips/onlyText、BoundedSocket | message_images容量并发/断流重启、chat composer、capacity/text-only evidence | HTTP网络等待 C1；实时可行动反馈 W4；回执增长 W2 |
| 仅IM HTTPS、证据不泄secret、恢复、免费配置（463–479） | public_server single worker/loopback/redaction、runbook与恢复SQL | launcher测试与握手redaction、restore集成 | 本地 covered；链接 W1、迁移 W3、真实公网/免费恢复 C2 |

## Coherence

| Design 决定 | 遵守情况 | 代码/证据 |
|---|---|---|
| 单IM实例单公司；保留包依赖边界，不增加内核HTTP | 是 | IM/PA通信HTTP/WS，无kernel/coding_cli差异；复用167 contract证据 |
| 默认公司门禁 + 原对象ACL；admin不继承他人资源 | 是 | CompanyBoundary/current_user及每路由对象依赖 |
| 撤销以DB提交为界，网络慢消费者不能占无限资源 | 部分 | 上传发布在gate复核、socket发送有界；HTTP响应全程占gate，C1 |
| 持久refresh/sid/epoch，WS一次票据与Origin | 是 | auth_sessions与user websocket；生产query脱敏 |
| 本机私钥证明 + active接收人 + 本机确认 + 整机事务/epoch/AAD恢复 | 是（迁移操作缺口） | device_binding、PA rewrap、manifest；旧无钥节点需CLI且跨机公钥导入缺失，W3 |
| 公司任务、多对多群活动、独立群生命周期、来源按ACL | 是 | task_graphs/repository/schema；activity采用独立chat endpoint和updated_at，可观察群视图语义一致，不因字段或路由调整单列缺陷 |
| 明确真人删除、revision/receipt、不级联掉回执但有限7天 | 部分 | 删除授权/稳定ID/事务满足；schema移除FK后未接到期清理，W2 |
| 自动附件只许可IM/provider/bytes，有界流/额度 | 是 | IM/private images、PA IM fetcher、Feishu资源stream、reply_images；provider真实验收仍 C3 |
| 公网URL来自明确配置、免费Tunnel、不公开其他入口 | 部分 | public launcher通过；binding URL仍request.base_url，W1；实际CF未执行C2 |

### Prototype / Reference Contract

仅核 explicit contract 与证据链，不评分审美。已实际查看 bind-complete-390、attachment-partial-failure-390、group-tasks-a-1440 和 prototype group-tasks-390：本机确认结果、逐文件草稿反馈、当前群列表、真实Task ID对应均可见。

| Must-match | Milestone | Implementation | Durable evidence（product-20260930/） | 状态 |
|---|---|---|---|---|
| 登录/注册/pending/suspended/冷却输入保留 | R1/W1 | AuthPageFrame/RequireAuth/Membership/Cooldown | pending-390、suspended-live-390；无完整产品双视口冷却/错误对照 | partial C4 |
| 管理员桌面头像/手机Me→成员；批准/停用取消失败 | R2/W1 | UserMenu/Me/CompanyMembersPage | ordinary-me-390、suspend-impact-390；无完整产品桌面入口/失败对照 | partial C4 |
| 全局Tasks沿用图/详情/来源保护，当前群→同图→回聊草稿 | R3/W1 | TaskGraphsPage/GroupTaskPanel/ChatWorkspace | group-tasks-a-1440、b-390、empty-b-390、node-b-390、return-1440、protected-root-390 | 有覆盖；全must-match双视口仍C4 |
| 本机→链接→接收/换号→整机→本机→结果，取消/过期/中断 | R4/W1 | BindConfirmPage/PA CLI | bind-accept/await-local/complete-390、handoff-result.json；无完整桌面/失败对照 | partial C4 |
| 单文件/容量/格式/网络/冷却，逐文件草稿保留/移除/重试/仅文字 | R5/W1 | MessagePane/upload error | attachment-partial-failure-390、text-only-retains-files-390、capacity-*；无完整双视口网络/冷却/发送失败对照 | partial C4 |
| admin专属容量+成员只读，原六字段/双卡/保存失败草稿 | R5/W1 | PoliciesPage/admin endpoint | policies-readonly-390、capacity-full-admin-390；缺产品桌面/保存失败重试对照 | partial C4 |

C4 不要求机械逐像素相同；要求已有明确 must-match 在两个 viewport 具有可复查实际对照。原型截图不等同产品截图，自动化DOM不补足现场视觉证据。产品 reviewer 后续补证可以关闭此项。

## Issues

### CRITICAL

- **C1：慢附件 HTTP 响应阻止停用和全体操作。** 契约：design:75–79、spec:235–254、M1-R1/R5。实际：`src/IM/api/public_boundary.py:102/129` 持gate覆盖整次下游ASGI send；`message_images.get_image/get_attachment` 返回FileResponse。隔离复现见 `repro-results.json`：send body 未释放时 suspend 未完成且仍active，释放后200。建议只在准入及副作用提交需要的范围持锁，HTTP网络写出有界且复核撤销，补一个慢下载/停用竞争的公开ASGI回归；不能只加更长timeout。
- **C2：R6实际公网、免费项及真实恢复发布现场未完成。** 契约：design Milestones M1-R6、spec:202–207/465–479。实际：implementation:未完成退出标准、public-rollout:3/14–18明确尚未发布，当次授权/CF权限未确认。建议在取得设计要求的当次上线授权后按限定入口做真实域名与恢复验收，保留免费项和真实HTTP/WS证据；不以本地200/hosts/Tailscale代替。
- **C3：R7真实飞书必验路径未执行。** 契约：M1-R7及spec Q16/374–379/407–411。实际：implementation及product evidence记录专用Bot被另一unit占用；自动化模拟不能证明真实provider图片、主人识别、群背景、@Bot和离线正常对话。建议待专用Bot释放后复用成熟流程验证资格/能力矩阵及真实往返；不抢占其他unit。
- **C4：W1全部must-match产品双视口对照证据不完整。** 契约：design:178–188/M1-W1。实际：上表截图链主要为390，1440仅若干任务旅程；无全部入口/错误态桌面产品截图和逐项对照结论。建议由产品reviewer补真实桌面/窄屏检查与durable对照，不能仅凭原型已验或788前端绿声称W1完成。此项是验收证据缺口，不据此推定视觉实现失败。

### WARNING

- **W1：绑定确认链接降级为HTTP。** 契约：配置公开入口、HTTPS与M1-R4/R6。实际：`src/IM/api/routes/device_binding.py:47`，`src/IM/cli/public_server.py`关闭代理头并通过HTTP源站，`PA gateway/device_binding.py`直接open bind_url。复现配置https仍生成http。建议使用app.state.public_url生成链接；覆盖受信HTTP源站/HTTPS配置，不引入无约束代理信任。
- **W2：删除回执有界七天保留缺实现。** 契约：design:125。实际：`src/IM/infra/task_graph_schema.py:15`移除FK、`repositories/task_graphs.py:205`写回执后无清理；全src检索只有create/read/insert/migrate。`receipt-results.json`中2000年回执启动后仍有2条且delete重复可用。建议有界清理到期回执，并保护窗口内结果重试；不增加通用清理平台。
- **W3：存量缺公钥节点的跨主机迁移操作不可完整执行。** 契约：design启动迁移/本机私钥保持与M1-W4。实际：`public-rollout.md:10`只有bind；`DeviceBindingStore.start`旧nodes缺key直接拒绝；现有`IM/cli/enroll_device.py:25/63`必须同时读取私钥文件和IM本机DB，无仅公钥导入。两主机Gateway私钥与Mini IM DB不共存。`test_legacy_node_cannot_acquire_remote_key`以及本地enrollment测试证明该门禁和单机路径。建议最小本机公钥导出、源站本地导入/核对key_id操作并写入runbook，保持私钥不离Gateway且公网关闭时登记；不能通过复制私钥或HTTP补钥绕过。
- **W4：票据拒绝/慢连接缺可行动用户反馈。** 契约：agents-nodes delta“票据签发失败与资格撤销”、M1-R5。实际：`user-stream/index.ts:47`仅console.error，runtime:326–351票据失败/close只有重连；onclose无CloseEvent/状态发布，不能显示等待/重新登录或慢消费者提示。建议复用已有反馈组件暴露受控连接状态及适当等待/重试，不添加新身份旁路。核心服务器限制已实现，此项为前端实质契约偏离。

### SUGGESTION

无。未把字段/路由实现选择、canonical待归并、共享Work的既定隐私模型或假设攻击量当缺陷。

## Evidence and Commands

复用 `implementation.md` 记录的4090 Python、788 frontend、167 contract/company/launcher、后续11/1/18/54/2窄测、build/Ruff/docs_check；独立读取 `/tmp/feat572-python-final2.log` 与 `/tmp/feat572-ui-final.log`末尾确认总数。日志/DB/私钥均不提交，当前snapshot与后续窄修关系以实施交接为准。

独立追加仅必要核验：

1. `IM_PUBLIC_URL=http://testserver PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/im_service/integration/test_agent_config_api.py::test_get_agent_config_prefers_live_gateway_snapshot` → **1 passed / 0.33s**。真人source=live的`agent.config`响应在runtime RPC白名单，绕过gate；等锁循环候选 **REFUTED**，未在50620发挂起请求。
2. 隔离ASGI脚本：create_app(public_url=https, db=本unit output私有DB)，HTTP origin=http模拟Tunnel；start产生绑定链接，只保存scheme；注册/激活fixture、创建群、上传文本；GET附件的send body由Event暂挂；并发suspend超时后读取成员状态，释放Event再观察200。`repro-results.json`保存全部非敏感结果；无服务启动、无外部网络/生产写入。
3. 隔离company task fixture：经TaskGraphService真实create/delete，created_at置2000年；调用initialize_schema后检查回执count及旧delete重放。`receipt-results.json`只保存结果；不写永久测试或修改实现。
4. 读代码覆盖全部生产差异与新增/改写fixture；六份delta与对应current规则、SPEC架构、testing规范逐项核对。内核和coding_cli **no spec delta**。没有发现通过canonical未归并掩盖的额外实现要求。

本审查自建隔离runtime目录已清理；没有启动进程、改生产、共享50620或另一unit。报告/JSON/脱敏结果交caller提交，`report_commit`由caller记录；本报告validated_at保持固定原受审HEAD。

## Round 2: targeted closure

> verification_mode: closure · finding_origin_head: `d5de5f9f7abeb33a3ba2959d8ef602ea0b222b96` · validated_at: `bf9fde9e31848bbd290586ab5e7633e7e180d20c` · report_commit: caller 待记录。
> `ce0c557c4` 为测试收尾，受审生产实现仍为 bf9fde；未实施被审代码，未提交本轮报告。复用 Round 1 未失效的身份/授权/附件/架构/运行证据；不重复全量。

**Verdict: fail。当前 4 CRITICAL、0 WARNING、0 SUGGESTION。代码 JSON 存活 1 CONFIRMED。** C1 有剩余实现缺陷；C2/C3 是 R6/R7 外部资源依赖的 inconclusive；C4 等待独立产品 Round 2 完整 must-match 对照。本轮未扩大共享主体或包边界，不要求再跑完整 full 静态审查；后续可按明确修复及失败旅程继续 closure。

| Focus / 契约 | 结论 | 实现与证据 |
|---|---|---|
| C1 慢 HTTP 网络等待、停用提交后尚未发送数据 | **still_open**（锁阻塞已关闭；响应撤销缺口仍存活） | `public_boundary.py:112–119` headers 前释放 gate、每次 send 5s timeout，管理员不再等慢下载；但其后没有资格复核。真实 FileResponse 分块隔离复现见下文和 `closure-results.json`。 |
| W1 公网 bindURL | **closed** | `routes/device_binding.py` 使用 `app.state.public_url`；HTTP Tunnel / HTTPS public_url 专门用例独立通过。此 W1 是原 WARNING，不等同 milestone W1 prototype 验收。 |
| W2 删除回执七天窗口 | **closed** | `repositories/task_graphs.py:receipt` 在查询中排除过期 delete，按索引有界删除每次最多100条；create/apply 原重试语义保持。七天内幂等与过期 delete 不重放用例有效；独立到期用例通过。 |
| W3 旧设备跨主机公钥登记 | **closed** | `IM/cli/enroll_device.py` 仅接受公钥和独立核对 key_id，校验 raw X25519 与 SHA256，拒绝替换不同旧公钥；`public-rollout.md:13–37` Gateway 本机导出、IM 停止时只公钥导入、再持有证明/账号接受/本机确认。明确不复制私钥、不远程抢占。登记窄测13证据复用。 |
| W4 共享 user stream 可行动恢复/冷却 | **closed** | 原 shared runtime 保持一个socket；状态广播共享订阅者、连接成功清除；ticket429尊重 Retry-After、1013等待30s，指数重试及 Notice 倒计时/重新登录。UI30、build证据复用；不把原型完整视觉对照视为已经 pass。 |
| 产品 P1 全局 delete 的 Inbox committed run 来源与真人命名确认 | **covered，未发现新增 confirmed 缺陷** | `global_run_coordinator` 保存 ingress-owned IM message_id；`global_inbox.committed_human_sources` 按当前 agent/session/run durable committed tool-read，要求 attention 真人且全文parts都读完，拒绝历史/部分读取/其他run；bridge 从可信 tool ctx run_id 取来源，IM 从已持久真人消息与聊天成员资格核实当前图/节点明确命名，不信模型 confirmed。独立 global bridge 与 IM source 用例通过；真实产品结果留给 reviewer Round 2。 |
| C2 R6 / C3 R7 | **inconclusive，still_open 验收标准** | 当次上线授权尚缺；真实专用Feishu Bot由另一unit占用。保持原要求与隔离，不降为本地模拟 pass。 |
| C4 milestone W1 prototype完整对照 | **still_open / 等产品 Round 2** | 本轮没有冒称已有原型/局部截图已补齐所有 must-match 双视口实测结论。 |

### Remaining confirmed C1

`response_send` 解除 headers 前 gate 后，后续 body 仅转发到 bounded_send。使用本unit独立临时目录和真实 FastAPI app（无监听端口），注册/fixture激活两个真人、创建群并上传200000字节文本附件；首个65536字节 body 已交给 ASGI client 后让该 send 暂不返回，此时并发 suspend。管理员200，新 GET401；允许旧send返回后，FileResponse继续读文件并新发送65536、65536、3392字节，合计 **134464字节**。这些不是停用前已交给客户端的首块，设计“停用返回前清空尚未发送的数据”不成立。当前新增慢下载回归仅证明锁可释放，并允许失效旧响应最终完整返回；不能证明撤销要求。

建议保持 network send 有界、避免占全局锁，另在公司数据响应后续分块写出遵守当前撤销资格，中止已失效响应。只修该明确路径即可，无需通用新平台或假设边界。

### Validation and limits

独立窄测：在本unit临时 `output/review-targeted-*` 中设置 import app 的独立 IM_DB_PATH，执行 repo venv `python -m pytest -q` 以下4用例，**4 passed in 0.41s**：

- `tests/unit/personal_assistant/test_global_task_authorization.py`
- `tests/im_service/integration/test_company_task_graphs.py::test_expired_delete_receipt_is_not_replayed_or_retained`
- `tests/im_service/integration/test_company_task_graphs.py::test_global_consumed_sources_require_explicit_human_request_and_chat_access`
- `tests/im_service/integration/test_device_binding_protocol.py::test_device_link_uses_configured_https_origin_behind_http_tunnel`

另独立执行上述200000字节 ASGI 分块撤销复现，保存脱敏结果。所有自建临时DB/上传文件已随临时目录清理，无服务启动、无共享50620请求、无公网/生产/其他unit操作。

复用caller修复批次证据：global/inbox/bridge/company31 passed，网络绑定9 passed，TTL/登记13 passed，UI30 passed，build pass。后续全量not-e2e 4095 passed + 1测试行数contract失败；仅测试拆分后contract及搬迁测试4 passed。前端全量792 passed + 1旧 `getByRole(status)` 歧义；选择器限定确认文本后Agent edit5 passed。这些修正不改受审生产实现，不能把失败原始全量标成全绿。

最新额外 stub E2E `/tmp/feat572-review-e2e-updated.log` 为 **3 passed / 3 failed**（config PATCH503/重连、compaction摘要0、skill allowlist未更新），caller正在核实根因，尚未构成独立 confirmed finding，但收尾不能忽略。Round 1 live config RPC直接回包白名单的 REFUTED 仅排除“响应本身等gate”假说，**不排除 WS顺序recv先读普通帧等gate、后续RPC响应因此读不到**的不同FIFO路径；这个新候选须用caller确定性复现/修复证据闭合。

当前 `code-review.json` 是本轮存活数组；Round 1原问题与原full证据保留在上文和已提交历史，本轮 `closure-results.json` 只保存非敏感数字与用例名。报告与JSON交caller提交。

## Round 3: final targeted closure

> verification_mode: closure · executed_base: `bf9fde9e31848bbd290586ab5e7633e7e180d20c` · validated_at: `7df4556795567602333771351fc4bd75ec322e94` · report_commit: caller 待记录。
> 只核派发的修复和新增 delta；复用前两轮未失效证据。未修实现、未提交报告、未重跑完整全量或操作共享产品服务。

**Code review: pass，存活 CONFIRMED/PLAUSIBLE finding 为0，`code-review.json = []`。Verification: fail / 外部门槛阻塞。当前3 CRITICAL（C2 R6、C3 R7、C4完整prototype对照证据待补）、0 WARNING、0 SUGGESTION。** R6/R7保持 inconclusive；不能据本地代码 pass 宣称M1完成或Ready PR。若独立产品Round2随后提供全部 must-match对照，C4可由对应证据闭合，本报告不预支结论。

| Focus | Closure / 实现与证据 |
|---|---|
| HTTP C1后续分块撤销 | **closed**。`public_boundary.py:response_send` 对受保护body在短gate范围内重新核对current_data_principal，失效发空终结body并停止该响应；网络send仍5s有界、在锁外，不恢复慢下载阻塞。独立重复Round2相同200000-byte/首块65536/停用竞争：suspend200、新GET401，之后仅空body，**未发送剩余134464字节**，见closure-results.round3。 |
| 同WS普通帧等gate挡住后续RPC（Round2新候选） | **closed / 原候选已被caller证实并修复**。`ws/gateway/runtime.py:serve` reader继续分发明确RPC回执；其他业务帧进入256条/4MiB有界队列，单worker顺序消费时在gate中重验连接授权。先heartbeat等gate、后config.apply.result的确定性用例独立通过；43窄测与实际config更新E2E pass证据复用。Round1直接回包白名单反证仍只针对原假说，不能覆盖此FIFO问题；本轮才闭合FIFO。 |
| ASGI取消时两个owned任务与连接回收 | **covered**。serve FIRST_COMPLETED后取结果，finally shield中取消/await gather两个owned任务，再按expected_websocket注销；没有遗留reader/worker持续消费。断开/取消15项证据复用，最终IM/contract763覆盖。 |
| 机器自演化Skill创建后激活 | **closed**。PA `agent_config_sync._patch_agent_skills` 改 POST追加入口，IM `agents.enable_agent_skills` 仅 current_gateway+相同owner/node Agent，输入extra=forbid、版本乐观锁，合并原skills、从candidate_from_profile保留完整其余字段，走已有Gateway apply事务。真人完整PATCH仍current_user，机器不能因此取得真人管理能力。边界/版本/保留配置测试独立通过；相关45项和真实Skill创建/启用/新会话使用20.58s pass复用。 |
| 直接ASGI与public launcher日志脱敏 | **covered**。共享 `IM.infra.logging.RedactCredentials`，直接app lifespan安装实际uvicorn.access/error logger过滤；public launcher仍handler过滤。两启动入口测试独立通过，保留握手诊断但去ticket/token等值。 |
| 新delta与design一致性 | **covered**。新增 `specs/im/gateway-relay.md` 对应current gateway-relay consumers，场景覆盖本机机器HTTP数据、失效身份/错node、shadow真实来源、不授予真人管理、仅本机Skill追加；design“复审实施补充”明确队列有界/纯RPC继续读、逐块撤销及两启动脱敏，与实现和测试吻合。current spec保持不动，pending归并不当缺陷。 |
| 全局exact delete/认证两视口 | caller交接 **实际产品pass**；静态授权边界沿用Round2 covered（真实human/current run/完整committed parts/命名匹配）。其余must-match产品对照尚在独立补证，完整C4保持未关闭。 |

### Evidence and limits

独立执行本unit隔离import数据库路径（临时output目录）下 repo venv `python -m pytest -q`：`test_company_slow_download.py`、`test_gateway_rpc_gate.py`、`test_gateway_skill_activation.py`、`tests/unit/IM/test_public_server.py`，**5 passed in 0.93s**。随后独立重放Round2先发首块再暂停return的ASGI harness，结果200000-byte文件仅返回65536，停用之后body bytes为0。自建临时目录全部回收，无端口服务/公网/生产/其他unit操作。

复用且直接核日志末尾：`/tmp/feat572-review-im-final.log` **763 passed / 32.09s**；`/tmp/feat572-machine-skills-e2e.log` **1 passed / 20.58s**；`/tmp/feat572-final-docs.log` **251 maintained /75 routes**。43 FIFO与15断开、45技能相关、Ruff及实际config更新E2E按implementation/caller交接复用；无需角色交接重复全量。前两轮4090/4095基础和前端792+窄修证据保持各自原始状态，不冒称所有历史E2E全绿。

压缩stub E2E `summary_records=0` 在本unit前 `7340a7805` 独立gitarchive源码亦失败，`/tmp/feat572-compaction-baseline.log`末尾同断言0==1、1 failed/7.26s；本unit未改kernel。此项记录为**已证实基线sidefinding**，不作为本unit回归/新code-review finding，不扩展内核修复。

R6真实公网/免费项/真实恢复需要当次授权，R7专用Feishu Bot仍被另一unit占用，均未验收；保持设计要求，不以模拟、本地服务或机器E2E替代。完整原型对照仍等独立产品Round2。报告与最新JSON交caller提交；受审实现固定7df455679。

## Round 4: product evidence closure only

> evidence_snapshot: `ccb75e104c164fe0dba62231898be374e358f3f4` · implementation_validated_at remains `7df4556795567602333771351fc4bd75ec322e94`。
> 本轮仅消费新独立产品报告/必要证据，不重审源码、不改实现、不提交报告。

**C4（M1-W1完整must-match双视口对照）：closed。代码审查仍pass，`code-review.json=[]`。Verification仍fail / 必验门槛阻塞，当前4 CRITICAL证据缺口组、0 WARNING、0 SUGGESTION。** 这里新增列出的两组本地缺口来自独立产品验收的inconclusive，不推定实现错误；它们不能由已有单测或实施陈述升级为产品pass。

### C4 closure basis

`acceptance.md` Round2“必需原型对照补齐”按八个区域列出真实1440×900/390×844状态与match结论，继承Round1未失效的已验主流程，并补齐曾缺的登录错误、成员批准失败、任务搜索空/错、绑定取消/失效/过期、附件格式/网络/冷却、策略保存失败草稿/重试、双语Me及实时恢复。Round1完整交接/本机中断恢复、群任务/回聊草稿、管理员容量/普通只读有效证据仍适用。产品Round2明确区分浏览器故障注入、后端限额实测与fixture，不把注入当成真实自然冷却或实际GiB上传。

必要证据核查：`reviewer-round2-20260930` **36张PNG**的IHDR尺寸全部为其命名声明的1440×900或390×844；独立查看 `login-error-390.png`（对齐输入简短红字/输入保留）、`attachment-network-1440.png`（对应文件chip可Retry、正文和仅文字入口保留）、`policy-failed-390.png`（六字段双卡、Unsaved changes、保存控件）、`bind-expired-390.png`（接收影响/账号与不可接受旧链接状态）。它们与产品报告结论一致。原C4是产品证据链不足，现已补足；无需对已验全部页面机械再执行旅程。

### Current required gates

| ID | 未完成标准 / 当前证据 | 状态与下一步 |
|---|---|---|
| C2 / R6 | 真实域名HTTP/WS、公网仅IM、免费项、真实停入口/恢复发布现场，缺当次授权及CF/源站窗口 | **inconclusive / blocked by external prerequisites**。保持原标准，取得授权后真实验收；本地服务不能替代。 |
| C3 / R7 | 真实Feishu主人识别/外部图片理解/任务读写资格/离线普通对话，专用Bot被另一unit占用 | **inconclusive / blocked by external prerequisites**。独占窗口后验证，不能抢占或mock补pass。 |
| C5 / 本地认证滥用保护的完整旅程 | product Round2“单一来源反复尝试被节流”“同一账号的分散密码猜测受到限制”仍inconclusive；已见账号自然恢复与伪造头不能绕过，但注册/来源自然完整冷却、多真实TCP来源同账号证据仍缺 | **inconclusive / evidence pending**。caller正在补限定隔离证据，交产品reviewer定点验收后再闭合，不提前pass。对应spec认证滥用保护、M1-R1/W2。 |
| C6 / 按需读取而非自动摄取全部任务 | product Round2真实get/search及不自动执行已见，尚缺该测试真实轮次发送给模型的完整输入 | **inconclusive / evidence pending**。caller补限定会话模型输入证据，产品reviewer核对后闭合；无工具调用不等于未注入正文。对应spec任务读取Scenario、M1-R3/W3。 |

独立产品Round2合并结果为 **42 pass / 10 inconclusive**，无新major实施失败，P1真实global精确短指令删除、P2认证视觉、最终启动ticket日志均closed。UX1长自然语言仍需精确短确认保留为报告中的minor确认体验限制；最终错误提示话术未单独再次造图重验，按原报告保留此事实，不擅自升级成新实施阻塞或已闭合证据。

当前四组缺口覆盖产品10个未决Scenario；不降低要求、不预支caller正在补的证据。产品场景通过、代码pass、M1完整验收/发布是不同结论。生产实现7df455679与Round3代码证据保持不变；本轮只更新verification当前门槛。git diff --check通过，交caller提交。

## Round 5: final evidence and two-fixture closure

> final_evidence_head: `f695942d9892eb7af6814b48577d8620e5e26048` · production_implementation: `7df4556795567602333771351fc4bd75ec322e94` · fixture_delta: `cfbd481a456e692a611d834fc7a1aa2b9c141fab`。
> 本轮仅消费独立产品Round3/4与脱敏证据，审两个已审机器技能入口对应的旧测试桩差异；没有全量重跑/源码全审、没有实施修改。三份既有报告由本审查者按caller授权直接提交，实际report_commit可查本文件git历史。

**Code review: pass，`code-review.json=[]`。Verification: fail / 2 CRITICAL（C2 R6、C3 R7必验未完成）、0 WARNING、0 SUGGESTION。独立产品最终合并45 pass / 7 inconclusive，剩余7条全部属于R6/R7。不可Ready PR，不可宣称M1完成、归档或已部署。**

| Focus | 最终结论与足够证据 |
|---|---|
| C5 来源限流、跨来源账号节流、完整自然冷却 | **closed（限定本机真实TCP双源）**。产品Round4 `f695942d9` 独立读完整隔离server/qualify/results/peer日志并只读DB；脱敏 `reviewer-round4-c5-20260930/auth-source-evidence.json` 有48条HTTP、两OS绑定源、proxy_headers=False、无伪造来源头、未改时钟/限额/DB计数。A注册5次201后429而B201；A来源登录上限429而B200；两个源同账号交替10次错密后正确密码也429。相应自然301.85/901.34/902.61秒后原来源登录/注册/账号均恢复。7用户35会话与成功请求计数吻合。不是两台Internet客户端，不代替R6域名/代理来源验证。 |
| C6 模型按需读取而非自动摄取全部任务 | **closed（限定真实隔离会话）**。产品Round3 `332d6a93f` 独立读94个实际上游请求，脱敏manifest94条；现存图早于会话存在，首次引用前69个完整输入均无该图ID/标题/正文片段，首3请求task_graph启用，全部94个system图标记0。首次ID来自人类点名的inbox结果，正文随后来自显式task_graph get并留在普通工具历史，之后无Agent新委派，图保持revision5。证据 `reviewer-round3-c6-20260930/model-input-evidence.json` 不导出完整system/工具schema/消息，只保留哈希、计数、布尔和块位置。不推广成所有provider/channel穷举结论。 |
| C4 原型对照 | 保持Round4 **closed**，没有失效实现变化。 |
| 两个旧测试桩适配 | **pass，未发现实质问题**。`test_session_run_coordinator_real_kernel.py` 模拟请求从PATCH改POST，断言确切 `/agents/agent-a/skills/enable` 和仅profile_version/skills；仍构造完整候选送真实apply，验证响应尚阻塞时运行admission使用原system、无pending边界、自动技能已持久登记。`test_gateway_reconcile_callback.py` 对静态Agent技能POST返回503，config只允许GET，仍断言失败静态Agent保持原memory且另一个Agent成功对账。未弱化原应用时序/失败隔离语义；相关6项及最终全量绿证据复用，不重复跑。 |

### Final validation evidence

直接读取日志末尾并核implementation新增记录：

- `/tmp/feat572-final-all-backend-green.log`：not-e2e **4099 passed / 27 warnings / 84.53s**。
- `/tmp/feat572-final-all-frontend.log`：**793 passed /85 files**。
- `/tmp/feat572-final-docs-closure.log`：**252 maintained Markdown /75 required routes**。

以上是caller最终冻结回归，本审查者没有重跑。源码生产保持7df455679；cfbd仅2个测试桩与implementation记录，332d/f695仅独立报告和脱敏证据。前几轮HTTP撤销/FIFO/机器技能/日志入口独立closure证据仍有效。compaction stub同7340基线失败的sidefinding保持原边界，不称所有E2E全绿、不扩展kernel。

### Only remaining required gates

| ID | 尚未验收Scenario | 状态 |
|---|---|---|
| C2 / R6 | 实际域名访问/实时；公网仅IM；真实停止公开访问与恢复；实际免费项核对 | **inconclusive**。真实公网未获当次授权、未部署；localhost、测试全绿与报告提交不能替代。 |
| C3 / R7 | 飞书主人识别/Agent公司资格；外部渠道任务写入资格；正常上传与Agent图片理解（Web已验，外部飞书仍缺） | **inconclusive**。原专用Bot锁仍unit-feat-569/PID15775存活；不抢占、不mock补pass。 |

本地验收服务均由各owner清理，8572原型保留；本轮未再启动或操作服务。UX1确认体验限制保持原产品报告记录，不扩大要求、不放宽人工授权。三份报告范围之外dirty/untracked保留，提交报告不等于Ready PR、远端同步、上线或M1归档。

## Round 6: real R7 shadow identity patch review

> review_mode: patch · executed_base: `00a7f05e49fd953e47a675089c8097c20efff467` · validated_at: `821ff6ce1a53c8046b9c37d5d350470527ed0b30`。
> 仅审此批12文件中的机器identity接口、shadow生产接线、相应测试与gateway-relay delta；复用其余独立代码/产品证据，没有全量重跑、实现修改或现场服务操作。报告由审查者按caller授权提交。

**Code review: pass，CONFIRMED/PLAUSIBLE存活数组仍 `[]`。Verification: fail，2 CRITICAL外部验收门槛（C2 R6、C3 R7）、0 WARNING、0 SUGGESTION。不能Ready PR、宣称M1完成或已完成部署。** 新真实R7发现的机器token访问真人/me401回归已在本批实现修复并有窄证据，真实飞书回复/外部图片/任务资格结果仍等独立产品reviewer，不用80项模拟/集成绿预支R7 pass。

| 定向核对 | 结论及证据 |
|---|---|
| 新机器identity查询 | **covered**。`IM/api/routes/account.py:get_gateway_identity` 依赖既有current_gateway，不收模型owner/node参数，只返回被当前已注册运行token证明的node_id/owner_id。current_gateway及HTTP公司门禁沿用现有连接/owner资格验证，真人JWT不能用此入口，也不扩大机器读取真人/me或/nodes管理能力。新增真实API用例要求正常返回exact两字段、真人默认会话401、机器访问/me/nodes401、owner停用后identity401。 |
| shadow身份与生产构造点 | **covered**。composition只给IMShadowConversationSync传gateway_token_getter和本node。sync_user_message先持久准备外部源事实，再require当前机器token，GET gateway/identity；严格匹配本node并验证非空owner，按token缓存真实owner。没有真人token_getter或/me、全节点列表依赖，离线先保存durable事实、不丢后续恢复。写数据再取当前机器token，沿用原机器Agent/聊天权限入口。 |
| 旧owner saga/回放与错node拒绝 | **covered**。确认真实本node owner后，保留原recover_owner、shadow用户/输出幂等键、anchor与divider promotion、恢复顺序和原sender_source_id。测试将旧本地owner调和到已认证owner并复核未决output与boundary一次完成；另一个node身份只产生identity请求、保留旧saga owner且不写外部会话。既有已确认anchor复用语义未改，不将本地owner当远程授权证据。 |
| 当前token/吊销与外部普通行为 | **covered**。shadow-auth测试不提供token时无HTTP请求且saga留存；有效runtime-one恢复；输出使用runtime-two；无token时输出保持pending。原回放/离线图片/入口管线测试只改身份stub与请求序号，保持原源身份/顺序/交付断言。不新增外部真人IM登录前置。 |
| delta/current spec | **covered**。gateway-relay delta新增“外部镜像核实当前机器管理者”，描述current machine identity、node一致、旧owner调和、拒绝真人/失效机器，与实现吻合；current spec未提前覆盖。接口仍是PA↔IM机器协议，无包import越界或新真人管理旁路。 |

复用本批red→green证据：实际API入口与禁止/me/nodes的shadow恢复先2项red；`/tmp/feat572-shadow-identity-batch-green.log`末尾独立读取确认为 **80 passed /8.46s**，范围包括机器identity/授权、shadow saga、离线图片与入口管线；Ruff/diff按implementation交接通过。本审查者未重复全量或已有效的80项测试。4099/793全量仍只是此前未失效基线，不代表新真实R7已验收。

### Updated external prerequisites and verdict

- **R6 / C2仍未验收。** 用户已明确授权公网部署，CF域名Free/Active、专用Tunnel/DNS已准备；公网尚未启动，当前待用户选择首次成员名单。**原“尚缺当次授权”原因已失效**，但实际域名HTTP/WS、仅IM公开、真实停止公开入口/恢复、实际免费项仍需独立实测，不能以准备就绪补pass。
- **R7 / C3仍未验收。** 用户已授权接管569原专用Bot，原资源占用已由caller处理；独立reviewer首次实测发现真实消息无回复并定位本次shadow身份回归。正在重启复验修复。**原“不能接管Bot”仅是历史状态**，当前缺口是修复后真实飞书全部必验旅程结果，不能提前pass。

C4/C5/C6前轮已闭合并未因这批窄身份查询变化失效；产品45 pass/7 inconclusive仅作为上一轮合并历史，待新R7报告按实际结果更新。无新增推测要求、无全量源码重新审查。三份报告中code-review.json保持有效空数组无需制造格式差异，closure-results追加本轮元数据；无secret/完整日志/本地配置提交。

## Round 7: final verification closure and corrected-delta

> verification_mode: targeted-closure + corrected-delta · implementation/product_validated_at: `821ff6ce1a53c8046b9c37d5d350470527ed0b30`。
> R7 evidence: `1fc64aa24`；R6 evidence: `b106af9b6819a7ac2d6afd229f6c5b6736ed61f9`；corrected Work/directory delta: `0c24484eba53081afb787487ba266d01858c0ec3`；scope/cleanup document snapshot: `84c8d168b2e227b4077025de98f7bb82eeabd477`。
> final sync origin/main `1519ebb82`只增加bugfix-574首文档，无src/tests变化。上述文档/evidence提交不冒充真实产品执行版本。前轮代码审查pass和未失效测试/产品证据复用，不机械重审实现、不重跑全量或再次操作现场。

**Verdict: pass。0 CRITICAL、0 WARNING、0 SUGGESTION。corrected-delta: aligned。requires_full_verification: false。code-review pass（`code-review.json=[]`）。独立产品最终52 pass /0 fail /0 inconclusive，Highest Required Action pass，新增blocking/major为0。** 当前实施/验收/校正delta门槛已完成，可继续canonical归并、归档及PR/CI流程；本报告不代替合并授权、CI结果或正式生产切换。

### Completeness / final external closure

| 历史门槛 | 最终证据与结果 |
|---|---|
| C3 / M1-R7真实Feishu | **closed**。acceptance Round5为真实原专用Bot、原ownerOpenId、独立新IM/Gateway/node/数据。821修复后真实DM交付卡与shadow镜像恢复；原生PNG实际辨认橙色三角形/蓝色圆；群无@背景不回复、@读取背景并改同图revision2→3；短明确删除revision4/get拒绝；provenance是feishu真实发言人而非IM管理者。关闭工具真实PermissionDenied；IM不可达/owner停用普通飞书继续但任务如实失败且无新图；pending binding403、批准后真实整体换绑。通用失效机器矩阵复用有效前轮证据，没有声称每个身份又独立发真实飞书。`reviewer-round5-r7-20261001/feishu-evidence.json`保存脱敏消息/卡、哈希与事实核对。 |
| C2 / M1-R6真实域名、限定公网、免费配置、停止/恢复 | **closed**。acceptance Round6在`https://im.nanoim.win`实际独立测试部署：TLS正确、无Cloudflare Access额外登录；浏览器登录/聊天/LLM/图片/任务/Work可见。真实en0物理出口HTTPS200和WSS101/resume成员事件，cloudflared公网上游；仅127.0.0.1:18572源站与指定域名Tunnel ingress+末尾404，无Gateway公网映射。停止测试Tunnel实得502。停写同次SQLite backup+data快照恢复独立副本，旧access/refresh/runtime401，未使用ticket在1.07秒（寿命30秒）403；freshlogin/bind后旧runtime仍401、新runtime200，排除仅离线造成的假验证。历史聊天/图响应exact equal、3330-byte附件SHA一致，真实恢复后get/回复成功。官方Dashboard Free/Active、Zero Trust Free/0美元月费已独立核对，免费范围不含域名/硬件/LLM。 |
| C4/C5/C6及其余R1–R5/W1–W4 | **保持closed/covered**。全must-match双视口、真实TCP来源自然冷却、完整真实模型输入及原身份/对象ACL/任务/交接/容量/SSRF/架构证据未失效；不重复整个unit验收。 |

必要最终证据消费：直接读取R7/R6独立报告和脱敏JSON；R6结构化证据的5张PNG SHA全部匹配、尺寸全部1200×731，抽查真实Work与恢复聊天画面符合产品报告。未读取/输出无关私聊、完整凭据或生产配置，不把HTTP健康替代实际回复。Round2 UX1长自然语言仍需精确短确认保留为非阻塞minor体验记录，不放宽人工授权、不新增实施要求。

### Corrected-delta / coherence

| 最终delta | 核对结论 |
|---|---|
| 新 `specs/im/agent-work.md` MODIFIED | **aligned**。与current同名Requirement逐块比较，恰好仅两处“登录用户”前提改为有效公司成员；全部原Work完整共享、子执行、持续更新与原聊天/附件ACL语义不变。实际`agent_work.py:get_work/get_turns/get_items`依赖current_user（active），不添加owner过滤；批准spec“既有共享Work保持”及pending/suspended拒绝直接成立。 |
| `specs/im/agents-nodes.md`追加目录MODIFIED | **aligned**。保持current同名Requirement和所有Scenario，唯一目录准入WHEN改为已登录有效公司成员。实际`web_im.py:list_contacts/get_contact`依赖current_user，不放开完整配置管理；和已批准公司共享联系人要求吻合。 |
| 其余七份已审delta / 最终八份合计 | **aligned**。既有auth-tenancy、agents-nodes其余块、IM/gateway task-graphs、conversations-messages、external-channels、gateway-relay（含821 machine identity）按前轮已审生产实现/证据保持有效。独立校验八份delta中全部MODIFIED/REMOVED标题在对应current文档存在；ADDED、REMOVED任务owner范围与active公司目标一致。最终没有发现缺少的受影响对外行为或需要文档修订的差异。 |
| current与active归并时机 | current尚未覆盖是正确active阶段，**不列缺陷**。caller下一步按已aligned delta归并canonical/归档；本审查者未提前修改current或实现。 |
| 用户确认的部署/验收边界 | design M1-R6补充、public-rollout与implementation明确：全部验收独立测试部署，用新账号/数据/密钥/node，不复制生产数据；PR+CI后用户合入，再正式生产切换。真实域名只映射隔离18572，撤回错误Access登录前置而非换域名绕过。此边界已授权，不把生产迁移追加为PR门槛。 |

### Validation / cleanup / residuals

- 直接核 `/tmp/feat572-r7-identity-full.log`末尾：修复后backend **4100 passed /27 warnings /122.45s**。frontend **793 passed /85 files**原有效证据复用；tracked Python Ruff/checkformat1126按caller交接复用。基线compaction stub E2E sidefinding保留既有证据范围，不扩展kernel。
- 独立追加仅文档完整性：repo venv `python scripts/docs_check.py` → **254 maintained Markdown sources /75 required routes passed**。工作和目录delta逐块比对True，八份MODIFIED/REMOVED current标题映射均存在，五张公网截图哈希/尺寸一致。git diff --check通过。
- 审查者未创建新现场。R7已e2e-down释放Bot测试锁/关闭本轮进程；84c8 cleanup记录官方stop已停止本机测试PID78527、Mini测试IM1973和testTunnel，18572/51636无listener、相关tmux无会话，8572原型保留HTTP200。隔离原目录/快照保留，正式生产8011和生产数据未触碰；这是caller收尾记录，不冒称审查者再次现场复验。

**无剩余verification/code-review阻塞。** 全部结论限定到受审821实现、有效基线和明确隔离真实平台证据；不宣称零漏洞、全provider穷举或正式生产已切换。只有verification报告发生本轮必要更新，空code-review无需无意义改动；报告提交与后续PR/CI/合入/生产切换各自保持可辨。

## 2026-10-02 用户 UI 反馈修复补充

- 独立 code-review 范围 `fb31ccf9e..64b4b0b57`，结果 `[]`；`79dfcbfa4` 仅精简行内 Suspend 文案并禁止换行，辅助名称保留，无权限或数据逻辑变更。
- 相关前端 14 项、附件接口 14 项通过，TypeScript/Vite、Ruff、diff-check 通过；源代码提交 `79dfcbfa4` 的四项 PR CI 全部通过。
- 独立产品复验 8 项通过，0 个确认问题，覆盖三项 UI 反馈及准入/批准/取消停用/旧会话拒绝；实际桌面和手机截图见 acceptance Round 7。原有其他验收场景未在本轮重跑。
- docs-check：235 maintained Markdown sources / 75 required routes 通过。仅隔离测试站更新，生产未部署。
