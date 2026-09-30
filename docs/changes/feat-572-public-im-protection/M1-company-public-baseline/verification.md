# Verification Report: feat-572-public-im-protection

> 最新结论见末尾 Round 2：固定生产实现 `bf9fde9e3` targeted closure，C1 still_open；W1–W4 closed；P1 全局删除来源修复 covered。R6/R7 与完整 prototype 对照仍未验收。Round 1 保留历史基线，不能将其旧问题数当作当前存活问题数。

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
