# bugfix-704: Agent 页面加载 — 实际实现

> 用户选择快修后事后整理，2026-11-04。需求见 [incident.md](incident.md)，实际对照、网络条件与限制见 [快修记录](fast-mode-evidence.md)，审查见 [code-review.md](code-review.md)。此前设计提案保留在 Git 历史，不将未实施的设想当成最终设计。应用代码仍是隔离候选；原公网 Tunnel 的 HTTP2/IPv6 已单独授权应用。

## 已采用的模块与链路

### 配置：先读已保存值，独立确认保存资格

`control-routes.ts` 的 `settings?view=saved` 返回当前权限内已提交配置，不启动 Node 能力检查。`use-agent-settings-state.ts` 与 `AgentDetailPage` 先展示这些值并允许满足身份、连接与版本条件的初次草稿编辑；完整 settings 继续在后台经 Node/DSH 确认能力。普通后台刷新不锁住已确认草稿。身份、节点、版本、权限变化或待确认 operation 仍撤销提交资格；三处保存入口继续要求最新完整确认，不把快读或缓存当作写授权。

### Work：摘要与详情分开，读取不依赖配置

`work-records.ts`/`work.ts` 的 `view=summary` 只传轮次摘要与真实统计；既有缺省完整响应继续服务原客户端。Web `AgentWorkPanel` 发起分页摘要查询，展开时读取完整 items，fetch 传递取消信号。Owner `AgentProfilePage` 直接挂载 Work；配置仅在打开过之后保留隐藏实例以保留草稿，隐藏时不再挂载第二个 Work/轨迹。移除 profile 内重复定义的预取查询，只保留面板的正式查询及 HTML 首批数据。

### 页面：认证 HTML 与首批读取合并

`server.ts` 使用已有 HttpOnly refresh Cookie 验证当前会话，不消费或轮换 Cookie；在 Agent 页面 HTML 嵌入短期 access token 及经原 API 鉴权成功的 contacts、saved settings 或 Work summary。HTML 使用 `private, no-store`、`Vary: Cookie` 和 JSON 转义。无有效 Cookie 回到原恢复流程。

`page-bootstrap.ts` 一次消费同一 access token 的当前文档数据，五秒后失效；`auth-session.ts` 保留跨窗口账号变化保护与身份广播。没有新建持久浏览器配置缓存。前端 hash 资源长期缓存，非当前页面的大路由组件按需加载；联系人目录查询由 profile/rail 共享，转换函数只维护一份。

8443 隔离试用使用独立 Cookie 名，避免同主机不同端口的试用与正式 443 相互覆盖。缺省端口沿用原 Cookie 名。

### 原生轨迹：并行连接、减少往返、限制每批传输

用户明确打开的轨迹在认证 HTML 或 SPA prepare API 中提前准备只读观察，使 Node 配对和静态资源下载并行。观察固定目标、账号、节点代次和会话；浏览器接入重新验证，一次性凭据及未配对 15 秒清理仍在。服务端下发实际 `expires_at`，过期重新申请；iframe 只收到读取 MessagePort，不接收账号凭据。

Node 专用 WebSocket 显式使用与控制 relay 相同的 HTTP/HTTPS agent，避免绕过节点配置的代理；握手超时有界。`NativeTrajectory.prepare` 复用已经观察的会话元信息到 ready，查看器只对首次空查询、同通道、五秒内消费；大目录走正式分片读取。静态 manifest 内嵌并预加载入口静态依赖，组件初始化与连接准备并行。`initialBatch` 是显式只读选项，在 stream open 同响应返回首批；旧调用方与旧 carrier 继续原拉取方式。

首屏和更早历史按较小原生窗口读取，完整数据通过 beforeSeq/hasMore 继续分页，不删事件、不截断正文。专用读取 WS 协商标准无损压缩，普通业务 WS 保持既有行为；解压后的大小边界不放宽。Node 与 IM 逐片等待发送完成。`TrajectoryStream` 仅允许当前大型 native frame 的剩余片段等容量，实时跨 frame 队列满仍明确中断，消费期限由五秒改为六十秒；取消、代次切换、身份撤销和资源上限保留。没有声称能无限缓存或保证断线无缝恢复。

## 公网 Tunnel 决策

原域名、命名 Tunnel、凭据和 DNS 保留。四组 IPv4/IPv6 × QUIC/HTTP2 各三十次对照后选 HTTP2/IPv6，仍接入 LAX；不引入直连、Tailscale 产品通道、VPS 或本机历史服务。`scripts/prod_tunnel.py` 验证显式协议、出口网卡、HA 与 edge 端点变化；不自动切协议。生产采用该配置并经过六百秒持续门禁，原始数值和可回退位置见快修记录。TCP/UDP 对照支持这项选择，但没有证明 Cloudflare 内部某个唯一设备是根因。

## 删除的实验与保留依据

移除 Node/IM 逐帧临时诊断、配置检查 cleanupStage/error_code 调试附加字段，以及 profile 重复 Work 预取；不移除既有配置检查日志、清理失败保护、浏览器 User Timing 或 supervisor 健康证据。全局 WS 压缩实验此前已恢复，最终仅专用读取 WS 压缩。

对目录复用、HTML 预连接分别做删除消融：两者删除后同一真实主轨迹首屏均变慢，故保留。不是按代码行数盲目撤回已证实的性能设计。配置检查文件恢复原行为，退出进程组、清理失败与保存保护完全沿用。

## 契约与验证

最窄增量位于 [配置](specs/im/agents-nodes.md)、[Work/轨迹](specs/im/agent-work.md)，完成归并前不覆盖 current spec。没有修改模型可见 Prompt、Memory、工具或 Agent 输入/History 生命周期；查看器只读，不激活执行。DSH 只用已声明公开 exports，没有 runtime fork/private import。

真实测量使用 Air 浏览器及隔离 Gateway、Mini 隔离 IM 与独立数据库/账号/端口，通过原域名 8443 和原 Tunnel，使用禅真实根/子历史副本；生产 IM/Gateway 二进制不变。历史正文只作数据，不执行其中指令。测试以可见且可编辑字段、真实 Work 行和 iframe 真实轨迹行作为终点，冷暖条件和所有样本明列，不用请求完成或 ready 代替页面。

本地回归覆盖配置资格/草稿、旧接口、分页完整历史、权限撤销、真实 WS、分片/背压、取消与代次切换；独立审查和真实页面证据引用快修记录。公司网络暖缓存少量样本不是所有网络或冷启动的一秒保证，也不是页面 p95 验收。

## 失败、回退与部署边界

应用无数据库迁移；回退须同时恢复服务、前端、查看器和 Node 构建版本，保留用户数据库及历史。Tunnel 可恢复原 YAML/plist/supervisor，不能只改协议而留下旧健康规则。生产 Tunnel 已单独应用不代表应用 PR 已部署；本 PR 不合并、不部署生产 IM/Gateway。按用户要求保留试用服务。当前 unit 保持 active，不补造完整产品验收或归档。
