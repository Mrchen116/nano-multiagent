// Fixture for bugfix-717: mounts the repository's real `NewConversationMenu` inside the chat
// sidebar shell reproduced from `conversation-sidebar.tsx:206-262`.
//
// Only the surrounding presentational markup is hand-written; the menu, its focus behaviour and the
// i18n labels are the real modules, because the defect is a layout/stacking interaction between the
// menu and its ancestors. `run-verification.mjs` bundles this file with the repo's React and serves
// `harness.html` from an isolated port.
import { useState } from "react";
import { createRoot } from "react-dom/client";

import { NewConversationMenu } from "../../../../../../src/IM/frontend/src/features/chat/components/new-conversation-menu.tsx";
import { useTranslation } from "../../../../../../src/IM/frontend/src/i18n/index.ts";

const FILTER_LABEL = ["chat.list.filterAll", "chat.list.filterAgent", "chat.list.filterGroup"];

function Sidebar() {
  const { t } = useTranslation();
  const [searching, setSearching] = useState(false);
  const [filter, setFilter] = useState(0);
  (window as unknown as { __setSearching: (value: boolean) => void }).__setSearching = setSearching;

  return (
    <aside className={`chat-sidebar${searching ? " chat-sidebar--searching" : ""}`} aria-label="chat">
      <header className="chat-sidebar-header">
        <div className="chat-sidebar-header-row" inert={searching}>
          <span className="chat-sidebar-title">{t("chat.list.header")}</span>
          <NewConversationMenu
            onNewChat={() => { (window as unknown as { __picked?: string }).__picked = "new-chat"; }}
            onNewGroup={() => { (window as unknown as { __picked?: string }).__picked = "new-group"; }}
            onDiscover={() => { (window as unknown as { __picked?: string }).__picked = "discover"; }}
          />
        </div>
        <div className="chat-search-input-row">
          <button type="button" className="chat-search-back" aria-hidden={!searching} disabled={!searching} tabIndex={searching ? 0 : -1}>‹</button>
          <input type="search" role="searchbox" className="chat-sidebar-search" placeholder={t("chat.list.search")}
            onFocus={() => setSearching(true)} />
        </div>
        <div className="chat-sidebar-filters" role="tablist">
          {FILTER_LABEL.map((key, index) => (
            <button key={key} type="button" role="tab" aria-selected={filter === index}
              className={`chat-sidebar-filter${filter === index ? " chat-sidebar-filter--active" : ""}`}
              onClick={() => setFilter(index)}>{t(key)}</button>
          ))}
        </div>
      </header>
      <ul className="chat-sidebar-list">
        {Array.from({ length: 12 }, (_, index) => (
          <li key={index}><button type="button" className="chat-sidebar-row">会话 {index + 1}</button></li>
        ))}
      </ul>
    </aside>
  );
}

createRoot(document.getElementById("root")!).render(
  <div className="im-shell"><div className="chat-workspace">
    <Sidebar />
    <main className="chat-pane"><div className="chat-pane-header" /></main>
  </div></div>
);
