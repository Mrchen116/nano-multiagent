import { useState, type FormEvent } from "react";

import { useTranslation } from "../../../../i18n";
import { Avatar, colorForAgent } from "./avatar";

// Fixed (non-agent) avatar colour for the human "you" member — agents derive
// their colour from colorForAgent (display_name seed).
const SELF_AVATAR_COLOR = "oklch(0.55 0.14 255)";

/** One row in the group member list, pre-resolved by the workspace. */
export interface GroupSettingsMember {
  /** participant.id — agent_id for agents (drives config navigation), user_id for the human. */
  id: string;
  /** participant.user_id (UUID) — the value the remove endpoint keys on (决策 5). */
  userId: string | null;
  type: "user" | "agent" | "system";
  displayName: string;
  isSelf: boolean;
  isCreator: boolean;
  status?: "online" | "offline" | null;
  isStale?: boolean | null;
}

/** A candidate agent for the add-members picker (already filtered to non-members). */
export interface GroupSettingsAgentOption {
  agentId: string;
  displayName: string;
  status?: "online" | "offline" | null;
}

export interface GroupSettingsProps {
  title: string;
  members: GroupSettingsMember[];
  addableAgents: GroupSettingsAgentOption[];
  isMobile: boolean;
  /** True while a write mutation is in flight; disables destructive/primary actions. */
  isBusy?: boolean;
  onClose(): void;
  // Write handlers may be async — when they reject, the failure is surfaced
  // inline inside the panel (the global toast sits below the panel's z-index and
  // would be hidden by the scrim / mobile full-screen page).
  onRename(title: string): void | Promise<unknown>;
  onAddParticipants(agentIds: string[]): void | Promise<unknown>;
  /** Remove by the member's user_id (UUID), never its agent_id (决策 5 / CRITICAL-1). */
  onRemoveParticipant(userId: string): void | Promise<unknown>;
  onDissolve(): void | Promise<unknown>;
  onOpenAgentConfig(agentId: string): void;
}

/**
 * Group settings surface — one component, two forms: a right-side drawer on
 * desktop and a full-screen pushed page on mobile (决策 1). State (rename / add /
 * remove-confirm / dissolve-confirm / manage) is shared; only the layout forks
 * on `isMobile`. All data is pre-resolved by the workspace so the component stays
 * presentational and testable.
 */
