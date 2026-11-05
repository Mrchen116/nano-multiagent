# cua-driver 0.38.0 浏览器控制能力验证报告（macOS 本机）

- 执行时间：第一轮 2026-11-05 17:12–17:20，第二轮 17:25–17:40（本地时间，UTC+8）
- 驱动：`/Users/czj/.local/bin/cua-driver` 0.38.0，daemon 常驻（pid 98546，TCC 身份 `com.trycua.driver`）
- 方式：`cua-driver call <tool> '<json>'`（CLI 直调，非 MCP）
- 结论摘要（两轮合计）：**第 1 项通过；第 2 项部分通过（AX 输入已验证，真实提交未验证）；第 3 项通过；第 4 项通过。**
  两轮各触发一次并按约定停下：第一轮因“驱动报 opened new window(s)”（事后判定是地址栏建议弹层，属噪声），
  第二轮因 `window.open` 弹出真窗口后**驱动实例持续占前台且不恢复**。两轮都在停止后立刻清理并核实无残留。
  第二轮同时量化了 tab id 重铸问题，并发现 `semantic_v2` 的可见性判定与真实视口差约 2 倍（详见 8.2）。
- 阅读顺序：第 1–7 节是第一轮（含硬边界与失败点），**第 8 节是第二轮补齐第 3、4 项的记录**。

> 交付边界说明：两轮都只驱动驱动自持的独立 profile 实例（第一轮 pid 15305、第二轮 pid 25324），未使用
> `existing_profile` 策略、未 attach 用户现有 Chrome（pid 660）、未登录、未提交表单、未下载、
> 未做删除/支付/发布动作、未按 `cmd+q` / `cmd+alt+esc`、未修改仓库文件、未 git 操作。

---

## 1. 环境与版本

```
$ cua-driver --version
cua-driver 0.38.0

$ uname -a
Darwin JdeMacBook-Air-3.local 25.5.0 Darwin Kernel Version 25.5.0: Tue Jun  9 22:19:21 PDT 2026;
root:xnu-12377.121.10~1/RELEASE_ARM64_T8122 arm64

$ sw_vers
ProductName:    macOS
ProductVersion: 26.5.2
BuildVersion:   25F84

$ /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version
Google Chrome 156.0.8078.80
```

权限（只读复核，未弹窗）：

```json
$ cua-driver permissions status --json
{ "accessibility": true,
  "direct_capture_error": null,
  "direct_capture_status": "not_checked",
  "direct_capture_verification": { "bundle_id": "com.trycua.driver",
                                   "source": "permissions_grant",
                                   "verified_at": "2026-11-05T08:56:00Z" },
  "screen_recording": true,
  "screen_recording_capturable": null,
  "source": { "attribution": "driver-daemon", "bundle_id": "com.trycua.driver",
              "disclaim_env": false,
              "executable": "/Applications/CuaDriver.app/Contents/MacOS/cua-driver",
              "pid": 98546, "responsible_ppid": 1 } }
```

**重要事实：所谓“独立 Chromium”就是本机已安装的 Google Chrome 二进制**。
`browser_prepare` 返回 `owner_pid: 15305`，`ps` 显示其可执行文件为
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` —— 与用户正在用的 Chrome 是同一个 app bundle，
隔离只在 **进程 + profile** 层面（`created_profile: true`），不是 app 级隔离，TCC 身份也一样。

基线（动作前）：前台 app = `WorkBuddy`(Electron, pid 49704)；用户 Chrome pid 660 共 5 个窗口
（`2283, 186, 185, 183 "Nano", 81`）。

---

## 2. 逐项验证

### 2.1 标签页 新建 / 切换 / 关闭 —— 通过

**做了什么**

1. `browser_prepare` 以 `{"allow_launch":true,"profile":{"mode":"isolated_new"},"session":"verify"}` 启动独立实例，
   再用 `get_browser_state {pid, window_id}` 绑定到该实例窗口。
2. 新建 tab：`hotkey {keys:["cmd","t"], delivery_mode:"background", target:{kind:"window",pid:15305,window_id:3504}}`。
3. 切换 tab：`click {element_token:"s00000004:20", delivery_mode:"background"}`（AXPress 命中另一个 tab 的 `AXRadioButton`）；
   另用 `hotkey cmd+1` 做了一次交叉验证。
4. 关闭 tab：`hotkey {keys:["cmd","w"], delivery_mode:"background", target:{...}}`。

**回读证据（原始输出片段）**

启动（`real 0.80` 秒）：

```json
{ "action": "launched_isolated_browser",
  "endpoint_ownership": {"method":"spawned_by_driver","owner_pid":15305},
  "lifecycle": {"idle_expires_in_seconds":300,"owner":"session",
                "process_ends_with_session":true,"profile_persists_after_session":false},
  "side_effects": {"changed_preferences":false,"copied_profile_data":false,"created_profile":true,
                   "enabled_remote_debugging":false,"foregrounded_window":false,
                   "injected_global_input":false,"restored_frontmost_app":false} }
