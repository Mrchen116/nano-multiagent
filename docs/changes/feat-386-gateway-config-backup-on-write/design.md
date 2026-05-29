# feat-386: Gateway 配置写前自动备份 — 技术方案

> 对齐: spec.md v1
> Unit branch: `unit/feat-386-gateway-config-backup-on-write` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `src/personal_assistant/config/local_store.py:295` `save_local_config(config, config_path)` —— **唯一的配置写盘收口**。当前实现把整个 `LocalConfig` 序列化后 `dest.write_text(...)` 全文重写（:410-412），无备份、无原子写。本 unit 的备份逻辑就内置在这里。
- `src/personal_assistant/config/local_store.py:289` `default_local_config_path()` —— 返回 `~/.nano-assistant/config.yaml`（expanduser + resolve）。用作"是不是主配置"的判定基准。
- `src/personal_assistant/main.py:447` `_persist_agent_config` —— 写盘路径 1：前端新建/编辑 agent 触发，写 `cfg.source_path`。
- `src/personal_assistant/main.py:1632` `_make_token_getter._persist` —— 写盘路径 2：IM token 轮换（refresh / login，每次重连刷新）触发，同样写 `cfg.source_path`。
- `tests/unit/personal_assistant/test_local_store.py` —— 现有单测，`tmp_path` + monkeypatch home 风格，本 unit 的备份单测落在此文件。

### 既有约束

- 两条写盘路径都调 `save_local_config(cfg, cfg.source_path)`，所以**备份逻辑只能放进 `save_local_config` 内部**，放调用方会漏掉另一条且重复。
- worktree e2e 用 `--config <wt>/.gateway-config.yaml` 启动，其 `source_path` ≠ 默认主配置路径——用"`dest == default_local_config_path()`"判定即可天然排除一次性副本，无需 Gateway 感知 worktree。
- `save_local_config` 是同步函数，被同步（`_persist_agent_config`）和 async（`_persist`）两侧调用；备份实现必须保持同步、纯文件 IO，不引入 await。
- 单测走 `tmp_path`：判定主配置不能写死真实 `~/.nano-assistant/`，要能在测试里把"默认路径"指到 tmp（monkeypatch `default_local_config_path` 或注入）。

### 可复用能力

- **复用** `default_local_config_path()` 做主配置判定——已存在，不新造。
- **复用** `test_local_store.py` 的 `tmp_path` 单测骨架。
- **不复用 / 新增**：备份本身（拷贝旧文件 + 时间戳命名 + 留存裁剪）项目里无既有实现，本 unit 新增一个内部 helper（如 `_backup_existing_config(dest)`），仅 `save_local_config` 调用。

### 相关历史

- `bugfix-362-im-ghost-agent-reconcile`：治理"IM 有 agent 但 Gateway config 没有"的幽灵 agent。本 unit 与它互补——362 修 IM 侧对账（症状治理），386 防 config 被静默覆盖丢 agent（源头之一的后路保护）。
- `feat-379` / `refactor-382`：近期扩过 `save_local_config` 序列化字段（features / custom_prompt / llm 段）。本 unit **不动序列化逻辑**，只在写盘前插入备份步骤，与这些无冲突。

## 架构总览

`save_local_config` 在写盘前插入一个"主配置专属"的备份步骤，其余序列化逻辑完全不变。

```
Before:
  save_local_config(cfg, path)
    └─ serialize → dest.write_text(...)        # 全文重写，无后路

After:
  save_local_config(cfg, path)
    ├─ serialize → new_text
    ├─ IF dest == default_local_config_path() AND dest 已存在:
    │     ├─ 若 new_text 与 dest 现有内容逐字节相同 → 跳过备份（no-op churn 防护）
    │     └─ 否则 copy dest → ~/.nano-assistant/backups/config.<UTC时间戳>.yaml.bak
    │            ├─ 备份失败(磁盘满/无权限) → raise，dest 原文不动
    │            └─ 备份成功 → 裁剪 backups/ 只留最近 30 份
    └─ dest.write_text(new_text)               # 原有写盘
```

