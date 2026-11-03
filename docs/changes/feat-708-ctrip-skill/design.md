# feat-708: As-built Design

> 本文在实现后记录实际改动；本次采用用户明确选择的快速开发方式。

## 实现与决定

- Base: `6c072da43887ef8e144c0d1ef40ef3d7a2575fed`。
- 原样复制上游 `ac042255234d1905cc221193aa7f9ab4c23d7d65` 的根 `SKILL.md` 到 `packages/personal-assistant/assets/skills/tripai-skill/`，另附来源记录，不修改上游指令。
- `apps/node/src/capabilities.ts` 为该 builtin Skill 上报 `default_on: true`；其他 Skill 的默认值保持原规则。
- 复用已有 `builtinSkillsRoot`、原生目录发现和 `skill` 加载链路。正文仅按需加载；既有 explicit allowlist/denylist 与工具权限继续生效，不把该 Skill 变为固定不可关闭项。
- 安装包构建已复制全部受版本管理的 PA assets，无需新增安装逻辑。
- 凭证仍由原版读取 `TRIPAI_API_KEY` 或 `~/.config/tripai-skill/api_key`，按运行系统用户存放；本次不实现新的 Nano 主人级凭证存储或不同系统用户之间的同步。没有随包密钥，不使用对话截图里的密钥。
- 没有独立迁移；撤销本次资产和默认标记即可回退。原版 API 失败及缺少凭证处理保持原样。

## 验证定位

- `apps/node/tests/capabilities.test.ts`：扩展已有能力投影用例，核对 builtin 携程默认开启及无关 builtin 默认值不变。
- 保留 `packages/personal-assistant/tests/builtin-skills.test.ts` 和 `packages/dsh-integration/tests/capabilities.test.ts` 既有覆盖，验证随包安装与显式 Skill 选择、加载链路。
- 上述三文件共 12 项通过；全仓构建及类型检查通过。初次在新 worktree 构建前运行投影测试因缺少编译后的包入口失败，构建后同一测试通过。
- 实际运行时探针、请求捕获与缺失凭证执行结果保存在本机 `/Users/czj/.codex/reports/ctrip-wendao-20261103/`；仅验证确定性接线，不使用真实模型或调用携程 API。
- 安装包归档包含 `tripai-skill/SKILL.md` 与来源记录；正文与固定上游版本逐字比较。
- 用户实际验收：待确认。未部署，不把自动检查当作真实携程查询成功。

## Canonical 影响

最窄 delta 见 `specs/gateway/agent-capabilities.md`，归并目标为 `docs/specs/gateway/agent-capabilities.md`；待用户实际验收及快速收尾完成后归并，当前契约尚未改写。
