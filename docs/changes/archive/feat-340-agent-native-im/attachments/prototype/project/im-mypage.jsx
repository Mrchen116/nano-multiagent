// im-mypage.jsx — WeChat-style "我的" tab page

function MyRow({ icon, label, sub, value, trailing, onClick, danger, isLast }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        width: "100%", display: "flex", alignItems: "center", gap: 14, padding: "14px 18px",
        border: "none", background: hover ? "oklch(0.96 0.005 240)" : "transparent", cursor: "pointer", textAlign: "left",
        fontFamily: "inherit", minHeight: 60,
        borderBottom: isLast ? "none" : "1px solid oklch(0.93 0.005 240)",
        transition: "background 0.1s"
      }}>
      {icon && (
        <span style={{
          width: 28, height: 28, borderRadius: 7, display: "flex", alignItems: "center",
          justifyContent: "center", fontSize: 15, flexShrink: 0,
          background: danger ? "oklch(0.96 0.04 25)" : "oklch(0.95 0.006 240)"
        }}>{icon}</span>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          margin: 0, fontSize: 15, fontWeight: 500,
          color: danger ? "oklch(0.50 0.15 25)" : "oklch(0.14 0.01 240)"
        }}>{label}</p>
        {sub && <p style={{ margin: "2px 0 0", fontSize: 12, color: "oklch(0.55 0.01 240)" }}>{sub}</p>}
      </div>
      {value && <span style={{ fontSize: 13.5, color: "oklch(0.50 0.01 240)", flexShrink: 0 }}>{value}</span>}
      {trailing}
      <span style={{ fontSize: 18, color: "oklch(0.70 0.01 240)", flexShrink: 0, fontWeight: 300 }}>›</span>
    </button>
  );
}

function LangRowMobile({ lang, setLang, isLast }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14, padding: "14px 18px",
      fontFamily: "inherit", minHeight: 60,
      borderBottom: isLast ? "none" : "1px solid oklch(0.93 0.005 240)"
    }}>
      <span style={{
        width: 28, height: 28, borderRadius: 7, display: "flex", alignItems: "center",
        justifyContent: "center", fontSize: 13, fontWeight: 700, flexShrink: 0,
        background: "oklch(0.95 0.006 240)", color: "oklch(0.30 0.01 240)"
      }}>文</span>
      <p style={{ flex: 1, margin: 0, fontSize: 15, fontWeight: 500, color: "oklch(0.14 0.01 240)" }}>{t("Language")}</p>
      <div style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: 3, borderRadius: 99, background: "oklch(0.94 0.005 240)" }}>
        {[{ k: "en", l: "EN" }, { k: "zh", l: "中" }].map(o => {
          const active = lang === o.k;
          return (
            <button key={o.k} type="button" onClick={() => setLang(o.k)} style={{
              padding: "5px 13px", borderRadius: 99, border: "none", cursor: "pointer",
              fontFamily: "inherit", fontSize: 12.5, fontWeight: 700,
              background: active ? "#fff" : "transparent",
              color: active ? "oklch(0.14 0.01 240)" : "oklch(0.55 0.01 240)",
              boxShadow: active ? "0 1px 2px oklch(0.05 0.01 240 / 0.12)" : "none",
              transition: "all 0.12s"
            }}>{o.l}</button>
          );
        })}
      </div>
    </div>
  );
}

function MyPage({ isMobile, onNavigate, lang, setLang }) {
  const acct = IM_DATA.account;
  const ownedNodes = IM_DATA.nodes.filter(n => acct.owned_node_ids.includes(n.node_id));
  const onlineCount = ownedNodes.filter(n => n.status === "online").length;
  const offlineCount = ownedNodes.length - onlineCount;

  const cardStyle = {
    background: "#fff",
    borderTop: "1px solid oklch(0.91 0.005 240)",
    borderBottom: "1px solid oklch(0.91 0.005 240)"
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", background: "oklch(0.95 0.005 240)" }}>
      {/* User identity card */}
      <button onClick={() => onNavigate("account")} style={{
        width: "100%", textAlign: "left", border: "none", cursor: "pointer", fontFamily: "inherit",
        background: "#fff", padding: "26px 18px 24px",
        display: "flex", alignItems: "center", gap: 16,
        borderBottom: "1px solid oklch(0.91 0.005 240)"
      }}>
        <Avatar initials={(acct.display_name || "U").slice(0,2).toUpperCase()} color="oklch(0.52 0.14 270)" size={62} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "oklch(0.14 0.01 240)", letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {acct.display_name}
          </p>
          <p style={{ margin: "5px 0 0", fontSize: 13, color: "oklch(0.55 0.01 240)", fontFamily: "'IBM Plex Mono', monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {acct.user_id}
          </p>
        </div>
        <span style={{ fontSize: 20, color: "oklch(0.70 0.01 240)", flexShrink: 0, fontWeight: 300 }}>›</span>
      </button>

      {/* Group 1: Nodes (the differentiator, surfaced first) */}
      <div style={{ ...cardStyle, marginTop: 14 }}>
        <MyRow
          icon="🖥"
          label={t("Nodes")}
          sub={`${ownedNodes.length} ${t("owned")} · ${onlineCount} ${t("online")}${offlineCount ? ` · ${offlineCount} ${t("offline")}` : ""}`}
          onClick={() => onNavigate("nodes")}
          trailing={offlineCount > 0 ? (
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "oklch(0.60 0.01 240)", flexShrink: 0 }} />
          ) : null}
          isLast
        />
      </div>

      {/* Group 2: Account */}
      <div style={{ ...cardStyle, marginTop: 14 }}>
        <MyRow
          icon="👤"
          label={t("Account")}
          sub={t("Profile and gateway")}
          onClick={() => onNavigate("account")}
          isLast
        />
      </div>

      {/* Group 3: Language */}
      <div style={{ ...cardStyle, marginTop: 14 }}>
        <LangRowMobile lang={lang} setLang={setLang} isLast />
      </div>

      {/* Group 4: Sign out */}
      <div style={{ ...cardStyle, marginTop: 14, marginBottom: 24 }}>
        <MyRow icon="↗" label={t("Sign out")} onClick={() => {}} danger isLast />
      </div>
    </div>
  );
}

Object.assign(window, { MyPage });
