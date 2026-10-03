# Code Review: bugfix-576-public-auth-hardening

## Round 1

- reviewer: `/root/static_review_576`，未参与受审实现；分别使用 change-code-review / change-verifier。
- review_mode: full
- executed_base: `d357729af19d5860db79ae5617eaee5b44ada0d7` (`origin/main`)
- validated_at: `9b9478ebe0c1075ccc9b166afae80f3190a604fb`
- scope: 完整 48 文件实现 diff、incident、Gate 2 R3 Approved 的 design、canonical delta，以及相关 current auth/fork/config/Gateway 与架构契约。
- verdict: Issues Found；2 CONFIRMED，0 PLAUSIBLE。仅提交报告；未修改实现、测试、设计或环境。

## Findings

```json
[
  {
    "file": "src/IM/application/web_im_service.py",
    "line": 455,
    "summary": "[P1] RPC 失败清理仍会删除等待期间已写入的用户消息",
    "failure_scenario": "fork 的 Gateway Future 等待现已让出 company gate；预建分支对会话列表可见，真人可在另一个请求中向其发消息。request_fork 返回 None 或 ok:false 时此处仍无条件 _rollback_fork，cascade 删除分支及用户消息。成功结果后的展示历史复制异常路径同样无条件回滚（:588），也须保留等待期间写入的内容。新 :445 的异常路径空检查没有覆盖这些路径。应在重取 gate 后识别已有用户内容，仅清理本请求仍空的半成品；复制失败仅回滚复制前仍空的自身半成品，并增加公开 HTTP/WS 回归。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/IM/application/auth_service.py",
    "line": 132,
    "summary": "[P2] 新密码字节上限未接入注册字段校验和拒绝反馈",
    "failure_scenario": "新增 bcrypt 的 72 UTF-8 字节注册限制，但 validateRegistration 只校验 256 codepoints；73 位 ASCII 或 25 个中文字符会被前端视为可提交。服务返回 422/password must be at most 72 UTF-8 bytes，registrationFeedbackForApiError 没有对应映射，register-page:88 显示 serviceUnavailable。可由用户修正的输入被当作服务故障，且重试永远失败。应同步字节边界、本地化密码字段反馈及 canonical delta，保持现有哈希方案。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Direct evidence

### R1-C1: fork data loss

使用临时隔离 SQLite、当前 `IM.app.create_app`、真实 ASGI HTTP `TestClient` 和现有 `gateway_socket` 协议节点。初始化专用用户、Agent、原始完成消息；在另线程发 `POST /im/v1/conversations/{source}/fork`，收到真实 `session.fork.request` 后保留结果等待，再通过真人公开 HTTP 入口操作预建分支：

1. `GET /im/v1/conversations` → 200，包含该预建分支。
2. `POST /im/v1/conversations/{branch}/messages`，普通真人身份、普通 content、无 `suppress_relay` → 201。
3. 协议节点发送相关 `session.fork.result {ok:false,error:"fork rejected"}`。
4. 原 fork → 502；随后 `GET /im/v1/conversations/{branch}` → 404；数据库该分支消息数 → 0。

更低层的 company_lease / await_outside_gate 受控 Future 复现也观察到“等待时消息数 1 → 失败后 0”，并确认 gate 未泄漏。成功后的复制异常关联来自同一可到达分支及 :588 无条件 cascade；本轮没有将其单独虚构为第二 finding。临时目录自动清理，无残留服务；未操作生产或用户浏览器。

### R1-C2: password feedback

同版本临时隔离 HTTP 注册 `password='a' * 73` → 422，detail 为 `password must be at most 72 UTF-8 bytes`。源码直接连接：`auth-form-feedback.ts:37,44-51` 放行该输入，`:54-70` 对此 detail 返回 null，`register-page.tsx:83-88` 因而选 serviceUnavailable。当前契约 `docs/specs/im/auth-tenancy.md:57-75` 要求可本地判断及服务端可修正拒绝提供字段反馈。

## Coverage and reused validation

已核对 lease 的任务归属、响应释放、取消重取及身份复核；密码线程的实际名额生命周期与用户/hash/epoch 复核；独立限流连接生命周期、固定窗口及 source/pair/target 预算；每 Agent 锁等待和 create existence 重查、已有 CAS/pending/recovery；全部 control Future 与 permission wait 接线；Cookie/Origin/标记/原生 JSON 边界；Web Locks、single-flight、会话 revision、无凭据 BroadcastChannel 和既有用户缓存清理；生产 HTML CSP、API 文档例外、HTTPS 配置驱动 HSTS、附件及 WS 配置。其余变动主要为旧 refresh fixture 移除及相应存储/会话测试重写，未发现存活问题。

复用冻结版本已有可信验证，未重复全量：Python `pytest -m 'not e2e' -n4 --dist worksteal` 4112 passed / 27 warnings / 85.35s；前端 85 files / 799 tests passed / 17.42s。独立读取 `/tmp/bugfix-576-full-tests.log` 与 `/tmp/bugfix-576-frontend-tests.log` 末尾摘要确认；窄回归、build、Ruff、docs-check 结果由 progress/主 Agent 回报提供。全量通过没有覆盖上述新增触发场景，不能作为它们的反证。

产品 HTTPS 真浏览器 full 验收已交付 `M1-hardening/regression.md`（report commit `4f008a8bd`，源实现仍为 `9b9478ebe`）。其主链、两标签、真实 TLS/头、图片和 WS 均通过；唯一 R1-01 major 为密码字节上限服务故障反馈，与本轮 R1-C2 是同一根因。复用其真实浏览器证据，没有将本静态审查冒充视觉或部署验收。
