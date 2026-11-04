# 快修代码审查

## 专用轨迹传输压缩审查（2026-11-04）

独立 reviewer 对基线 `19e18297b` 后的 `server.ts` 与真实进程 `trajectory.test.ts` 增量执行 patch 审查，结论 `[]`。范围包括专用路由协商、普通业务 WS 保持原协商行为、解码上限、多 MB 分片及无压缩客户端兼容。此项不改模型可见上下文。实测更早历史 32.376 → 9.990 秒，仍未满足完整性能目标，不等于产品验收。

## 原域名不同端口试用补充审查（2026-11-04）

独立 reviewer 对 `928e89c41` 后端口 Cookie 命名、登录/refresh/logout/HTML bootstrap 使用及对应回归执行 patch 审查，并核对 Mini 的本地 HTTP/WS 分流脚本，结论 `[]`。默认端口保持原名，8443 使用独立名称；未发现明确破坏正式 443 请求的缺陷。实际原 Tunnel 下仍有显著性能等待，功能审查不等于性能达标，见 [快修记录](fast-mode-evidence.md#原域名与原命名-tunnel-纠正2026-11-04)。

审查范围：以 `50f19d16d` 为基线的本任务实现和测试；不包含并行的 feat-705 文档。独立 reviewer：Codex `gpt-6.1-sol/high`。

首次 full 审查确认：跨原生 frame 停止拉取可能使 DSH 上游订阅队列无界增长；摘要缺少后台结果的标题分类。修订后恢复跨 frame 队列满时的中断保护，补充真实摘要分类字段；closure 核实两项关闭。单个大 frame 内等待的上游既有限制仍在 [快修记录](fast-mode-evidence.md) 明列。

后续 patch 审查确认：异步恢复书签可能覆盖用户的新阅读位置；版本资源未核对 rev 就长期缓存可能污染旧版本。修订后用户交互取消恢复，动画帧执行前再次核对取消与生命周期；静态资源与部署 manifest 不同版本返回 404。两项经 closure 核实关闭。握手/配对超时、诊断字段、历史窗口和组件 preload 的有界 patch 审查未发现其他已确认缺陷；预加载的 bootstrap URL 改为带相同版本以避免额外下载。

末轮确认保存结果待确认时不能提示可以编辑；页面以最终 pending 状态覆盖普通后台刷新的可编辑提示，保留离线/未知优先级，closure 已核实。

本审查不是性能验收：真实公网的轨迹和配置仍未达到目标，具体数据和未完成项见 [快修记录](fast-mode-evidence.md)。


## 继续快修的独立审查

审查范围：以 `f5a2ee8bc` 为基线，本轮 settings saved 快读、Owner Work 解耦、认证 HTML bootstrap、路由资源拆分、显式代理及对应测试。独立 reviewer：Codex `gpt-6.1-sol/high`，完成整轮审查和针对实际发现的 closure。

已确认并修复：切换 Work 丢失草稿；Owner 页签/动作入口回归；预取未保留分页参数；隐藏配置重复挂载轨迹；bootstrap 接纳前未初始化身份广播；403/404 后仍准许新草稿；文档下载期间其他页登录/退出可能接纳旧账号。最后一项用无凭据会话变更时间与普通 Cookie 恢复收口，补充回归；复审结论均为 `[]`。随后 contacts 查询合并、时区重复写入抑制与首次 stream 同步复用在途确认的有界 patch 复审也为 `[]`。

功能审查通过不等于性能达标。最终实测和仍未满足的 1 秒目标见 [快修记录](fast-mode-evidence.md)。未经用户验收，不归档或宣称完成。


## 公司网络继续优化审查（2026-11-04）

独立 reviewer 对 `2f6dded9d` 之后的工作树增量执行 patch 审查：查看器静态预加载与初始化并行、构建内嵌 manifest、只读 carrier opt-in initialBatch（IM/Node 转发、原生首批获取和前端消费）及其测试，结论 `[]`。追加审查实时 user stream 取票显式 JSON body 的单行改动，结论 `[]`。该改动由真实拓扑中空 POST 415 / JSON POST 200 的对照触发。

前端首次用根目录 runner 执行时 matcher 来自另一依赖实例，出现 Invalid Chai property；改用前端自身 runner 后 44 项通过。Node 全包类型检查另有未修改的 `main.ts:347` FeishuConnection 类型不匹配，不能写成全包通过；本轮修改的 Node trajectory 单文件严格类型检查通过。其余具体检查和页面样本见快修记录。


## 连接准备并行审查

对 `a29bce53c` 之后的源码增量执行独立 patch 审查（同一 Codex reviewer）。确认 HTML 后 JS 超过 15 秒才消费缓存时会取到已失效 ticket；修订为服务端 deadline 同源 `expires_at`、客户端过期重新 prepare，新增前端回归。closure 确认 closed，结论 `[]`。错误目标的 Node 清理由默认正常关闭码改为 1008。服务端后续真实进程覆盖双方到达次序、一次性能力、错误范围、未接入超时、HTML 提前建链及退出撤销，全部通过。性能对照及仍存限制见快修记录。


## 初始目录复用审查

独立 reviewer 审查 `96d664a1f` 后本轮 prepare 目录、ready 单帧边界、transport 一次性/时效/代次与父页面转交增量，结论 `[]`。随后针对“连接关闭而 iframe 迟到”补充 OPEN 准入及清除待交付字段，并经有界 patch 审查 `[]`；对应前端回归通过。实验性全局 WebSocket 压缩没有获得真实浏览器扩展协商证据，源码与隔离服务都已恢复，该设置不在交付 diff 内。
