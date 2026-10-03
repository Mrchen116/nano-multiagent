# bugfix-576 — 回归验证

> 对齐：incident.md、design.md。Round 1，mode=full。
> Validation snapshot: `9b9478ebe0c1075ccc9b166afae80f3190a604fb → 9b9478ebe0c1075ccc9b166afae80f3190a604fb`

## Verdict

**fail** — 1 major，Highest Required Action: **fix-implementation**，needs_re_review=true。

真实浏览器认证、Cookie 恢复、聊天与安全头主链通过；注册密码超过 72 UTF-8 字节时，用户可修正的输入错误被错误呈现为临时服务故障。修复后可 targeted 复验这一问题及相邻密码校验，保留下列未失效证据。独立静态核对报告的后端问题由其自身门禁裁决，本报告不替代它。

## Reference Artifacts Reviewed / 环境

- `incident.md` 全部验收场景、`design.md` 的浏览器策略、Runbook 和 M1 两轨退出标准；current `docs/specs/im/auth-tenancy.md`。
- 未读取实现寻找根因，未修改代码、测试、配置或设计。
- 开始时 HEAD 与指定版本一致，branch `unit/bugfix-576`；仅有本次运行 `output/` 未跟踪文件。调用方交接 PID 39780、该 checkout 的前端产物，未重启服务。
- `https://localhost:50352`，独立 SQLite、上传目录和账号；Chromium 1234 临时隔离 profile。仅 context ignoreHTTPSErrors 接受临时自签证书，未改系统钥匙串。
- 真实 UI 创建 `review-member576`，经专用管理员批准，创建群聊 `c_1gzk61md`，最后停用该成员。无真实 LLM、外部平台或生产资源。
- 截图均实际打开检查：本地 `output/security-hardening/reviewer/` 的 `pending-desktop.png`、`chat-desktop.png`（1440×1000）、`login-mobile.png`、`chat-mobile.png`、`long-password.png`（390×844）、`network-error.png`。截图和运行数据不提交；下面保留可审核的步骤及脱敏结果。

## 复现验证与场景矩阵

| incident 场景 | 结果 | 实际证据与边界 |
|---|---|---|
| 并发错误登录与正常读取 | pass | 独立真 HTTPS 实例同时发五个不同未知账号错误登录：两次 401，耗时 0.198/0.202s；三次 429，0.009/0.011/0.013s，Retry-After=1。并发 `/auth/me` 200，0.003s，在密码校验结束前完成。临时 probes.py 驱动真实 HTTP，不是容量承诺。 |
| Gateway 等待与成员撤销 | not-applicable（本轮浏览器独立证据范围） | design M1 明确将慢 RPC、撤销、取消清理和同 Agent 锁列为 worker 退出项；caller 确认沿用此分工。对应 `test_company_control_waits.py` 和 fork 三结果回归由 worker/verification 门禁承担，不把本轮浏览器结果冒充完整 RPC 验收。 |
| 错误来源受限、合法来源仍可尝试 | pass（确定性回归；非双真实 IP） | `test_auth_concurrency.py` 验证来源 A 十次错误后正确密码仍 429/Retry-After>800，B 正确 200，C 紧接 429/1s，一秒后 200。Mac 的真实 `local_address=127.0.0.2` 返回 Errno49，未修改系统网络或伪造不可信来源头来声称真实跨来源通过。 |
| 分散猜测与重试 | pass（预算回归与真 HTTP） | 上述真实两计算名额/有界拒绝；固定窗口与目标桶由 auth_concurrency 确定性回归覆盖。未知账号返回 401；用户存在与密码错误无账户存在性文案。未做生产或持续分布式负载测试。 |
| 登录、刷新页面与多标签续期 | pass | UI 注册直接到 Waiting for approval；批准后 Refresh status 到 chat。两同源标签同时 reload 后均显示成员身份且位于 chat。浏览器 login/refresh JSON 仅 access_token,user；refresh Cache-Control=no-store。Cookie 名 im_refresh，HttpOnly=true、Secure=true、SameSite=Strict、Path=/；localStorage={}、sessionStorage={}、document.cookie=""。 |
| 登出、停用与失败恢复 | pass | UI Sign out 后两标签均 /login、Cookie 消失、公司消息不在页面。未登录访问 `/chat/c_1gzk61md?review=576#anchor`，UI 登录回原完整 URL。拦截 refresh 并在发送前 abort：显示服务暂不可用与 Refresh status；取消拦截后点击恢复原群聊。管理员 suspend 后旧会话不再读公司；再登录进入 Membership suspended，无公司缓存。原生 refresh 轮换200、旧refresh重放401、logout200、旧access读取401。未声称响应已经轮换但响应丢失可无损恢复；严格CAS场景可能要求重登。 |
| Cookie 不能被第三方站点驱动 | pass | 对 refresh/logout/login，browser 标记+evil.invalid Origin 和 browser标记无Origin均403，无Set-Cookie；无标记refresh/logout空JSON均422。无标记程序login200且不写Cookie。整个矩阵前后浏览器Cookie值相同。 |
| 页面加载与嵌入 | pass | 首页200；CSP script-src self、frame-ancestors none、connect-src self+wss://localhost:50352；X-Frame-Options DENY、nosniff、Referrer-Policy strict-origin-when-cross-origin、HSTS max-age=86400（无子域/preload）。真实注入inline script未执行并触发script-src-elem违规；iframe加载被frame-ancestors拦截，子frame为chrome-error。正常UI消息成功，真实用户wss连接发送1帧/收到2帧。上传PNG返回201，消息201，页面实时出现附件，img complete=true、naturalWidth=1、blob URL正常解码。 |
| 单机开发与维护边界 | not-applicable（生产构建浏览器验收范围） | caller提供的loopback HTTPS内置前端实际正常；HTTP/Vite开发流程、策略集中位置和无新增外部依赖属于worker/verification静态与回归范围。本轮未重启另一个HTTP服务或修改实现。 |

