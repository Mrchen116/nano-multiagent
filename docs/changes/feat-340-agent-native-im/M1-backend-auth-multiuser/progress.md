# feat-340-M1 — Progress

## R1 — auth domain + service (bcrypt + JWT)

- Context: 多用户特性的根:每个 user 行需要 password_hash;auth 流必须用真 bcrypt + 真 JWT 而不是占位符,否则后续路由切换无法做真鉴权。
- Decision:
  - User domain 加 `password_hash: str | None`(legacy 行可空)+ `locale: str` 字段
  - users 表 ALTER 加两列(开发期不写 down migration,DB 自动 backfill)
  - `IM.application.auth_service.AuthService` 提供 register/login/refresh/logout/verify_access_token,bcrypt + PyJWT,refresh-token jti 内存黑名单实现 rotation
  - 添加项目级 dep:`bcrypt>=4`、`pyjwt>=2.8`
- Rationale:
  - bcrypt:行业默认,无需新引入 argon2 依赖
  - JWT HS256:无外部 IdP,签名密钥从 env(`IM_JWT_SECRET`)或开发期 per-process 随机
  - refresh jti 黑名单:进程内存即可——FastAPI 单实例;重启全失效是可接受的开发态权衡
  - 未做 oracle 隔离:登录失败的"unknown user"和"wrong password"统一抛 `InvalidCredentialsError`,避免存在性泄漏
- Evidence:
  - `pytest tests/im_service/unit/test_auth_service.py` 12/12 通过
  - 全 IM unit + contract:80/80 通过,未回归
- Rollback: revert C2(19f105a),`alter table users drop column password_hash, locale`(开发期可直接 reset DB)
- Commits: C1=13a7a8a(tests RED), C2=19f105a(实现), C3 待跟进
- Next: R2 — auth HTTP routes + Bearer dependency

## R2 — auth HTTP routes + Bearer dependency

- Context: 服务态需要 5 个端点(register/login/refresh/logout/me)对接前端,且后续路由都需要从 `Authorization: Bearer <token>` 提 user。
- Decision:
  - `src/IM/api/routes/auth.py`:5 个端点,统一返回 `TokenPairResponse`(register/login/refresh)或 `AuthUserResponse`(me)
  - `deps.py`:加 `get_auth_service` + `current_user`(Bearer 头解析)+ `_extract_bearer_token` 私函数(401 + WWW-Authenticate)
  - `app.py`:lifespan 内构造 AuthService 挂到 `app.state.auth_service`;`resolve_jwt_secret()` 从 env 或 per-process 随机 token;`app.include_router(auth_router)`
- Rationale:
  - AuthService per-app instance:每个 TestClient 拿到全新黑名单,杜绝跨测试污染
  - 错误码:duplicate username = 409,wrong password / no token / bad token / expired / revoked refresh 统一 401(避免存在性 oracle)
  - 响应体不含 `password_hash`,通过新建 `AuthUserResponse` 显式包装 User
- Evidence:
  - `pytest tests/im_service/integration/test_auth_routes.py` 8/8 通过(register / duplicate 409 / login + me / wrong password 401 / no header 401 / bad token 401 / refresh rotation + replay 401 / logout 401)
  - `pytest tests/im_service/{unit,contract,integration} --deselect <pre-existing PA failures>` 130/130 通过(无回归)
- Rollback: revert C2(aa52a39) + drop `include_router(auth_router)`
- Commits: C1=ac35438, C2=aa52a39, C3 待跟进
- Next: R3 — UserRepository 已就绪;R3 改名为 owner-scoped 数据访问 + route 接 token-derived owner_id(原 R3+R4 合并)

## R3 — owner-scoped repository reads (foundational data layer)

- Context: 多用户隔离的硬约束(design §2a)要求 repository 在 SQL 层就把 `WHERE owner_id = ?` 加上,杜绝 API 路由层"漏写过滤"导致的跨租户泄漏。本 roadpoint 先把基础设施层铺好,下个 roadpoint 才能把路由切到 `current_user` 后无缝接入。
- Decision:
  - 在 `ConversationRepository` 上加 `list_conversations_for_owner` / `get_conversation_for_owner`
  - 在 `AgentProfileRepository` 上加 `list_runtime_selectable_profiles_for_owner` / `get_profile_for_owner`
  - 在 `NodeRepository` 上加 `list_nodes_for_owner` / `get_node_for_owner`
  - 跨租户语义:"另一个 owner 的资源"统一返回 **None**(让 route 层翻成 404),**不**抛 PermissionError——避免存在性 oracle
- Rationale:
  - 不引入 `OwnerScopedRepository` 包装类:本项目 repo 是 sqlite-thin 风格,直接在底层方法上加 `_for_owner` 后缀更明确、不增加间接层(符合用户写明的"代码复杂度最低 + 易于演进 + 运行稳定"决策原则)
  - SQL 层过滤(`WHERE owner_id = ?`)而不是 Python 后过滤:防止有人用旧 `list_*()` 在 route 里 forgot 过滤
- Evidence:
  - `pytest tests/im_service/unit/test_owner_scoped_repositories.py` 5/5 通过
  - IM unit + contract 全套:85/85 通过(无回归)
