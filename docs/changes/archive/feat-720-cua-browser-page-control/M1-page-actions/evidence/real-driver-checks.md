# M1 实施期真实驱动验证（orchestrator 执行，2026-11-05）

环境：macOS，`cua-driver 0.38.0`（daemon 运行中），Accessibility / Screen Recording 均为 true；夹具 `/tmp/desktop-verify/page.html` 由 `python3 -m http.server 8765 --bind 127.0.0.1` 提供（`browser_navigate` 拒绝 `file://`）。夹具与截图只在 `/tmp/desktop-verify/`，不入库。前台 app 探测用 `lsappinfo front` + `lsappinfo info -only name`（不引入 Automation 授权）。

## 结论

| 项 | 状态 | 证据 |
|---|---|---|
| V1 页面内 `browser_type`（background + DOM 回读 + 前台不变） | **PASS** | `browser_type {ref:"p27:2", text:"hello-v1-typed", delivery_mode:"background"}` → `{"delivery":{"delivered_count":14,"mode":"background"},"effect":"unverifiable"}`；回读 `refs[textbox].value="hello-v1-typed"`，`#echo` 静态文本相同；前台前后均为用户自己的 `Google Chrome` |
| V5 `ref` 锚点滚动（`browser_pointer` scroll + ref） | **PASS（带锚点约束）** | `browser_pointer {action:"scroll", ref:"p32:2"(button, actions `["click","pointer"]`), delta_y:600, delivery_mode:"background"}` → `summary:"dispatched trusted scroll in tab-…"`；截图 `v5-before.png`（顶部 Row 1–7）→ `v5-after.png`（顶部 Row 5–19），位移与 600 CSS px 一致；前台不变 |
| V6 截图证据链（workspace 相对路径可被 `read_image` 读取） | **PASS** | 把视口截图写入 `<workspace>/.nanoassistant/browser/v6check/shot.png`，以 workspace 相对路径 `read_image` 读到 2400×1464 内容。注：本次实测在 orchestrator workspace（同一 DSH 版本），产品节点 workspace 的等价性按同一路径解析规则推断，未在产品节点内复跑 |
| V4 主窗口登记（prepare 后唯一候选） | **PASS + 设计纠正** | `browser_prepare {allow_launch:true, profile:{mode:"isolated_new"}}` → `endpoint_ownership.owner_pid`；`list_windows {pid}` 返回**恰好 1 个**窗口（title `about:blank`）；`get_browser_state {pid,window_id}` → `binding_quality:"exact"`、`tabs:[{url:"about:blank"}]`。**按 design 原文“exact 且至少一个 http(s) tab”会得到 0 候选 → 每次都 `browser_session_lost`**，因此登记判据改为“唯一 exact 绑定”，`http(s)` 只用于新窗口事件分类（design 约束五第 1 条已同步） |
| V4 弹窗半边（弹窗不被采纳为主窗口） | **未执行（需授权）** | 见下“未执行项” |
| V2 真窗口后 `end_session` 是否归还前台（≥2 次采样） | **未执行（需授权）** | 见下“未执行项”；证据报告 L549–554 仅有 1 次观察 |
| V3 `browser_prepare` 首次启动前台行为（≥3 次采样） | **部分** | 本轮 3 次 prepare 中的前 2 次（V4 探测与快照形状探测）`side_effects.foregrounded_window=false` 且前台保持用户 `Google Chrome`；第 3 次起的前台批次被授权门禁拦下 |

## 未执行项与原因（如实记录）

计划中的前台批次（3× `browser_prepare` 采样 + 页面 `window.open` 弹窗 + `end_session` 归还前台）在执行前被策略门禁拒绝，理由是：这会再次在用户账号上启动多个真实 Chrome 实例并点击打开新窗口，而此前实测该操作会抢占前台且持续不恢复；用户授权的是受四条边界约束的验证，并要求出现意外立即停止，未授权在已发现前台抢占后继续重复测试。

因此 **V2、V4 的弹窗半边、V3 的独立采样次数**在本 unit 收尾时点未完成。按 design：V2 未通过前不得发布该能力；本 unit 的交付 PR 必须在正文标注这一未验证项，由主人/父 Agent 决定补充授权后复验。

驱动会话 `vchk` / `vchk2` 均以 `end_session` 结束并核实进程消失（`ps` 无、`list_windows` 中该 pid 窗口数 0）；静态服务已 kill。

## 驱动行为实测补充（供实现与评审核对）

1. `get_browser_state {session, pid, window_id, target_id, tab_id, snapshot_format:"semantic_v2", include_screenshot:true}` 的响应：
   - 顶层键：`content_refs, mode, oopif, outline, page, refs, screenshot, screenshot_height, screenshot_mime_type, screenshot_png_b64, screenshot_width, snapshot, status, tab_id, target_id`；
   - `snapshot` 只是元数据（`complete, continuation, format, hint, id, node_budget, omitted, scope, selected_nodes, total_nodes`），**没有 `text`/`content`/`page_text`/`markdown`**；页面文本在顶层 `outline`（字符串，夹具页 5363 字符）；
   - `refs[]` = 交互元素 `{actions, frame, name, ref, role, states, value, visibility}`；`content_refs[]` 是全节点；截图 base64 约 124 KB。
2. `browser_pointer {action:"scroll", ref}` 只接受**声明了 `scroll`/`pointer` 动作**的 ref：`listitem`/静态文本被拒（`browser_action_unavailable`，“does not declare the scroll or pointer action”）；button/link/textbox 声明 `pointer`，可作锚点。
3. `get_browser_state` 每次 bind 都重铸 `target_id`/`tab_id`；`browser_navigate` 返回 `refs_invalidated:true`，旧 ref 全部作废。
4. 同时携带 `pid + window_id + target_id + tab_id` 合法；`browser_navigate` 带 `delivery_mode:"background"` 返回 `status:"ok"`。
5. `semantic_v2` 的 `visibility`（`in_viewport`/`near_viewport`/`offscreen`）与真实视口仍约 2× 偏差，位置结论只能以截图为准（与证据报告 8.2 一致）。