export function GroupSettings(props: GroupSettingsProps) {
  const { t } = useTranslation();
  const {
    title,
    members,
    addableAgents,
    isMobile,
    isBusy = false,
    onClose,
    onRename,
    onAddParticipants,
    onRemoveParticipant,
    onDissolve,
    onOpenAgentConfig
  } = props;

  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(title);
  const [adding, setAdding] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [confirmingRemoveId, setConfirmingRemoveId] = useState<string | null>(null);
  const [confirmingDissolve, setConfirmingDissolve] = useState(false);
  const [manageMode, setManageMode] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const agentMembers = members.filter((m) => m.type === "agent");
  const nameInvalid = nameDraft.trim().length === 0;

  // Run one write handler, surfacing any rejection inline. On failure we keep the
  // current UI (rename input / add selection / remove confirm) intact so the user
  // can retry — the caller only resets state when this resolves true.
  async function runAction(fn: () => void | Promise<unknown>): Promise<boolean> {
    setActionError(null);
    try {
      await fn();
      return true;
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t("chat.groupSettings.actionError"));
      return false;
    }
  }

  function startRename() {
    setNameDraft(title);
    setActionError(null);
    setRenaming(true);
  }

  async function submitRename(e?: FormEvent) {
    e?.preventDefault();
    const trimmed = nameDraft.trim();
    if (!trimmed) return;
    if (await runAction(() => onRename(trimmed))) setRenaming(false);
  }

  function toggleAgent(agentId: string) {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId) ? prev.filter((x) => x !== agentId) : [...prev, agentId]
    );
  }

  function closeAdd() {
    setAdding(false);
    setSelectedAgentIds([]);
    setActionError(null);
  }

  async function submitAdd() {
    if (selectedAgentIds.length === 0) return;
    // Keep the selection if the add fails — only clear on success.
    if (await runAction(() => onAddParticipants(selectedAgentIds))) closeAdd();
  }

  async function confirmRemove(userId: string | null) {
    if (!userId) {
      setConfirmingRemoveId(null);
      return;
    }
    if (await runAction(() => onRemoveParticipant(userId))) setConfirmingRemoveId(null);
  }

  function handleDissolve() {
    // On success the workspace navigates away (this component unmounts); on
    // failure the error stays visible inline.
    void runAction(() => onDissolve());
  }

  const errorBanner = actionError ? (
    <div className="group-settings-error" role="alert">
      {actionError}
    </div>
  ) : null;

  // ─── Avatar cluster (group identity) ──────────────────────────────────────
  const clusterMembers = agentMembers.length > 0 ? agentMembers : members;
  const clusterAvatars = (size: number) => {
    const shown = clusterMembers.slice(0, 3);
    const extra = clusterMembers.length - shown.length;
    return (
      <div className="group-settings-cluster">
        {shown.map((m) => (
          <Avatar
            key={m.id}
            initials={m.displayName}
            color={m.isSelf ? SELF_AVATAR_COLOR : colorForAgent({ display_name: m.displayName })}
            size={size}
          />
        ))}
        {extra > 0 && (
          <span className="group-settings-cluster-more" style={{ width: size, height: size }}>
            +{extra}
          </span>
        )}
      </div>
    );
  };

  // ─── Rename block (shared) ────────────────────────────────────────────────
  const renameBlock = renaming ? (
    <form className="group-settings-rename" onSubmit={submitRename}>
      <input
        autoFocus
        aria-label={t("chat.groupSettings.groupName")}
        className={`group-settings-rename-input${nameInvalid ? " group-settings-rename-input--err" : ""}`}
        value={nameDraft}
        placeholder={t("chat.groupSettings.groupNamePlaceholder")}
        onChange={(e) => setNameDraft(e.target.value)}
      />
      {nameInvalid && (
        <span className="group-settings-rename-hint">{t("chat.groupSettings.nameRequired")}</span>
      )}
      <div className="group-settings-rename-acts">
        <button type="submit" className="chat-modal-btn-primary" disabled={nameInvalid || isBusy}>
          {t("chat.groupSettings.save")}
        </button>
        <button type="button" className="chat-modal-btn-ghost" onClick={() => setRenaming(false)}>
          {t("chat.groupSettings.cancel")}
        </button>
      </div>
    </form>
  ) : (
    <button
      type="button"
      className="group-settings-name-row"
      aria-label={t("chat.groupSettings.rename")}
      onClick={startRename}
    >
      <span className="group-settings-name">{title}</span>
      <span className="group-settings-name-edit" aria-hidden="true">✎</span>
    </button>
  );

  // ─── Add-members picker body (shared between inline drawer + mobile screen) ─
  const pickerRows =
    addableAgents.length === 0 ? (
      <div className="group-settings-empty">
        <span className="group-settings-empty-icon" aria-hidden="true">👥</span>
        <p>{t("chat.groupSettings.noAddableAgents")}</p>
      </div>
    ) : (
      addableAgents.map((a) => {
        const on = selectedAgentIds.includes(a.agentId);
        return (
          <label key={a.agentId} className={`group-settings-pick${on ? " group-settings-pick--on" : ""}`}>
            <input type="checkbox" checked={on} aria-label={a.displayName} onChange={() => toggleAgent(a.agentId)} />
            <Avatar initials={a.displayName} color={colorForAgent({ display_name: a.displayName })} size={30} />
            <span className="group-settings-pick-name">{a.displayName}</span>
          </label>
        );
      })
    );

  // ─── Member row (shared) ──────────────────────────────────────────────────
  function memberRow(m: GroupSettingsMember) {
    const confirming = confirmingRemoveId !== null && confirmingRemoveId === m.userId;
    // userId must be present to remove (the endpoint keys on it). Guard against a
    // null user_id so the ✕ never becomes a silent no-op.
    const removable = m.type === "agent" && !m.isSelf && m.userId != null;
    const showRemoveAffordance = removable && (!isMobile || manageMode);
    return (
      <li key={m.id} className="group-settings-member">
        <div className="group-settings-member-main">
          {showRemoveAffordance && !confirming && (
            <button
              type="button"
              className="group-settings-member-remove"
              aria-label={t("chat.groupSettings.removeMember", { name: m.displayName })}
              onClick={() => setConfirmingRemoveId(m.userId)}
            >
              ✕
            </button>
          )}
          {m.type === "agent" && !manageMode ? (
            <button
              type="button"
              className="group-settings-member-body group-settings-member-body--link"
              onClick={() => onOpenAgentConfig(m.id)}
            >
              {memberFace(m)}
            </button>
          ) : (
            <div className="group-settings-member-body">{memberFace(m)}</div>
          )}
          {m.type === "agent" && !manageMode && <span className="group-settings-chev" aria-hidden="true">›</span>}
        </div>
        {confirming && (
          <div className="group-settings-inline-confirm">
            <span>{t("chat.groupSettings.removeConfirm")}</span>
            <div className="group-settings-inline-confirm-acts">
              <button
                type="button"
                className="group-settings-btn-danger"
                disabled={isBusy}
                onClick={() => confirmRemove(m.userId)}
              >
                {t("chat.groupSettings.remove")}
              </button>
              <button
                type="button"
                className="chat-modal-btn-ghost"
                onClick={() => setConfirmingRemoveId(null)}
              >
                {t("chat.groupSettings.cancel")}
              </button>
            </div>
          </div>
        )}
      </li>
    );
  }

  function memberFace(m: GroupSettingsMember) {
    const statusText =
      m.type === "agent"
        ? `${m.status === "online" ? t("chat.groupSettings.online") : t("chat.groupSettings.offline")} · ${t("chat.groupSettings.agentRole")}`
        : t("chat.groupSettings.self");
    return (
      <>
        <span
          className={m.isStale ? "group-settings-av--stale" : undefined}
          title={m.isStale ? t("chat.groupSettings.stale") : undefined}
        >
          <Avatar
            initials={m.displayName}
            color={m.isSelf ? SELF_AVATAR_COLOR : colorForAgent({ display_name: m.displayName })}
            size={34}
          />
        </span>
        <span className="group-settings-member-text">
          <span className="group-settings-member-name">
            {m.displayName}
            {m.isCreator && <span className="group-settings-role-tag">{t("chat.groupSettings.creator")}</span>}
          </span>
          <span className="group-settings-member-sub">{statusText}</span>
        </span>
      </>
    );
  }

  // ─── Dissolve danger zone (shared) ────────────────────────────────────────
  const dissolveBlock = confirmingDissolve ? (
    <div className="group-settings-dissolve-confirm" data-testid="group-settings-dissolve-confirm">
      <p>{t("chat.groupSettings.dissolveConfirm")}</p>
      <div className="group-settings-inline-confirm-acts">
        <button type="button" className="group-settings-btn-danger-solid" disabled={isBusy} onClick={handleDissolve}>
          {t("chat.groupSettings.dissolve")}
        </button>
        <button type="button" className="chat-modal-btn-ghost" onClick={() => setConfirmingDissolve(false)}>
          {t("chat.groupSettings.cancel")}
        </button>
      </div>
    </div>
  ) : (
    <button type="button" className="group-settings-btn-danger-wide" onClick={() => setConfirmingDissolve(true)}>
      {t("chat.groupSettings.dissolve")}
    </button>
  );

  // ─── Mobile: full-screen add picker takes over the whole screen ────────────
  if (isMobile && adding) {
    return (
      <div className="group-settings-mobile" role="dialog" aria-label={t("chat.groupSettings.addMembers")}>
        <div className="group-settings-mobile-nav">
          <button type="button" className="group-settings-nav-btn" onClick={closeAdd}>
            ‹ {t("chat.groupSettings.back")}
          </button>
          <span className="group-settings-nav-title">{t("chat.groupSettings.addMembers")}</span>
          <span className="group-settings-nav-spacer" />
        </div>
        {errorBanner}
        <div className="group-settings-mobile-scroll">
          <div className="group-settings-pick-list">{pickerRows}</div>
        </div>
        {addableAgents.length > 0 && (
          <div className="group-settings-mobile-foot">
            <button
              type="button"
              className="chat-modal-btn-primary"
              disabled={selectedAgentIds.length === 0 || isBusy}
              onClick={submitAdd}
            >
              {t("chat.groupSettings.addCountMobile", { count: selectedAgentIds.length })}
            </button>
          </div>
        )}
      </div>
    );
  }

  if (isMobile) {
    return (
      <div className="group-settings-mobile" role="dialog" aria-label={t("chat.groupSettings.title")}>
        <div className="group-settings-mobile-nav">
          <button type="button" className="group-settings-nav-btn" onClick={onClose}>
            ‹ {t("chat.groupSettings.back")}
          </button>
          <span className="group-settings-nav-title">
            {manageMode ? t("chat.groupSettings.manageTitle") : t("chat.groupSettings.title")}
          </span>
          <button
            type="button"
            className="group-settings-nav-btn group-settings-nav-btn--act"
            onClick={() => setManageMode((v) => !v)}
          >
            {manageMode ? t("chat.groupSettings.done") : t("chat.groupSettings.manage")}
          </button>
        </div>
        {errorBanner}
        <div className="group-settings-mobile-scroll">
          <div className="group-settings-hero">
            {clusterAvatars(52)}
            {renameBlock}
            <div className="group-settings-meta">{t("chat.groupSettings.createdByYou", { count: members.length })}</div>
          </div>
          <div className="group-settings-group">
            <div className="group-settings-group-label">
              {t("chat.groupSettings.members")} · {members.length}
            </div>
            <ul className="group-settings-card">
              {!manageMode && (
                <li className="group-settings-add-row">
                  <button type="button" className="group-settings-add-link" onClick={() => setAdding(true)}>
                    <span className="group-settings-add-icon" aria-hidden="true">＋</span>
                    {t("chat.groupSettings.addMembers")}
                  </button>
                </li>
              )}
              {members.map(memberRow)}
            </ul>
          </div>
          <div className="group-settings-group">
            <div className="group-settings-card group-settings-card--danger">{dissolveBlock}</div>
          </div>
        </div>
      </div>
    );
  }

  // ─── Desktop: right-side drawer ───────────────────────────────────────────
  return (
    <>
      <div className="group-settings-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="group-settings-drawer" role="dialog" aria-label={t("chat.groupSettings.title")}>
        <div className="group-settings-drawer-head">
          <button
            type="button"
            className="group-settings-close"
            aria-label={t("chat.groupSettings.close")}
            onClick={onClose}
          >
            ✕
          </button>
          {clusterAvatars(44)}
          {renameBlock}
          <div className="group-settings-meta">{t("chat.groupSettings.createdByYou", { count: members.length })}</div>
        </div>

        {errorBanner}

        <div className="group-settings-section">
          <span className="group-settings-section-label">
            {t("chat.groupSettings.members")} · {members.length}
          </span>
          {!adding && (
            <button type="button" className="group-settings-add-link" onClick={() => setAdding(true)}>
              ＋ {t("chat.groupSettings.addMembers")}
            </button>
          )}
        </div>

        {adding && (
          <div className="group-settings-addbox">
            <div className="group-settings-addbox-head">{t("chat.groupSettings.addMembersTitle")}</div>
            <div className="group-settings-pick-list">{pickerRows}</div>
            {addableAgents.length > 0 && (
              <div className="group-settings-addbox-foot">
                <button
                  type="button"
                  className="chat-modal-btn-primary"
                  disabled={selectedAgentIds.length === 0 || isBusy}
                  onClick={submitAdd}
                >
                  {t("chat.groupSettings.addCount", { count: selectedAgentIds.length })}
                </button>
                <button type="button" className="chat-modal-btn-ghost" onClick={closeAdd}>
                  {t("chat.groupSettings.cancel")}
                </button>
              </div>
            )}
          </div>
        )}

        <ul className="group-settings-list">{members.map(memberRow)}</ul>

        <div className="group-settings-danger-zone">{dissolveBlock}</div>
      </aside>
    </>
  );
}
