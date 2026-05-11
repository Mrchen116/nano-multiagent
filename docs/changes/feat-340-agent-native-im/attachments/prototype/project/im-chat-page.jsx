// Chat page — desktop two-column + mobile stacked navigation

// ─── New Group Bottom Sheet / Modal ──────────────────────────────────────────
function NewGroupModal({ onClose, onCreate, isMobile }) {
  const allAgents = IM_DATA.agents;
  const [selected, setSelected] = React.useState([]);
  const [name, setName] = React.useState("");

  function toggle(id) {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  }
  function handleCreate() {
    if (selected.length < 1) return;
    const participants = selected.map(id => IM_DATA.agents.find(a => a.id === id));
    onCreate({ selected, name: name.trim() || participants.map(a => a.name).join(", "), participants });
  }

  const inner = (
    <>
      <div style={{ padding: isMobile ? "0 16px 12px" : "18px 20px 14px", borderBottom: "1px solid oklch(0.87 0.006 240)", background: "#fff" }}>
        {isMobile && (
          <div style={{ display: "flex", justifyContent: "center", padding: "10px 0 14px" }}>
            <div style={{ width: 36, height: 4, borderRadius: 2, background: "oklch(0.80 0.01 240)" }} />
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.02em" }}>{t("New group chat")}</h2>
            <p style={{ margin: "3px 0 0", fontSize: 12.5, color: "oklch(0.55 0.01 240)" }}>{t("Select agents, then give the group a name.")}</p>
          </div>
          {!isMobile && <Btn variant="ghost" onClick={onClose}>✕</Btn>}
        </div>
      </div>

      <div style={{ padding: "14px 16px", display: "grid", gap: 14, overflowY: "auto", flex: 1 }}>
        <div>
          <p style={{ fontSize: 11, fontWeight: 700, color: "oklch(0.45 0.01 240)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>{t("Agents")}</p>
          <div style={{ display: "grid", gap: 6 }}>
            {allAgents.map(agent => {
              const on = selected.includes(agent.id);
              return (
                <label key={agent.id} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "11px 12px",
                  borderRadius: 12, cursor: "pointer", minHeight: 52,
                  background: on ? "oklch(0.93 0.06 180)" : "oklch(0.97 0.004 240)",
                  border: on ? "1px solid oklch(0.75 0.12 180)" : "1px solid oklch(0.88 0.005 240)",
                  transition: "all 0.12s"
                }}>
                  <input type="checkbox" checked={on} onChange={() => toggle(agent.id)}
                    style={{ width: 16, height: 16, accentColor: "oklch(0.52 0.14 180)", flexShrink: 0 }} />
                  <Avatar initials={agent.initials} color={agent.color} size={30} status={agent.status} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: 0, fontSize: 13.5, fontWeight: 600, color: "oklch(0.14 0.01 240)" }}>{agent.name}</p>
                    <p style={{ margin: 0, fontSize: 12, color: "oklch(0.55 0.01 240)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{agent.description}</p>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 99, flexShrink: 0,
                    background: agent.status === "online" ? "oklch(0.93 0.10 145)" : "oklch(0.93 0.005 240)",
                    color: agent.status === "online" ? "oklch(0.35 0.14 145)" : "oklch(0.55 0.01 240)"
                  }}>{t(agent.status)}</span>
                </label>
              );
            })}
          </div>
        </div>
        <div>
          <label style={{ fontSize: 11, fontWeight: 700, color: "oklch(0.45 0.01 240)", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: 6 }}>{t("Group name (optional)")}</label>
          <input value={name} onChange={e => setName(e.target.value)}
            placeholder={selected.length > 0 ? IM_DATA.agents.filter(a => selected.includes(a.id)).map(a => a.name).join(", ") : t("Auto-generated from participants")}
            style={{ width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid oklch(0.87 0.006 240)", background: "#fff", fontSize: 14, fontFamily: "inherit", outline: "none", boxSizing: "border-box" }}
            onFocus={e => e.target.style.borderColor = "oklch(0.52 0.14 180)"}
            onBlur={e => e.target.style.borderColor = "oklch(0.87 0.006 240)"}
          />
        </div>
      </div>

      <div style={{ padding: "12px 16px", borderTop: "1px solid oklch(0.87 0.006 240)", display: "flex", gap: 8, background: "#fff",
        paddingBottom: isMobile ? "calc(12px + env(safe-area-inset-bottom, 0px))" : "12px"
      }}>
        {!isMobile && <Btn variant="ghost" onClick={onClose}>{t("Cancel")}</Btn>}
        <Btn variant="primary" disabled={selected.length === 0} onClick={handleCreate}
          style={{ flex: isMobile ? 1 : undefined }}>
          {t("Create group")} {selected.length > 0 ? `(${selected.length})` : ""}
        </Btn>
      </div>
    </>
  );

  if (isMobile) {
    return (
      <div style={{ position: "absolute", inset: 0, zIndex: 50, background: "oklch(0.08 0.01 240 / 0.55)", display: "flex", flexDirection: "column", justifyContent: "flex-end" }}
        onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
        <div style={{ background: "oklch(0.96 0.005 240)", borderRadius: "20px 20px 0 0", maxHeight: "88vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {inner}
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 50, background: "oklch(0.08 0.01 240 / 0.55)", display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ width: 420, background: "oklch(0.96 0.005 240)", borderRadius: 16, boxShadow: "0 24px 64px oklch(0.05 0.01 240 / 0.4)", border: "1px solid oklch(0.87 0.006 240)", maxHeight: "80vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {inner}
      </div>
    </div>
  );
}

// ─── @Mention Dropdown ────────────────────────────────────────────────────────
function MentionDropdown({ candidates, query, onSelect }) {
  const filtered = candidates.filter(a => !query || a.name.toLowerCase().startsWith(query.toLowerCase()));
  if (filtered.length === 0) return null;
  return (
    <div style={{ position: "absolute", bottom: "calc(100% + 6px)", left: 0, right: 40, background: "oklch(0.96 0.005 240)", borderRadius: 10, border: "1px solid oklch(0.87 0.006 240)", boxShadow: "0 8px 24px oklch(0.05 0.01 240 / 0.18)", overflow: "hidden", zIndex: 20 }}>
      <div style={{ padding: "6px 12px 4px", borderBottom: "1px solid oklch(0.90 0.005 240)" }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, color: "oklch(0.55 0.01 240)", letterSpacing: "0.06em", textTransform: "uppercase" }}>{t("Mention agent")}</span>
      </div>
      {filtered.map(agent => (
        <button key={agent.id} onMouseDown={e => { e.preventDefault(); onSelect(agent); }}
          style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", border: "none", cursor: "pointer", background: "transparent", fontFamily: "inherit", textAlign: "left", minHeight: 44, transition: "background 0.1s" }}
          onMouseEnter={e => e.currentTarget.style.background = "oklch(0.92 0.006 240)"}
          onMouseLeave={e => e.currentTarget.style.background = "transparent"}
        >
          <Avatar initials={agent.initials} color={agent.color} size={26} />
          <div>
            <p style={{ margin: 0, fontSize: 13.5, fontWeight: 600, color: "oklch(0.20 0.01 240)" }}>{agent.name}</p>
            <p style={{ margin: 0, fontSize: 11.5, color: "oklch(0.55 0.01 240)", fontFamily: "'IBM Plex Mono', monospace" }}>@{agent.id.replace("agent_", "")}</p>
          </div>
        </button>
      ))}
    </div>
  );
}

// ─── Node Status Chip ─────────────────────────────────────────────────────────
function NodeChip({ agentId }) {
  const cfg = IM_DATA.agentConfigs.find(c => c.agent_id === agentId);
  if (!cfg) return null;
  const online = cfg.node_status === "online";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 9px 3px 7px", borderRadius: 99,
      background: online ? "oklch(0.93 0.07 145)" : "oklch(0.92 0.005 240)",
      border: `1px solid ${online ? "oklch(0.80 0.12 145)" : "oklch(0.85 0.005 240)"}`,
      fontSize: 11.5, fontWeight: 600,
      color: online ? "oklch(0.32 0.14 145)" : "oklch(0.50 0.01 240)"
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: online ? "oklch(0.55 0.18 145)" : "oklch(0.65 0.01 240)", display: "inline-block" }} />
      {cfg.node_name}
    </div>
  );
}

// ─── Conversation Sidebar (shared desktop + mobile list) ──────────────────────
function ConvSidebar({ convs, activeConvId, onSelect, filter, setFilter, search, setSearch, onNewGroup, isMobile }) {
  const FILTERS = [
    { key: "all", label: t("All") }, { key: "direct-agent", label: t("Agent") },
    { key: "group", label: t("Group") }, { key: "agent-network", label: t("Network") },
  ];
  const filtered = convs.filter(c => {
    const matchKind = filter === "all" || c.kind === filter;
    const q = search.toLowerCase();
    return matchKind && (!q || c.title.toLowerCase().includes(q) || (c.last_preview || "").toLowerCase().includes(q));
  });

  const S = { sidebarBg: isMobile ? "oklch(0.93 0.007 240)" : "oklch(0.24 0.012 240)", border: isMobile ? "oklch(0.87 0.006 240)" : "oklch(0.29 0.010 240)" };

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: isMobile ? 1 : undefined, width: isMobile ? "100%" : 262, flexShrink: 0, background: S.sidebarBg, borderRight: isMobile ? "none" : `1px solid ${S.border}` }}>
      <div style={{ padding: isMobile ? "10px 16px 10px" : "14px 12px 10px", borderBottom: isMobile ? `1px solid ${S.border}` : "none" }}>
        {isMobile ? (
          <div style={{ position: "relative", height: 36, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 10 }}>
            <h1 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.01em" }}>{t("Messages")}</h1>
            <button onClick={onNewGroup} title={t("New group chat")} style={{
              position: "absolute", right: 0, top: 0, height: 36, padding: "0 14px", borderRadius: 10, border: "none",
              background: "oklch(0.52 0.14 180)", color: "#fff", cursor: "pointer",
              fontSize: 13, fontWeight: 600, fontFamily: "inherit"
            }}>{t("+ Group")}</button>
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "oklch(0.55 0.01 240)", textTransform: "uppercase" }}>{t("Messages")}</span>
            <button onClick={onNewGroup} title={t("New group chat")} style={{
              height: 36, padding: "0 12px", borderRadius: 8, border: "none",
              background: "oklch(0.30 0.012 240)", color: "#fff", cursor: "pointer",
              fontSize: 13, fontWeight: 600, fontFamily: "inherit"
            }}>{t("+ Group")}</button>
          </div>
        )}
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder={t("Search…")}
          style={{ width: "100%", boxSizing: "border-box", padding: "8px 12px", borderRadius: 10,
            background: isMobile ? "#fff" : "oklch(0.29 0.010 240)",
            border: `1px solid ${isMobile ? "oklch(0.87 0.006 240)" : "oklch(0.33 0.010 240)"}`,
            color: isMobile ? "oklch(0.14 0.01 240)" : "oklch(0.85 0.01 240)",
            fontSize: 13.5, outline: "none", fontFamily: "inherit" }} />
        <div style={{ display: "flex", gap: 6, marginTop: 10, overflowX: "auto", paddingBottom: 2 }}>
          {FILTERS.map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)} style={{
              padding: "5px 12px", borderRadius: 99, fontSize: 12, fontWeight: 600, border: "none", cursor: "pointer", fontFamily: "inherit", flexShrink: 0,
              background: filter === f.key ? "oklch(0.52 0.14 180)" : isMobile ? "oklch(0.90 0.006 240)" : "oklch(0.30 0.010 240)",
              color: filter === f.key ? "#fff" : isMobile ? "oklch(0.45 0.01 240)" : "oklch(0.55 0.01 240)",
              transition: "all 0.12s"
            }}>{f.label}</button>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: isMobile ? "8px 8px 0" : "4px 8px 12px" }}>
        {filtered.length === 0
          ? <p style={{ textAlign: "center", fontSize: 13, color: "oklch(0.55 0.01 240)", padding: "24px 0" }}>{t("No conversations")}</p>
          : filtered.map(c => <ConvItem key={c.id} conv={c} active={c.id === activeConvId} onClick={onSelect} />)
        }
      </div>
    </div>
  );
}

