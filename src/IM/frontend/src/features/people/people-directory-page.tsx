import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useTranslation } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { createConversation } from "../chat/chat-api";
import { Avatar } from "../chat/components/avatar";
import { contactActor, listContacts, type Contact } from "../chat/contacts-api";
import "../settings/agents/agent-settings.css";
import "./people-directory.css";

/**
 * Organization-level People directory (/people): makes human colleagues, their
 * public Personal Assistants, and the specialist Agents they manage equally
 * discoverable alongside the Agents directory.
 */
export function PeopleDirectoryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const selfId = user?.id ?? null;
  const isActiveMember = user?.membership_status === "active";
  const isAdmin = Boolean(user?.is_company_admin);

  const [search, setSearch] = useState("");
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState(false);

  const contactsQuery = useQuery({
    queryKey: ["contacts", selfId],
    queryFn: () => listContacts(),
    enabled: Boolean(selfId),
    refetchInterval: 5000
  });

  const { allHumans, filteredHumans, agentsByOwner } = useMemo(() => {
    const items = contactsQuery.data ?? [];
    const humans = items
      .filter((c) => c.kind === "human")
      .sort((a, b) => {
        // Put teammates first so every top slot is immediately actionable; self stays visible with a "You" badge.
        if ((a.user_id === selfId) !== (b.user_id === selfId)) {
          return a.user_id === selfId ? 1 : -1;
        }
        return a.display_name.localeCompare(b.display_name);
      });
    const byOwner = new Map<string, { pa?: Contact; specialists: Contact[] }>();
    for (const item of items) {
      if (item.kind !== "agent") continue;
      const ownerKey = item.owner_user_id ?? item.owner_id;
      if (!ownerKey) continue;
      const bucket = byOwner.get(ownerKey) ?? { specialists: [] };
      if (item.role === "personal") bucket.pa = item;
      else if (item.agent_id) bucket.specialists.push(item);
      byOwner.set(ownerKey, bucket);
    }
    const rawQ = search.trim().toLowerCase();
    const userQ = rawQ.startsWith("@") ? rawQ.slice(1) : rawQ;
    const matched = !rawQ
      ? humans
      : humans.filter((person) => {
          if (person.display_name.toLowerCase().includes(rawQ)) return true;
          if (person.username && userQ) {
            const uname = person.username.toLowerCase();
            if (uname.includes(rawQ) || uname.includes(userQ)) return true;
          }
          const linked = byOwner.get(person.user_id);
          if (linked?.pa?.display_name.toLowerCase().includes(rawQ)) return true;
          if (linked?.specialists.some((a) => a.display_name.toLowerCase().includes(rawQ))) return true;
          return false;
        });
    return { allHumans: humans, filteredHumans: matched, agentsByOwner: byOwner };
  }, [contactsQuery.data, selfId, search]);

  async function openDirectChat(target: Contact) {
    if (pendingId) return;
    setPendingId(target.user_id);
    setActionError(false);
    try {
      const chat = await createConversation({
        type: "direct",
        title: target.display_name,
        participants: [contactActor(target)]
      });
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      navigate(`/chat/${chat.id}`);
    } catch {
      setActionError(true);
    } finally {
      setPendingId(null);
    }
  }

  if (contactsQuery.isPending) {
    return (
      <section className="im-agent-panel im-agent-settings im-agent-directory im-people-directory">
        <div className="im-settings-list-header">
          <h1>{t("people.title")}</h1>
        </div>
        <p className="im-settings-empty" role="status">{t("common.loading")}</p>
      </section>
    );
  }

  if (contactsQuery.isError) {
    return (
      <section className="im-agent-panel im-agent-settings im-agent-directory im-people-directory">
        <div className="im-settings-list-header">
          <h1>{t("people.title")}</h1>
        </div>
        <div className="im-settings-feedback" role="alert">
          <p>{t("people.loadError")}</p>
        </div>
        <button type="button" className="im-settings-action" onClick={() => void contactsQuery.refetch()}>
          {t("people.retry")}
        </button>
      </section>
    );
  }

  return (
    <section className="im-agent-panel im-agent-settings im-agent-directory im-people-directory">
      <header className="im-settings-list-header">
        <div className="im-people-header-copy">
          <h1>
            {t("people.title")}
            {isActiveMember && (
              <span className="im-settings-count">{t("people.count", { count: allHumans.length })}</span>
            )}
          </h1>
          <p className="im-people-subtitle">{t("people.subtitle")}</p>
        </div>
        <div className="im-people-toolbar">
          {isActiveMember && (
            <input
              type="search"
              role="searchbox"
              className="im-input im-settings-search"
              aria-label={t("people.search")}
              placeholder={t("people.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          )}
          {isAdmin && isActiveMember && (
            <Link className="im-settings-action" to="/settings/company">
              {t("people.manageMembers")}
            </Link>
          )}
        </div>
      </header>

      {actionError && (
        <div className="im-settings-feedback" role="alert">
          <p>{t("chat.contacts.failed")}</p>
        </div>
      )}

      {!isActiveMember && (
        <div className="im-people-personal-banner" data-testid="people-personal-space-guide">
          <h2>{t("people.personalSpaceTitle")}</h2>
          <p>{t("people.personalSpaceBody")}</p>
          <Link className="im-settings-action" to="/settings/account">
            {t("people.openTeamAccess")}
          </Link>
        </div>
      )}

      <div className="im-directory-content">
        {filteredHumans.length === 0 ? (
          <p className="im-settings-empty">{t("people.noSearchResults")}</p>
        ) : (
          <ul className="im-people-grid">
            {filteredHumans.map((person) => {
              const isSelf = person.user_id === selfId;
              const linked = agentsByOwner.get(person.user_id);
              const hasLinkedAgents = Boolean(linked?.pa || linked?.specialists.length);
              return (
                <li key={person.user_id} className="im-people-row" data-testid={`person-row-${person.user_id}`}>
                  <div className="im-people-row-main">
                    <Avatar id={person.user_id} size={40} />
                    <div className="im-people-identity">
                      <div className="im-people-name-line">
                        <strong className="im-people-name">{person.display_name}</strong>
                        {isSelf && <span className="im-people-self-badge">{t("people.you")}</span>}
                      </div>
                      {person.username && <span className="im-people-username">@{person.username}</span>}
                    </div>
                    {isSelf ? (
                      <Link className="im-settings-action" to="/settings/account">
                        {t("people.accountLink")}
                      </Link>
                    ) : (
                      <button
                        type="button"
                        className="im-settings-action"
                        disabled={pendingId !== null}
                        onClick={() => void openDirectChat(person)}
                      >
                        {t("people.message")}
                      </button>
                    )}
                  </div>
                  {hasLinkedAgents && (
                    <div className="im-people-agents">
                      {linked?.pa && (
                        <button
                          type="button"
                          className="im-people-agent-chip im-people-agent-chip--pa"
                          disabled={pendingId !== null}
                          onClick={() => void openDirectChat(linked.pa!)}
                        >
                          <Avatar id={linked.pa.user_id} size={20} status={linked.pa.status} />
                          <span>{linked.pa.display_name}</span>
                          <small>· {t("people.personalAssistant")}</small>
                        </button>
                      )}
                      {linked?.specialists.map((agent) => (
                        <Link
                          key={agent.user_id}
                          to={`/settings/agents/${encodeURIComponent(agent.agent_id!)}`}
                          className="im-people-agent-chip"
                        >
                          <Avatar id={agent.user_id} size={20} status={agent.status} />
                          <span>{agent.display_name}</span>
                          <ArrowUpRight size={13} aria-hidden="true" />
                        </Link>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