- Rollback: revert 9e464f0 + e245862
- Commits: C1=e245862, C2=9e464f0, C3 待跟进
- Next: R4(剩余):把路由层切到 `current_user` 派发的 owner_id;并发文 issue 提示 reviewer/orchestrator

## [Handoff after R3] 余下工作清单(供下一 worker 继续)

实现期内 budget 限制,M1 在 R3 截止。下面的 roadpoint 由后续 worker 接同一 worktree+branch 续跑(`change-impl-worker` 的"继续派发"语义):

### R4 — 路由切 `current_user`(主体)

需改的文件:
- `src/IM/api/routes/account.py`:`get_me` / `update_me` 不再读 `?user_id=`,改 `user = Depends(current_user)`;`bind_device` confirm 从 token 取 user_id
- `src/IM/api/routes/web_im.py`:`list_conversations` / `get_conversation` / `update_conversation` / `delete_conversation`(后者从 token 取 requester_id,删 `DeleteConversationRequest.requester_id`)走 `current_user`;路由内调 `list_conversations_for_owner` / `get_conversation_for_owner`;404 替代 403 隔离泄漏
- `src/IM/api/routes/messages.py`:`create_message` / `list_messages` 用 `current_user`;在动作前用 `get_conversation_for_owner` 校验会话归属(否则 404)
- `src/IM/api/routes/agents.py`:`list_agents` / `get_agent_config` / `update_agent_config` / `get_agent_capabilities` 用 `current_user`;route 内调 `list_runtime_selectable_profiles_for_owner` / `get_profile_for_owner`
- `src/IM/api/routes/nodes.py`:`list_nodes` / `get_node_capabilities` / `create_node_agent` / `update_node_config` 用 `current_user`;owner 不属于 current → 404
- 删 `src/IM/api/routes/users.py` 的 `GET /im/v1/users` 与 `POST /im/v1/users`(register 接管);保留文件骨架仅在 app.py 不再 include 即可,或整文件删除 + 改 app.py
- `src/IM/api/routes/policies.py` / `metrics.py`:策略文档是单例,policies 不需 owner 过滤;`metrics` 必须 owner-scope(改 `UsageMetricsRepository.list_usage_metrics` 接 owner_id 参数,加 owner-scoped 方法)

测试 fixture:加 `_make_authed_client(tmp_path) -> (client, user)`:register + 返回 access_token + 注入 `Authorization` header(`client.headers["Authorization"] = f"Bearer {token}"`)。所有 9 个集成测试改用它(或加 conftest 共享 helper)。

### R5 — WS owner-scoped 鉴权

- `serve_user_websocket` 从 `?token=<jwt>` query 或 `Sec-WebSocket-Protocol: bearer.<jwt>` 解 token → user_id(用 `AuthService.verify_access_token`)。无效 → close 1008。app.py 的 `user_stream_websocket` 处理函数移除 `?user_id=` 参数。
- `resolve_recipient_user_ids` 本质已 owner-scoped(按 conversation_participants 过滤;参与者必须属于本 owner)。但要新增一道防御:`user_id ∈ conversation_participants` 的同时,触发事件的 conversation 的 owner_id 必须 = user 的 owner_id —— 否则丢弃(防止数据库历史脏数据穿透)。
- 新增 e2e:启 TestClient,A 和 B 各注册并连 WS,A 触发 B 的会话事件 → B 不接收。

### R6 — cross-tenant isolation e2e + init_admin CLI

- 新 `tests/im_service/integration/test_auth_multiuser_isolation.py`:覆盖每种资源(conversation / message / agent / node / me)的跨租户 404
- 新 `src/IM/cli/__init__.py` + `src/IM/cli/__main__.py` + `src/IM/cli/init_admin.py`:`python -m IM.cli init_admin --username X --password Y --display-name Z` 直接调 AuthService.register
- 集成测试:`subprocess` 跑 CLI 后用 `TestClient` 登录验证

### R7 — 收尾

- 回填 progress.md(每个完成的 R)
- 更新 `docs/operator-runbook.md`:多用户启动流程 + init_admin
- 合并到 unit/feat-340-agent-native-im,清理 worktree
- 通知 orchestrator DONE

### 已完成基础(可信赖)

| 模块 | 状态 |
|---|---|
| auth_service (bcrypt + JWT + jti blacklist) | ✓ 12 unit tests |
| `/im/v1/auth/{register,login,refresh,logout,me}` | ✓ 8 integration tests |
| `current_user` FastAPI dep + Bearer 解析 | ✓ |
| User.password_hash / User.locale + users 表 ALTER | ✓ |
| owner-scoped repo reads (Conversation/AgentProfile/Node) | ✓ 5 unit tests |
| Bcrypt + PyJWT 项目依赖 | ✓ pyproject.toml |

### Baseline 已知失败(非本 milestone 范围)

- `tests/im_service/integration/test_m103_im_gateway_e2e.py` — `_FakeKernelClient.submit_message` 缺失,属于 personal_assistant gateway 桥接破损,M1 前已存在
- `tests/im_service/integration/test_m136_group_chat_flow.py` (3 个) — 同上,同一根因
- 这些不在 M1 改动文件范围内,留给后续修复或 orchestrator 立 issue