## 回归问题 R1-01

- Severity: **major**；Regression Relation: **suspected-regression**。
- Recommended Action: **fix-implementation**。
- Action Rationale: current auth-tenancy 要求服务端可修正输入拒绝在对应字段给出可行动反馈；design 保留既有表单错误语义。此问题使用户持续重试无效密码，无法从界面判断修正办法。
- 重现：打开 `/register`，用户名 `review-long576`，密码填 73 个 ASCII `x`，点击 Create account。
- 实际：HTTP 422，`detail="password must be at most 72 UTF-8 bytes"`；页面密码帮助只有“At least 8 characters.”，错误文案为“The authentication service is temporarily unavailable. Try again shortly.”，没有密码字段上限反馈。
- 期望：按实际 UTF-8 字节上限说明并定位可修正的密码输入错误，不能把它伪装成服务故障；多字节密码适用相同语义。
- 直接证据：390×844 `long-password.png` 已人工查看，浏览器响应与可见文案一致。未创建该超长密码账号。
- 复验：73 ASCII 字节与超过72字节的Unicode密码得到明确字段反馈，合法边界仍可注册；桌面/窄屏可读。

## 自动化测试与证据分工

Reviewer 未新增或修改测试。单独执行既有 `test_auth_concurrency.py`、`test_company_control_waits.py`，结果 **4 passed in 3.44s**（命令 `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest tests/im_service/integration/test_auth_concurrency.py tests/im_service/integration/test_company_control_waits.py -q`）；这些确定性回归补充真浏览器证据，不代替上述 UI 旅程。调用方提供其完整本地 CI 4112 passed 的上下文，本报告不将其标成 reviewer 独立全量执行。

## 上层文档同步

- [x] `SPEC.md`：无需更新，未改变跨包顶点架构。
- [x] `docs/specs/im/auth-tenancy.md`：需要收尾归并已验证 Cookie/安全头/预算 delta；R1-01 修复并复验前不将目标状态冒充 current。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

仅保存报告；未改动或停止 caller 的服务，未提交截图、账号密码、Cookie、令牌、运行库或临时配置。

## Round 2 — targeted 复验

> Verdict: **pass**；Highest Required Action: **pass**；open issues=0；R1-01 closed；needs_re_review=false（本报告产品验收范围）。
> Validation snapshot: `d357729af → c2d36427d1c442204fda3d87ae509aeaae901fc3`。
> fix_delta_range: `9b9478ebe..c2d36427d`；prior_acceptance: 本报告 Round 1；focus: R1-01 和相邻密码边界。

### 元数据澄清与证据继承

调用方澄清：executed_base 应为 `origin/main` 的 `d357729af`；R1 交接误将实现 HEAD 同时作为 executed_base。本追加纠正该元数据，不改写 R1 实际执行事实：其浏览器及回归执行版本始终是 `9b9478ebe`。本轮开始确认 HEAD=`c2d36427d1c442204fda3d87ae509aeaae901fc3`，调用方已在同一隔离 HTTPS origin 重建前端并启动新 PID 44204；未重启服务。

范围只覆盖注册上限字段反馈及边界。R1 的会话、Cookie、多标签、退出/停用、深链、请求发送前网络失败恢复、安全头、正常 WSS 和附件证据仍保留，并未因报告提交而重跑。此次 fork 清理变更不属于本次 UI 旅程，继续由独立 verification 门禁裁决。未读取实现定位根因；只追加本报告。

### 真实 Chromium 复验

| 检查 | 实际结果 | 结论 |
|---|---|---|
| EN 桌面，73 ASCII 字节 | UI 输入73个ASCII字符并提交，注册网络请求数0；密码字段 aria-invalid=true，显示“Password is too long. Shorten it to at most 72 bytes; non-English characters can use several bytes.” | pass |
| 中文窄屏，25个中文字符/75字节 | 输入25个“密”并提交，注册网络请求数0；显示“密码过长，请缩短至 72 字节以内；中文或表情会占多个字节。”，无服务异常误报，无水平溢出 | pass |
| Unicode 合法边界 | 同字段改为24个“密”/72字节，旧错误立即消失；真实注册201，响应只有access_token,user，进入等待管理员批准页，测试用户review-boundary576a | pass |
| 服务端422字段映射 | 表单填合法72ASCII字节，通过Playwright request route仅将发往真实服务端的password改为73ASCII字节，未模拟响应；真实422/detail=“password must be at most 72 UTF-8 bytes”，UI映射为对应密码字段提示且aria-invalid=true | pass |
| ASCII 合法边界 | 撤销上述request route，表单填72ASCII字节，真实注册201，进入Waiting for approval，测试用户review-boundary576b | pass |
| 桌面/窄屏视觉 | 1440×1000和390×844截图均已实际打开审阅；提示位于密码输入框下、换行正常，创建账号按钮与页脚可操作，pending页正常 | pass |

本轮仅3次真实注册提交（两个成功边界账号、一次故意触发服务端422）；前端两次超界验证不消耗注册请求。没有修改系统配置或访问生产。

### 本地视觉证据

位于 `output/security-hardening/reviewer/`：`r2-ascii-desktop.png`、`r2-unicode-mobile.png`、`r2-server-field.png`、`r2-ascii-boundary.png`、`r2-unicode-boundary.png`。均已人工查看，不提交截图缓存。未创建临时Python脚本；结束仅关闭本次Chromium会话，保留caller服务。

R1-01 的期望用户结果现已出现，不再阻塞产品验收。上层文档同步要求沿用R1，等待orchestrator按最终门禁归并。
