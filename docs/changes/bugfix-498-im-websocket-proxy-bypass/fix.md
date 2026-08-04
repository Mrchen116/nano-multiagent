# bugfix-498: IM WebSocket proxy bypass

## Relations

- Related: 无

## 原始报告

> `src/personal_assistant/gateway/composition.py` 保留，但不要裸提交。`proxy=None` 是修复本机 SOCKS 干扰远端 IM WebSocket 的真实 bug；应新建 Bugfix lite，补一个连接参数回归测试后，以 `fix(gateway): bypass system proxy for IM websocket` 提交。

> WebSocket Bugfix lite这个先停留在spec建立。

## 澄清记录

- Q1: 修复边界是否确认为——仅 Gateway 到配置 IM 的持久 WebSocket 强制直连、不使用系统 SOCKS/HTTP proxy；IM HTTP bootstrap 和飞书、搜索等其他出站连接保持各自现有行为？
  A(原话): 这个我有保留，因为tailscale链接过去IM服务器，这是我这的做法，别人的做法可能不一定。比如别人的IM可能在防火墙外，需要用代理。我觉得我们的软件应该和这些解耦
  Agent 解读: Gateway 到 IM 的网络路径不能隐式继承操作系统代理，也不能固定为直连；它应独立于部署网络做法。

- Q2: 运维者是否应当只配置一次“Gateway 连 IM 的网络路径”，并同时用于 WebSocket、绑定和 token 刷新等 IM 通信？
  A(原话): ok
  Agent 解读: 未配置时默认直连；需要代理时由运维者显式选择代理，并统一应用到 Gateway 的全部 IM 通信。

- Q3: 选定直连或代理后，若该路径不可达，是否保留该选择并按现有重试/报错路径处理，不自动改走另一条网络路径？
  A(原话): 对
  Agent 解读: 网络路径由运维者负责；Gateway 不得根据一次连接失败暗中从直连切到代理，或从代理切到直连。

## 现象 / 复现

Gateway 启动后会对配置的 IM 服务建立持久 WebSocket，以注册节点、维持在线状态和接收控制消息。当前部署同时满足下列条件时会失败：

1. 运维者已将 IM 地址配置为 Tailscale、局域网等可直连地址；
2. Gateway 进程所在环境设置了 SOCKS/HTTP 系统代理；
3. WebSocket 客户端自动拾取该系统代理。

连接被送往代理而非配置的直连路径；代理无法到达私网 IM，或环境没有安装代理所需的依赖时，Gateway 无法注册为在线节点。反过来，IM 位于防火墙外且必须经代理访问的部署，也没有一个由 Gateway 明确拥有的代理选择。于是同一份 Gateway 配置在不同机器的系统代理环境下会有不同结果，且 WebSocket 与绑定、token 刷新等其他 IM 通信可能各走各的路径。

目标行为是：默认直连；运维者需要代理时显式配置一条 Gateway 到 IM 的网络路径，并让 WebSocket、绑定和 token 刷新共用它。所选路径不可达时，Gateway 沿既有重试和诊断路径报错，不自动切换到另一条路径。

## 根因

`_connect_websocket()` 调用 `websockets.connect()` 时没有传入 `proxy` 参数。当前依赖版本会默认启用系统代理发现，因此 Gateway 的关键 IM WebSocket 实际受进程环境变量和系统代理配置支配，而不是受 Gateway 自己的配置支配。

直接写死 `proxy=None` 只能修复“本机 SOCKS 干扰 Tailscale/局域网 IM”的部署，却会破坏“防火墙外 IM 必须经代理”的有效部署。根因不是缺少一次直连参数，而是 Gateway 缺少一个显式、统一的“到 IM 的网络路径”配置：该配置必须同时约束 WebSocket、绑定和 token 刷新，不能分别继承隐式系统代理，也不能在失败时猜测并切换路径。

持久 WebSocket 的现有职责是连接配置的 IM 地址并在断开后重连；本修复只补足该连接的网络路径归属，不改变 Gateway 与 IM 的连接和重连职责。

## 修复

## 验证
