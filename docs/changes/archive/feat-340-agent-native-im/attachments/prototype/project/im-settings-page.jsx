// Settings page — agent list + detail + new agent, mobile + desktop

const EMPTY_AGENT = {
  agent_id: "", display_name: "", owner_id: "owner_1",
  description: "", system_prompt: "",
  group_reply_policy: "MENTION", skills: [], tool_allowlist: [],
  default_model: "", profile_version: 1,
  workspace_root: "", node_id: "", node_name: "", node_status: "offline",
  updated_at: null
};

// ─── Agent List (shared mobile + desktop sidebar) ─────────────────────────────
function AgentListView({ configs, activeId, onSelect, onNew, isMobile }) {
  const S = { bg: isMobile ? "oklch(0.93 0.007 240)" : "oklch(0.24 0.012 240)", border: isMobile ? "oklch(0.87 0.006 240)" : "oklch(0.29 0.010 240)" };
  return (
    <div style={{ width: isMobile ? "100%" : 240, display: "flex", flexDirection: "column", flex: isMobile ? 1 : undefined, background: S.bg, borderRight: isMobile ? "none" : `1px solid ${S.border}` }}>
      <div style={{ padding: isMobile ? "10px 16px 12px" : "14px 12px 10px", borderBottom: `1px solid ${S.border}` }}>
        {isMobile ? (
          <div style={{ position: "relative", height: 36, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <h1 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.01em" }}>{t("Agents")}</h1>
            <button onClick={onNew} style={{
              position: "absolute", right: 0, top: 0, height: 36, padding: "0 14px", borderRadius: 10, border: "none",
              background: "oklch(0.52 0.14 180)", color: "#fff", cursor: "pointer",
              fontSize: 13, fontWeight: 600, fontFamily: "inherit"
            }}>{t("+ New")}</button>
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "oklch(0.55 0.01 240)", textTransform: "uppercase" }}>{t("Agents")}</span>
            <button onClick={onNew} style={{
              height: 36, padding: "0 12px", borderRadius: 8, border: "none",
              background: "oklch(0.30 0.012 240)", color: "#fff", cursor: "pointer",
              fontSize: 13, fontWeight: 600, fontFamily: "inherit"
            }}>{t("+ New")}</button>
          </div>
        )}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: isMobile ? "8px 10px" : "6px 8px" }}>
        {configs.map(cfg => {
          const agent = IM_DATA.agents.find(a => a.id === cfg.agent_id);
          const active = cfg.agent_id === activeId;
          const online = cfg.node_status === "online";
          return (
            <button key={cfg.agent_id} onClick={() => onSelect(cfg.agent_id)} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 12,
              padding: isMobile ? "12px 10px" : "9px 10px", borderRadius: 12, border: "none",
              cursor: "pointer", textAlign: "left", fontFamily: "inherit", marginBottom: 4,
              background: active ? (isMobile ? "oklch(0.90 0.010 180)" : "oklch(0.31 0.015 240)") : "transparent",
              outline: active ? `1px solid ${isMobile ? "oklch(0.75 0.12 180)" : "oklch(0.40 0.08 180)"}` : "none",
              transition: "background 0.1s", minHeight: 52
            }}
            onMouseEnter={e => { if (!active) e.currentTarget.style.background = isMobile ? "oklch(0.90 0.006 240)" : "oklch(0.28 0.012 240)"; }}
            onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
            >
              <Avatar initials={agent?.initials || cfg.display_name.slice(0,2).toUpperCase()}
                color={agent?.color || "oklch(0.52 0.14 180)"} size={isMobile ? 38 : 32}
                status={online ? "online" : "offline"} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <p style={{ margin: 0, fontSize: isMobile ? 15 : 13, fontWeight: 600, color: active && !isMobile ? "#fff" : "oklch(0.18 0.01 240)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {cfg.display_name}
                </p>
                <p style={{ margin: "2px 0 0", fontSize: isMobile ? 12.5 : 11, color: isMobile ? "oklch(0.55 0.01 240)" : "oklch(0.50 0.01 240)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: isMobile ? "inherit" : "'IBM Plex Mono', monospace" }}>
                  {isMobile ? cfg.description : cfg.agent_id}
                </p>
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3, flexShrink: 0 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: online ? "oklch(0.55 0.18 145)" : "oklch(0.45 0.01 240)" }} />
                {isMobile && <span style={{ fontSize: 11, color: "oklch(0.65 0.01 240)" }}>›</span>}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Shared Form Fields (mobile-aware) ────────────────────────────────────────
function AgentForm({ form, patch, capabilities, isMobile, isNew = false, ownedNodes, errors }) {
  const policyOptions = [
    { value: "MENTION", label: t("MENTION — Reply only when @-mentioned") },
    { value: "ALWAYS", label: t("ALWAYS — Reply to every group message") }
  ];
  const modelOptions = [
    { value: "", label: `${t("Platform default")} (${capabilities.platform_default_model})` },
    ...capabilities.model_options.map(m => ({ value: m, label: m + (m === capabilities.platform_default_model ? " " + t("(default)") : "") }))
  ];
  const cols = isMobile ? "1fr" : "1fr 1fr";

  return (
    <>
      <SectionCard title={t("Identity")} sub={isNew ? t("Agent ID is permanent and used in mentions and API calls.") : t("Name and purpose shown to users and other agents.")}>
        <div style={{ display: "grid", gridTemplateColumns: cols, gap: 14, alignItems: "start" }}>
          <Field label={isNew ? t("Agent ID *") : t("Agent ID")} id="f-agent-id"
            help={isNew ? t("Lowercase letters, numbers, _ and -") : undefined}>
            {isNew
              ? <Input id="f-agent-id" value={form.agent_id} onChange={e => patch("agent_id", e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))} placeholder={t("e.g. my_agent")} mono />
              : <Input id="f-agent-id" value={form.agent_id} disabled mono />
            }
          </Field>
          <Field label={isNew ? t("Display Name *") : t("Display Name")} id="f-display-name">
            <Input id="f-display-name" value={form.display_name} onChange={e => patch("display_name", e.target.value)} placeholder={isNew ? t("e.g. My Agent") : undefined} disabled={!isNew && false} />
          </Field>
        </div>
        <Field label={t("Description")} id="f-desc" help={t("Short summary shown in group chats.")}>
          <Input id="f-desc" value={form.description} onChange={e => patch("description", e.target.value)} placeholder={isNew ? t("What does this agent do?") : undefined} />
        </Field>
        {isNew && ownedNodes && (
          <Field label={t("Owning Node *")} id="f-node" help={t("The node that will host and run this agent.")}>
            <Select id="f-node" value={form.node_id || ""} onChange={e => {
              const n = ownedNodes.find(x => x.node_id === e.target.value);
              patch("node_id", n ? n.node_id : "");
              patch("node_name", n ? (n.alias || n.node_name) : "");
              patch("node_status", n ? n.status : "offline");
            }} options={[
              { value: "", label: t("— Select a node —") },
              ...ownedNodes.filter(n => n.status !== "offline").map(n => ({ value: n.node_id, label: `${n.alias || n.node_name} (${t(n.status)})` }))
            ]} />
          </Field>
        )}
      </SectionCard>

      <SectionCard title={t("Behavior")} sub={t("System prompt is the primary behavior contract.")}>
        <Field label={isNew ? t("System Prompt *") : t("System Prompt")} id="f-prompt" help={t("Defines role, tone, and constraints.")}>
          <Textarea id="f-prompt" value={form.system_prompt} onChange={e => patch("system_prompt", e.target.value)}
            placeholder={isNew ? "You are a helpful assistant. Your job is to...\n\nBe concise and ask clarifying questions when needed." : undefined}
            rows={isMobile ? 5 : 7} mono />
        </Field>
        <Field label={t("Group Reply Policy")} id="f-policy" help={t("When this agent replies in group conversations.")}>
          <Select id="f-policy" value={form.group_reply_policy} onChange={e => patch("group_reply_policy", e.target.value)} options={policyOptions} />
        </Field>
      </SectionCard>

      <SectionCard title={t("Access & Model")} sub={t("Keep allowlists minimal.")}>
        <Field label={t("Skills")}><MultiSelect all={capabilities.skills} selected={form.skills} onChange={val => patch("skills", val)} /></Field>
        <Field label={t("Tool Allowlist")}><MultiSelect all={capabilities.tools} selected={form.tool_allowlist} onChange={val => patch("tool_allowlist", val)} /></Field>
        <Field label={t("Default Model")} id="f-model">
          <Select id="f-model" value={form.default_model || ""} onChange={e => patch("default_model", e.target.value || null)} options={modelOptions} />
        </Field>
      </SectionCard>

      {!isNew && (
        <SectionCard title={t("Workspace & Runtime")} sub={t("Read-only. Managed by the owning node.")}>
          <div style={{ display: "grid", gridTemplateColumns: cols, gap: 14 }}>
            <Field label={t("Workspace Root")}><Input value={form.workspace_root} disabled mono /></Field>
            <Field label={t("Profile Version")}><Input value={String(form.profile_version)} disabled /></Field>
            <Field label={t("Owning Node")}><Input value={`${form.node_name} (${form.node_id})`} disabled /></Field>
            <Field label={t("Last Updated")}><Input value={form.updated_at ? new Date(form.updated_at).toLocaleString() : "—"} disabled /></Field>
          </div>
        </SectionCard>
      )}
    </>
  );
}

// ─── New Agent Panel ──────────────────────────────────────────────────────────
function NewAgentPanel({ onCancel, onCreate, isMobile, initialNodeId }) {
  const { capabilities } = IM_DATA;
  const ownedNodes = IM_DATA.nodes.filter(n => IM_DATA.account.owned_node_ids.includes(n.node_id));
  const onlineNodes = ownedNodes.filter(n => n.status === "online");
  const defaultNode =
    (initialNodeId && ownedNodes.find(n => n.node_id === initialNodeId)) ||
    ownedNodes.find(n => n.node_id === IM_DATA.account.default_entry_node_id) ||
    onlineNodes[0] || ownedNodes[0] || null;
  const [form, setForm] = React.useState({
    ...EMPTY_AGENT,
    node_id: defaultNode?.node_id || "",
    node_name: defaultNode?.alias || defaultNode?.node_name || "",
    node_status: defaultNode?.status || "offline"
  });
  const [errors, setErrors] = React.useState({});

  function patch(key, val) { setForm(f => ({ ...f, [key]: val })); setErrors(e => ({ ...e, [key]: null })); }

  function validate() {
    const errs = {};
    if (!form.agent_id.trim()) errs.agent_id = t("Required");
    if (!form.display_name.trim()) errs.display_name = t("Required");
    if (!form.system_prompt.trim()) errs.system_prompt = t("Required");
    if (form.agent_id && !/^[a-z0-9_-]+$/.test(form.agent_id)) errs.agent_id = t("Lowercase letters, numbers, _ and - only");
    if (!form.node_id) errs.node_id = t("Required");
    return errs;
  }

  function handleCreate(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    const node = ownedNodes.find(n => n.node_id === form.node_id) || defaultNode;
    const newAgent = { ...form, agent_id: form.agent_id.trim(), display_name: form.display_name.trim(), system_prompt: form.system_prompt.trim(), workspace_root: `~/nano-assistant/workspace/${form.agent_id.trim()}/`, node_id: node.node_id, node_name: node.alias || node.node_name, node_status: node.status, updated_at: new Date().toISOString() };
    IM_DATA.agentConfigs.push(newAgent);
    IM_DATA.agents.push({ id: form.agent_id.trim(), name: form.display_name.trim(), initials: form.display_name.trim().slice(0,2).toUpperCase(), color: `oklch(0.52 0.14 ${Math.round(Math.random()*360)})`, description: form.description.trim(), status: node.status === "online" ? "online" : "offline", node: node.node_id, model: form.default_model || capabilities.platform_default_model });
    const nIdx = IM_DATA.nodes.findIndex(n => n.node_id === node.node_id);
    if (nIdx >= 0) IM_DATA.nodes[nIdx] = { ...IM_DATA.nodes[nIdx], agent_count: (IM_DATA.nodes[nIdx].agent_count || 0) + 1 };
    onCreate(form.agent_id.trim());
  }

  const border = "oklch(0.87 0.006 240)";

  return (
    <form onSubmit={handleCreate} style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: isMobile ? "14px 16px" : "18px 28px 14px", borderBottom: `1px solid ${border}`, background: "#fff", flexShrink: 0,
        paddingTop: isMobile ? "calc(14px + env(safe-area-inset-top, 0px))" : "18px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {isMobile && (
            <button type="button" onClick={onCancel} style={{ width: 36, height: 36, borderRadius: 10, border: "none", background: "oklch(0.91 0.006 240)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: "oklch(0.40 0.01 240)", flexShrink: 0 }}>‹</button>
          )}
          <div style={{ flex: 1 }}>
            <h1 style={{ margin: 0, fontSize: isMobile ? 18 : 18, fontWeight: 800, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.02em" }}>{t("New agent")}</h1>
            <p style={{ margin: "3px 0 0", fontSize: 12.5, color: "oklch(0.55 0.01 240)" }}>{t("Configure identity, behavior, and tool access.")}</p>
          </div>
          {!isMobile && (
            <div style={{ display: "flex", gap: 8 }}>
              <Btn variant="ghost" onClick={onCancel} type="button">{t("Cancel")}</Btn>
              <Btn type="submit" variant="primary">{t("Create agent")}</Btn>
            </div>
          )}
        </div>
      </div>

      <div style={{ flex: 1, padding: isMobile ? "14px 14px" : "20px 28px", display: "grid", gap: 14, alignContent: "start" }}>
        <AgentForm form={form} patch={patch} capabilities={capabilities} isMobile={isMobile} isNew ownedNodes={ownedNodes} errors={errors} />
        <div style={{ background: "#fff", borderRadius: 12, border: `1px solid ${border}`, padding: "14px 16px", display: "flex", gap: 8, justifyContent: isMobile ? "stretch" : "flex-end",
          paddingBottom: isMobile ? "calc(14px + env(safe-area-inset-bottom, 0px))" : "14px"
        }}>
          {!isMobile && <Btn variant="ghost" onClick={onCancel} type="button">{t("Cancel")}</Btn>}
          <Btn type="submit" variant="primary" style={{ flex: isMobile ? 1 : undefined }}>{t("Create agent →")}</Btn>
        </div>
      </div>
    </form>
  );
}

// ─── Agent Detail Panel ───────────────────────────────────────────────────────
function AgentDetailPanel({ agentId, onOpenChat, onBack, isMobile }) {
  const { capabilities } = IM_DATA;
  const orig = IM_DATA.agentConfigs.find(c => c.agent_id === agentId);
  const [form, setForm] = React.useState(orig ? { ...orig } : null);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    const c = IM_DATA.agentConfigs.find(c => c.agent_id === agentId);
    setForm(c ? { ...c } : null); setSaved(false);
  }, [agentId]);

  if (!form) return <EmptyPane icon="🤖" title={t("Select an agent")} sub={t("Choose an agent to view or edit its configuration.")} />;

  const agent = IM_DATA.agents.find(a => a.id === agentId);
  const isDirty = JSON.stringify(form) !== JSON.stringify(orig);
  const online = form.node_status === "online";
  const border = "oklch(0.87 0.006 240)";

  function patch(key, val) { setForm(f => ({ ...f, [key]: val })); setSaved(false); }
  function handleSave(e) {
    e.preventDefault();
    const idx = IM_DATA.agentConfigs.findIndex(c => c.agent_id === agentId);
    if (idx >= 0) IM_DATA.agentConfigs[idx] = { ...form };
    setSaved(true); setTimeout(() => setSaved(false), 2000);
  }

  return (
    <form onSubmit={handleSave} style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: isMobile ? "14px 16px" : "18px 28px 14px", borderBottom: `1px solid ${border}`, background: "#fff", flexShrink: 0,
        paddingTop: isMobile ? "calc(14px + env(safe-area-inset-top, 0px))" : "18px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {isMobile && (
            <button type="button" onClick={onBack} style={{ width: 36, height: 36, borderRadius: 10, border: "none", background: "oklch(0.91 0.006 240)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: "oklch(0.40 0.01 240)", flexShrink: 0 }}>‹</button>
          )}
          <Avatar initials={agent?.initials || form.display_name.slice(0,2).toUpperCase()} color={agent?.color || "oklch(0.52 0.14 180)"} size={isMobile ? 38 : 42} status={online ? "online" : "offline"} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{ margin: 0, fontSize: isMobile ? 17 : 18, fontWeight: 800, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{form.display_name}</h1>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, flexWrap: "wrap" }}>
              <span style={{ fontSize: 11.5, color: "oklch(0.55 0.01 240)", fontFamily: "'IBM Plex Mono', monospace" }}>{form.agent_id}</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, fontWeight: 600, color: online ? "oklch(0.40 0.14 145)" : "oklch(0.55 0.01 240)" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: online ? "oklch(0.55 0.18 145)" : "oklch(0.55 0.01 240)", display: "inline-block" }} />
                {form.node_name}
              </span>
            </div>
          </div>
          {!isMobile && (
            <div style={{ display: "flex", gap: 8 }}>
              <Btn variant="ghost" onClick={() => onOpenChat(agentId)} type="button">{t("Open chat ↗")}</Btn>
              <Btn type="submit" variant="primary" disabled={!isDirty}>{saved ? t("✓ Saved") : isDirty ? t("Save") : t("No changes")}</Btn>
            </div>
          )}
        </div>
      </div>

      <div style={{ flex: 1, padding: isMobile ? "14px 14px" : "20px 28px", display: "grid", gap: 14, alignContent: "start" }}>
        <AgentForm form={form} patch={patch} capabilities={capabilities} isMobile={isMobile} />
        <div style={{ background: "#fff", borderRadius: 12, border: `1px solid ${border}`, padding: "14px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap",
          paddingBottom: isMobile ? "calc(14px + env(safe-area-inset-bottom, 0px))" : "14px"
        }}>
          <span style={{ fontSize: 12.5, color: saved ? "oklch(0.45 0.15 145)" : isDirty ? "oklch(0.50 0.15 60)" : "oklch(0.55 0.01 240)", fontWeight: saved || isDirty ? 700 : 400 }}>
            {saved ? t("✓ Saved") : isDirty ? t("● Unsaved changes") : `v${form.profile_version}`}
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            {isMobile && <Btn variant="ghost" onClick={() => onOpenChat(agentId)} type="button">{t("Open chat ↗")}</Btn>}
            {isDirty && <Btn variant="ghost" onClick={() => setForm({ ...orig })} type="button">{t("Discard")}</Btn>}
            <Btn type="submit" variant="primary" disabled={!isDirty}>{t("Save Agent")}</Btn>
          </div>
        </div>
      </div>
    </form>
  );
}

