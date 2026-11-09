# perf-754 · 独立设计审查

## Round 1

- Reviewer target `/root/work_reads_design`，独立设计 reviewer。
- review_mode `full`。首次 Gate 2，覆盖首文档、设计、delta-spec、milestone，以及真实节点／中心／Work 客户端。
- started_at `2026-11-10T00:53:02+08:00`，completed_at `2026-11-10T00:54:12+08:00`，duration 70 秒。
- 基线 `3179cd45f`。冻结输入 `motivation.md` SHA-256 前缀 `ba9d2622fa2e`、`design.md` `569284a33fab`、`specs/im/agent-work.md` `5f87194096ca`，milestone 骨架仅 `.gitkeep`。

**Issues Found · 1 CRITICAL / 6 WARNING**

### Coverage

- `apps/node/src/main.ts:299–324,429–431,609` 在现有节点注册与生命周期下启动 PA 包的 `WorkSync`，沿独立 HTTP 上传本地共享 journal；`packages/personal-assistant/src/work-sync.ts:129–181` 在前条 durable ACK 后才发下一条。现有 16 MiB 本机 pause 和服务端 413 有测试覆盖。基线确认任一根的超限事件会挡住同节点的下一条。
- 中心真实装配在 `apps/im-server/src/server.ts:112–121,147–155,191,195`。继续用一个 append/project/journal 主链，文件存储负责原字节，客户端按需读取，符合当前职责。无需改 DSH 接入、模型上下文、聊天准入或把 Work 改为第二条 journal。大原文路由独立于 perf-753 的目录读取，但二者有共同的 Work item 和客户端入口。
- 现有 Web 和 iOS 从已授权 Work 轮次打开执行明细。局部的原文入口、进度与错误状态可以沿用当前卡片和列表控件，设计评审无需生成独立原型。已读实现基线，未观察候选画面。
- 本轮仅审设计和源码。容量、恢复、前端交互以及成对备份恢复的实际证据仍由 M1 交付。

### Issues

#### R1-C1 · 必须在中心把原文归到实际已授权的事件

[设计](design.md) 约定完整原文和小投影分别到达。全量 SHA-256 可以确认重传的字节相同，却不能确认原文里的 root、session、event、turn、type 与投影相同。现有中心从实际上传内容解码后再检查 root、node、session 和可用性。若新版只校验投影，拥有同一节点凭据的上传方可以将 PA 或其他私有根的原事件绑定到可被公司成员查看的根，读取方的 Work 权限此时只保护伪造的关联。明确中心如何在内存受限下校验原事件格式及安全相关身份，并验证投影中影响授权、链接和事件语义的字段与原文一致。每个原文请求从已提交记录反查当前 root、session 和访问资格，路径或哈希不能成为凭据。隔离测试覆盖两个同节点、不同 Work 资格的根以及正文／投影错配。证据见 `apps/im-server/src/work-sync.ts:231–242,290–305`、`work-records.ts:123–177`、`work.ts:394–406` 和 `packages/product-contracts/src/work-event-codec.ts:24–38,83–94`。

#### R1-W1 · 文件、引用与游标缺少可恢复的提交和删除边界

[设计](design.md) 承诺原子同进度，但文件系统与 SQLite 是两个持久资源。现有 append 会在同一事务内投影并推进 ACK，也允许 redaction 或 owner 对空间失去资格时只保留进度；v1 另有按游标标记上传已完成的 trigger。应收口新协议的有界状态与提交顺序，确保可读文件持久后才原子写入原文引用、投影、receipt 和 checkpoint，拒绝中途的绑定／删除状态变化与 v1 并发填同一位置，只有成功提交才允许返回前进 ACK。回执丢失应直接用持久事实应答。删除沿用现有精确 manifest 和 purge 语义，需说明暂存／已提交文件如何与删除 tombstone 交接、重启如何继续清理，以及怎样避免删除同一 journal 的其他根。验证覆盖文件持久前后、DB commit 前后和删除与 finalization 并发；保留失权位置按原协议推进时不留下可下载正文。证据见 `work-records.ts:105–204`、`work-sync.ts:34–79,93–111,198–215,270–305`、`agent-deletion.ts:32–39,64–69,92–105`、`apps/node/src/main.ts:547–555`。