worktree 一次性副本（`dest != 默认主配置`）走 `IF` 的 else，直接写盘，无备份——行为与今天一致。

## 关键决策

### 决策 1: 备份逻辑位置

- **选择**: 内置进 `save_local_config`，新增私有 helper `_backup_existing_config(dest)`，仅由它调用。
- **理由**: `save_local_config` 是唯一写盘收口，两条调用路径（agent 增改 / token 轮换）都经它，单点覆盖、零调用方改动。
- **拒绝**: 在 `_persist_agent_config` / `_persist` 各自加备份——会漏路径、重复逻辑、且把文件 IO 泄漏进 main.py。
- **风险**: 无显著风险；helper 纯文件 IO，保持同步。

### 决策 2: 主配置判定

- **选择**: 仅当 `Path(config_path).expanduser().resolve() == default_local_config_path()` 时备份。
- **理由**: 主配置是用户长期维护、丢了要手工重建的那份；worktree 副本路径不同，天然排除（spec Q2）。复用既有 `default_local_config_path()`，无新概念。
- **拒绝**: 按"是否在 `.worktrees/` 下"判断——需 Gateway 感知 worktree、脆弱。按"是否显式传了 `--config`"判断——`source_path` 已归一，拿不到该信号。
- **风险**: 单测里默认路径指向真实 home。对策：备份目标路径从 `default_local_config_path()` 的父目录派生，测试通过 monkeypatch 该函数把"默认主配置"指到 `tmp_path`。

### 决策 3: 备份位置 / 命名 / 留存

- **选择**: 子目录 `~/.nano-assistant/backups/`（= 主配置父目录下的 `backups/`）；文件名 `config.<UTC紧凑时间戳>.yaml.bak`，时间戳含足够精度避免同秒碰撞；保留最近 **30** 份，按文件名（时间戳单调）排序删最旧。新序列化内容与 dest 现有内容逐字节相同时**跳过备份**。
- **理由**: 子目录不污染主配置目录、便于整体管理；30 份给 token 轮换的高频写盘留足回溯窗口（spec Q1：扛连续误写）；逐字节相同跳过可避免 no-op 写盘产生无意义备份。用户已确认 30 + 子目录。
- **拒绝**: 单份 `.bak`（扛不住连续误写，spec Q1 已否）；平铺在主目录（污染、列举裁剪麻烦）。
- **风险**: 同秒多次写盘（token 轮换可能密集）若时间戳精度不足会撞名。对策：时间戳带亚秒精度或撞名时追加序号——留给 worker 实现，单测覆盖"同一时刻两次备份不互相覆盖"。

### 决策 4: 备份与写盘的顺序 / 失败语义

- **选择**: 先 `copy(dest → 备份)` 再 `dest.write_text(new)`。备份失败（磁盘满 / 无权限）→ 直接 raise，**绝不**触碰 dest（原配置保持不变）。dest 不存在（首次写盘）→ 无旧文件可备份，跳过备份、正常写。
- **理由**: 满足 spec Q3 fail-closed——最高风险时刻（磁盘异常）宁可让本次保存失败报错，也不无后路覆盖；首次写盘无后路问题（本就没有可丢的旧版本）。
- **拒绝**: 备份失败仅 warning 照常写——异常态下失去保护，spec Q3 已否。
- **风险**: token 轮换路径（`_persist`）的 save 抛异常会冒泡到 token 刷新流程。但磁盘满时原 `write_text` 本就会失败，行为不退化；备份只是把失败提前并保住旧文件。可接受。

## 接口与数据流

新增私有 helper（签名示意，行级实现留给 worker）：

```
def _backup_existing_config(dest: Path, new_text: str) -> None:
    # 仅当 dest 是默认主配置、已存在、且 new_text 与现有内容不同才备份
    # 备份目标: dest.parent / "backups" / f"config.<ts>.yaml.bak"
    # 备份失败抛异常（不吞）；成功后裁剪 backups/ 至最近 30 份
```

