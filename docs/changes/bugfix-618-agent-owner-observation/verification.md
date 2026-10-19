# Verification Report: bugfix-618-agent-owner-observation

> Validation snapshot: `9b110168359b9c9ae5937d07a77b697e03a61d65 → 03d1d5a65550061a10c944552f0078dac9085408`

- verification_mode: full + corrected-delta
- review_round: 1
- executed_base: `9b110168359b9c9ae5937d07a77b697e03a61d65`
- validated_at: `03d1d5a65550061a10c944552f0078dac9085408`
- requires_full_verification: false（本轮已按 full 执行；修复后的定向复验范围由 caller 决定）
- verdict: fail / 等待修复与门禁完成

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 未闭合；W1 有有效证据，W2 的 Web 新回归失败，R1/R2/R3 与 W3 尚未全部完成 |
| Correctness | 核心读取/拒写与当前资格一致；观察界面待审批写控件存在遗漏 |
| Coherence | 统一会话资格、无成员/ACL新增、无DSH改动遵守设计；只读界面不完全 |

1 critical issue, 2 warnings found. Fix before PR.

## Completeness

- Tasks：单一 M1，无强制 tasks.md；以 `design.md:105` 六项退出标准为准。
- W1：独立重跑3文件13测试通过；真实节点HTTP/WS证据复用 `evidence/implementation.md:22-30` 与 `/tmp/nano618-http-ws-audit.log`（已读取通过结果及脚本的实际断言）。该审计覆盖 live双方、reconnect replay、owner变化后双方差异、成员不变；不验证真实模型自主协作。
- W2：DTO、分类、只读普通消息路径、原生send guard实现存在。独立 Web 新用例在历史滚动前提上失败，未执行撤权/迟到断言，不能写为通过。原生测试主 Agent 正在汇总；读取到 `/tmp/nano618-ios-test.log` 有 `TEST SUCCEEDED`，但本轮不替 caller 认领构建版本、Release archive及真实UI验收全部完成。
- R1/R2/R3：实施记录与一张真实 Web 窄屏截图证明部分普通观察路径；尚无冻结版完整独立产品报告，尤其1280/390、长内容滚动、原生长按/侧滑及普通成员发送对照。不能以原型截图代替产品证据。
- W3：最终全量/CI/契约归并及独立产品门禁未有完整通过结果。本轮见到此前全量日志有失败，来源与最终处置需 caller 汇总，不将超时或在跑称通过。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 双方真实owner读取：同owner、跨owner公司、私人空间 | `apps/im-server/src/conversation-access.ts:16-40`；`messaging.ts:167-176` | `tenancy.test.ts:226-278`；独立后端窄测通过；真实HTTP审计通过 | covered |
| 恰两个同空间Agent，不信旧conversation owner；旧历史不重建 | `conversation-access.ts:18-22`；`messaging.ts:126` | `tenancy.test.ts:238-245,297-303`，保留原id/消息，第三参与者与异空间拒绝 | covered |
| 观察不新增成员/消息/运行，不授予写入 | `messaging.ts:90-93`；各write routes；`media.ts`上传门禁 | `tenancy.test.ts:256-278` 验证发送/冒充Agent、上传、PATCH、参与者、删除、join拒绝，消息1条/relay0；实际Agent通信现有e2e通过 | covered |
| 不相关管理员与另一私人空间拒绝 | `conversation-access.ts:30-33` | `tenancy.test.ts:271-274`；HTTP审计charlie列表空 | covered |
| list/sync与受保护媒体按同一资格 | `messaging.ts:167-176,730-740`；`media.ts:47-68` | `tenancy.test.ts:245-255,271,292-293`，双方读附件及撤权后404 | covered |
| 实时双方读取与replay；当前owner变化后拒绝 | `messaging.ts:342-345,583`；`gateway.ts:211,240-256` | `tenancy.test.ts:280-293`；真实WS审计双方live/reconnect/revocation通过 | covered |
| 账号/空间失效；stale/离线保留已知归属历史 | `identity.ts:41-69`；`conversation-access.ts:27-32` | `tenancy.test.ts:285-303`及既有tenancy资格测试独立通过；offline不参与owner判定 | covered |
| Web Network包含Agent direct与既有Agent群，不混普通人机 | `chat-types.ts:272-282`；`conversation-sidebar.tsx:100-108` | 新sidebar测试独立通过，既有群/人机筛选测试保留 | covered |
| Network分类不改变direct业务形态 | `chat-workspace-page.tsx:503,1187,1237,1255`；`message-pane.tsx:591` | 源码真实type门禁；新observer页面在到达历史阶段前确认无Config/Join/Send | covered |
| Web清楚双方身份，只读普通消息，无composer/join/菜单 | `messaging.ts:126`；`message-pane.tsx:990-1012,1062-1067` | 新observer页面到达失败前此组断言通过；`implemented-web.png`已查看 | 普通消息covered；审批卡warning |
| Web在线owner变化后清正文/媒体、缓存、列表并拒迟到历史 | `chat-workspace-page.tsx:613-627,683-724`；`chat-api.ts:44` | 实施者真实浏览器自检声明有清理；新永久回归在test:47前失败，清理/迟到保护未执行 | warning：关键回归保护未通过 |
| iOS只读底栏、无composer/join、列表无写动作、详情真实参与者 | `ConversationView.swift:88-104`；`ChatListView.swift:51-57`；`ChatInfoView.swift:29-49` | `ChatStateTests.swift:103-120`解码/send guard；真实UI产品验收待完成 | 源码covered；视觉pending；审批卡warning |
| iOS撤权后清正文/条目；store拒发送 | `ChatStore.swift:166-169,174-188,254-255` | 现有失效保护源码有revoked guard，新增guard测试；原生完整门禁caller汇总 | source covered / validation pending |
| 普通真人成员仍可聊天，既有Work资格不变 | member分支与write门禁保留；Work模块未改 | 独立messaging/server窄测通过；Web/原生真实成员发送由产品门禁补齐 | 后端covered / 产品pending |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 当前真实参与者/profile/space派生只读owner，不新增ACL/成员 | 是 | `conversation-access.ts:16-40`；diff无schema变化 |
| 读与成员写分离；媒体共用读取门禁 | 是 | `messaging.ts:90-93`；`media.ts:47-68` |
| 列表/事件/replay共用读取资格，保留全局游标 | 是 | `messaging.ts:176,343,583`；`gateway.ts:240-256` |
| Web Network是分类，群功能依据真实type | 是 | `chat-types.ts:274`；`chat-workspace-page.tsx:503`；`message-pane.tsx:591` |
| Web/iOS observer不提供写入操作 | 部分 | composer/菜单已隐藏；待审批卡未传播can_write，见WARNING 1 |
| 非成员前台下一次权限复查后收敛，无新撤权push | 是 | Web messages 3s轮询与403/404 effect；iOS `ConversationView.swift:120-129` |
| 不改DSH、PA或跨包依赖边界 | 是 | 完整24文件diff限定IM服务端/客户端/测试/unit证据；无新运行时import |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Network条目含双方身份，桌面/窄屏 | R1 | title派生、Network分类 | `implemented-web.png`为513宽聊天，无列表；实施记录声明Network三条 | 部分；桌面/390对照待产品报告 |
| 双方作者、只读提示、无输入发送加入 | R1/R2 | Web `message-pane.tsx:990-1067` | 已独立查看真实`implemented-web.png`与`prototype-web.png`，双方作者与底栏层次对应 | 普通消息covered；审批卡例外 |
| 新消息追加与长内容滚动 | R3 | 原消息滚动容器保留，stream与poll不改归属 | 实施图有新增第三条；未见长内容真实对照 | pending |
| 失效不可访问且停止交付 | R3 | 后端当前资格复检；前端reconcile | HTTP/WS审计通过；实施浏览器自检声明；新Web回归失败 | 后端covered / UI保护warning |
| 原生只读底栏，无composer/join，列表无长按/侧滑写动作 | R2 | SwiftUI条件已核实 | prototype-ios是设计示意；真实模拟器证据待独立产品报告 | pending |