#### R1-W2 · 固定分片尚未形成整条传输的资源上界

[设计](design.md) 没有确定新分片尺寸／分片数、在途进度表示和单条支持范围。复用现有行为会让 Gateway 读出整个 SQLite JSON、解析、重新序列化并创建全量 Buffer。服务端在每次分片返回累积 `received_parts`，客户端验证和合并数组，单条事件的进度处理随分片数二次增长。流式重算总哈希虽可控内存，单次最后分片处理时间仍随原文体量增长。请定义从持久字节到有界块的节点路径，明确进度如何以固定规模表达、最终验证和请求时限的关系，以及并发读写和永久原文磁盘配额耗尽时的行为。把“支持上限内能续传，随后另一根继续”与超过上限或资源耗尽的状态分开，避免用新的不可恢复 pause 静默重现 P0。验收给出有代表性的大小、分片数、请求次数及时间、Node 和中心 RSS／external Buffer 峰值、临时与最终字节数，并覆盖大原文上传时其他节点和用户读取的路径。证据见 `inbox.ts:578–584`、`packages/personal-assistant/src/work-sync.ts:111–119,129–187`、`apps/im-server/src/work-sync.ts:149–156,259–269,289–305`。

#### R1-W3 · 原文索引、可显示投影和两端详情入口未闭合

[设计](design.md) 说在记录详情主动打开原文。当前多个 journal 事件可以投影成同一 item，典型例子是工具开始／结束／附带发送事实，或对同一 message 的增量。也有只影响轮次摘要的事件、没有独立 Work item 的事实，以及原 codec 保留的未知类型。只在 item 上放一个引用可能使较早大事件失去入口，复用现有结构也不保证旧端看见被截取的状态。请定义原文与实际事件的一对一身份、附到何处、多个原文如何按真实顺序访问、无 item／未知类型和权限敏感字段如何处理。明确 Web 和 iOS 使用带当前授权、可取消的文件读取路径和有限预览／文件打开，避免直接复用 `response.json()`、整体 blob／Data 或 UI 渲染整个 JSON。补旧客户端预览、同一工具两条大事实、打开失败／撤权的旅程。证据见 `work-records.ts:309–392`、`work-event-codec.ts:24–35,79–81`、`agent-work-api.ts:16–24`、`IMClient.swift:18–30,43–46` 和 `Session.swift:106–121`。

#### R1-W4 · 回退会影响已提交原文的保留与删除

[设计](design.md) 指定中心先行，并提到备份包含持久文件。旧中心启动会扫描 `${dbPath}.work-sync` 并删除所有不对应 v1 未提交 upload 的目录。旧中心还不知道新 sidecar，因此即使投影可读，也可能报告 Agent 已删除但留下原文。只恢复 SQLite 而保留其已推进的游标同样不能触发节点重传缺失文件。请明确永久原文与 v1 staging 的物理隔离、旧中心回退窗口允许的操作和可再升级路径、DB 与文件的同一恢复切点，以及新节点如何确认能力和在旧中心不可用后恢复而无需误当永久错误。验证真实混合版本、已提交文件的回退／再升级、删除边界和成对备份恢复。证据见 `apps/im-server/src/work-sync.ts:119–145`、`agent-deletion.ts:64–69,92–105`、`packages/personal-assistant/src/work-sync.ts:39–57,72–79,103–108,123–135`。现设计未要求改写旧行，不需另外引入一次性数据迁移。

#### R1-W5 · delta 需要替换当前 16 MiB 行为契约

当前 `docs/specs/im/agent-work.md:182–195` 明确超过 16 MiB 取得 `event_too_large` 并让该条及后续留在本机。只 ADDED「大明细按需访问」会使新版上传与旧承诺同时存在。以正确 canonical 目标 MODIFIED 现有 Requirement，保留「工作记录暂未同步」和聊天独立等未改变场景，表达新版实际支持的超限、仍超范围或配额不足时的结果、后续正常事实和原文授权。Gateway 当前聊天准入独立场景仍适用。

