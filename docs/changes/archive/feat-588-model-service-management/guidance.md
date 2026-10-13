# feat-588：安装包发布与部署交接

本文件是本 unit 合入后的发布交接，供部署 Agent 执行。编写指南不代表已发布 Release、更新线上 manifest 或部署生产。执行时重新核对 GitHub、生产配置和运行态，不把历史验收报告当作当前线上状态。

## 目标与完成边界

用户从正式 IM 首次设置页获得安装说明或终端命令，无需克隆仓库、预装 Node 或手写 YAML；安装器准备运行环境、下载固定版本程序包、安装依赖，随后用户在网页确认电脑绑定，配置模型并开始与助手聊天。

当前交互是“一条终端命令，或交给本机 Agent 执行，再到网页确认绑定”，不是浏览器按钮直接静默安装本机程序。支持目标为 macOS、Linux / Windows WSL；不要宣称原生 Windows 安装器已经交付。

完成需要三件事同时成立：

1. 固定源码版本的公开 GitHub Release asset 已通过匿名下载与 SHA-256 校验。
2. 对应 IM 后端、Web 前端和已验证的 `manifest.json` 已配套部署，公网安装入口可用。
3. 从公网入口完成一次真实首次安装、绑定、模型连接和助手回复；现有生产舰队仍正常。

## 先读与执行范围

- 本 unit [安装分发设计](design.md)、[已有分发证据与边界](M1/evidence/release-distribution.md)。既有 fixture 测试不证明真实 GitHub 下载或生产安装成功。
- [生产部署 skill](../../../../.claude/skills/prod-fleet-deploy/SKILL.md)、[生产拓扑](../../../operations/prod-fleet.md)、[节点操作](../../../operations/gateway.md)。实际启停、备份和舰队验收遵循这些入口，不在本文件复制整套命令。
- [发布工作流](../../../../.github/workflows/node-release.yml)、[发布脚本](../../../../scripts/publish-node-release.mjs)、[构建脚本](../../../../scripts/build-node-release.mjs)、[安装脚本](../../../../apps/im-server/assets/install.sh)、[IM 安装路由](../../../../apps/im-server/src/install.ts)。

执行发布与部署前应已有用户针对这些动作的授权；本文件本身不是现在执行发布的请求。若用户要求“按本指南发布并部署”，在该范围内完成整个闭环，不把只构建、只重启或只发布 Release 当成交付。

## 1. 固定发布版本

1. 确认前置 feat-587（PR #337）和本 unit（PR #339）已按依赖顺序合入；实时检查 PR 状态，不沿用编写时的快照。
2. 选择包含这两个 unit 的已通过 CI 的 main commit，记为 `RELEASE_SHA`，必须是完整的 40 位小写 SHA。IM、前端与安装包使用这个明确版本；不要发布临时试用 worktree 的 dirty 构建产物。
3. 核对现有生产版本、manifest 是否存在、实际 `IM_NODE_RELEASE_DIR`、IM launcher 的 `IM_PUBLIC_URL`，保存可恢复的旧构建与旧 manifest。保留生产数据库、附件、签名密钥、节点身份、模型凭据和用户工作区。
4. 只读检查 `node-${RELEASE_SHA}` 是否已有 Release。若已有，先核对其发布记录和原始已验证 manifest，不直接重复运行发布或覆盖 asset。

## 2. 发布并取得经过验证的 manifest

在 GitHub Actions 手动执行 **Publish Node installer**，输入上一步的完整 SHA。该 workflow 仅由 `workflow_dispatch` 触发，merge 不会自动发布。

也可以在已授权的部署会话执行以下命令；先把占位值替换成已核实的 SHA：

```bash
RELEASE_SHA='<已通过 CI 的完整 main commit SHA>'
gh workflow run node-release.yml --repo Mrchen116/nano-multiagent --ref main -f commit="$RELEASE_SHA"
gh run list --repo Mrchen116/nano-multiagent --workflow node-release.yml --event workflow_dispatch --limit 5
```

从返回列表确认本次 run ID，并核对 run 的输入确实是 `RELEASE_SHA`；不要不加核对地取最新一条并行运行。等待该 run 成功后，下载其产物：

```bash
RELEASE_RUN_ID='<本次已核实的 run ID>'
RELEASE_ARTIFACT_DIR="$(mktemp -d /tmp/nano-release-manifest.XXXXXX)"
gh run watch "$RELEASE_RUN_ID" --repo Mrchen116/nano-multiagent --exit-status
gh run download "$RELEASE_RUN_ID" --repo Mrchen116/nano-multiagent \
  --name "node-manifest-$RELEASE_SHA" --dir "$RELEASE_ARTIFACT_DIR"
```

工作流会在干净 checkout 中安装锁定依赖、构建一次、执行 typecheck/tests，然后：

- 发布 tag `node-<完整 SHA>`，asset 为 `nano-node.tgz`；
- 不携带用户 GitHub 凭据重新下载公开 asset，校验真实字节的 SHA-256；
- 只有校验通过才生成可部署的 `manifest.json`，并上传 `node-manifest-<SHA>` artifact。

