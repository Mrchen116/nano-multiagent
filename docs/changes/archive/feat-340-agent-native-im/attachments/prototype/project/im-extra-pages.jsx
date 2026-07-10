// im-extra-pages.jsx — Nodes page + Account page

function NodeStatusBadge({ status }) {
  const online = status === "online";
  const c = online
    ? { bg:"oklch(0.93 0.07 145)",fg:"oklch(0.32 0.14 145)",dot:"oklch(0.55 0.18 145)",bd:"oklch(0.80 0.12 145)" }
    : { bg:"oklch(0.92 0.005 240)",fg:"oklch(0.50 0.01 240)",dot:"oklch(0.60 0.01 240)",bd:"oklch(0.85 0.005 240)" };
  return (
    <span style={{ display:"inline-flex",alignItems:"center",gap:5,padding:"3px 10px 3px 7px",borderRadius:99,fontSize:11.5,fontWeight:700,background:c.bg,color:c.fg,border:"1px solid "+c.bd }}>
      <span style={{ width:6,height:6,borderRadius:"50%",display:"inline-block",background:c.dot,animation:online?"im-pulse 2s infinite":"none" }} />
      {t(status)}
    </span>
  );
}

function NodeCard({ node, onSave, isMobile }) {
  const [draft, setDraft] = React.useState({ ...node });
  const isDirty = JSON.stringify(draft) !== JSON.stringify(node);
  const bd = "oklch(0.87 0.006 240)";

  return (
    <div style={{ background:"#fff",borderRadius:14,border:"1px solid "+bd,overflow:"hidden" }}>
      <div style={{ padding:"14px 18px",borderBottom:"1px solid "+bd,display:"flex",alignItems:"center",gap:12,flexWrap:"wrap",justifyContent:"space-between" }}>
        <div style={{ display:"flex",alignItems:"center",gap:12 }}>
          <div style={{ width:38,height:38,borderRadius:10,background:node.status==="online"?"oklch(0.92 0.08 145)":"oklch(0.92 0.005 240)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:16,flexShrink:0 }}>
            {node.status==="online"?"🖥":"💤"}
          </div>
          <div>
            <div style={{ display:"flex",alignItems:"center",gap:8,flexWrap:"wrap" }}>
              <h3 style={{ margin:0,fontSize:14,fontWeight:800,color:"oklch(0.14 0.01 240)" }}>{draft.alias||node.node_name}</h3>
              <NodeStatusBadge status={node.status} />
            </div>
            <p style={{ margin:"2px 0 0",fontSize:11.5,color:"oklch(0.55 0.01 240)",fontFamily:"'IBM Plex Mono',monospace" }}>{node.node_id}</p>
          </div>
        </div>
        <div style={{ display:"flex",gap:14,fontSize:12,color:"oklch(0.55 0.01 240)",flexShrink:0,textAlign:"right" }}>
          <span><b style={{ color:"oklch(0.25 0.01 240)",fontSize:15 }}>{node.agent_count}</b><br/>{t("agents")}</span>
          <span><b style={{ color:"oklch(0.25 0.01 240)",fontSize:15 }}>v{node.version}</b><br/>{t("version")}</span>
        </div>
      </div>
      <div style={{ padding:"14px 18px",display:"grid",gap:14 }}>
        <div style={{ display:"grid",gridTemplateColumns:isMobile?"1fr":"1fr 1fr",gap:14,alignItems:"start" }}>
          <Field label={t("Alias")} id={"al-"+node.node_id} help={t("Friendly name shown in the UI.")}>
            <Input id={"al-"+node.node_id} value={draft.alias||""} onChange={e=>setDraft(d=>({...d,alias:e.target.value}))} placeholder={node.node_name} />
          </Field>
          <div>
            <p style={{ margin:"0 0 6px",fontSize:13,fontWeight:600,color:"oklch(0.30 0.01 240)" }}>{t("Live Snapshot")}</p>
            <div style={{ background:"oklch(0.95 0.005 240)",borderRadius:8,padding:"10px 12px",fontSize:12,fontFamily:"'IBM Plex Mono',monospace",display:"grid",gap:4,border:"1px solid "+bd }}>
              <div style={{ display:"flex",justifyContent:"space-between" }}>
                <span style={{ color:"oklch(0.55 0.01 240)" }}>{t("Heartbeat")}</span>
                <span style={{ color:"oklch(0.25 0.01 240)" }}>{node.last_heartbeat_at?new Date(node.last_heartbeat_at).toLocaleTimeString():"—"}</span>
              </div>
              <div style={{ display:"flex",justifyContent:"space-between" }}>
                <span style={{ color:"oklch(0.55 0.01 240)" }}>{t("Version")}</span>
                <span style={{ color:"oklch(0.25 0.01 240)" }}>{node.version||"—"}</span>
              </div>
              {node.last_error&&<div style={{ marginTop:4,padding:"5px 8px",borderRadius:6,background:"oklch(0.96 0.06 25)",color:"oklch(0.45 0.14 25)",fontSize:11,lineHeight:1.5,wordBreak:"break-all" }}>⚠ {node.last_error}</div>}
            </div>
          </div>
        </div>

        <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8,paddingTop:4,borderTop:"1px solid oklch(0.91 0.005 240)" }}>
          <span style={{ fontSize:12,color:isDirty?"oklch(0.50 0.15 60)":"oklch(0.65 0.01 240)",fontWeight:isDirty?700:400 }}>{isDirty?t("● Unsaved changes"):t("All saved")}</span>
          <div style={{ display:"flex",gap:8 }}>
            {node.status!=="offline"&&<Btn variant="ghost" small onClick={()=>window.__imNav&&window.__imNav("settings",null,{newAgent:true,nodeId:node.node_id})}>{t("+ New agent on node")}</Btn>}
            <Btn variant="primary" small disabled={!isDirty} onClick={()=>onSave(draft)}>{t("Save")} {node.node_id}</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

function PageBackHeader({ title, onBack }) {
  return (
    <div style={{ position:"sticky",top:0,zIndex:5,display:"flex",alignItems:"center",gap:8,height:48,padding:"0 8px 0 4px",background:"oklch(0.97 0.004 240)",borderBottom:"1px solid oklch(0.91 0.005 240)" }}>
      <button onClick={onBack} style={{ height:40,width:40,borderRadius:10,border:"none",background:"transparent",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,color:"oklch(0.30 0.01 240)",fontFamily:"inherit" }}>‹</button>
      <h1 style={{ margin:0,fontSize:16,fontWeight:700,color:"oklch(0.14 0.01 240)",letterSpacing:"-0.01em" }}>{title}</h1>
    </div>
  );
}

function NodesPage({ isMobile, onBack }) {
  const [nodes,setNodes] = React.useState([...IM_DATA.nodes]);
  function handleSave(updated) {
    setNodes(prev=>prev.map(n=>n.node_id===updated.node_id?{...updated}:n));
    const idx=IM_DATA.nodes.findIndex(n=>n.node_id===updated.node_id);
    if(idx>=0) IM_DATA.nodes[idx]={...updated};
  }
  const stats=[{label:t("Total nodes"),value:nodes.length},{label:t("Online"),value:nodes.filter(n=>n.status==="online").length},{label:t("Offline"),value:nodes.filter(n=>n.status==="offline").length},{label:t("Total agents"),value:nodes.reduce((s,n)=>s+n.agent_count,0)}];
  return (
    <div style={{ flex:1,overflowY:"auto",background:"oklch(0.95 0.005 240)" }}>
      {isMobile && onBack && <PageBackHeader title={t("Nodes")} onBack={onBack} />}
      <div style={{ padding:isMobile?"16px 14px":"24px 28px",display:"grid",gap:16 }}>
        {!isMobile && <div>
          <h1 style={{ margin:0,fontSize:22,fontWeight:800,color:"oklch(0.14 0.01 240)",letterSpacing:"-0.02em" }}>{t("Nodes")}</h1>
          <p style={{ margin:"4px 0 0",fontSize:13,color:"oklch(0.55 0.01 240)" }}>{t("Gateway nodes connected to this workspace.")}</p>
        </div>}
        <div style={{ display:"grid",gridTemplateColumns:isMobile?"1fr 1fr":"repeat(4,1fr)",gap:10 }}>
          {stats.map(s=>(
            <div key={s.label} style={{ background:"#fff",borderRadius:10,border:"1px solid oklch(0.87 0.006 240)",padding:"12px 14px" }}>
              <p style={{ margin:0,fontSize:24,fontWeight:800,color:"oklch(0.14 0.01 240)",letterSpacing:"-0.02em" }}>{s.value}</p>
              <p style={{ margin:"3px 0 0",fontSize:12,color:"oklch(0.55 0.01 240)" }}>{s.label}</p>
            </div>
          ))}
        </div>
        {nodes.map(node=><NodeCard key={node.node_id} node={node} onSave={handleSave} isMobile={isMobile} />)}
      </div>
    </div>
  );
}

function AccountPage({ isMobile, onBack }) {
  const [form,setForm] = React.useState({...IM_DATA.account});
  const [saved,setSaved] = React.useState(false);
  const isDirty = JSON.stringify(form)!==JSON.stringify(IM_DATA.account);
  const bd = "oklch(0.87 0.006 240)";
  const ownedNodes = IM_DATA.nodes.filter(n=>form.owned_node_ids.includes(n.node_id));

  function handleSave(e) {
    e.preventDefault();
    Object.assign(IM_DATA.account,form);
    setSaved(true);
    setTimeout(()=>setSaved(false),2000);
  }

  return (
    <div style={{ flex:1,overflowY:"auto",background:"oklch(0.95 0.005 240)" }}>
      {isMobile && onBack && <PageBackHeader title={t("Account")} onBack={onBack} />}
      <form onSubmit={handleSave} style={{ padding:isMobile?"16px 14px":"24px 28px",display:"grid",gap:16,maxWidth:620,width:"100%",margin:"0 auto" }}>
        {!isMobile && <div>
          <h1 style={{ margin:0,fontSize:22,fontWeight:800,color:"oklch(0.14 0.01 240)",letterSpacing:"-0.02em" }}>{t("Account")}</h1>
          <p style={{ margin:"4px 0 0",fontSize:13,color:"oklch(0.55 0.01 240)" }}>{t("Your profile and default gateway configuration.")}</p>
        </div>}

        <SectionCard title={t("Profile")} sub={t("Your identity inside the workspace.")}>
          <div style={{ display:"flex",alignItems:"center",gap:16,paddingBottom:4 }}>
            <div style={{ width:54,height:54,borderRadius:"50%",background:"oklch(0.52 0.14 270)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,fontWeight:800,color:"#fff",flexShrink:0 }}>
              {form.display_name.slice(0,2).toUpperCase()}
            </div>
            <div>
              <p style={{ margin:0,fontSize:16,fontWeight:800,color:"oklch(0.14 0.01 240)" }}>{form.display_name}</p>
              <p style={{ margin:"3px 0 0",fontSize:12,color:"oklch(0.55 0.01 240)",fontFamily:"'IBM Plex Mono',monospace" }}>{form.user_id}</p>
            </div>
          </div>
          <div style={{ display:"grid",gridTemplateColumns:isMobile?"1fr":"1fr 1fr",gap:14,alignItems:"start" }}>
            <Field label={t("User ID")}><Input value={form.user_id} disabled mono /></Field>
            <Field label={t("Display Name")} help={t("Shown in conversations and group chats.")}>
              <Input value={form.display_name} onChange={e=>setForm(f=>({...f,display_name:e.target.value}))} />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title={t("Gateway")} sub={t("Controls which node routes your messages by default.")}>
          <Field label={t("Default Entry Node")} help={t("Choose from your owned nodes.")}>
            <Select value={form.default_entry_node_id||""} onChange={e=>setForm(f=>({...f,default_entry_node_id:e.target.value||null}))}
              options={[{value:"",label:t("— Select a node —")},...ownedNodes.map(n=>({value:n.node_id,label:(n.alias||n.node_name)+" ("+t(n.status)+")"}))]}>
            </Select>
          </Field>
          <div style={{ display:"grid",gap:8 }}>
            {ownedNodes.map(node=>(
              <div key={node.node_id} style={{ display:"flex",alignItems:"center",gap:12,padding:"10px 12px",borderRadius:10,background:"oklch(0.96 0.005 240)",border:"1px solid "+bd }}>
                <NodeStatusBadge status={node.status} />
                <div style={{ flex:1 }}>
                  <p style={{ margin:0,fontSize:13,fontWeight:700,color:"oklch(0.18 0.01 240)" }}>{node.alias||node.node_name}</p>
                  <p style={{ margin:0,fontSize:11,color:"oklch(0.55 0.01 240)",fontFamily:"'IBM Plex Mono',monospace" }}>{node.node_id}</p>
                </div>
                <div style={{ textAlign:"right",fontSize:12,color:"oklch(0.55 0.01 240)" }}>
                  <p style={{ margin:0 }}>{node.agent_count} {t("agents")}</p>
                  <p style={{ margin:0 }}>v{node.version}</p>
                </div>
                {node.node_id===form.default_entry_node_id&&(
                  <span style={{ fontSize:11,fontWeight:700,padding:"2px 8px",borderRadius:99,background:"oklch(0.93 0.06 180)",color:"oklch(0.35 0.12 180)",border:"1px solid oklch(0.78 0.12 180)" }}>{t("Default")}</span>
                )}
              </div>
            ))}
          </div>
          <div style={{ padding:"10px 12px",borderRadius:8,background:"oklch(0.96 0.005 240)",border:"1px solid "+bd,display:"grid",gap:4,fontSize:12 }}>
            <div style={{ display:"flex",justifyContent:"space-between",color:"oklch(0.55 0.01 240)" }}>
              <span>{t("Member since")}</span>
              <span style={{ color:"oklch(0.30 0.01 240)",fontWeight:600 }}>{new Date(form.created_at).toLocaleDateString()}</span>
            </div>
            <div style={{ display:"flex",justifyContent:"space-between",color:"oklch(0.55 0.01 240)" }}>
              <span>{t("Owned nodes")}</span>
              <span style={{ color:"oklch(0.30 0.01 240)",fontWeight:600 }}>{form.owned_node_ids.length}</span>
            </div>
          </div>
        </SectionCard>

        <div style={{ background:"#fff",borderRadius:12,border:"1px solid "+bd,padding:"14px 16px",display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,paddingBottom:isMobile?"calc(14px + env(safe-area-inset-bottom, 0px))":"14px" }}>
          <span style={{ fontSize:12.5,fontWeight:saved?700:400,color:saved?"oklch(0.45 0.15 145)":isDirty?"oklch(0.50 0.15 60)":"oklch(0.60 0.01 240)" }}>
            {saved?t("✓ Saved"):isDirty?t("● Unsaved changes"):""}
          </span>
          <Btn type="submit" variant="primary" disabled={!isDirty}>{t("Save account")}</Btn>
        </div>
      </form>
    </div>
  );
}

Object.assign(window, { NodesPage, AccountPage, NodeStatusBadge });
