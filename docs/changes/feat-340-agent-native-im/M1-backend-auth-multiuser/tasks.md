# feat-340-M1: backend-auth-multiuser — Tasks

> 对齐: ../design.md v1

## 目标

IM 后端从"单用户硬编码"切到"多用户 JWT auth + 严格 owner_id 租户隔离"。
完成后:
- `POST /im/v1/auth/{register,login,refresh,logout}` 可注册/登录/刷新/登出
- `GET /im/v1/auth/me` 返回当前用户
- 所有现有 `/im/v1/*` 路由从 `Authorization: Bearer <token>` 提取 owner_id,不再吃 `?user_id=` query
- 所有列表/详情查询在 repository 底层被 `OwnerScopedRepository` 强制按 owner_id 过滤
- `/im/ws/user` 用 token 鉴权;事件分发器只把事件投给资源 owner 的连接
- 跨租户单元测试:用户 A 的 token 访问 owner_id=B 的资源一律 404
- `python -m IM.cli init_admin --username … --password …` 可在空库里建第一个用户
- `GET /im/v1/users` 删除(隔离原则下没有"列出全部用户"的合法用例)

## 退出标准

- [ ] register → login → 拿 access_token → `Authorization: Bearer <t>` 调 `/im/v1/auth/me` 返回正确身份
- [ ] 路由全部不再读 `?user_id=`、`payload.user_id`(account/me)、`payload.requester_id`(delete_conversation)——身份来自 token
- [ ] `OwnerScopedRepository` 基类已落地;list_conversations / list_messages / list_agents / list_nodes / get_me 自动按 owner_id 过滤
- [ ] 用户 A 用 token A `GET /im/v1/conversations/{B 的 conv_id}` 返回 404(不泄漏存在性)
- [ ] 用户 A 用 token A `GET /im/v1/agents/{B 的 agent_id}/config` 返回 404
- [ ] 用户 A 的 WS 连接收不到 owner_id=B 的 conversation_event
- [ ] `GET /im/v1/users` 路由删除(返回 404)
- [ ] `init_admin` CLI 可建首用户
- [ ] 全部既有非 personal_assistant 测试绿;新增多用户隔离测试全绿
- [ ] M1 改动只涉及 `src/IM/**` 和 `tests/im_service/**`(不动 frontend / personal_assistant)

## 测试策略

**真实入口测试(必须)**: 用 FastAPI `TestClient` 走真实 HTTP 路径:register → login → 用拿到的 token 调 `/im/v1/me` / `/im/v1/conversations` / `/im/v1/agents`。不 mock auth_service。bcrypt + JWT 算法用真实库,签名校验真发生。

**跨租户隔离 e2e**: 创建两个用户 A/B,分别建会话/agent/node;用 A 的 token 尝试读取 B 的资源——必须 404。新增 `tests/im_service/integration/test_auth_multiuser_isolation.py`。

**WS 隔离**: 用 `TestClient.websocket_connect` 起 A 的 WS,触发 B 的 message——A 的 WS 不应收到。

**单元**: `auth_service` 的 password hash / verify / JWT encode-decode / refresh 黑名单 — 单独单测。`OwnerScopedRepository` 的过滤行为单测。

**回归现有**: 修改大量现有测试以注入 token header(必要时)。优先在测试 fixture 集中加 `authed_client(user_id)` helper,避免每个测试改 30 行。

## Roadpoints

### R1 — auth domain + service:用户 password_hash/locale + JWT + bcrypt [DONE]

- 步骤:
  - 加 User.password_hash / locale 字段(domain model)
  - users 表加 password_hash TEXT / locale TEXT NOT NULL DEFAULT 'en'(migrate_users)
  - 新 `src/IM/application/auth_service.py`:register / login / refresh / logout / verify_token / current_user_id_from_token,bcrypt + PyJWT,黑名单 in-memory
  - 单元测试 `tests/im_service/unit/test_auth_service.py`:hash/verify、JWT 签发/解码、refresh 轮换、过期、错密码、错 token、黑名单
- 验证: 单元测试全绿;`pytest tests/im_service/unit/test_auth_service.py`

### R2 — auth HTTP routes + Bearer 依赖

- 步骤:
  - 新 `src/IM/api/routes/auth.py`:5 个端点
  - 新 `current_user_dep` (FastAPI dep) 从 Authorization header 解 token → user_id;失败 401
  - app.py include auth_router;`auth_service` 单例放 app.state
  - 集成测试 `tests/im_service/integration/test_auth_routes.py`:注册→登录→me→refresh→logout 全链路真请求
- 验证: 集成测试全绿

### R3 — OwnerScopedRepository 基类 + UserRepository.create_user 接收 password/locale

- 步骤:
  - `src/IM/infra/repository_scope.py`:`OwnerScopedRepository` (装饰已有 repos,绑定 owner_id);提供 list/get/update/delete 自动加 `WHERE owner_id = ?` 的方法签名。实际做法:在现有 repo 上新增"owner-scoped"读方法(list_conversations_for_owner、get_conversation_for_owner 等)+在 deps.py 改 factory 返回绑定 owner_id 的瘦包装。
  - UserRepository.create_user 接收 password_hash(可选 None — auth 流程会强制非 None,但兼容旧测试 fixture 走"system create" 时给 None)。locale 同理。
  - 单元测试:跨租户过滤行为
- 验证: 单元测试

### R4 — 路由切到 token-derived owner_id;删 GET /im/v1/users

- 步骤:
  - account/me, messages, web_im(conversations), agents, nodes 路由全部把 user_id query 改成 `current_user = Depends(current_user_dep)`,从中取 owner_id
  - delete_conversation 不再读 payload.requester_id;改读 current_user
  - `GET /im/v1/users` 删除;`POST /im/v1/users` 也删(register 接管创建)
  - 改 deps.py factory 接受 request 注入 owner_id 后建立 owner-scoped repository 视图
  - 改既有测试 fixture:加 `register_and_login()` helper 在每个 IM 集成测试里建 user + 拿 token + 注入 header
- 验证: `pytest tests/im_service -k "not e2e and not personal_assistant"` 全绿

### R5 — WS owner-scoped 广播 + token query / protocol 鉴权

- 步骤:
  - `serve_user_websocket`:从 `?token=` query(开发环境最简)或 `Sec-WebSocket-Protocol` 拿 token 解出 user_id;无效 → close 1008
  - `resolve_recipient_user_ids` 已经按 conversation_participants 过滤,本质上已 owner-scoped(参与者必须有 user_id),只要 conversation 创建时严格按 owner_id 隔离就 OK
  - 新增 e2e 隔离测试:用户 A 的 WS 不收到用户 B 的会话事件
- 验证: 集成测试

### R6 — init_admin CLI + 跨租户 e2e 全套测试

- 步骤:
  - `src/IM/cli/__init__.py` + `init_admin.py`:`python -m IM.cli init_admin --username X --password Y` 直接调 UserRepository.create_user_with_credentials
  - `tests/im_service/integration/test_auth_multiuser_isolation.py`:覆盖每种资源(conversation / message / agent / node / me)的跨租户 404
- 验证: `pytest tests/im_service --ignore=tests/im_service/e2e -k "not test_m103_im_gateway_e2e and not test_m136_group_chat_flow"` 全绿(后两个是 pre-existing personal_assistant 桥接破损,不在本 milestone 范围)

### R7 — 文档收尾

- 步骤: 回填 progress.md + 更新 AGENTS.md/docs/operator-runbook(若需要)说明 init_admin 用法
- 验证: 自检