`save_local_config` 数据流（改动后）：

```
save_local_config(config, config_path)
  new_text = yaml.safe_dump(serialize(config))     # 不变
  dest = Path(config_path).expanduser().resolve()
  dest.parent.mkdir(parents=True, exist_ok=True)   # 不变
  _backup_existing_config(dest, new_text)          # 新增；非主配置 / 首次写 → 内部 no-op
  dest.write_text(new_text)                         # 不变
```

对调用方零改动：`_persist_agent_config` 与 `_persist` 的调用签名不变；仅在备份失败时它们会收到异常（spec Q3 期望行为）。

## 风险与回退

- **风险 1 — torn write（非本 unit 修）**: 当前 `write_text` 非原子，进程在写一半挂掉会 truncate 主配置。本 unit **不改**为原子写（spec 非目标），但写前备份让用户能从上一版恢复，缓解后果。若未来要根治，另立 unit 做 tmp+`os.replace` 原子写。
- **风险 2 — token 轮换高频备份**: 频繁写盘 → backups/ churn 快。30 份留存 + "内容相同跳过" 缓解；若实测 churn 过快冲掉有用版本，调大留存数即可（单点常量）。
- **风险 3 — 同秒撞名**: 见决策 3 风险，worker 用亚秒精度 / 撞名追加序号，单测覆盖。
- **回退**: 本 unit 改动局限于 `save_local_config` + 一个私有 helper + 单测。回滚 = revert 该 commit，行为回到"无备份直接写盘"，无数据迁移、无 schema 变更、无遗留状态。

## Runbook for Reviewer

本 unit 改动 Gateway 的配置写盘逻辑，reviewer 验收时需重启 Gateway 走 agent 增改触发写盘。IM 也需在线（agent 创建经 IM 推送到 Gateway）。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM (uvicorn) | `kill "$(cat .im.pid)" 2>/dev/null; rm -f .im.pid` | `IM_JWT_SECRET=<unit专属> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" > .im.log 2>&1 & echo $! > .im.pid` | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$IM_PORT/` = 200 |
| Gateway | `kill "$(cat .gateway.pid)" 2>/dev/null; rm -f .gateway.pid` | `PYTHONPATH=src python -m personal_assistant.main --config "$WT_CFG" --im-service-url "http://127.0.0.1:$IM_PORT" --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 IM 连接成功；新建 agent 后检查 `$WT_CFG` 父目录 `backups/` 出现备份 |

> 推荐直接用 `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh` 一键起停（已封装端口分配 / config 隔离 / auto-bind）。注意：验收"只备份主配置"这一条时，e2e 用的是 worktree 副本 `.gateway-config.yaml`（非默认主配置路径），所以**不会**产生备份——这正是 D2 期望行为；要验"主配置会备份"需在单测层覆盖（把默认路径 monkeypatch 到 tmp）。

## Milestones

单 M1：改动局限于一个文件的一个函数 + 一个私有 helper + 同文件单测，无并行/分阶段/跨模块触发条件（SKILL §4.2 均不满足）。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-386-M1 | backup-on-write | — | A | `src/personal_assistant/config/local_store.py`（`save_local_config` + 新增 `_backup_existing_config`）；`tests/unit/personal_assistant/test_local_store.py` | `[reviewer]` 覆盖 spec 全部 Requirement/Scenario：主配置写盘前产生内容等于旧版的时间戳备份、可恢复；保留最近 30 份且超出删最旧；备份失败则保存失败报错且原文件不变；首次写入与 worktree 副本不产生备份。<br>`[worker]` `pytest tests/unit/personal_assistant/test_local_store.py` 全绿，新增单测覆盖：主配置备份内容一致 / 留存裁剪到 30 / 备份失败 raise 且 dest 不变 / dest 不存在跳过备份 / 非默认路径（worktree 副本）不备份 / 内容相同跳过备份 / 同时刻两次备份不互相覆盖。<br>`[worker]` `pytest -m "not e2e"` 无回归。 |