#### R1-W6 · 单一 M1 合理，需固定证据和与分页单元的集成边界

[设计](design.md) 的验收已列断线、ACK 丢失、配额、撤权和删除，骨架符合阶段要求。请补 Full workflow 的 M1 表，列实际 HTTP 与 Work 双端的 [reviewer] 可观察结果，以及 [worker] 可复查的协议、资源、权限和数据恢复证据。注明与 perf-753 共同涉及的中心记录读模型、Web／iOS item API 与视图如何集成和排序，确保原文访问在旧分页客户端和目录独立模式各自可达。单 M1 即可，无需按后端和前端拆交付。

### Author Resolutions

- R1-C1 accepted。中心 worker 使用同一 decoder 从实际原文验证归属和关键字段，重用现有当前授权，下载基于 committed row。
- R1-W1 accepted。SQLite 分片和 projection/receipt/ACK 共事务，最终重验 epoch/撤权/deletion。
- R1-W2 accepted。固定块和 offset、支持上限、Node worker、超限保留本地并推进、并发资源与测量证据。
- R1-W3 accepted。按执行/轮次/revision 枚举每条原事件，原文响应流式、客户端主动文件读取。
- R1-W4 accepted。SQLite 同备份和 FK cascade，待提交清理；能力协商允许恢复。
- R1-W5 accepted。修改原 Requirement 并保留未变场景。
- R1-W6 accepted。M1 退出表与读取分页组合关系明确。

## Round 2

- Reviewer target `/root/work_reads_design`，延续独立设计 reviewer。
- review_mode `full`。持久存储由文件改为 SQLite，新增有界镜像、降级确认和补齐分支，改变提交、回退和可见结果。重新核对 R1 的七个问题与实际协议、删除和双端授权入口。
- started_at `2026-11-10T01:11:17+08:00`，completed_at `2026-11-10T01:12:44+08:00`，duration 87 秒。
- 复核 checkout `19aea6d07`。相关 IM／客户端、PA WorkSync 和 product codec 基线相对 `3179cd45f` 无变更。冻结设计 SHA-256 前缀 `c2512dae2801`，delta `d54a301d9749`。首文档与骨架沿用 R1。

**Issues Found · 0 CRITICAL / 4 WARNING**

### Coverage

- 真实节点 journal、Fastify、append 和 Work 权限装配沿用 Round 1 的代码定位。新版用当前 Work 投影和一个中心进度源，后台 worker 只做读取与校验，中心数据库事务继续拥有可见结果。Web 和 iOS 各自沿既有 Work 卡片与执行详情提供局部增量，现阶段不需要独立原型。
- 新模式能力协商与旧内联路径分离，保持聊天准入和现有 Gateway 模型输入。64 MiB 镜像范围外明确只保留节点原文，不再以缺原文卡住共享日志。SQLite 中的已提交正文与引用可同切点备份。M1 已写两轨退出，并给出原文访问与 perf-753 解耦的交付边界。
- 本轮独立审查仍限于设计。未运行候选协议、回退、性能或产品旅程。

### 历史问题闭环