## Issues

### CRITICAL（提 PR 前必须修）

- C1：`design.md:105` 的 M1 退出标准尚未完成：最终全量/CI、独立产品R1-R3、原生实际UI和Release gate及契约归并不能从当前证据认定通过。建议 caller 完成并记录确切版本、命令、结果和入口证据后再判M1完成；与后端13测试通过分开。此项是尚未完成门禁，非已证产品实现缺失。

### WARNING（提 PR 前必须修）

- W1：观察者仍显示可操作审批卡：Web `message-pane.tsx:1779` 的disabled只核参与Agent；iOS `ChatMessageView.swift:159-168`无会话写资格。已独立证明两个single_thread Agent direct能经正式gateway处理产生pending card，owner可读，POST决定404。请向两端消息/卡片传播只读资格，仅展示审批状态与操作输入，保留成员审批并补最低层界面回归。服务端拒写有效。
- W2：`chat-public-visitor.test.tsx:46-47` 缺滚动尺寸，`message-pane.tsx:837-838`在jsdom的零高度提前返回。独立两次失败，撤权/迟到断言均未运行。请提供可滚动容器前提并重跑，不能把现有新增测试计为迟到历史已保护。

### SUGGESTION（可以修）

- 无。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/im/auth-tenancy.md`：双方owner只读、账号/space/实际归属、成员写门禁 | access统一派生，REST/media/live/replay共享；旧owner不参与 | 独立tenancy/messaging/server 13通过 | aligned |
| `specs/im/conversations-messages.md`：已有/新会话、旧随机owner、附件、私聊写菜单/改名成员前提 | list和事件共享，DTO标题双方身份，写route未放宽 | tenancy覆盖旧owner与媒体，sidebar分类通过，消息路由e2e通过 | aligned |
| `specs/im/web-chat-ux.md`：Network、只读UI、在线owner变化清理/迟到历史 | Network/direct区分已实现；普通composer/菜单隐藏；审批卡遗漏只读资格 | sidebar通过；新observer用例失败，撤权与迟到保护未执行 | implementation-mismatch（只读界面缺口及验证阻塞） |
| `specs/im/ios-client.md`：只读底栏与列表/详情无写表单 | SwiftUI普通路径与send guard对齐；消息审批仍提供写表单 | 原生解码/guard测试已添加；UI门禁待caller；审批遗漏经源链核实 | implementation-mismatch |
| `specs/im/agent-work.md`：原聊天按统一资格；Work本身不扩权 | Work模块未改，来源附件复用messaging.access | tenancy媒体与无关账号拒绝，既有Work边界不被改写 | aligned |
| corrected link：auth delta的gateway-relay相对链接 | `../../../../specs/im/gateway-relay.md`指向current spec | 按路径直接核实；无产品行为改变 | aligned |

### Uncovered Observable Behavior

`ChatModels.swift:30` 同时把原生Agent-agent direct投影到已有Network筛选。该细节未单列在ios delta，但遵守design复用发现语义与既有导航的边界，无新增导航体系，也未发现与首文档相悖的独立行为。Web对所有can_write=false会话隐藏composer、原生对只读行隐藏写菜单，属于current只读约束的统一落实。

Outcome: implementation-mismatch

## 执行与证据边界

- 本轮未接生产、未启动长驻外部服务、未修改源码/测试/设计、未提交。审批复现临时服务已关闭且DB清理。
- 独立后端命令与结果、Web两次失败及可达审批复现详见同目录 `code-review.md`；结果均在冻结HEAD执行。
- `evidence/implementation.md` 是实施者证据，版本前后的测试必须区分；其中“最终版须复跑”和“仍在运行”未升级成pass。
- 本报告允许 caller 的独立产品报告与最终门禁补充后关闭 C1；W1/W2需要实现/测试修复及固定版本复验。