部署前核对下载的 manifest：`version` 等于 `RELEASE_SHA`；`download_url` 等于该 SHA 的固定 GitHub Release asset URL；`sha256` 是该已上传包的哈希。保存 run URL、Release URL 和这份原始 manifest。

**不要把本地 `pnpm build` 生成的 `manifest.candidate.json` 改名充当发布结果。** 同一源码重新打包也不能保证压缩包字节相同，必须使用对应发布 run 的已验证 manifest。

## 3. 部署对应 IM、前端和清单

1. 按生产部署 skill 更新指定版本的 IM、Web 前端和双节点。实际生产 checkout、launcher 和进程路径以现场为准；不修改本次无关的代理或 Tunnel 配置。
2. 在切换服务前完成旧版本备份及新构建准备。IM 的 `IM_PUBLIC_URL` 应为用户实际访问的公网 origin；现有生产拓扑记录为 `https://im.nanoim.win`，执行时核实。
3. 把上一步下载的 `manifest.json` 放入 IM 实际使用的 `IM_NODE_RELEASE_DIR`。未配置该变量时，默认是该 IM checkout 根目录下的 `dist/node-release`。跨机器部署必须把 workflow artifact 传到 IM 所在机器，不能只留在操作端电脑。
4. IM 切换到匹配构建时同步切换 manifest；先写临时文件再原子替换，避免读到半份 JSON。记录旧文件是否存在和备份位置。
5. IM 只需要 manifest，程序包仍由 GitHub 提供，不需要把 `nano-node.tgz` 搬到 IM 或另开下载服务。发布 workflow 不会自动执行本节操作。

注意：现有 `docs/operations/local-stack.md` 若仍写“`pnpm build` 直接生成 `manifest.json`，IM 提供包体”，那是本次分发改动前的旧说明。此次部署应以本 unit 的设计及上列实际构建、发布、安装路由源码为准，不能依照旧说明部署 candidate。

## 4. 公网与真实安装验收

先完成部署 skill 要求的 HTTPS/WSS、前端资源、两节点 online、进程版本/身份和真实消息验收，再核对新增安装链路：

| 验收项 | 必须观察到的结果 |
|---|---|
| 公网 `/install.sh` | 返回 200，脚本注入正式 IM origin，没有本地试用端口或用户凭据 |
| 公网 `/install/manifest.json` | 返回 200、`Cache-Control: no-store`，内容与本次已验证 artifact 一致 |
| 旧 `/install/nano-node.tgz` | 返回 302、`no-store`，Location 为同一 manifest 的固定 GitHub asset URL |
| 匿名下载 | 不使用 GitHub 登录或 token，能下载 manifest 指定包，SHA-256 与 manifest 相同 |
| 首次设置页 | 安装材料可用，命令/交给本机 Agent 的说明指向正式站点 |
| 新用户安装 | 在专用测试用户/测试机或隔离安装根执行页面原始命令；实际下载、依赖安装、网页绑定完成，电脑 online |
| 首次使用 | 通过网页连接 API/模型并真实测试，创建助手，发消息获得真实回复 |
| 重跑安装 | 重跑同一命令保留该测试连接身份、模型和助手，没有重复创建或破坏现有安装 |

测试电脑需要能访问正式 IM、GitHub Release asset、Node.js 下载源和 npm 依赖源；安装包不内置所有依赖。网络下载失败应按真实错误定位，不能通过测试机已有缓存宣称全新安装已经成功。

优先使用专用测试账号和测试环境，不占用或重绑现有生产节点。使用 `NANO_INSTALL_ROOT` 隔离时仍须核对实际生成的 config、node identity 和后台进程，结束后只清理本次测试创建的资源。浏览器截图或 fixture 成功不能替代完整实际安装证据；未覆盖的平台明确标注未验证。

## 5. 失败与回退

- **发布前失败**：不变更线上 manifest，修复后重新验证。
- **Release 已创建、后续匿名下载/哈希校验失败**：该 tag 可能已经存在，但没有可部署 manifest；不得当成发布成功，不得覆盖 asset 或盲目重复发布。先确认失败原因和已发布字节，保留原线上版本，再决定恢复验证或发布新版本。
- **部署后安装失败**：记录失败阶段、目标 SHA 和公网 manifest；保留用户原安装与配置，不删除数据库、绑定或凭据来“重试”。
- **需要回退**：恢复上一套匹配的 IM 构建、前端与已验证 manifest；双节点若也升级，按部署 skill 回退对应运行版本并验证。若此前没有 installer manifest，则恢复原来的未发布状态，不伪造一个旧 manifest。
- 同一 tag/asset 不覆盖，不用 `latest` URL 代替固定版本，不把 candidate 当紧急 fallback。

## 交付报告

部署 Agent 的最终报告应提供：实际部署 SHA、发布 run 和 Release 链接、manifest 版本/哈希与生产绝对落点、IM/双节点运行版本、公网三个安装接口结果、真实首次安装与助手回复证据、重跑安装结果、未验证平台及回退备份位置。敏感信息不进入报告或仓库。

只有以上发布、部署和真实安装验收都完成，才能报告“用户安装入口已上线可用”。若仅完成部分，明确已完成项与剩余阻塞。
