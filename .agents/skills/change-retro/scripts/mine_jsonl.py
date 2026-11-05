#!/usr/bin/env python3
"""mine_jsonl.py — Claude Code session/subagent jsonl 取证挖掘工具（change-retro 用）.

为什么需要它：复盘一个 unit 时，"它什么时候在干什么、worker 空转多久、worker 和主 agent
有没有对话、派发包怎么写的、worker 报 DONE 时真做了什么" 这些都只在 jsonl 里。每次手写
提取脚本是重复劳动，这里固化成子命令。

数据布局（Claude Code）：
  主 session: ~/.claude/projects/<proj-slug>/<uuid>.jsonl
  subagent : ~/.claude/projects/<proj-slug>/<uuid>/subagents/agent-*.jsonl
             角色名在同名 .meta.json 的 "agentType" 字段

用法：
  python mine_jsonl.py sessions  <projects_dir> <unit_id>      # 哪些主 session 涉及该 unit
  python mine_jsonl.py humans    <session.jsonl> [more...]     # 人类真输入时间线(滤掉噪声)
  python mine_jsonl.py subagents <session_dir>                 # subagent 角色/时长/轮数表
  python mine_jsonl.py churn     <session.jsonl> [min_gap_min] # 无人干扰的自主空转段
  python mine_jsonl.py dispatches <session.jsonl>              # orchestrator 派发 worker 的 prompt
  python mine_jsonl.py dialogue  <session_dir>                 # 每个 subagent 与主 agent 的往返次数

注：<session_dir> 是去掉 .jsonl 的同名目录（subagents/ 在其下）。
"""

import json, sys, os, glob, re
from datetime import datetime


