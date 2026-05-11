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