| R1 issue | Author Resolution 与本轮证据 | 状态 |
| --- | --- | --- |
| R1-C1 | [设计](design.md) 第 11 行从实际原文解码授权和关联字段，中心派生投影，下载反查已提交记录和当前资格。初次镜像关闭错配路径。降级后补齐需沿用此条件，见 R2-W1。 | closed |
| R1-W1 | SQLite BLOB、投影、receipt 和游标在同一持久边界，提交前重验身份和删除。新增的已推进后补齐状态缺少完整转移，见 R2-W1。 | still-open |
| R1-W2 | 256 KiB 连续 offset、64 MiB 上限、后台解析与固定块给出单事件预算，超限可进日志。中心收齐后的验证调度和下载事务边界仍需固定，见 R2-W2。 | still-open |
| R1-W3 | 一对一事件定位、同 item 多个原文和无独立 item 的事实已能在执行内检查。iOS 有文件下载方案，Web 受保护原文的实际传输方式未确定，见 R2-W3。 | still-open |
| R1-W4 | 同 SQLite 快照、已提交正文的 FK cascade 和能力探测闭合原主要回退风险。回退期间处理暂存原文仍有缺口，见 R2-W4。 | still-open |
| R1-W5 | delta 改为 MODIFIED 原 canonical Requirement，保留聊天独立与中断恢复，表达可镜像范围和缺原文仍可前进。 | closed |
| R1-W6 | 单 M1 的双轨退出、负载证据、真实双端和 perf-753 独立路径均已明确。 | closed |

### Issues

#### R2-W1 · 已确认预览的后续原文补齐缺少持久转移

[设计](design.md) 第 5、13 行允许配额用尽时以有界预览推进，之后按原 event ID 补齐。当前上传对 `seq <= through` 只回已有游标，append 对已存在事件只接受同 payload，无法靠原上传重放完成这一转移。请明确可补齐和永久仅节点两种状态，什么持久依据让支持范围内的配额降级在断线或重启后可重试，以及补齐如何核对已确认的 journal/seq/event、实际 root/session/turn/type 和原文摘要。补齐只为已确认事件附原文，不能重投影或重推游标，仍执行当前 epoch 和 redaction 检查。后台补齐的配额和调度应让新日志继续。验证一次配额释放后的重启补齐、重复补齐，以及降级后删除或身份改变。证据见 `apps/im-server/src/work-sync.ts:246–257` 和 `work-records.ts:123–157`。

#### R2-W2 · 收齐后的验证与下载读取需要保持其预算

[设计](design.md) 第 5、11、13 行固定了分片和 offset，但未说明收齐后何时调度验证、客户端在等待验证时看到哪种状态。现有 v1 在最后请求内完成解析，持有全局和每节点 HTTP slot，客户端单请求超时后会重试。直接把该调用换成等待 worker，最后一片重试或连接重建仍可能重复排队读取和解析整个 64 MiB。请规定同一已收齐代的验证如何去重，等待和 commit 后分别如何响应，验证并发如何约束。SQLite 在中心使用 WAL，固定块下载还应避免把读事务持过客户端网络等待，否则慢下载会长时间占用旧快照。M1 用暂停的验证或慢下载覆盖并发正常 Work，记录请求重试与中心内存／WAL 增长。证据见 `apps/im-server/src/work-sync.ts:170–195,289–311`、`packages/personal-assistant/src/work-sync.ts:93–105` 和 `db.ts:6–9`。

#### R2-W3 · Web 直接下载尚未接上真实的用户认证

[设计](design.md) 第 17 行要求浏览器同源下载且避免整份 Blob。现有 `/im/v1` Work 通过 `authenticateRequest()` 要求 Bearer，浏览器直接导航不能使用 `authFetch()` 注入这个头。仓库存在稳定 HttpOnly Cookie 与 `browserSession()`，但当前只用于浏览器身份入口及 HTML 启动桥接，常规受保护附件则由 `authFetch()` 后整份转 Blob。明确本次采用的浏览器桥接及其同一 Agent Work 检查，或直接使用已有 Bearer 会话的有界文件流。说明离开、身份切换与请求取消的适用边界。两端验收应证实可用账号下载成功、撤权后新请求失败且没有 URL 凭据或完整应用缓冲。证据见 `identity.ts:106–109,345–364,457–461`、`server.ts:112–121,341–363`、`auth-fetch.ts:7–13,26–41` 和 `attachment-link.tsx:21–34`。

#### R2-W4 · 回退期间的永久删除还需覆盖新版暂存 BLOB