// ─── Message Pane ─────────────────────────────────────────────────────────────
function MessagePaneView({ conv, messages, isMobile, onBack, onSend, draft, setDraft, mentionCandidates, mentionQuery, showMentionMenu, onMentionSelect, composerRef, listRef }) {
  const isGroup = conv?.kind === "group" || conv?.kind === "agent-network";

  function handleSend(e) {
    e.preventDefault();
    if (!draft.trim()) return;
    onSend(draft.trim());
    setDraft("");
  }

  const S = { bg: isMobile ? "oklch(0.93 0.007 240)" : "oklch(0.93 0.007 240)", cardBg: "oklch(0.96 0.005 240)", border: "oklch(0.87 0.006 240)" };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, background: S.bg }}>
      {/* Header */}
      <div style={{ padding: isMobile ? "10px 14px" : "11px 20px", borderBottom: `1px solid ${S.border}`, background: S.cardBg, display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
        paddingTop: isMobile ? "calc(10px + env(safe-area-inset-top, 0px))" : "11px"
      }}>
        {isMobile && (
          <button onClick={onBack} style={{ width: 36, height: 36, borderRadius: 10, border: "none", background: "oklch(0.91 0.006 240)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: "oklch(0.40 0.01 240)", flexShrink: 0 }}>‹</button>
        )}
        {(() => {
          const agent = conv.agent_id ? IM_UTILS.agentById(conv.agent_id) : null;
          const initials = agent ? agent.initials : conv.title.slice(0,2).toUpperCase();
          const color = agent ? agent.color : conv.kind === "group" ? "oklch(0.52 0.14 270)" : "oklch(0.52 0.14 30)";
          return <Avatar initials={initials} color={color} size={34} status={agent ? (agent.status === "online" ? "online" : "offline") : null} />;
        })()}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: "oklch(0.14 0.01 240)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{conv.title}</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2, flexWrap: "wrap" }}>
            {!isMobile && <span style={{ fontSize: 12, color: "oklch(0.55 0.01 240)" }}>{conv.participants.join(" · ")}</span>}
            {conv.agent_id && <NodeChip agentId={conv.agent_id} />}
          </div>
        </div>
        {!isMobile && <KindBadge kind_label={conv.kind_label} />}
        {conv.agent_id && !isMobile && (
          <Btn variant="ghost" small onClick={() => window.__imNav && window.__imNav("settings", conv.agent_id)}>⚙ {t("Config")}</Btn>
        )}
        {conv.agent_id && isMobile && (
          <button onClick={() => window.__imNav && window.__imNav("settings", conv.agent_id)}
            style={{ width: 36, height: 36, borderRadius: 10, border: "none", background: "oklch(0.91 0.006 240)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0, color: "oklch(0.40 0.01 240)" }}>⚙</button>
        )}
      </div>

      {/* Messages */}
      <div ref={listRef} style={{ flex: 1, overflowY: "auto", padding: isMobile ? "14px 12px 8px" : "20px 20px 8px", WebkitOverflowScrolling: "touch" }}>
        {messages.length === 0
          ? <EmptyPane icon="✨" title={t("No messages yet")} sub={t("Send the first message.")} />
          : messages.map(msg => <MessageBubble key={msg.id} msg={msg} isGroupChat={isGroup} isMobile={isMobile} />)
        }
      </div>

      {/* Composer */}
      <form onSubmit={handleSend} style={{
        padding: isMobile ? "10px 12px" : "11px 16px 13px",
        paddingBottom: isMobile ? "calc(10px + env(safe-area-inset-bottom, 12px))" : "13px",
        borderTop: `1px solid ${S.border}`, background: S.cardBg, flexShrink: 0
      }}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", position: "relative" }}>
          {showMentionMenu && (
            <div style={{ position: "absolute", bottom: "calc(100% + 6px)", left: 0, right: 40 }}>
              <MentionDropdown candidates={mentionCandidates} query={mentionQuery} onSelect={onMentionSelect} />
            </div>
          )}
          <textarea ref={composerRef} value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => {
              if (showMentionMenu && e.key === "Escape") { setDraft(d => d.replace(/@\w*$/, "")); return; }
              if (!isMobile && e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(e); }
            }}
            placeholder={isGroup ? `${t("Message…")} ${t("(type @ to mention)")}` : `${t("Message ")}${conv.title}…`}
            rows={isMobile ? 1 : 2}
            style={{
              flex: 1, padding: "10px 12px", borderRadius: 12,
              border: "1px solid oklch(0.85 0.006 240)", background: "oklch(0.975 0.004 240)",
              color: "oklch(0.14 0.01 240)", fontSize: isMobile ? 15 : 13.5,
              fontFamily: "inherit", resize: "none", outline: "none",
              lineHeight: 1.5, transition: "border 0.15s", minHeight: isMobile ? 42 : undefined
            }}
            onFocus={e => e.target.style.borderColor = "oklch(0.52 0.14 180)"}
            onBlur={e => e.target.style.borderColor = "oklch(0.85 0.006 240)"}
          />
          <button type="submit" disabled={!draft.trim()} style={{
            width: isMobile ? 42 : 38, height: isMobile ? 42 : 38, borderRadius: 12, border: "none",
            background: draft.trim() ? "oklch(0.52 0.14 180)" : "oklch(0.88 0.005 240)",
            color: draft.trim() ? "#fff" : "oklch(0.65 0.01 240)",
            cursor: draft.trim() ? "pointer" : "not-allowed", fontSize: 18,
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.15s"
          }}>↑</button>
        </div>
        {!isMobile && (
          <p style={{ margin: "5px 0 0", fontSize: 11.5, color: "oklch(0.65 0.01 240)" }}>
            {t("Enter to send · Shift+Enter new line")}{isGroup ? t(" · @ to mention") : ""}
          </p>
        )}
      </form>
    </div>
  );
}

// ─── Main Chat Page ───────────────────────────────────────────────────────────
function ChatPage({ activeConvId, setActiveConvId, isMobile }) {
  const [convs, setConvs] = React.useState(IM_DATA.conversations);
  const [filter, setFilter] = React.useState("all");
  const [search, setSearch] = React.useState("");
  const [draft, setDraft] = React.useState("");
  const [msgs, setMsgs] = React.useState(() => {
    const map = {};
    IM_DATA.conversations.forEach(c => { map[c.id] = [...c.messages]; });
    return map;
  });
  const [showNewGroup, setShowNewGroup] = React.useState(false);
  const listRef = React.useRef(null);
  const composerRef = React.useRef(null);

  const activeConv = convs.find(c => c.id === activeConvId) || null;
  const isGroup = activeConv?.kind === "group" || activeConv?.kind === "agent-network";
  const mentionMatch = isGroup ? /@(\w*)$/.exec(draft) : null;
  const mentionQuery = mentionMatch ? mentionMatch[1] : null;
  const mentionCandidates = React.useMemo(() => {
    if (!activeConv || !isGroup) return [];
    return IM_DATA.agents.filter(a => activeConv.participants.includes(a.name));
  }, [activeConv, isGroup]);

  React.useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [activeConvId, msgs]);

  React.useEffect(() => {
    if (!isMobile && composerRef.current) composerRef.current.focus();
  }, [activeConvId, isMobile]);

  function handleSend(text) {
    if (!text || !activeConvId) return;
    const newMsg = { id: `m_${Date.now()}`, sender: "user", content: text, at: new Date().toISOString() };
    setMsgs(prev => ({ ...prev, [activeConvId]: [...(prev[activeConvId] || []), newMsg] }));
    setConvs(prev => prev.map(c => c.id === activeConvId ? { ...c, last_preview: text, last_at: newMsg.at } : c));
  }

  function handleMentionSelect(agent) {
    if (mentionMatch == null) return;
    const before = draft.slice(0, draft.length - mentionMatch[0].length);
    setDraft(before + `@${agent.name} `);
    composerRef.current?.focus();
  }

  function handleNewGroup({ selected, name, participants }) {
    const newId = `conv_group_${Date.now()}`;
    const newConv = { id: newId, kind: "group", kind_label: "Group", title: name, unread: 0, last_at: new Date().toISOString(), last_preview: t("Group created"), participants: ["You", ...participants.map(a => a.name)], messages: [] };
    setConvs(prev => [newConv, ...prev]);
    setMsgs(prev => ({ ...prev, [newId]: [] }));
    setShowNewGroup(false);
    setActiveConvId(newId);
  }

  const activeMessages = activeConvId ? (msgs[activeConvId] || []) : [];

  // Mobile: show list OR detail
  const showDetail = isMobile ? !!activeConvId : true;
  const showList = isMobile ? !activeConvId : true;

  return (
    <div style={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden", position: "relative" }}>
      {showList && (
        <ConvSidebar convs={convs} activeConvId={activeConvId} onSelect={setActiveConvId}
          filter={filter} setFilter={setFilter} search={search} setSearch={setSearch}
          onNewGroup={() => setShowNewGroup(true)} isMobile={isMobile} />
      )}
      {showDetail && (
        activeConv
          ? <MessagePaneView
              conv={activeConv} messages={activeMessages}
              isMobile={isMobile} onBack={() => setActiveConvId(null)}
              onSend={handleSend} draft={draft} setDraft={setDraft}
              mentionCandidates={mentionCandidates} mentionQuery={mentionQuery}
              showMentionMenu={mentionQuery !== null} onMentionSelect={handleMentionSelect}
              composerRef={composerRef} listRef={listRef} />
          : !isMobile && (
              <div style={{ flex: 1, background: "oklch(0.93 0.007 240)", display: "flex" }}>
                <EmptyPane icon="💬" title={t("Select a conversation")} sub={t("Pick a thread to chat with your agents.")} />
              </div>
            )
      )}
      {showNewGroup && <NewGroupModal onClose={() => setShowNewGroup(false)} onCreate={handleNewGroup} isMobile={isMobile} />}
    </div>
  );
}

Object.assign(window, { ChatPage });
