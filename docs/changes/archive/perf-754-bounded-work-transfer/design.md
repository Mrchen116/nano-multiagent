# perf-754 · 实施设计

## 流程与界限

普通内联及 16 MiB 以内的 v1 传输保留。中心在 cursor 明确返回 large-detail 能力。大记录走独立传输，按 node epoch、journal、seq、event ID 绑定。每段 256 KiB，按连续 offset 幂等上传；中心只返回已持久化 offset，重发旧段校验内容哈希。支持单条原文至 64 MiB 的中心镜像。文件/磁盘资源不足由可重试状态表达。若原文超过支持上限或待传配额用尽，网关可提交同一身份的明确「原文仅保留在节点，中心未补齐」预览并推进共享 journal。保留原始本地记录，用户可在节点可用时按同一 Work 权限读取原生轨迹。这里不把中心未有的正文显示为完整离线记录。支持范围内的延迟镜像以后可按原 event ID 补齐，不能重新推进 seq。

Gateway 用 SQLite 里的原始 journal 字节，先从元数据判定大小。只有大记录使用可复用后台 worker 做一次读取、JSON 校验和有界字段投影，避免 Gateway 进程事件循环读、解析、再序列化巨型字符串。worker 把原字节流写临时文件，主循环读取固定大小块；清理按 ACK、重启和 deletion，进程退出不依赖临时文件恢复。一次只解析一条支持上限内记录。超限路径只读取 SQLite 元数据/有限投影，保持 source 原字节不变，验收测主线程、总进程 RSS 与存储峰值。

## 中心安全与事务

中心把暂存和已确认原文存成 SQLite BLOB 分片，避免新持久文件逃出 SQLite 一致备份或被旧 staging 清理。每节点只保留一条当前大记录暂存，有界连接数、全局暂存及持久字节预算。中心后台只读 worker 按分片验证 SHA 与实际 JSON，使用同一个公开 Work codec 解析，并由原文提取和验证 root、session、event、turn、seq、type、lifecycle/关联字段和有界投影。网关投影不能单独决定原文读权限。中心仍以现有 Work append 权限、绑定 epoch 与 redaction 判定为准，最终 commit 前再次检查；另一个节点、过期身份、未授权根、已撤销内容不产生可读大明细。原文读取由已提交记录反查 Agent 当前访问权，URL 或 hash 不携带权限，响应以固定分片及明确取消边界流式写出。

中心最终 commit 在同一 SQLite 事务中保存可见投影、原文引用状态、原始摘要收据及 Work journal watermark。超配额走明确未镜像的状态，原文恢复与 ordinary ACK 独立；同 seq v1/v2 竞争通过现有节点 lease 和 DB 行约束拒绝。原文落库后使用持久收据回答丢失 ACK 的重试。中心仅推进已撤权位置时不保留正文；redaction 与完成提交按事务重验，不返回复活数据。已确认原文用 Work 事件 revision 的 FK cascade 删除，旧中心也会删除对应 Work 事件并启用外键；暂存用既有 Agent 删除 manifest 精确处理，进程崩溃后扫描仍存在的未提交小集合，按当前授权/TTL 回收。恢复 SQLite 副本同时恢复原文、引用、收据与游标。新 Gateway 探测能力，旧中心不宣称 v2 可用且可在升级后自动继续；已经确认的小投影可被回退中心读取，完整原文在恢复支持后可读。没有一次性数据重写。

## 原文入口

每个原文绑定一个 journal 事件，用 root + session + turn（有则）+ revision 排序分页，和投影的 item 合并方式独立。一个 tool 有多条时可以分别回看；没有独立 item 的事实出现在该执行的原文列表。Work 卡片只显示有界状态/预览和原文动作，普通客户端保留兼容预览。新版 Web 按当前身份从同源已授权 download 入口导出文件（避免 response.json 或全量 Blob），iOS 使用可取消的 URLSession 文件下载，有限预览并交文件查看器。离开/撤权响应使用既有 Work 边界，源聊天或附件不因查看 Work 获得额外授权。原文入口与 perf-753 是否选择分页兼容，已有历史页面可通过同样的 session/turn ID 查。

## 验收

| ID | 依赖 | 并行组 | 范围 | 退出标准 |
| --- | --- | --- | --- | --- |
| M1-large-work-detail | 与 perf-753 共用详情入口但协议独立 | D | WorkSync、中心提交与下载、Web/iOS | [reviewer] 断线续传后完整原文和顺序可查，多个原文分别打开，用户撤权/删除立即限制读取，其他根普通记录继续。[worker] 真中心+Gateway 以 20、64 MiB 可压缩/不可压缩合成原文测 offset、总请求、峰值 RSS/Buffer/磁盘与并发发信；覆盖不支持大小、配额、跨根原文与投影错配、丢 ACK、commit/撤权/删除竞态、SQLite 成对备份恢复、旧中心与两端入口。 |

独立代码审查、性能对照与实际 Web/iOS 打开旅程验证该表。原文由 Work 读端消费，不改变模型上下文。

## 提交与下载细则

- 支持范围内的降级记录需要可恢复补传。Gateway 在提交小投影之前持久登记 journal、seq、event ID 与原文哈希，重启继续枚举待传表，中心持久确认 complete 后才移除。中心将同一身份和哈希的 pending manifest 与降级投影同事务提交。补传只接受同一原文和当前 epoch，并在提交时重验访问资格与删除状态。原文验证通过后，manifest 原子转 complete，不重新推进原 seq。超硬上限明确保留在节点，不加入自动候补。
- 最后请求只写入校验意图并返回 verifying。中心按身份合并任务，一节点一件、全中心限制并行 worker。相同请求不会重开校验，重启由 manifest 续领。worker 在独立的有界时限内完成，失败可重新领取。下载用 async iterator 逐段查询，每次查询结束后释放 SQLite 读取快照；慢连接不会一直持有 WAL 读事务。每次取下一段重新确认绑定或用户权限与 committed manifest。
- Web 下载的 GET 独立使用现有 Path=/、HttpOnly、SameSite=Strict browser session cookie，服务端复用 browserSession 校验和当前 Work 访问检查。API/iOS 仍用 Bearer。下载设置附件 Content-Disposition、nosniff 和 private/no-store，不作为站内页面执行。Chrome/Safari 从同源 GET 直接下载，不在 JS 中缓冲整个文件。
- 加入 SQLite trigger 在 Agent 删除进入 deleted 时删除该根所有待确认 manifest 和级联 BLOB。旧中心仍会写该事务状态并启用 SQLite 外键，新增 trigger 在回退时也有效；已提交原文另随对应 Work 事件删除。

## 解码预算与重试隔离

- 64 MiB 原文字节上限之外，两个 worker 在完整解码前均检查 JSON 字符串外的数组、对象和槽位数量。超过 100,000 个结构符号或达到 worker 堆限额的记录提交仅节点预览并推进普通日志。中心清除这次暂存，不提供未经共享 codec 验证的下载。保留节点原始字节。
- 已确认预览的同一 manifest 可能经历多次暂存。每次重新取得暂存位置递增持久 generation，校验结束与校验错误都只处理其领取的 generation。Gateway 只保留一个按日志身份和摘要标识的临时文件，普通 Work 可中断其补传，之后复用已准备的文件。
