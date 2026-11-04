# Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_stable_session`，独立于 design author。
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖首文档、完整方案、真实装配入口、canonical delta 和单 M1。
- reviewed_tree: `1cb246bee786ea77cec95e5dff0657e3ba1a01db`；审查开始时 checkout clean，detached HEAD。
- started_at: `2026-11-04T09:12:41+08:00`（报告计时起点；此前已完成资料读取）
- completed_at: `2026-11-04T09:13:38+08:00`
- duration: 报告整理 57 秒；资料读取与代码核对不含在此计时内。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

稳定浏览器凭据、30 天滚动期限和程序客户端继续一次性轮换的核心设计可在现有架构内实现。当前 delta 尚不能按 canonical 归并规则执行，需要补齐后复核；本轮不批准进入实施。

### Coverage 与证据

1. **现状与实际装配入口。** `apps/im-server/src/server.ts:70-91,173` 通过 `openDatabase`、`createIdentity` 和 `registerIdentityRoutes` 组装真实 IM；审查的不是仅供测试使用的身份实现。`identity.ts:290-335,363-407` 当前按有效会话、签名、JWT 期限、epoch 和 refresh hash 校验，`issuePair` 在响应前更新 hash，因此响应丢失后旧 Cookie 被拒的 RCA 与代码一致。具体造成生产响应未保存的请求仍未知，incident 没有把推论写成已确认触发条件。
2. **需求与协议闭合。** `design.md:5-17` 复用随机 sid、hash、expires_at、revoked、epoch 与短期 access。稳定两段凭据只验证、不替换 secret，续期只延长期限，符合用户明确选择的“不按每次 refresh 轮换”及 30 天滚动要求。保留现有 JWT `jti` 与 hash 并返回 `sid.jti`，可由同一有效旧 JWT 重复计算相同 Cookie，首个升级响应丢失不会消费旧凭据。旧 JWT 仍须满足自身签名、期限和当前 hash；已经失步、过期或撤销的凭据不会复活。此处不要求恢复历史失步会话。
3. **浏览器与程序客户端隔离。** `identity-routes.ts:14,36-54,79-97,129-144` 当前已经以浏览器标记区分 Cookie 与 JSON transport 并验证许可 Origin。新设计在 Identity 内用 `browser_session` 阻止已升级旧 JWT 被程序 refresh 再次消费，并要求稳定凭据仅匹配已标记会话，能够避免程序接口轮换破坏稳定 Cookie。Web `src/IM/frontend/src/features/auth/auth-api.ts:24-30,58-64` 只传浏览器标记与 Cookie，不读取 refresh；`auth-session.ts:49-78` 在失败后保留临时重试路径。iOS `src/IM/ios/NanoIM/Client/Session.swift:125-160` 继续显式 JSON refresh 与 TokenPair 安装，设计不要求客户端布局或存储协议改变。
4. **退出、期限与安全边界。** `identity.ts:290-335,409-433` 的有效会话与撤销事务能继续覆盖 access、epoch、ticket 与会话期限。`identity-routes.ts:33-54,79-97` 的 host-only、HttpOnly、SameSite、Secure、Cookie-only 和 Origin 边界，以及 `server.ts:123-153` 的认证 no-store/CORS 响应装配有真实落点。新增浏览器 logout 复用撤销事务与现有 closeSession 路由接续，不新增第二套撤销状态。稳定凭据泄露后的可重复使用期限是用户明确选择的协议性质，本轮不以此要求恢复逐次轮换。
5. **数据升级与职责。** `db.ts:26-38` 已有按 `PRAGMA table_info` 加列的启动机制；新增带默认值的 `browser_session` 可沿该模式幂等升级，旧行默认保持程序/未升级语义。无须人工数据映射或生产测试写入，因此没有 `deployment-prompt.md` 不构成缺口。身份验证与状态更新由 Identity 持有、transport 由 identity-routes 持有、schema 升级由 db/schema 持有，复用既有会话及撤销能力优于另造浏览器会话表/撤销机制；依赖仍停留 IM 内，不触及 PA、Channels、Node 或 DSH。
6. **delta 与 milestone。** canonical target `docs/specs/im/auth-tenancy.md` 正确，但 delta 的位置及完整替换内容存在 R1-W1。`design.md:23-27` 的单 M1 覆盖响应丢失、并发、旧 JWT 重试、失效边界、原生轮换、旧库启动以及隔离 Chrome 旅程，未将自动测试当作用户验收，也未把生产当作验证环境。新增字段会影响 `apps/im-server/tests/identity.test.ts:330` 的位置式 INSERT，该文件已在 M1 范围内，实施时直接调整 fixture 即可，无须新增里程碑。
7. **前端与 Agent Context。** 本次不改变画面、信息组织或交互入口，浏览器使用既有登录恢复路径，不需 prototype 或视觉 must-match。本轮没有启动 UI，也不声称完成真实产品验收；相关 Chrome 旅程已明确留给实施后的独立产品 reviewer。变更仅影响真人认证凭据，不改变模型可见信息或其选择、注入、加载和恢复，不触发 Agent Context review。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — delta 不是可执行归并的完整 canonical 条目

- 位置：`docs/changes/bugfix-709-stable-browser-session/delta-spec.md:1-15`。
- 证据：`docs/specs/CONTRIBUTING.md` 的“契约层增量”要求 delta 位于 `specs/<包>/<target>.md`，采用 Requirement/Scenario 骨架，MODIFIED 写修改后的完整 Requirement；归并规则按同名 Requirement 替换。当前文件位于 unit 根目录，只提供摘要和“保留既有……场景”，还将 canonical Requirement 内的 `refresh 并发、登出与重启` Scenario 列成单独 MODIFIED 条目。canonical 的 Requirement 正文、“refresh 轮换令牌”场景以及“浏览器令牌保存与页面恢复”场景均继续明确要求浏览器一次性轮换，与目标行为冲突。
- 未修后果：下游无法据此直接替换完整 Requirement；若只追加摘要会保留互相冲突的浏览器轮换契约，若把摘要当作完整替换则会丢失注册、登录错误、Origin、准入和登录记录等未改变场景。
- 所需修订：将 delta 放到 `specs/im/auth-tenancy.md`，提供该 MODIFIED Requirement 的完整最终条目，明确区分程序 refresh 与浏览器稳定凭据，并保留全部未改变场景；响应丢失、旧 JWT 升级和并发差异放入该 Requirement 对应场景。无需扩展到其他 canonical Requirement 或新增 milestone。

### Recommendations

- **R1-R1：** 在 design 补一句回退边界：旧版本无法解析两段稳定 Cookie，回退会使已升级浏览器重新登录；新增字段可保留，勿通过清空认证表或恢复已消费凭据来回退。该后果可由现有 JWT-only 解码器直接确定，不需引入双协议长期兼容或生产演练。
- **R1-R2：** 按 `docs/changes/README.md:73` 补齐仅含 `.gitkeep` 的 `M1-session/` 骨架。当前单 M1 的内容和范围已经明确，此项不改变技术决定。

## Author Resolutions

R1-W1 已按 canonical Requirement 完整复制与修订场景到 specs/im/auth-tenancy.md，删除摘要式 delta-spec.md。核心协议和范围不变。
