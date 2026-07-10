// Shared UI components for IM Prototype
// Exports to window for cross-file access

function Avatar({ initials, color, size = 32, status }) {
  return (
    <div style={{ position: "relative", display: "inline-flex", flexShrink: 0 }}>
      <div style={{
        width: size, height: size, borderRadius: "50%",
        background: color || "oklch(0.52 0.14 180)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: size * 0.35, fontWeight: 700, color: "#fff", letterSpacing: "-0.02em",
        flexShrink: 0
      }}>{initials}</div>
      {status && (
        <div style={{
          position: "absolute", bottom: 1, right: 1,
          width: size * 0.28, height: size * 0.28, borderRadius: "50%",
          background: status === "online" ? "oklch(0.55 0.18 145)" : status === "running" ? "oklch(0.70 0.18 60)" : "#94a3b8",
          border: "2px solid var(--sidebar-bg, #fff)"
        }} />
      )}
    </div>
  );
}

function Badge({ children, variant = "neutral" }) {
  const styles = {
    neutral: { background: "oklch(0.93 0.005 240)", color: "oklch(0.40 0.01 240)" },
    agent:   { background: "oklch(0.93 0.06 180)", color: "oklch(0.35 0.12 180)" },
    group:   { background: "oklch(0.93 0.05 270)", color: "oklch(0.38 0.12 270)" },
    network: { background: "oklch(0.93 0.05 30)", color: "oklch(0.38 0.12 30)" },
    online:  { background: "oklch(0.93 0.10 145)", color: "oklch(0.35 0.14 145)" },
    offline: { background: "oklch(0.93 0.005 240)", color: "oklch(0.50 0.01 240)" },
    running: { background: "oklch(0.95 0.10 60)", color: "oklch(0.40 0.15 60)" },
    unread:  { background: "oklch(0.52 0.14 180)", color: "#fff" },
  };
  const s = styles[variant] || styles.neutral;
  return (
    <span style={{
      ...s, borderRadius: 99, padding: "2px 8px",
      fontSize: 11, fontWeight: 700, letterSpacing: "0.04em",
      display: "inline-flex", alignItems: "center", gap: 4, whiteSpace: "nowrap"
    }}>{children}</span>
  );
}

function KindBadge({ kind_label }) {
  const variant = kind_label === "Agent" ? "agent" : kind_label === "Group" ? "group" : kind_label === "Agent↔Agent" ? "network" : "neutral";
  return <Badge variant={variant}>{t(kind_label)}</Badge>;
}

// ─── Tool Call Expander ────────────────────────────────────────────────────────