[设计](design.md) 第 13 行的 Work event FK cascade 对已提交原文有效。暂存原文此时没有对应已提交 event，旧中心的删除 manifest 只处理 v1 upload 表和文件目录。若中心在有暂存原文时回退，旧中心可确认 Agent 删除而仍保留其暂存 BLOB，直到再次升级触发清理，违反中心确认完成后才显示已删除的契约。请定义让旧中心删除仍生效的 DB 级 redaction 衔接，或规定安全回退前清空所有未提交 v2 暂存并保持 Gateway 原 journal 可重传。验证暂存到一半、旧中心启动、删除完成、重新升级的实际顺序。证据见 `work-sync.ts:44–78,119–145`、`agent-deletion.ts:64–69,92–105` 和 `docs/specs/im/agents-nodes.md:1115–1118`。

### Author Resolutions

- R2 延迟镜像 accepted。Gateway 与中心持久记录、同一身份与 hash、重新验证权限，确认后才清除。
- R2 资源边界 accepted。异步合并校验与有限 worker；下载逐段独立读取，慢连接不固定读快照。
- R2 Web 认证 accepted。限定同源附件 GET，复用现有 browserSession cookie 与当前 Work 权限。
- R2 回退清理 accepted。SQLite trigger 在旧中心 deletion 事务状态变化时也清理待确认数据。

## Round 3

- Reviewer target `/root/work_reads_design`，延续独立设计 reviewer。
- review_mode `closure`。新增提交与下载细则仅关闭 R2 局部问题，镜像范围、协议分支、存储边界、delta 和 M1 未变。
- started_at `2026-11-10T01:18:14+08:00`，completed_at `2026-11-10T01:18:29+08:00`，duration 15 秒。
- 复核 checkout `616a0a2d0`。相关 WorkSync、中心、客户端及 codec 基线相对 `3179cd45f` 无变更。冻结设计 SHA-256 前缀 `658516f8167a`，delta `d54a301d9749`。retained_from Round 2，原文归属、既有客户端兼容、目标范围与 M1 验证仍适用。

**Approved · 0 CRITICAL / 0 WARNING**

### 历史问题闭环

| 问题 | Author Resolution 与本轮证据 | 状态 |
| --- | --- | --- |
| R2-W1（R1-W1） | [设计](design.md) 第 29 行明确 Gateway 先持久登记固定 journal/seq/event/hash，重启后续传。中心 pending manifest 和降级投影共事务，重验实际原文、同一身份、当前 epoch 和访问／删除状态后，仅附加原文并转 complete。节点收到持久完成确认才移除候补，硬超限无候补。这条路径独立于 `work-sync.ts:246–257` 的旧 ACK，也不需要把同位置事件再 append。 | closed |
| R2-W2（R1-W2） | [设计](design.md) 第 30 行最后片只提交 verifying 意图，按 manifest 身份去重、限制 worker 数、重启续领，避免把原文解码放进已有 `work-sync.ts:170–195` 的 HTTP lease。每个下载块独立读并释放 SQLite 快照，网络等待时不持住 WAL 旧视图。后续分片重新核验资格和提交状态。 | closed |
| R2-W3（R1-W3） | [设计](design.md) 第 31 行确定同源附件 GET 使用现有 HttpOnly、SameSite=Strict 浏览器 cookie 和 `browserSession()`，实际签发与校验落在 `identity-routes.ts:33–36`、`identity.ts:457–461`。新入口复用 Work 对当前 Agent、用户和删除状态的判定，iOS 保持 Bearer，浏览器以下载流接收，无需在 JS 拼装文件。第 30 行的逐段权限核验同时适用于持续传输。 | closed |
| R2-W4（R1-W4） | [设计](design.md) 第 32 行以 `agent_deletions` 的 deleted 状态转移触发清理，覆盖未确认 manifest 和其级联 BLOB，已提交原文仍随 Work event 删除。旧中心的 `agent-deletion.ts:92–105` 在清理事务写同一状态，且 `db.ts:6–9` 启用外键。按 Agent 与既有精确 manifest 归属清理，保留其他根。 | closed |

本轮结论限于 Gate 2 设计。实际持久恢复、旧中心删除和双端流式打开仍按 M1 验证。
