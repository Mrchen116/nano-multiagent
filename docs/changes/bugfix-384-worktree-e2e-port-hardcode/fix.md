# bugfix-384: worktree e2e 测试链路上的端口硬编码遗漏（kernel.base_url + vite proxy）

## Relations

- Closes: #59
- Related: refactor-381-e2e-workflow

## 原始报告

> worktree e2e 测试链路上有两处端口硬编码导致隔离失效，每次 worktree 测试都得手工绕过。
>
> ---
>
> ## 问题 A: scripts/e2e-up.sh 漏 patch kernel.base_url
>
> ### 症状
>
> worktree 里跑 `./scripts/e2e-up.sh`：Kernel API 起在 ephemeral 端口（如 51140），但 Gateway 仍按默认 `http://127.0.0.1:8000` 去连主仓 kernel。
> - 主仓 kernel 也起着 → Gateway 把流量打到主仓 kernel（worktree 隔离失效）
> - 主仓 kernel 没起 → Gateway 连不上，所有需要 kernel 的功能（agent 对话、capabilities、prompt-preview）失败
>
> ### 根因
>
> `scripts/e2e-up.sh` 给 worktree 复制 `.gateway-config.yaml` 时只 patch 了三处：
> - `node.node_id`
> - `im_service.url`
> - `agents[].workspace_root`
>
> **漏 patch `kernel.base_url`**。Gateway 的 `KernelConfig.base_url` 默认值是 `http://127.0.0.1:8000`（见 `src/personal_assistant/config/local_store.py:16`）。
>
> ### 影响
>
> 每次 worktree e2e 启动（worker e2e 验证 / reviewer 走旅程 / 手动测试 PR）都得**手动 patch** `.gateway-config.yaml`：
>
> ```yaml
> kernel:
>   base_url: http://127.0.0.1:$API_PORT
> ```
>
> 然后重启 Gateway。feat-383 实施期 worker 撞过、reviewer 撞过、orchestrator 手动测试时又撞了——重复劳动且易遗漏。
>
> ### 修复方向
>
> `scripts/e2e-up.sh` 的 yq 段加：
>
> ```
> .kernel.base_url = "http://127.0.0.1:$API_PORT"
> ```
>
> Python fallback 分支同步加：
>
> ```python
> cfg.setdefault("kernel", {})["base_url"] = f"http://127.0.0.1:{os.environ['API_PORT']}"
> ```
>
> ---
>
> ## 问题 B: src/IM/frontend/vite.config.ts proxy 硬编码 8021
>
> ### 症状
>
> worktree 里跑 `cd src/IM/frontend && npm run dev`：
> - Vite dev server 起在动态端口
> - 但 `/im` proxy target 写死 `http://127.0.0.1:8021`
> - worktree IM 起在 ephemeral 端口（如 51139）
> - proxy 失败 → 登录请求打到错地址 → 死循环 / 401
>
> ### 根因
>
> `vite.config.ts` 的 `server.proxy` 配置硬编码 `8021`，无 env override 接口。
>
> ### 影响
>
> - 仅影响 "Vite dev server 调试前端 + hot reload" 的工作流
> - 不影响 "IM 直接 serve dist 产物" 的路径（e2e-up.sh 默认路径）
> - 所以日常 e2e 不撞，但前端开发者切到 worktree 时撞
>
> ### 修复方向
>
> 支持 env override：
>
> ```ts
> const IM_PROXY_TARGET = process.env.VITE_IM_PROXY_TARGET ?? 'http://127.0.0.1:8021';
> ```
>
> 或更激进：读 `.e2e-ports.env` 自动对齐 worktree IM 端口。
>
> ---
>
> ## 相关
>
> - 在 feat-383 (#58) 实施期反复浮现的 out-of-unit Side Findings
> - 两处都是 worktree e2e 端口隔离链路上的硬编码遗漏；e2e-up.sh 由 refactor-381 引入，旨在替代 12 步手工 ritual，这两条是该自动化的遗漏
> - 问题 A 优先级高于问题 B：A 撞每个跑 e2e-up.sh 的人；B 只撞前端 dev workflow
>
> ## 影响范围
>
> 仅工具脚本与前端配置，无运行时 / 业务代码改动。lite bugfix 一次性修掉即可。

## 澄清记录

- Q1: 本 unit 的范围是同时修 A + B,还是只修 A、B 单独立 unit?
  A(原话): 都修

- Q2: 问题 B 修复方式 —— env override(`VITE_IM_PROXY_TARGET`)还是让 `vite.config.ts` 自动读 `.e2e-ports.env`?
  A(原话): ok
  Agent 解读: 采用 env override,变量名 `VITE_IM_PROXY_TARGET`,默认仍为 `http://127.0.0.1:8021`。

- Q3: `scripts/e2e-up.sh` 要不要顺手把 `VITE_IM_PROXY_TARGET=$IM_URL` 导进 `.e2e-ports.env`?
  A(原话): ok
  Agent 解读: 导。`.e2e-ports.env` 多加一行 `export VITE_IM_PROXY_TARGET=$IM_URL`,worktree 前端 dev 可一气呵成 `source .e2e-ports.env && npm run dev`。

## 现象 / 复现

### 问题 A: `e2e-up.sh` 漏 patch `kernel.base_url`

worktree 跑 `./scripts/e2e-up.sh` 后,Kernel API 起在 ephemeral 端口(如 51140),但 Gateway 的 `.gateway-config.yaml` 仍按默认 `http://127.0.0.1:8000` 去连 kernel:

- 主仓 kernel 在跑 → Gateway 流量打到主仓 kernel,worktree 隔离失效(分支代码的修改被主仓 kernel 吞掉)。
- 主仓 kernel 没跑 → Gateway 连不上,agent 对话 / capabilities / prompt-preview 全部失败。

复现:在 worktree 内 `./scripts/e2e-up.sh && cat .gateway-config.yaml | grep -A1 '^kernel:'`,看到 `base_url: http://127.0.0.1:8000` 而非 `:$API_PORT`。

### 问题 B: `vite.config.ts` proxy 硬编码 `8021`

worktree 跑 `cd src/IM/frontend && npm run dev`:Vite dev server 起在动态端口,但 `/im` proxy target 写死 `http://127.0.0.1:8021`;worktree IM 起在 ephemeral 端口(如 51139)→ proxy 失败 → 登录请求打到错地址 → 死循环 / 401。

仅影响"Vite dev server 调试前端 + hot reload"工作流;e2e-up.sh 默认走 IM serve dist 路径不受影响。

## 根因

两处都是 worktree e2e 端口隔离链路上的硬编码遗漏,根因同构:**`refactor-381-e2e-workflow` 引入 `e2e-up.sh` 替代 12 步手工 ritual 时,端口动态化没扫全所有消费点。**

- A: `scripts/e2e-up.sh` 给 worktree 复制 `.gateway-config.yaml` 时只 patch 了 `node.node_id` / `im_service.url` / `agents[].workspace_root` 三处,**漏 `kernel.base_url`**。Gateway `KernelConfig.base_url` 默认值 `http://127.0.0.1:8000`(见 `src/personal_assistant/config/local_store.py:16`),不被 patch 就一直指向主仓 kernel 默认端口。yq 与 Python fallback 两条分支都漏。
- B: `src/IM/frontend/vite.config.ts` 的 `server.proxy['/im'].target` 写死 `http://127.0.0.1:8021`,无 env override 接口;`.e2e-ports.env` 输出契约里也没相应变量。

**原始设计意图(refactor-381)**:`e2e-up.sh` 的存在意义是"worktree 内起的所有服务都用 ephemeral 端口 + 自动改 config,主仓默认端口保留给用户手起的主实例,避免 worktree 流量误打到主仓"。修复必须保住的不变量:**worktree 内任何下游(Gateway / vite dev)都只引用本 worktree 起的服务端口,不引用主仓默认端口**。

feat-383 实施期 worker / reviewer / orchestrator 反复手动 patch `kernel.base_url`,即是该不变量在 A 点失守的直接症状。

## 修复

## 验证