function ToolCallRow({ tc, defaultOpen = false }) {
  const [open, setOpen] = React.useState(defaultOpen);
  const statusColor = tc.status === "completed" ? "oklch(0.55 0.18 145)" : tc.status === "running" ? "oklch(0.70 0.18 60)" : "oklch(0.55 0.15 25)";
  const duration = tc.duration_ms != null ? IM_UTILS.formatDuration(tc.duration_ms) : "…";

  return (
    <div style={{ borderBottom: "1px solid oklch(0.25 0.01 240)" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          padding: "7px 14px", background: "none", border: "none",
          cursor: "pointer", textAlign: "left",
          color: "oklch(0.85 0.01 240)", fontFamily: "inherit"
        }}
      >
        <span style={{ fontSize: 10, color: statusColor, flexShrink: 0 }}>
          {tc.status === "running" ? "◌" : tc.status === "completed" ? "●" : "✕"}
        </span>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: "oklch(0.90 0.05 180)", fontWeight: 500 }}>
          {tc.name}
        </span>
        <span style={{ fontSize: 11, color: "oklch(0.55 0.01 240)", marginLeft: "auto" }}>{duration}</span>
        <span style={{ fontSize: 10, color: "oklch(0.50 0.01 240)", marginLeft: 6 }}>{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div style={{ padding: "0 14px 10px 14px", display: "grid", gap: 6 }}>
          {tc.input != null && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "oklch(0.50 0.01 240)", marginBottom: 4 }}>{t("INPUT")}</div>
              <pre style={{
                margin: 0, padding: "8px 10px", borderRadius: 6,
                background: "oklch(0.09 0.01 240)", color: "oklch(0.80 0.04 180)",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: 11.5,
                overflowX: "auto", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-all"
              }}>{typeof tc.input === "string" ? tc.input : JSON.stringify(tc.input, null, 2)}</pre>
            </div>
          )}
          {tc.output != null && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "oklch(0.50 0.01 240)", marginBottom: 4 }}>{t("OUTPUT")}</div>
              <pre style={{
                margin: 0, padding: "8px 10px", borderRadius: 6,
                background: "oklch(0.09 0.01 240)", color: "oklch(0.85 0.02 240)",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: 11.5,
                overflowX: "auto", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-all",
                maxHeight: 200, overflow: "auto"
              }}>{typeof tc.output === "string" ? tc.output : JSON.stringify(tc.output, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolCallsExpander({ tool_calls }) {
  const [expanded, setExpanded] = React.useState(false);
  if (!tool_calls || tool_calls.length === 0) return null;
  const total = IM_UTILS.totalDuration(tool_calls);
  const anyRunning = tool_calls.some(tc => tc.status === "running");

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "4px 10px", borderRadius: 99,
          background: expanded ? "oklch(0.18 0.02 240)" : "oklch(0.92 0.008 240)",
          border: `1px solid ${expanded ? "oklch(0.30 0.04 180)" : "oklch(0.86 0.01 240)"}`,
          cursor: "pointer", fontSize: 12, fontWeight: 600,
          color: expanded ? "oklch(0.75 0.10 180)" : "oklch(0.45 0.01 240)",
          transition: "all 0.15s", fontFamily: "inherit"
        }}
      >
        <span style={{ fontSize: 10 }}>{expanded ? "▾" : "▸"}</span>
        <span>
          {anyRunning
            ? <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: "oklch(0.70 0.18 60)", animation: "im-pulse 1.2s infinite" }} />
                {tool_calls.length} {tool_calls.length > 1 ? t("tool calls") : t("tool call")}{t(" · running")}
              </span>
            : `${tool_calls.length} ${tool_calls.length > 1 ? t("tool calls") : t("tool call")} · ${IM_UTILS.formatDuration(total)}`
          }
        </span>
      </button>

      {expanded && (
        <div style={{
          marginTop: 8, borderRadius: 10, overflow: "hidden",
          background: "oklch(0.13 0.015 240)",
          border: "1px solid oklch(0.22 0.02 240)",
          boxShadow: "0 4px 16px oklch(0.05 0.01 240 / 0.5)"
        }}>
          {tool_calls.map((tc, i) => (
            <ToolCallRow key={tc.id} tc={tc} defaultOpen={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Markdown Content ─────────────────────────────────────────────────────────

function MarkdownContent({ content }) {
  const html = React.useMemo(() => {
    if (!window.marked) return content;
    try {
      return window.marked.parse(content, { breaks: true, gfm: true });
    } catch {
      return content;
    }
  }, [content]);

  if (!window.marked) {
    return <p style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{content}</p>;
  }
  return <div className="im-md" dangerouslySetInnerHTML={{ __html: html }} />;
}

// ─── Token Usage Chip ─────────────────────────────────────────────────────────

function TokenChip({ usage }) {
  const [open, setOpen] = React.useState(false);
  if (!usage) return null;
  const pct = Math.round((usage.context_used / usage.context_window) * 100);
  const warn = pct >= 70;
  const critical = pct >= 90;
  const barColor = critical ? "oklch(0.55 0.15 25)" : warn ? "oklch(0.65 0.18 60)" : "oklch(0.52 0.14 180)";
  function fmtK(n) { return n >= 1000 ? `${(n/1000).toFixed(1)}k` : String(n); }

  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "3px 9px", borderRadius: 99,
        background: open ? "oklch(0.20 0.015 240)" : "oklch(0.84 0.010 240)",
        border: `1px solid ${open ? "oklch(0.35 0.05 240)" : "oklch(0.76 0.012 240)"}`,
        cursor: "pointer", fontSize: 11.5, fontWeight: 600,
        color: open ? "oklch(0.80 0.04 240)" : "oklch(0.38 0.01 240)",
        fontFamily: "'IBM Plex Mono', monospace", transition: "all 0.14s"
      }}>
        <span style={{ opacity: 0.7, fontSize: 10 }}>{open ? "▾" : "▸"}</span>
        <span>{fmtK(usage.output)} {t("tok")}</span>
        <span style={{ opacity: 0.4, fontSize: 10, margin: "0 1px" }}>·</span>
        <span style={{ color: critical ? "oklch(0.55 0.15 25)" : warn ? "oklch(0.55 0.16 60)" : "inherit" }}>
          {t("ctx")} {pct}%
        </span>
      </button>

      {open && (
        <div style={{
          marginTop: 4, padding: "10px 12px", borderRadius: 9,
          background: "oklch(0.14 0.014 240)",
          border: "1px solid oklch(0.22 0.015 240)",
          fontFamily: "'IBM Plex Mono', monospace", fontSize: 11.5,
          display: "grid", gap: 8, minWidth: 220
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "oklch(0.75 0.02 240)" }}>
            <span style={{ color: "oklch(0.50 0.01 240)" }}>{t("output tokens")}</span>
            <span>{usage.output.toLocaleString()}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", color: "oklch(0.75 0.02 240)" }}>
            <span style={{ color: "oklch(0.50 0.01 240)" }}>{t("context used")}</span>
            <span>{usage.context_used.toLocaleString()} / {(usage.context_window/1000).toFixed(0)}k</span>
          </div>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 10.5, color: "oklch(0.50 0.01 240)" }}>
              <span>{t("context window")}</span>
              <span style={{ color: critical ? "oklch(0.70 0.15 25)" : warn ? "oklch(0.75 0.18 60)" : "oklch(0.65 0.10 180)", fontWeight: 700 }}>{pct}%{t(" used")}</span>
            </div>
            <div style={{ height: 5, borderRadius: 99, background: "oklch(0.22 0.01 240)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${pct}%`, borderRadius: 99, background: barColor, transition: "width 0.3s" }} />
            </div>
          </div>
          {warn && (
            <p style={{ margin: 0, fontSize: 10.5, color: critical ? "oklch(0.70 0.15 25)" : "oklch(0.70 0.16 60)", fontFamily: "inherit" }}>
              {critical ? t("⚠ Context nearly full — consider /compact") : t("↑ Context above 70% — watch for degradation")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Message Bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg, isGroupChat, agents }) {
  const isUser = msg.sender === "user";
  const isSystem = msg.sender === "system";
  const agent = msg.agent_id ? IM_UTILS.agentById(msg.agent_id) : null;

  if (isSystem) {
    return (
      <div style={{ textAlign: "center", padding: "4px 0 8px", color: "oklch(0.55 0.01 240)", fontSize: 12 }}>
        {msg.content}
      </div>
    );
  }

  return (
    <div style={{
      display: "flex", gap: 10, marginBottom: 16,
      flexDirection: isUser ? "row-reverse" : "row",
      alignItems: "flex-start"
    }}>
      {!isUser && agent && <Avatar initials={agent.initials} color={agent.color} size={30} />}
      {!isUser && !agent && (
        <div style={{ width: 30, height: 30, borderRadius: "50%", background: "oklch(0.80 0.01 240)", flexShrink: 0 }} />
      )}

      <div style={{ maxWidth: "72%", display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
        {!isUser && (isGroupChat || true) && agent && (
          <span style={{ fontSize: 11, fontWeight: 700, color: agent.color, marginBottom: 3, paddingLeft: 2 }}>
            {agent.name}
          </span>
        )}

        <div style={{
          padding: "9px 13px", borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          background: isUser ? "oklch(0.52 0.14 180)" : "oklch(0.91 0.007 240)",
          color: isUser ? "#fff" : "oklch(0.14 0.01 240)",
          fontSize: 13.5, lineHeight: 1.6,
          boxShadow: "0 1px 3px oklch(0.05 0.01 240 / 0.08)"
        }}>
          {isUser
            ? <p style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</p>
            : <MarkdownContent content={msg.content} />}

          {!isUser && <ToolCallsExpander tool_calls={msg.tool_calls} />}
          {!isUser && msg.status === "completed" && <TokenChip usage={msg.token_usage} />}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, paddingLeft: isUser ? 0 : 2, paddingRight: isUser ? 2 : 0 }}>
          <span style={{ fontSize: 11, color: "oklch(0.65 0.01 240)" }}>{IM_UTILS.formatTime(msg.at)}</span>
          {msg.status === "running" && (
            <span style={{ fontSize: 11, color: "oklch(0.65 0.15 60)", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "oklch(0.70 0.18 60)", animation: "im-pulse 1.2s infinite" }} />
              {t("working")}
            </span>
          )}
          {msg.status === "failed" && <span style={{ fontSize: 11, color: "oklch(0.55 0.15 25)" }}>{t("failed")}</span>}
        </div>
      </div>
    </div>
  );
}

// ─── Conversation List Item ────────────────────────────────────────────────────

function ConvItem({ conv, active, onClick }) {
  const agent = conv.agent_id ? IM_UTILS.agentById(conv.agent_id) : null;
  const initials = agent ? agent.initials : conv.title.slice(0, 2).toUpperCase();
  const color = agent ? agent.color :
    conv.kind === "group" ? "oklch(0.52 0.14 270)" : "oklch(0.52 0.14 30)";
  const statusDot = agent ? (agent.status === "online" ? "online" : "offline") : null;

  return (
    <button onClick={() => onClick(conv.id)} style={{
      width: "100%", display: "flex", alignItems: "center", gap: 11, padding: "10px 12px",
      borderRadius: 10, border: "none", cursor: "pointer", textAlign: "left",
      background: active ? "oklch(0.31 0.015 240)" : "transparent",
      transition: "background 0.1s", marginBottom: 2,
      outline: active ? "1px solid oklch(0.40 0.08 180)" : "none"
    }}
    onMouseEnter={e => { if (!active) e.currentTarget.style.background = "oklch(0.28 0.012 240)"; }}
    onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
    >
      <Avatar initials={initials} color={color} size={36} status={statusDot} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: active ? "#fff" : "oklch(0.88 0.01 240)", truncate: true, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 130 }}>
            {conv.title}
          </span>
          <span style={{ fontSize: 11, color: "oklch(0.50 0.01 240)", flexShrink: 0 }}>
            {IM_UTILS.formatDate(conv.last_at)}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 4, marginTop: 1 }}>
          <span style={{ fontSize: 12, color: "oklch(0.55 0.01 240)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 150 }}>
            {conv.last_preview}
          </span>
          {conv.unread > 0 && (
            <span style={{
              background: "oklch(0.52 0.14 180)", color: "#fff", borderRadius: 99,
              padding: "1px 7px", fontSize: 11, fontWeight: 700, flexShrink: 0
            }}>{conv.unread}</span>
          )}
        </div>
      </div>
    </button>
  );
}

// ─── Empty State ───────────────────────────────────────────────────────────────

function EmptyPane({ icon, title, sub }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, padding: 40, color: "oklch(0.65 0.01 240)" }}>
      <div style={{ fontSize: 32, opacity: 0.4 }}>{icon}</div>
      <p style={{ fontSize: 14, fontWeight: 600, color: "oklch(0.45 0.01 240)", margin: 0 }}>{title}</p>
      {sub && <p style={{ fontSize: 13, margin: 0, textAlign: "center", maxWidth: 260, lineHeight: 1.5 }}>{sub}</p>}
    </div>
  );
}

// ─── Form Field ───────────────────────────────────────────────────────────────

function Field({ label, id, children, help, error }) {
  return (
    <div style={{ display: "grid", gap: 5 }}>
      <label htmlFor={id} style={{ fontSize: 13, fontWeight: 600, color: "oklch(0.30 0.01 240)" }}>{label}</label>
      {children}
      {help && <p style={{ fontSize: 12, color: "oklch(0.55 0.01 240)", margin: 0, lineHeight: 1.5 }}>{help}</p>}
      {error && <p style={{ fontSize: 12, color: "oklch(0.50 0.15 25)", fontWeight: 600, margin: 0 }}>{error}</p>}
    </div>
  );
}

function Input({ id, value, onChange, disabled, placeholder, mono }) {
  return (
    <input id={id} value={value} onChange={onChange} disabled={disabled} placeholder={placeholder}
      style={{
        padding: "8px 11px", borderRadius: 8,
        border: "1px solid oklch(0.88 0.005 240)",
        background: disabled ? "oklch(0.96 0.003 240)" : "#fff",
        color: disabled ? "oklch(0.55 0.01 240)" : "oklch(0.14 0.01 240)",
        fontSize: 13, fontFamily: mono ? "'IBM Plex Mono', monospace" : "inherit",
        outline: "none", width: "100%", boxSizing: "border-box",
        transition: "border 0.15s"
      }}
      onFocus={e => e.target.style.borderColor = "oklch(0.52 0.14 180)"}
      onBlur={e => e.target.style.borderColor = "oklch(0.88 0.005 240)"}
    />
  );
}

function Textarea({ id, value, onChange, placeholder, rows = 5, mono }) {
  return (
    <textarea id={id} value={value} onChange={onChange} placeholder={placeholder} rows={rows}
      style={{
        padding: "8px 11px", borderRadius: 8,
        border: "1px solid oklch(0.88 0.005 240)",
        background: "#fff", color: "oklch(0.14 0.01 240)",
        fontSize: mono ? 12.5 : 13,
        fontFamily: mono ? "'IBM Plex Mono', monospace" : "inherit",
        outline: "none", width: "100%", boxSizing: "border-box", resize: "vertical",
        lineHeight: 1.6, transition: "border 0.15s"
      }}
      onFocus={e => e.target.style.borderColor = "oklch(0.52 0.14 180)"}
      onBlur={e => e.target.style.borderColor = "oklch(0.88 0.005 240)"}
    />
  );
}

function Select({ id, value, onChange, options, disabled }) {
  return (
    <select id={id} value={value} onChange={onChange} disabled={disabled}
      style={{
        padding: "8px 11px", borderRadius: 8,
        border: "1px solid oklch(0.88 0.005 240)",
        background: "#fff", color: "oklch(0.14 0.01 240)",
        fontSize: 13, fontFamily: "inherit",
        outline: "none", cursor: "pointer", transition: "border 0.15s",
        appearance: "auto"
      }}
      onFocus={e => e.target.style.borderColor = "oklch(0.52 0.14 180)"}
      onBlur={e => e.target.style.borderColor = "oklch(0.88 0.005 240)"}
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function Btn({ children, onClick, variant = "primary", disabled, small, type = "button" }) {
  const base = {
    padding: small ? "5px 12px" : "8px 16px",
    borderRadius: 8, border: "none", cursor: disabled ? "not-allowed" : "pointer",
    fontSize: small ? 12 : 13, fontWeight: 600, fontFamily: "inherit",
    transition: "all 0.15s", display: "inline-flex", alignItems: "center", gap: 6,
    opacity: disabled ? 0.5 : 1
  };
  const variants = {
    primary: { background: "oklch(0.52 0.14 180)", color: "#fff" },
    secondary: { background: "oklch(0.94 0.005 240)", color: "oklch(0.30 0.01 240)", border: "1px solid oklch(0.87 0.005 240)" },
    danger: { background: "oklch(0.55 0.15 25)", color: "#fff" },
    ghost: { background: "transparent", color: "oklch(0.45 0.01 240)", border: "1px solid oklch(0.87 0.005 240)" }
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      style={{ ...base, ...variants[variant] }}
      onMouseEnter={e => { if (!disabled) e.currentTarget.style.filter = "brightness(1.08)"; }}
      onMouseLeave={e => { e.currentTarget.style.filter = ""; }}
    >{children}</button>
  );
}

function SectionCard({ title, sub, children }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 12, border: "1px solid oklch(0.91 0.005 240)",
      padding: "20px 22px", display: "grid", gap: 16
    }}>
      <div>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "oklch(0.20 0.01 240)" }}>{title}</h3>
        {sub && <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "oklch(0.55 0.01 240)", lineHeight: 1.5 }}>{sub}</p>}
      </div>
      {children}
    </div>
  );
}

function MultiSelect({ label, all, selected, onChange }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {all.map(item => {
        const on = selected.includes(item);
        return (
          <button key={item} type="button" onClick={() => onChange(on ? selected.filter(s => s !== item) : [...selected, item])}
            style={{
              padding: "4px 11px", borderRadius: 99, fontSize: 12, fontWeight: 600, cursor: "pointer",
              fontFamily: "'IBM Plex Mono', monospace",
              background: on ? "oklch(0.93 0.08 180)" : "oklch(0.96 0.005 240)",
              color: on ? "oklch(0.35 0.14 180)" : "oklch(0.50 0.01 240)",
              border: on ? "1px solid oklch(0.75 0.12 180)" : "1px solid oklch(0.88 0.005 240)",
              transition: "all 0.12s"
            }}
          >{item}</button>
        );
      })}
    </div>
  );
}

// Export everything to window
Object.assign(window, {
  Avatar, Badge, KindBadge,
  MarkdownContent, ToolCallRow, ToolCallsExpander, TokenChip,
  MessageBubble, ConvItem, EmptyPane,
  Field, Input, Textarea, Select, Btn, SectionCard, MultiSelect
});