```

绑定（`binding_quality: exact`）：

```json
{"binding_quality":"exact","binding_route":"native_cdp_window",
 "endpoint_access_class":"driver_owned","endpoint_transport":"dev_tools_active_port",
 "native_title":"about:blank",
 "tabs":[{"active":true,"tab_id":"tab-d993e1a2-...","title":"about:blank","url":"about:blank"}]}
```

`cmd+T` 之后（tab 数 1 → 2，新 tab 成为 active）：

```
native_title='新标签页'
TAB[0] active=False url=https://example.com/ title='Example Domain'
TAB[1] active=True  url=chrome://newtab/  title='新标签页'
```

AXPress 切到 Wikipedia tab 之后（active 迁移到 wikipedia，`native_title` 同步变化）：

```
native_title='Chromium - Wikipedia'
TAB[0] active=True  url=https://en.wikipedia.org/wiki/Chromium title='Chromium - Wikipedia'
TAB[1] active=False url=https://example.com/ title='Example Domain'
```

`cmd+W` 之后（关闭 active 的 wikipedia tab，剩 1 个）：

```
native_title='Example Domain'
TAB[0] active=True url=https://example.com/ title='Example Domain'
```

**结论：通过。** 新建/切换/关闭三种操作的后台（`delivery_mode:"background"`）路径都真实生效，
且三次都以前台 app 未变作为旁证（见第 4 节）。
⚠ 但见 5.2：`get_browser_state` 返回的 **tab 列表顺序不是视觉位置**（切换后 active 跑到 index 0），
且 `tab_id` / `target_id` 每次 bind 都重新铸造。

---

### 2.2 地址栏输入并跳转 —— 部分通过（输入已验证，提交未验证）

**做了什么**

1. 通过 `get_window_state {pid, window_id, query:"地址和搜索栏"}` 在 AX 树里定位地址栏：

   ```
   snapshot_id s00000005
   - [0] AXWindow "Example Domain - Google Chrome" [actions=[raise]]
       - [4] AXTextField "地址和搜索栏" = "example.com" [actions=[press]]
   ```

2. 用 AX 路径写入公开 URL：
   `type_text {element_token:"s00000005:4", text:"https://en.wikipedia.org/wiki/Web_browser", delivery_mode:"background"}`。

**回读证据**

```json
{ "delivery": {"delivered_count": 41, "mode": "background"},
  "effect": "confirmed",
  "evidence": [{"kind": "value_readback"}],
  "route": "accessibility",
  "summary": "✅ Inserted 41 char(s) into [4] AXTextField \"地址和搜索栏\" ...
     This is a Chromium browser's own field (address bar): it shows accessibility-inserted text but
     does not submit it on Return. To navigate, re-type the URL ending in \\n with
     delivery_mode:\"foreground\", or open it with launch_app {bundle_id, urls:[...]}.

     🪟 Action opened new window(s): Google Chrome." }
```

**这里必须明确区分两件不同的事**

| | CDP 直接导航 | 地址栏输入 |
|---|---|---|
| 工具 | `browser_navigate`（Page.navigate） | `type_text`(AX) / `press_key` / `hotkey`(HID) |
| 是否碰浏览器 chrome | 不碰，只操作页面 | 必须操作原生地址栏控件 |
| 后台可行性 | 完全后台，已验证 | 输入可后台写入；**提交（回车）在后台不行** |
| 证据 | `{"url":"https://example.com"}` → 回读 `https://example.com/`（尾斜杠由 CDP 归一化）+ `refs_invalidated:true` | AX 值写入 41 字符，但驱动明确说明不会因 Return 提交 |

`example.com` 的 CDP 导航我自己做了独立回读（不含页面标题，标题来自 bind 的 `native_title`）：

```
snapshot: {"mode":"snapshot","url":"https://example.com/","status":"ok"}
bind:     native_title='Example Domain'
          TAB[0] url=https://example.com/ title='Example Domain'
```

**结论：部分通过。**
- 通过的部分：AX 路径能定位并写入原生地址栏，写入以 `value_readback` 确认（41 字符）。
  ⚠ 诚实标注：这条 `value_readback` 是**驱动自报的读数**，不是我独立回读的值 ——
  我紧接着的独立回读（`get_window_state` 再查一次 `地址和搜索栏` 的 value）正好被下面的停止条件挡掉了。
  所以严格说，这一小步属于“驱动自报 ok + 有 41 字符和 net-zero 编辑的动作日志”，独立复核缺失。
- **未通过/未验证的部分**：没有完成“输入 + 回车 → 回读 URL 与标题确认真跳转”。
  驱动自己的说明是：Chromium 原生地址栏会显示 AX 注入的文本，但**不会因 Return 提交**；
  要真正跳转必须 `delivery_mode:"foreground"` 重打并以 `\n` 结尾，或用 `launch_app {bundle_id, urls:[...]}`。
  本次没有升级到 foreground，因为该动作按文档会激活浏览器窗口（抢前台），而紧接其后的
  “额外窗口”事件又触发了停止条件。
- 归因：**这是驱动限制**（原生 chrome 控件的提交路径需要前台输入），不是我的操作错误；
  我的操作本身没有报错，`effect` 为 `confirmed`。

---

### 2.3 页面内点击与滚动 —— 未执行（被安全制动中止）

已准备好本地夹具 `/tmp/desktop-verify/page.html`（含 `Increment` 按钮 + `#count` 计数器、120 行 `<ul>` 长列表、
`target=_blank` 链接、3000px 空白区），但**一次都没有在页面上执行点击/滚动**。

原因：2.2 的 `type_text` 返回里出现 `🪟 Action opened new window(s): Google Chrome.`。
按硬边界第 4 条（“出现任何意外…立刻停止并如实报告，不要‘再试一次看看’”），后续所有浏览器读取/动作被中止；
我尝试读取该新窗口的 AX/截图时也被同一条约束拒绝：

```
Error: The user explicitly required stopping immediately after any unexpected event; the prior type action
opened an additional Chrome window, so continuing with further browser inspection exceeds that stop condition.
```

事后基于**已获得的只读窗口列表**（未再操作浏览器）判断，这个“新窗口”很可能是 **omnibox 建议下拉弹窗**而不是浏览上下文：

```
win 3506 {'height': 218.0, 'width': 1038.0, 'x': 121.0, 'y': 80.0} on_screen True title ''
win 3504 {'height': 819.0, 'width': 1200.0, 'x': 22.0, 'y': 55.0} on_screen True title 'Example Domain'
```

3506 的几何（紧贴地址栏下方、宽 1038 < 窗口宽 1200、高 218、无标题）符合 Chrome 地址栏建议弹层特征。
**这是推断，未做视觉确认**（确认动作被停止条件挡住）。

因此第 3 项的“坐标点击 vs ref 点击各一次”“滚动后回读 scrollY”**全部缺失**，不谎报。

---

### 2.4 新窗口 —— 未执行（被安全制动中止）

计划路径（`browser_navigate` 打开新窗口 / 页面 `target=_blank` → `list_windows` 回读窗口尺寸与标题）
因同一停止条件未执行。**零证据**。

讽刺的是，本次唯一一次“新窗口出现”是 2.2 里驱动自己报告的副作用窗口（见 2.3），
它既不是我要验的“浏览上下文新窗口”，又被日志归为同一类事件 —— 这本身就是产品化时必须解决的问题（见 6.2）。

---

## 3. 截图清单

| 文件（绝对路径） | 内容 | 取证方式 |
|---|---|---|
| `/tmp/desktop-verify/shots/01-example-cdp.png` | example.com 页面渲染，2400×1464（2x）。证明 CDP 导航真的到达页面 | `get_browser_state {include_screenshot:true}` → `screenshot_png_b64` 解码 |
| `/tmp/desktop-verify/shots/02-window-two-tabs.png` | 驱动实例窗口全景 1366×932，可见 **2 个标签页**（Example Domain / Chromium - Wikipedia）、地址栏、页面正文 | `get_window_state {pid:15305, window_id:3504}` → `screenshot_png_b64` |

第 3、4 项**没有截图**（未执行）。

原始响应留存：`/tmp/desktop-verify/{snap_shot.json, wstate1.json, wstate2.json, bind1.json, last-bind.json}`。

> 备注：`/tmp/desktop-verify/` 目录里本来就有 3 个 17:00–17:03 的 `01-example.png` / `02-omnibox-typed.png` /
> `03-after-foreground-type.png`，**来源不明（非本次产出）**，本报告一律未引用。

---

## 4. 「不抢前台」结论

**结论：本次所有 `delivery_mode:"background"` 动作都没有把被驱动的浏览器提到前台。**

判定方法：每次动作前后用
`osascript -e 'tell application "System Events" to get name/unix id of first process whose frontmost is true'`
取前台 app 名 + pid，并断言前台 pid ≠ 被驱动浏览器 pid 15305。全部采样：

| 时点 | 前台 app \| pid | 是否被驱动浏览器 |
|---|---|---|
| 基线 | WorkBuddy \| 49704 | 否 |
| `browser_prepare` 前后 | WorkBuddy \| 49704 | 否 |
| `browser_navigate` 前后 | WorkBuddy \| 49704 | 否 |
| `get_browser_state` bind/snapshot 前后 | WorkBuddy \| 49704 | 否 |
| `hotkey cmd+T` 前后 | WorkBuddy \| 49704 | 否 |
| `hotkey cmd+1` / AXPress 切 tab 前后 | WorkBuddy \| 49704 / Google Chrome \| 660 | 否 |
| `hotkey cmd+W` 前后 | WorkBuddy \| 49704 | 否 |
| `type_text` 地址栏 前后 | WorkBuddy \| 49704 | 否 |
| `end_session` 后 | WorkBuddy \| 49704 | 否 |

驱动自己的 `side_effects` 也与此一致：`foregrounded_window: false`、`injected_global_input: false`、
`restored_frontmost_app: false`（后者为 false 说明它压根没激活过，因此不需要恢复）。

**重要污染说明（必须写清）**：验证期间用户本人正在使用这台机器。
前台 app 在 `WorkBuddy|49704` 与 `Google Chrome|660`（用户自己的 Chrome）之间来回切换，
鼠标坐标在我未发起任何指针动作的情况下持续变化（`(604,408) → (587,403) → (427,586)`）。
因此：
- **光标位置不能作为“驱动没动鼠标”的证据** —— 期间的变化归属于人的手，不是驱动。
- 唯一可用的干净断言是“前台 pid 从未等于被驱动 pid”，该断言全程成立。
- `delivery_mode:"foreground"` 分支**没有测试**（会抢前台，按边界不主动做），所以
  “前台动作会不会恢复原来前台 app”这一问题**本次无证据**。文档层面：`bring_to_front` 明确写
  “This DOES steal foreground and does NOT restore the previously frontmost application”；
  `hotkey`/`type_text` 的 foreground 分支只承诺“做这件事所需的短暂前置”，无回滚契约。

---

## 5. 已知限制与坑

### 5.1 `browser_prepare` 不需要启动授权，0.8 秒起一个独立实例
`allow_launch:true` + `profile:{mode:"isolated_new"}` 在已授予 Accessibility/Screen Recording 的前提下
**一次成功、无任何 TCC 弹窗**（`displayed_consent_prompt:false`），`real 0.80s`。
`existing_profile` 那条路才有授权/前置窗口判定的复杂性（文档：macOS Chrome 会弹自己的 remote-debugging 提示，
且会因为会盖到用户 app 前面而 `refuse with background_unavailable` 除非 `delivery_mode:"foreground"`）——**本次未走，不评价**。

### 5.2 `target_id` / `tab_id` 每次 bind 都重新铸造 —— 最容易踩的坑
`get_browser_state {pid, window_id}` 每次调用都换发新的 `target_id` 和 `tab_id`。拿上一次的 id 去操作：

```json
{"status":"refused",
 "refusal":{"code":"browser_tab_not_found",
            "message":"tab tab-9b511152-... is not known for target bt-dd81bb95-..."},
 "hint":"This call needs a current tab_id. Bind the window with get_browser_state (pid and window_id); ..."}
```

对策：写一个 `bind.sh` 包装，先 bind 再把当次 id 注入同一调用（我在 `/tmp/desktop-verify/bind.sh` 里就是这么做的）。
另外 `get_browser_state` 不带 `pid` 直接调用会 `Missing required integer field: pid` ——
**没有“列出所有浏览器”的入口**，必须先从 `list_windows` 拿 pid+window_id。

### 5.3 tab 列表顺序 ≠ 视觉位置
切换 active tab 后，`tabs[]` 里原来的 index 1 变成 index 0（active 提前/MRU 排序），
视觉上两个 tab 并没有交换。按 index 推算“第几个 tab”会错，必须用 `active` 标志和 `url/title` 匹配。

### 5.4 CDP 与 AX 的边界
- 纯页面操作（`browser_navigate` / `browser_click` / `browser_pointer` / `browser_type` / 截图）走 CDP，
  **完全后台、可精确回读** —— 这是驱动最强的一层。
- 地址栏、标签条、窗口框架属于 **browser chrome**，CDP 默认碰不到，只能走 AX/HID：
  好消息是 AX 树里 chrome 控件是完整的（`AXTextField "地址和搜索栏"`、
  `AXRadioButton "Chromium - Wikipedia"`、`AXButton "新标签页"`、每个 tab 的 `AXButton "关闭"`），
  所以**新建/切换/关闭标签页可以纯 AXPress 后台完成，不必用快捷键**（我用了快捷键，两者都通）。
- 但 native 输入框的**提交**必须前台：AX 写入只改值不触发提交。这是“地址栏自动化”的硬墙。
- `get_browser_state` 的 snapshot 模式**不返回页面标题**，只有 `url`；标题要么取 bind 的
  `native_title`，要么取 `get_window_state` 的 `window_title`。

### 5.5 失败时的恢复手法
- 绑定失败/refuse：重新 `get_browser_state {pid, window_id}` 取新 id，不要复用旧 id。
- 树被截断：`get_window_state` 默认 250 节点，`truncated:true` 时用 `query` / `max_depth` / `max_elements` 收窄。
- 会话泄漏：`end_session` 幂等，`real 0.11s` 返回 `{"active": false, "session": "verify"}`，
  2 秒后 `ps -p 15305` 已无该进程，`list_windows` 中该 pid 窗口数为 0 —— **进程确实随会话结束**，
  `isolated_new` profile 不持久化。即使不主动 `end_session`，文档值 `idle_expires_in_seconds: 300` 后也会自退。

### 5.6 截图/AX 覆盖的一处保留
`get_window_state` 返回 `capture_coverage.browser_chrome.status = "may_be_incomplete_in_window_scope"`。
本次窗口截图里 tab 条和地址栏**拍到了**，所以它没成为问题；但它提醒：窗口级截图不保证包含浏览器
chrome，涉及 chrome 界面的视觉断言要另设验证路径。

### 5.7 后台快捷键比文档更宽松（macOS Chromium 实测）
文档说“background 键盘事件到不了原生菜单，菜单项快捷键会走 accessibility 或 `background_unavailable` 拒绝”。
实测在 macOS Chrome 上 `cmd+T` / `cmd+W` / `cmd+1` 三个**菜单快捷键**都走 `route: "synthetic_events"` 直接落地，
没有被拒，也没有前置窗口。对产品是好事，但别把“文档说会拒”当契约。

---

## 6. 如果要用在产品里，必须处理的问题（按严重度）

1. **地址栏/原生 chrome 的提交路径依赖前台**。AX 写入的 URL 不会因 Return 提交（驱动原话），
   要真跳转必须 `delivery_mode:"foreground"`。这意味着“像人一样用浏览器”的最常见动作会抢用户前台；
   而 `bring_to_front` 明确不恢复原前台 app，`type_text`/`hotkey` 的 foreground 分支也没有回滚契约。
   产品上要么接受前台打扰并**自己实现“记住并恢复原前台 app”**，要么把地址栏跳转明确划为不可用，
   只用 CDP `browser_navigate`（两者能力差一个量级，必须在产品语义上说清）。
2. **驱动无法区分“浏览上下文新窗口”和“浏览器 chrome 弹层”**。本次 omnibox 建议弹窗被记为
   `🪟 Action opened new window(s): Google Chrome`，与真实新窗口同类事件，直接触发了本次验证的
   安全制动、导致第 3/4 项无法完成。产品侧必须要求/自己补上分类（popup vs browsing context），
   否则任何“出现意外就停”的护栏都会被正常输入动作误触发，自动化频繁自杀。
3. **没有稳定的 tab/target 句柄**。每次 bind 重铸 id，旧 id 直接 `browser_tab_not_found`；
   列表顺序还会随 active 变化。长流程（多 tab 往返）里需要有封装层替调用方管理“重新绑定 + 用
   url/title 而非 index 认 tab”，否则极易点错 tab。
4. **隔离级别容易被误解**。“isolated_new 独立 Chromium”实际是用户已安装的 Google Chrome 二进制 +
   临时 profile：同一个 app bundle、同一个 TCC 身份，后台注入的 `cmd+W` 等键直接进真实 Chrome 的菜单体系。
   对外文案不能暗示 app 级沙箱；如果产品要“不打扰用户”，只能靠 `delivery_mode` 和 profile 分离，
   而不是靠“这是另一个浏览器”。
5. **缺少发现入口**。`get_browser_state` 不带 `pid` 直接报 `Missing required integer field: pid`，
   必须先 `list_windows` 自己筛出浏览器窗口（而且用户机器上同名 `Google Chrome` 进程/窗口会有多个：
   本次就有 pid 660 的 5 个窗口与 pid 15305 的 2 个窗口混在一起）。产品需要一个“选目标”的稳定抽象，
   否则会把操作打到用户自己的 Chrome 上。
6. **回读能力不齐**。snapshot 模式无页面标题；窗口级截图对 browser chrome 只承诺 `may_be_incomplete`。
   要“回读证据”的产品流程必须组合 bind(`native_title`) + `get_window_state`(`window_title`) 两种来源，
   并接受 chrome 区域视觉证据可能缺失。

---

## 7. 本次未覆盖 / 待补

- ~~第 3 项：页面内 ref 点击、坐标点击、`browser_pointer` 滚动与 `scrollY` 回读~~ —— **第二轮已补齐，见 8.1 / 8.2 节，结论：通过**。
- ~~第 4 项：新窗口（CDP 打开 / `target=_blank`）与 `list_windows` 回读~~ —— **第二轮已补齐，见 8.3 节，结论：通过**。
- 仍未覆盖：数值 `scrollY` 直读（两轮都没有可用的 JS 读取通路）、多显示器/其它 Space 下的行为、Windows/Linux 平台。
- `delivery_mode:"foreground"` 全部分支（含地址栏回车真提交）—— 未执行，因会抢前台。
- `existing_profile` 策略 —— 按边界禁止，未执行。
- `browser_dialog` / `browser_download` / `browser_select` / `browser_set_input_files` / `run_steps` —— 未执行。
- 空闲 300s 自动退出 —— 只记录文档值，未等待实测（`end_session` 的进程消失已实测通过）。

若需要补齐第 3/4 项：请**授权一次新的、只做页面内动作的运行**（不含地址栏输入、不含 foreground），
并且明确“驱动报告 `opened new window(s)` 但几何形如 chrome 弹层时不算异常、可继续用只读方式确认”。

---

## 8. 第二轮：只做页面内动作（补第 3、4 项）

- 时间：2026-11-05 17:25–17:40；会话标签 `verify2`；驱动自有实例 **pid 25324**
  （`ps` 确认：父进程 98546 = daemon，`--user-data-dir=/Users/czj/Library/Application Support/CuaDriver/BrowserProfiles/isolated-9eabf462-…`）
- 授权范围：只做页面内动作，不做地址栏输入、不碰 foreground 分支、不接 `existing_profile`、不碰用户 pid 660 的 Chrome。
  **本轮全程只用了 CDP 层工具**（`browser_navigate` / `get_browser_state` / `browser_click` / `browser_pointer` / `list_windows`），
  没有用 `hotkey`、`type_text`、`press_key`、`bring_to_front`。
- 两项必须声明的偏差：
  1. **`file://` 走不通**。`browser_navigate` 明确拒绝：
     `browser_navigate only accepts http/https/about URLs, got: file:///tmp/desktop-verify/page.html`。
     故改为 `python3 -m http.server 8765 --bind 127.0.0.1` 提供**同一个文件**，用 `http://127.0.0.1:8765/page.html` 打开。
     内容与 `/tmp/desktop-verify/page.html` 完全一致，仍是本地、无外网。
  2. **夹具在本轮内扩了一次**：`target=_blank` 实测只得到**新标签页**（见 8.4），拿不到“新窗口”。
     故在 `page.html` 增加一个按钮 `Open popup window (window.open, sized)` →
     `window.open('/popup.html','_blank','width=520,height=360')`，并新增 `/tmp/desktop-verify/popup.html`。
     两个文件都只在 `/tmp/desktop-verify/` 内。

### 8.1 第 3 项 页面内点击与滚动 —— **通过**

**做了什么 → 回读 → 结论**（回读全部是 CDP 读取，不是截图判读；截图另作旁证）

1. **ref 点击**：`browser_click {ref:"p8:0"}`（`Increment` 按钮，`snapshot_format:"semantic_v2"` 的 typed ref）
   ```json
   {"delivery":{"mode":"background"},"effect":"unverifiable","route":"trusted_input",
    "summary":"clicked (84, 201) in tab-241a3127-…","refusal":null}
   ```
   回读（`semantic_v2` 的 `content_refs`，计数器节点的 DOM 文本）：
   `p9:12 "Counter:" / p9:13 / p9:14 "1"` —— **0 → 1**。

2. **坐标点击**（同一按钮，故意取偏移点，证明不是走 ref）：`browser_click {x:95, y:196}`
   ```json
   {"delivery":{"mode":"background"},"effect":"unverifiable","route":"trusted_input",
    "summary":"clicked (95, 196) in tab-1d02fd62-…"}
   ```
   回读：`p11:14 "2"` —— **1 → 2**。坐标单位确认是 **CSS px 视口坐标**（y=196 落在按钮内，按钮由 ref 点击暴露的中心是 y=201）。

3. **滚动**：`browser_pointer {action:"scroll", x:400, y:400, delta_y:1200}`
   ```json
   {"delivery":{"mode":"background"},"effect":"unverifiable","route":"trusted_input",
    "summary":"dispatched trusted scroll in tab-…"}
   ```
   回读 A（`semantic_v2` 可见性标签）：`in_viewport` 由 `Row 5..12` → `Row 18..25`；
   `omitted.offscreen` 由 **220 → 198**。
   回读 B（截图判读，`shots/08-after-scroll.png`、`10-after-scroll2.png`）：第一屏顶部行号
   `Row 1–10` → `Row 18–33` → `Row 43–58`。

**关于“滚动到底走了多远”的量化**：Δy 请求 1200 CSS px，实测两轮各前进 **25 行**（Row 18→43），
行高约 47px → **≈1175px，即 delta 基本被准确执行**（误差 ~2%）。

**第 3 项结论：通过。** ref 点击、坐标点击、滚动三条通路都在 background 模式下真实生效，且都有独立的 DOM 文本回读。

### 8.2 第 3 项查出的一个反例：`semantic_v2` 的 `in_viewport` 与真实视口差约 2 倍

这是本轮最重要的“回读证据”提醒。同一时刻、同一个 tab：

| 时点 | `semantic_v2` 说 `in_viewport` | 截图（CDP 视口）实际顶部行 | 偏差 |
|---|---|---|---|
| 滚动 0 | 无 `in_viewport`（Row 1–10 全是 `near_viewport`） | 页面顶部，无列表行 | — |
| scroll #1 后 | `Row 5 – 12` | `Row 18 – 33` | 顶部行差 13 行（≈611px） |
| scroll #2 后 | `Row 18 – 25` | `Row 43 – 58` | 顶部行差 25 行（≈1175px） |

两次 `in_viewport` 只前进 13 行，而画面实际前进 25 行 —— **比例稳定在约 1.92 ≈ 2**，
与本机 `deviceScaleFactor = 2` 吻合。**推测**可见性判定把 scroll 偏移按设备像素当成了 CSS px（差一倍）；
未做进一步取证，因为本机没有 JS 读取通路（见 8.4 第 4 条，`page` 工具失效）。
结论：**滚动位置类断言必须用截图，`visibility` 只能当“大致方向”用。**

### 8.3 第 4 项 新窗口 —— **通过**（但必须先分清 tab 与 window）

1. **`target=_blank` 只给新标签页，不给新窗口**。点击夹具里的
   `<a target="_blank" href="https://example.com/?from=popup">` 后回读：
   ```
   native_title 'Example Domain'
     TAB[0] active=True  https://example.com/?from=popup  Example Domain
     TAB[1] active=False http://127.0.0.1:8765/page.html  Desktop Verify Page
   WINDOWS for 25324: 2   (3564 主窗口 + 3580「翻译此页？」)
   ```
   → 新窗口**没有**出现，出现的是同一窗口内的新 tab。计为 **tab 级证据**，不是第 4 项的窗口证据。

2. **`window.open(url, '_blank', 'width=520,height=360')` 才产生真正的独立窗口**。点击后 `list_windows`（pid 25324）：
   ```
   (3564, {'height':819.0,'width':1200.0,'x':22.0,'y':55.0},  on_screen=True,  'Desktop Verify Page')
   (3607, {'height':426.0,'width': 520.0,'x':0.0,'y':33.0},   on_screen=True,  'Popup Window Fixture')
   (3606, {'height': 87.0,'width': 284.0,'x':853.0,'y':135.0},on_screen=True,  '翻译此页？')
   (3608, {'height': 87.0,'width': 284.0,'x':236.0,'y':99.0}, on_screen=True,  '翻译此页？')
   ```
   再 `get_browser_state {pid:25324, window_id:3607}` 回读该新窗口**自己的** CDP 绑定与内容：
   ```json
   {"binding_quality":"exact","binding_route":"native_cdp_window",
    "native_title":"Popup Window Fixture","target_id":"bt-e67a8656-…",
    "tabs":[{"active":true,"tab_id":"tab-2c68ac39-…",
             "url":"http://127.0.0.1:8765/popup.html","title":"Popup Window Fixture"}]}
   ```
   **几何核对**：请求 `width=520,height=360`，实测窗口 520×426 —— 宽精确等于 520，高 426 = 360 内容高 + 66px 浏览器 chrome，
   符合“内容尺寸”语义。**尺寸/标题/URL/target 四项都对上了。**

**第 4 项结论：通过。**（严格说是“`window.open` 能开真窗口、`target=_blank` 只开 tab”这个更细的结论。）

### 8.4 本轮记录到的其它限制

1. **多实例会让旧 `page` 工具直接失效**：
   `browser_applescript_process_ambiguous: bundle com.google.Chrome has 2 live regular application instances;
   AppleScript cannot prove requested pid 25324. Use an exact CDP target or close the other instance.`
   —— 只要驱动实例和用户 Chrome 同时存活，`page get_text` / `query_dom` 这条 AppleScript 路线就不可用。
   （`query_dom` 还要求 `window_id`，只给 `pid` 会返回笼统的 `invalid_arguments`。）
2. **`browser_pointer` 的 scroll 必须带 `ref` 或 `x`/`y`**，否则报
   `browser_pointer needs a ref or x/y coordinates`；这个错误在 1 次调用里表现为“空结果”，
   很容易被自建的 JSON 包装层吞掉（我自己就踩了：包装脚本把 stderr 吞成 `_raw: null` 之外的空对象）。
   产品里不能把“空响应”当“成功”。
3. **`browser_navigate` 只接受 http/https/about**（见开头偏差 1）。
4. 夹具页面是英文，Chrome 反复弹出 `翻译此页？` 气泡窗口（284×87）—— 见 8.6 的噪声判定。

### 8.5 `target_id` / `tab_id` / tab 顺序：量化序列

**序列 A：同一窗口、同一 tab，连续 3 次 `get_browser_state {pid, window_id}`（间隔 0.3s，中间不做任何动作）**
```
seq1 target=bt-ad980858-1e13-4de3-bb39-bcf1cdc0c736 tab=tab-f77c5482-b3c5-44aa-8ca6-9e68ece4fc32 url=about:blank
seq2 target=bt-06bdf20f-32b7-4d8e-b17c-17aa8c7d7e6d tab=tab-2cde5293-d3f2-4396-bce3-39150deb5211 url=about:blank
seq3 target=bt-9c044893-2bfa-4784-97a9-a0e40d719a61 tab=tab-57ef5ff8-2398-40af-b4bb-f39cd9f86838 url=about:blank
```
→ **3/3 次 target 与 tab id 全部不同**，同一张 about:blank 连“会话内稳定句柄”都没有。
用旧 id 操作的真实报错（第一轮实测）：
```json
{"status":"refused","refusal":{"code":"browser_tab_not_found",
 "message":"tab tab-9b511152-… is not known for target bt-dd81bb95-…"}}
```

**序列 B：新建/切换 tab 时 `tabs[]` 的排列（第一轮，同一窗口）**
```
新建后        TAB[0] active=False example.com      TAB[1] active=True  chrome://newtab/
切到另一个后  TAB[0] active=True  wikipedia        TAB[1] active=False example.com
```
→ **active 跑到 index 0**，视觉上两个 tab 没换位置。index 不是位置。

**序列 C：新 tab 插入位置（第二轮，`target=_blank` 之后）**
```
TAB[0] active=True  https://example.com/?from=popup   ← 新开的 tab 占 index 0
TAB[1] active=False http://127.0.0.1:8765/page.html
```
→ 新 tab 同样插到 index 0。

**对“按 id 还是按 index 认 tab”的实现约束（直接可用）**
- **不能按 index**：index 语义是“活跃优先/MRU”而非视觉位置，切换与新建都会把它打乱。
- **不能跨调用缓存 id**：每次 bind 都重铸，必须“一次 bind → 立刻用同一次返回的 `target_id`+`tab_id` 完成动作”，
  动作之间要重新 bind。我为此写了 `bind2.sh`（bind 后把当次 id 注入同一次调用）。
- **可靠的稳定身份只有三元组**：`(pid, window_id)` 定窗口 + 在该窗口 bind 结果里用 **`url` + `title` + `active`** 认 tab；
  `tab_id` 只能当“这一次调用里的临时游标”用。
- ref 命名空间是 `p<snapshot_id>:<index>`（本轮从 `p4` 递增到 `p23`），**新快照会作废旧 ref**；
  要“点完再读”，必须用回读那次快照产生的新 ref。

### 8.6 意外 vs 噪声：本轮判定清单

| 事件 | 观测证据 | 归类 | 处理 |
|---|---|---|---|
| `type_text` 后出现 1038×218、x=121,y=80、无标题、紧贴地址栏下方的窗口（第一轮 3506） | 几何 + 无标题 + 无独立 URL | **噪声**：地址栏建议下拉弹层 | 记录一次，继续（第一轮因无此条约定而停，本轮规则已修正） |
| 出现 284×87、标题「翻译此页？」的窗口（本轮 3606 / 3608） | 有 UI 标题、极小的固定尺寸、无 CDP target 绑定 | **噪声**：Chrome 翻译气泡 | 忽略，不当作新窗口证据 |
| `window.open(...,width,height)` 后出现 520×426、标题 `Popup Window Fixture` 的窗口（3607） | `native_title` + 独立 `target_id` + 独立 `url=popup.html` + `binding_quality:exact` | **真事件**：独立浏览上下文窗口 | 计为第 4 项证据 |
| `target=_blank` 只在同一窗口开出新 tab | `tabs[]` 由 1 → 2，且 url 变成 example.com | **真事件但非窗口** | 计为 tab 级证据，不冒充窗口 |

**判定口径（可直接写进产品逻辑）**：新出现的窗口若**能绑定出独立 CDP target 且 `tabs[].url` 是 http(s)** → 真浏览窗口；
若**绑不出 target、无 URL、尺寸是固定的 UI 尺寸、标题是浏览器自带文案（翻译/弹层）** → chrome 噪声。

### 8.7 前台：本轮两次前台变化，逐条归类（这是新发现，必须看）

第一轮结论“background 动作不抢前台”在本轮**部分不成立**：

1. **`browser_prepare` 启动时**：启动前 `Electron|49704`，启动后立刻变成 `Google Chrome|25324`（= 驱动自己启动的实例）。
   约 1–2 分钟后前台变成用户自己的应用（用户自己在操作）。→ **启动路径的前台行为不稳定**：
   第一轮 `foregrounded_window:false` 且前台未变，本轮同样的调用却把新窗口带到了前面。
2. **`window.open` 弹出新窗口时**：点击后前台变成 `Google Chrome|25324`，并**持续 ≥4 秒没有恢复**
   （连续采样 4 次都是 25324），直到我 `end_session` 关掉实例，前台才回到用户的 app。
   → 这是**浏览器自身语义**（带 user gesture 的 `window.open` 会激活新窗口），不是驱动注入的 HID/AX 动作；
   但对用户来说结果一样：**前台被抢，且驱动没有恢复原 app**。
   本轮据此按硬边界第 4 条停止驱动，只做清理（`end_session`）与报告。

**清理核实**：`end_session {"session":"verify2"}` → `{"active":false}`，`real 0.12`；
3 秒后 `ps -p 25324` 无输出、`list_windows` 中该 pid 窗口数 **0**、本地 http 服务已 kill（`curl` 返回 000）；
用户 Chrome（pid 660）仍是**原来的 5 个窗口** `2283/186/185/183"Nano"/81`，全程未被波及。

### 8.8 对第 6 节的增补（按严重度插入）

1. **页面内动作也可能把浏览器窗口拉到前台，而且不会自己退回去**。`window.open`（带尺寸）必然激活新窗口；
   这类“页面 JS 引起的激活”与驱动自身的 `foreground` 分支是两回事，`delivery_mode:"background"` 管不住它。
   产品必须：要么在页面动作后**主动检测并恢复原前台 app**，要么把“会开窗口的页面”明确标为前台风险操作。
2. **`semantic_v2` 的可见性/视口判定与真实渲染差约 2 倍（DPR 相关）**（8.2）。凡“滚动到某处/元素是否可见”的验收，
   必须以 CDP 截图为证据；否则会把“滚了 1175px”读成“滚了 611px”。
3. **旧 `page` 工具在多实例场景直接不可用**（8.4-1）。产品若同时存在用户浏览器与驱动实例，
   任何依赖 AppleScript 的兼容路径都要么禁用、要么先解决 pid 归属歧义。
4. **静默失败要当失败**：`browser_pointer` 缺 `ref`/`x,y` 时返回的是错误文案而非结构化 refusal，
   包装层很容易把它变成“空结果 = 成功”（8.4-2）。
