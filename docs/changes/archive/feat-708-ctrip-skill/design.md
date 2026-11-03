# feat-708: As-built Design

> 本文在实现后记录实际改动；本次采用用户明确选择的快速开发方式。

## 实现与决定

- Base: `6c072da43887ef8e144c0d1ef40ef3d7a2575fed`。
- 原样复制上游 `ac042255234d1905cc221193aa7f9ab4c23d7d65` 的根 `SKILL.md` 到 `packages/personal-assistant/assets/personal-skills/tripai-skill/`，另附来源记录，不修改上游指令。
- PA 包导出 `personalSkillsRoot`；Node 仅在 canonical 配置含宿主授予的 `personal_agent` 身份时追加这一个 builtin root。不向普通 Global 或 single-thread Agent 追加此目录；非 PA 的 workspace/global 自建 Skill 发现保持。
- `apps/node/src/capabilities.ts` 仅为有 PA 身份的该 builtin Skill 上报 `default_on: true`；其他 Skill 的默认值保持原规则，普通新建 Agent 目录不会带入 PA 专用根。
- 复用已有原生目录发现和 `skill` 加载链路，不新增运行时角色过滤或选择模式。正文仅按需加载；既有 explicit allowlist/denylist 与工具权限继续生效，不把该 Skill 变为固定不可关闭项。
- 安装包构建已复制全部受版本管理的 PA assets，无需新增安装逻辑。
- 凭证仍由原版读取 `TRIPAI_API_KEY` 或 `~/.config/tripai-skill/api_key`，按运行系统用户存放；本次不实现新的 Nano 主人级凭证存储或不同系统用户之间的同步。没有随包密钥，不使用对话截图里的密钥。
- 没有独立迁移；撤销本次资产和默认标记即可回退。原版 API 失败及缺少凭证处理保持原样。

## 验证定位

- `apps/node/tests/capabilities.test.ts`：扩展已有能力投影用例，核对仅 PA 默认开启，非 PA Global、single-thread 及无 Agent 的创建目录均不默认开启，无关 builtin 默认值不变。
- `apps/node/tests/configuration.test.ts`：扩展已有根目录配置覆盖，PA 追加专用根，普通 Agent 不追加。
- 保留 `packages/personal-assistant/tests/builtin-skills.test.ts` 和 `packages/dsh-integration/tests/capabilities.test.ts` 既有覆盖，验证随包安装与显式 Skill 选择、加载链路。
- 上述三文件共 12 项通过；全仓构建及类型检查通过。初次在新 worktree 构建前运行投影测试因缺少编译后的包入口失败，构建后同一测试通过。
- 实际运行时探针、加载后下一次 `llm/stream` 输入捕获与缺失凭证执行结果保存在本机 `/Users/czj/.codex/reports/ctrip-wendao-20261103/`；仅验证确定性接线，不证明 provider wire 序列化，不使用真实模型或调用携程 API。
- 安装包归档包含 `tripai-skill/SKILL.md` 与来源记录；正文与固定上游版本逐字比较。
- 用户交付决定：在明确仅 PA 默认启用后要求“merge 吧”，按该指令收尾，不追加真人试用门禁；未执行真人试用或真实携程查询。未部署，不把自动检查或合并指令当作真实查询成功。

最初 `65e367358` 把该资产放在所有 Agent 共用根。用户随后明确 PA 范围，本轮按上述专用根方案修正；最初对普通两模式可加载的证据只保留为历史，不用于证明修正后的 PA 范围。

修正后全仓构建、类型检查及 Node 配置/能力/随包安装三文件 17 项测试通过。`scope-verify.mjs` 使用实际 `NodeConfiguration.runtime()` 产出的随包根，在各自独立原生执行进程核对：默认 PA 发现且成功加载原文；普通 Global、single-thread 及显式关闭该 Skill 的 PA 均不发现且不能通过 `skill` 加载。证据见同目录 `scope-summary.json` 与 `scope-*.json`。发行包只含 PA 专用位置的同一原版文件；未调用真实模型或携程 API。

## Canonical 影响

最窄 delta 见 `specs/gateway/agent-capabilities.md`，收尾归并至 `docs/specs/gateway/agent-capabilities.md`。