// ─── Settings Page ─────────────────────────────────────────────────────────────
function SettingsPage({ initialAgentId, initialNewAgentNodeId, newAgentNonce, onOpenChat, isMobile }) {
  const [configs, setConfigs] = React.useState([...IM_DATA.agentConfigs]);
  const [activeId, setActiveId] = React.useState(initialAgentId || (isMobile ? null : configs[0]?.agent_id));
  const [creatingNew, setCreatingNew] = React.useState(false);
  const [newNodeId, setNewNodeId] = React.useState(null);

  React.useEffect(() => {
    if (initialAgentId) { setActiveId(initialAgentId); setCreatingNew(false); }
  }, [initialAgentId]);

  // Triggered when Nodes page (or anywhere else) requests “new agent on this node”.
  React.useEffect(() => {
    if (newAgentNonce && newAgentNonce > 0) {
      setCreatingNew(true);
      setActiveId(null);
      setNewNodeId(initialNewAgentNodeId || null);
    }
  }, [newAgentNonce, initialNewAgentNodeId]);

  function handleCreate(newAgentId) {
    setConfigs([...IM_DATA.agentConfigs]);
    setCreatingNew(false);
    setActiveId(newAgentId);
  }

  // Mobile: show list OR detail/form
  const showList = isMobile ? (!activeId && !creatingNew) : true;
  const showDetail = isMobile ? (!!activeId || creatingNew) : true;

  return (
    <div style={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>
      {showList && (
        <AgentListView configs={configs} activeId={creatingNew ? "__new__" : activeId}
          onSelect={id => { setActiveId(id); setCreatingNew(false); }}
          onNew={() => { setCreatingNew(true); setActiveId(null); setNewNodeId(null); }}
          isMobile={isMobile} />
      )}
      {showDetail && (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, background: "oklch(0.93 0.007 240)", overflowY: "auto" }}>
          {creatingNew
            ? <NewAgentPanel initialNodeId={newNodeId} onCancel={() => { setCreatingNew(false); setNewNodeId(null); if (!isMobile) setActiveId(configs[0]?.agent_id); }} onCreate={(id) => { handleCreate(id); setNewNodeId(null); }} isMobile={isMobile} />
            : activeId
              ? <AgentDetailPanel agentId={activeId} onOpenChat={onOpenChat} onBack={() => setActiveId(null)} isMobile={isMobile} />
              : <EmptyPane icon="🤖" title={t("Select an agent")} sub={t("Choose an agent from the list.")} />
          }
        </div>
      )}
    </div>
  );
}

Object.assign(window, { SettingsPage });
