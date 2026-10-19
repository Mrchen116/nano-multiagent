# M1 实施与验证证据

## 实现与测试归属

- 统一 `conversation-access` 派生恰好两个同空间 Agent 的当前真人 owner；不插入成员、不信任旧 conversation.owner_id、stale/离线不阻断已知归属历史。
- list/sync、持久事件收件人、gateway 最后一跳和 replay 共用读取资格；现有 write 门禁仍要求成员。没有数据库迁移、DSH 或 PA 改动。
- Web Network 收入 Agent direct，以真实 type 区分群功能；只读底栏替代 composer，隐藏写菜单。非成员轮询得到403/404时重用清理流程；取消历史请求、阻止迟到历史恢复，清理正文/挂载媒体并回列表。
- iOS 共享 DTO、Network 分类、只读底栏、详情和列表写动作、store send guard 对齐；撤权清除行与正文。

测试处置：扩展已有 `tenancy.test.ts`（HTTP、当前资格、媒体与 live/replay seam）、`conversation-sidebar.test.tsx`（分类）、`chat-public-visitor.test.tsx`（非成员真实页面组合、拒绝读取后清理与迟到历史）和 `ChatStateTests.swift`（原生解码/send guard）。保留普通成员、公共访客和既有全 Agent 群测试，不新建 unit 编号永久测试。未向既有 2779 行 message-pane / 2162 行 workspace 集成文件堆入独立行为，复用较窄非成员页面 owner。一次性 HTTP/WS 审计脚本在 /tmp，收尾删除，不进入长期套件。

## 先红后绿与窄验证

- `pnpm exec vitest run apps/im-server/tests/tenancy.test.ts -t 'both real Agent owners'`：实现前真实失败，owner 详情期望200、实际404；日志 `/tmp/nano618-red.log`。首次运行缺 product-contracts 构建是环境准备错误，构建后才取得此产品红测。
- 实现后 `pnpm exec vitest run apps/im-server/tests/tenancy.test.ts apps/im-server/tests/messaging.test.ts apps/im-server/tests/e2e/server.test.ts`：3文件13测试通过，含受保护历史附件、观察拒写、不相关管理员拒绝、stale、owner变化、空间不匹配。
- Web 首轮非成员与 sidebar：2文件18测试通过。随后新增迟到历史断言与权限错误标题修正，须按最终版本重跑。
- `pnpm --filter @nano/im-server typecheck` 通过；Web `npm run build` 通过（已有 bundle体积提示）。
- Python standalone/architecture：62 passed，31 deselected；ruff check / format通过（83文件）。docs-check发现 unit delta 一个相对链接，已修正，最终版本须复跑。

## 真实入口自检

从 unit worktree 启动真实 IM fixture，临时 SQLite、已认证节点 WS、合成 alice/bob/charlie；Vite代理58054。独立HTTP/WS审计返回：

```json
{"result":"passed","sameOwner":true,"crossOwner":true,"personal":true,"unrelatedAdminDenied":true,"historyCount":6,"observerWritesDenied":true,"realWebSocketLiveBoth":true,"reconnectReplay":true,"revocationStopsLive":true,"membershipUnchanged":true}
```

该脚本先显式 resume，收到双方新增事件；断开 bob 后消息可重放；只变更 alpha owner 后 alice不再收到内容而bob继续收。6条包含此前审计产生的合成记录，最终相对基线新增3条，没有真人插话。HTTP/WS和模拟节点直接验证 IM 变动链路，未调用真实模型，不声称 DSH 自主协作或生产验证。

真实 Web：Network 筛选有私人、同 owner、跨 owner3条，成员群不混入；打开跨 owner后两位作者/节点可辨，底栏只读无发送/加入/配置，新增消息可见（[implemented-web.png](implemented-web.png)）。只改owner后下次前台复查清空正文并回列表；自检发现泛用“Send failed”标题，已改为访问失效专用标题，最终产品review复核。沿用现有头像/气泡/作者/时间，底栏层级和原型对应。

## 验证环境说明

首次同时执行默认并发Web全套、runtime构建与Xcode构建使本机load达到203，并出现多处未改模块超时；停止了仅本unit验证进程树，保留日志，不将未完成/超时全套称作通过。后续完整验证按受控并发、分阶段执行。原生首次构建停止后清理两个本unit孤儿swift进程；原生测试按可用iPhone17Pro模拟器进行。最终结论及独立门禁见后续报告。

设计 retained：fixture只补5秒节点心跳和对端send-back演示驱动、delta只修合法相对链接，未改变Gate2方案/用户契约；iOS Network分类投影既有发现语义，不新增导航体系。

## 首轮独立审查后的修复

pre_fix_head `03d1d5a65`。审批只读资格遗漏和滚动fixture前提问题均接受，具体闭环见code-review/verification的后续Round。

- Web修复+既有审批成员行为+分类+此前无关trajectory超时项：4文件35测试通过（`/tmp/nano618-web-fix.log`）；新增的真实页面用例同时证明审批内容可读、决定按钮/理由框不存在。
- iOS修复后：`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild ... -jobs 2 test`，30测试0失败，`/tmp/nano618-ios-fix.log`。
- Release设备归档：同工程 `generic/platform=iOS`、Release、`CODE_SIGNING_ALLOWED=NO`、`-jobs 2 archive`，ARCHIVE SUCCEEDED，`/tmp/nano618-ios-archive.log`。归档是未签名构建，不等于真机安装或生产发布。
- 全量Web首轮最终887/889通过：本unit滚动fixture和无关trajectory5秒超时各1项；两项均在上述35项复跑中通过，最终全套正在重跑。
- 后端全量343/347通过，4个超时分布3文件；串行重跑后model-fallback、control-work全部15项通过，只剩未改动workspace-tools的90秒超时。正在主仓对照同一测试，不把重试/基线疑点写成通过。
- 隔离资源补齐：fixture提供`/classifications`（真人/人机私聊）、`/history`（60条历史+100行长清单）、`/media`（受保护测试图标及文本附件）、`/approval`（正式节点streaming生成待审批卡），用于独立补验。原生origin应为53186，经同源Vite转发API和WS；58054仅用于不带浏览器Origin的直接API。
