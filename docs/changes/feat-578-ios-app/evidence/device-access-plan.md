# 真机访问隔离 IM（R1-W2）

选择：复用当前 Mac 的 **Tailscale Serve HTTPS**，将一个本次独占的 tailnet HTTPS 端口转发到 e2e IM 的 loopback HTTP。iPhone 使用同一 tailnet；Release App 保持 HTTPS/WSS 与系统证书验证，不增加 ATS 任意加载或跳过证书检查，不使用 Funnel 公网暴露。

官方依据：[Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve)、[HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates)。本轮只读核实当前 Mac Tailscale 自身 Online、DNSName 存在，CLI 支持 `serve --https <port> <target>`；已有 Foreground 配置必须保留，未新建代理。设备连通与证书实际可用仍待真机时段验证，列入 R1-W1 资源缺口。

## 执行与清理

1. 本次操作者先保存 `Tailscale serve status --json` 的本机副本（不提交），检查全部顶层及 Foreground TCP/Web 监听，选择无冲突 HTTPS 端口，例如 **19443**；不能覆盖已有 443/其他任务入口。域名从 `Tailscale status --json` 的 Self.DNSName 获取并去掉末尾点，形成 `https://<self-dns-name>:19443`。此地址写入本次私有运行记录，不硬编码为产品默认。
2. 以该精确 origin 和实际 Vite origin 组成 `IM_BROWSER_ORIGINS`，再按 worktree-runtime 启动 `e2e-up.sh --wt <unit-runtime>`。IM/Gateway 内部仍使用脚本生成的 loopback URL。全新 DB、owner、node identity、workspace、JWT 和测试对象保持隔离；不用生产 IM 或生产 Bot。
3. 在本次独立终端/tmux pane 前台运行：

   ```sh
   /Applications/Tailscale.app/Contents/MacOS/Tailscale serve --https=19443 http://127.0.0.1:<本次IM_PORT>
   ```

   不传 `--bg`，退出此进程即撤销本次 Foreground serve。若 CLI 要求首次启用 HTTPS/访问权限，停在其具体授权界面向用户说明，不能自动扩大 tailnet ACL 或启用 Funnel。沿现有 tailnet ACL，不将 test IM 公开到 Internet。
4. Mac 用 `curl -fsS https://<self-dns-name>:19443/openapi.json` 验证受信任 HTTPS；同时确认本次 PID/cwd/listener。iPhone 开启已有 Tailscale 连接，在 Safari 打开同一地址，必须无证书警告；再在 App 的服务地址填同一 HTTPS origin。手机失败不得以 Mac curl 通过代替。
5. 原生客户端的 WS URL 为同源 `wss://<self-dns-name>:19443/im/ws/user`，请求头 `Origin` 为上述 HTTPS origin；ticket 仍由同源 Bearer API 获取。必须验证 ticket→WS ready、重连后真实增量与图片/附件同源读取；新 Origin 只登记在本次隔离 IM 环境变量。
6. 测试结束停止该 Foreground Serve 进程，比较 `serve status --json`：本次端口消失、此前其他配置保持；然后执行本次 `e2e-down.sh` 并关闭自己的 Vite。**禁止 `serve reset`、杀全部 tailscale 进程或清其他任务配置。**

这补齐了接入方案，尚不是手机可达的实测证据。用户已明确将真机准备安排在有可安装版本后；实际手机 HTTPS/WSS 访问、签名/配对和 Mini AltServer 同网条件留在 M1 对应验收前落实，不作为设计/开始实施的阻断。方案本身不证明连通成功。