def _parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def _iter(jf):
    with open(jf, errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


_NOISE = (
    "<teammate-message",
    "<task-notification",
    "idle_notification",
    "<local-command",
    "This session is being continued",
    "Base directory for this skill",
    "Your tool call was malformed",
    "[Request interrupted",
)


def _human_text(o):
    """从 user 事件里取人类真输入文本；过滤工具结果/teammate/系统噪声。返回 None 表示非人类输入。"""
    if o.get("type") != "user":
        return None
    c = o.get("message", {}).get("content")
    if isinstance(c, str):
        t = c
    elif isinstance(c, list):
        parts = [
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        t = "\n".join(parts)
    else:
        return None
    t = " ".join(t.split()).strip()
    if not t:
        return None
    if any(b in t[:60] for b in _NOISE) or "system-reminder" in t[:40]:
        return None
    # 保留 slash command 的参数（用户意图），折叠成简短形式
    if "<command-name>" in t:
        m = re.search(r"<command-args>(.*?)</command-args>", t)
        cn = re.search(r"<command-name>(.*?)</command-name>", t)
        return f"[CMD {cn.group(1) if cn else ''}] {(m.group(1) if m else '').strip()}".strip()
    return t


def cmd_sessions(projects_dir, unit_id):
    rows = []
    for jf in glob.glob(os.path.join(projects_dir, "*.jsonl")):
        n = 0
        with open(jf, errors="replace") as fh:
            for line in fh:
                n += line.count(unit_id)
        if n:
            tss = [(_parse(o.get("timestamp"))) for o in _iter(jf)]
            tss = [t for t in tss if t]
            first = min(tss) if tss else None
            last = max(tss) if tss else None
            rows.append((n, os.path.basename(jf)[:8], str(first)[:16], str(last)[:16]))
    rows.sort(reverse=True)
    print(f"{'hits':>5}  {'session':8}  {'first':16}  {'last':16}")
    for n, sid, f, l in rows:
        print(f"{n:5}  {sid:8}  {f:16}  {l:16}")


def cmd_humans(files):
    rows = []
    for jf in files:
        sid = os.path.basename(jf).replace(".jsonl", "")[:8]
        for o in _iter(jf):
            t = _human_text(o)
            if t:
                rows.append((o.get("timestamp", ""), sid, t))
    rows.sort()
    for ts, sid, t in rows:
        if len(t) > 300:
            t = t[:300] + "…"
        print(f"[{ts[:16]}] ({sid}) {t}")


def _subagent_files(session_dir):
    return glob.glob(os.path.join(session_dir, "subagents", "*.jsonl"))


def _role(jf):
    mf = jf.replace(".jsonl", ".meta.json")
    if os.path.exists(mf):
        try:
            return json.load(open(mf)).get("agentType", "?")
        except Exception:
            pass
    return "?"


def cmd_subagents(session_dir):
    # 同一 agent 可能有多个 fork 文件；按角色取峰值轮数 + 合并时间跨度
    agg = {}
    for jf in _subagent_files(session_dir):
        role = _role(jf)
        first = last = None
        nass = 0
        for o in _iter(jf):
            ts = _parse(o.get("timestamp"))
            if ts:
                if first is None or ts < first:
                    first = ts
                if last is None or ts > last:
                    last = ts
            if o.get("type") == "assistant":
                nass += 1
        a = agg.setdefault(role, [first, last, 0, 0])
        a[2] = max(a[2], nass)
        a[3] += 1
        if first and (a[0] is None or first < a[0]):
            a[0] = first
        if last and (a[1] is None or last > a[1]):
            a[1] = last
    rows = []
    for role, (f, l, peak, nf) in agg.items():
        span = (l - f).total_seconds() / 60 if f and l else 0
        rows.append((f, role, peak, span, nf))
    rows.sort(key=lambda r: r[0] or datetime.max.replace(tzinfo=None))
    print(f"{'start':16}  {'role':22}  {'peakAsst':>8}  {'span_min':>8}  {'forks':>5}")
    print(
        "# peakAsst=单实例assistant轮数峰值(失控信号,正常milestone~100-300); forks=该角色transcript文件数"
    )
    for f, role, peak, span, nf in rows:
        print(f"{str(f)[:16]:16}  {role[:22]:22}  {peak:8}  {span:8.0f}  {nf:5}")


def cmd_churn(jf, min_gap=40.0):
    min_gap = float(min_gap)
    # 真人输入时间点
    msgs = []
    for o in _iter(jf):
        t = _human_text(o)
        if t:
            ts = _parse(o.get("timestamp"))
            if ts:
                msgs.append((ts, t[:50]))
    msgs.sort()
    # 活动量用 assistant 轮(主 session + subagents)度量。
    # 注意：不用"末次活动时间戳算闲置"——subagent transcript 常带 resume/idle 的尾部晚时间戳，
    # 会把过夜闲置误判成连续 churn。assistant 轮计数对此免疫：闲置时段不产 assistant 轮。
    sd = jf[:-6] if jf.endswith(".jsonl") else jf
    acts = []
    for o in _iter(jf):
        if o.get("type") == "assistant":
            ts = _parse(o.get("timestamp"))
            if ts:
                acts.append(ts)
    for sjf in _subagent_files(sd):
        for o in _iter(sjf):
            if o.get("type") == "assistant":
                ts = _parse(o.get("timestamp"))
                if ts:
                    acts.append(ts)
    acts.sort()
    print(
        f"# 相邻真人输入间隔 > {min_gap:.0f}min 的段。活动量=窗口内 assistant 轮数(主+子)："
    )
    print(
        "#   高=真在磨(自主空转,问题); 接近0=用户离开/闲置(不算)。具体磨在哪段→去读原文。"
    )
    for i in range(1, len(msgs)):
        gap = (msgs[i][0] - msgs[i - 1][0]).total_seconds() / 60
        if gap <= min_gap:
            continue
        s, e = msgs[i - 1][0], msgs[i][0]
        nturns = sum(1 for t in acts if s <= t <= e)
        last = max((t for t in acts if s <= t <= e), default=s)
        print(
            f"  {str(s)[5:16]} → {str(e)[5:16]} | 间隔{gap:6.0f}m({gap / 60:4.1f}h) | 活动量={nturns:4d}轮 末活动{str(last)[5:16]} | 之后: {msgs[i][1]}"
        )


def cmd_dispatches(jf):
    n = 0
    for o in _iter(jf):
        if o.get("type") != "assistant":
            continue
        c = o.get("message", {}).get("content")
        if not isinstance(c, list):
            continue
        for b in c:
            if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                inp = b.get("input", {})
                p = inp.get("prompt", "")
                if "impl-worker" in p or "milestone" in p.lower() or "skill:" in p:
                    n += 1
                    lab = inp.get("description") or inp.get("subagent_type") or ""
                    ts = o.get("timestamp", "")[:16]
                    print(f"\n===== [{ts}] 派发#{n} {lab} =====")
                    print(p[:1400])


def cmd_dialogue(session_dir):
    agg = {}
    for jf in _subagent_files(session_dir):
        role = _role(jf)
        out = inc = 0
        for o in _iter(jf):
            t = o.get("type")
            c = o.get("message", {}).get("content")
            if t == "assistant" and isinstance(c, list):
                for b in c:
                    if b.get("type") == "tool_use" and b.get("name") == "SendMessage":
                        out += 1
            elif t == "user":
                if isinstance(c, str) and c.strip():
                    inc += 1
                elif isinstance(c, list):
                    for b in c:
                        if (
                            isinstance(b, dict)
                            and b.get("type") == "text"
                            and len(b.get("text", "").strip()) > 20
                        ):
                            inc += 1
        a = agg.setdefault(role, [0, 0])
        a[0] = max(a[0], out)
        a[1] = max(a[1], inc)
    print(f"{'role':22}  {'→lead(SendMessage)':>18}  {'←lead(incoming)':>16}")
    print("# ≈2(开工信+DONE) = 近一次性,中途无问诊; 数值高 = 多轮对话(协作形态)")
    for role, (out, inc) in sorted(agg.items()):
        print(f"{role[:22]:22}  {out:18}  {inc:16}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "sessions":
        cmd_sessions(args[0], args[1])
    elif cmd == "humans":
        cmd_humans(args)
    elif cmd == "subagents":
        cmd_subagents(args[0])
    elif cmd == "churn":
        cmd_churn(args[0], args[1] if len(args) > 1 else 40.0)
    elif cmd == "dispatches":
        cmd_dispatches(args[0])
    elif cmd == "dialogue":
        cmd_dialogue(args[0])
    else:
        print(f"unknown command: {cmd}\n{__doc__}")
        sys.exit(1)


if __name__ == "__main__":
    main()
