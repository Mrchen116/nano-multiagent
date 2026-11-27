import { useState, type FormEvent } from "react";

import { useTranslation } from "../../../i18n";
import { Avatar, agentAvatarId } from "./avatar";

/** One row in the group member list, pre-resolved by the workspace. */
export interface GroupSettingsMember {
  /** participant.id — agent_id for agents (drives config navigation), user_id for the human. */
  id: string;
  /** participant.user_id (UUID) — the value the remove endpoint keys on (决策 5). */
  userId: string | null;
  type: "user" | "agent" | "system";
  displayName: string;
  username?: string | null;
  isSelf: boolean;
  isCreator: boolean;
  status?: "online" | "offline" | null;
  isStale?: boolean | null;
}

/** A candidate agent or colleague for the add-members picker (already filtered to non-members). */
export interface GroupSettingsAgentOption {
  agentId: string;
  type?: "user" | "agent";
  displayName: string;
  username?: string | null;
  status?: "online" | "offline" | null;
}

export interface GroupSettingsProps {
  readOnly?: boolean;
  privateAgentLocked?: boolean;
  projectAgentLocked?: boolean;
  foreignProjectAgentMemberLocked?: boolean;
  visibility?: "public" | "private";
  canChangeVisibility?: boolean;
  onVisibilityChange?(visibility: "public" | "private"): Promise<unknown>;
  title: string;
  members: GroupSettingsMember[];
  addableAgents: GroupSettingsAgentOption[];
  isMobile: boolean;
  /** True while a write mutation is in flight; disables destructive/primary actions. */
  isBusy?: boolean;
  isPinned?: boolean;
  isMuted?: boolean;
  onPreferenceChange?(patch: { is_pinned?: boolean; is_muted?: boolean }): Promise<unknown>;
  onClose(): void;
  // Write handlers may be async — when they reject, the failure is surfaced
  // inline inside the panel (the global toast sits below the panel's z-index and
  // would be hidden by the scrim / mobile full-screen page).
  onRename(title: string): void | Promise<unknown>;
  onAddParticipants(agentIds: string[]): void | Promise<unknown>;
  /** Remove by the member's user_id (UUID), never its agent_id (决策 5 / CRITICAL-1). */
  onRemoveParticipant(userId: string): void | Promise<unknown>;
  onLeave?(): void | Promise<unknown>;
  onDissolve(): void | Promise<unknown>;
  onOpenAgentConfig(agentId: string): void;
  onSelectHumanMember?(userId: string, element: HTMLButtonElement): void;
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
    isPinned, isMuted, onPreferenceChange,
    onClose,
    onRename,
    onAddParticipants,
    onRemoveParticipant,
    onDissolve,
    onLeave,
    onOpenAgentConfig
  } = props;

  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(title);
  const [adding, setAdding] = useState(false);
  const [addSearch, setAddSearch] = useState("");
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [confirmingRemoveId, setConfirmingRemoveId] = useState<string | null>(null);
  const [confirmingDissolve, setConfirmingDissolve] = useState(false);
  const [manageMode, setManageMode] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const readOnly = Boolean(props.readOnly);
  const isCreator = members.some(member => member.isSelf && member.isCreator);
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

  function openAdd() {
    setAddSearch("");
    setActionError(null);
    setAdding(true);
  }

  function closeAdd() {
    setAdding(false);
    setAddSearch("");
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
  const clusterMembers = members.filter((m) => m.type !== "system");
  const clusterAvatars = (size: number) => {
    const shown = clusterMembers.slice(0, 3);
    const extra = clusterMembers.length - shown.length;
    return (
      <div className="group-settings-cluster">
        {shown.map((m) => (
          <Avatar key={m.id} id={m.userId ?? (m.type === "agent" ? agentAvatarId(m.id) : m.id)} size={size} />
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
      disabled={readOnly}
      onClick={startRename}
    >
      <span className="group-settings-name">{title}</span>
      <span className="group-settings-name-edit" aria-hidden="true">✎</span>
    </button>
  );

  // ─── Add-members picker body (shared between inline drawer + mobile screen) ─
  const orderedAddable = [
    ...addableAgents.filter((a) => a.type === "user"),
    ...addableAgents.filter((a) => a.type !== "user")
  ];
  const rawAddSearch = addSearch.trim().toLowerCase();
  const userAddSearch = rawAddSearch.startsWith("@") ? rawAddSearch.slice(1) : rawAddSearch;
  const filteredAddable = !rawAddSearch
    ? orderedAddable
    : orderedAddable.filter((a) => {
        if (a.displayName.toLowerCase().includes(rawAddSearch)) return true;
        if (a.type === "user") {
          if (!a.username || !userAddSearch) return false;
          const uname = a.username.toLowerCase();
          return uname.includes(rawAddSearch) || uname.includes(userAddSearch);
        }
        return a.agentId.toLowerCase().includes(rawAddSearch);
      });
  const pickerRows =
    orderedAddable.length === 0 ? (
      <div className="group-settings-empty">
        <span className="group-settings-empty-icon" aria-hidden="true">👥</span>
        <p>{t("chat.groupSettings.noAddableAgents")}</p>
      </div>
    ) : (
      <>
        <div className="group-settings-add-search-wrap">
          <input
            type="search"
            className="chat-sidebar-search"
            aria-label={t("chat.contacts.search")}
            placeholder={t("chat.contacts.search")}
            value={addSearch}
            onChange={(e) => setAddSearch(e.target.value)}
          />
        </div>
        {filteredAddable.length === 0 ? (
          <p className="group-settings-empty-search">{t("chat.contacts.empty")}</p>
        ) : (
          filteredAddable.map((a) => {
            const on = selectedAgentIds.includes(a.agentId);
            return (
              <label key={a.agentId} className={`group-settings-pick${on ? " group-settings-pick--on" : ""}`}>
                <input type="checkbox" checked={on} aria-label={a.displayName} onChange={() => toggleAgent(a.agentId)} />
                <Avatar id={a.type === "user" ? a.agentId : agentAvatarId(a.agentId)} size={30} />
                <span className="group-settings-member-text">
                  <span className="group-settings-pick-name">{a.displayName}</span>
                  {a.type === "user" && a.username && <span className="group-settings-member-sub">@{a.username}</span>}
                </span>
              </label>
            );
          })
        )}
      </>
    );

  // ─── Member row (shared) ──────────────────────────────────────────────────
  function memberRow(m: GroupSettingsMember) {
    const confirming = confirmingRemoveId !== null && confirmingRemoveId === m.userId;
    // userId must be present to remove (the endpoint keys on it). Guard against a
    // null user_id so the ✕ never becomes a silent no-op.
    const removable = !readOnly && m.type !== "system" && !m.isCreator && !m.isSelf && m.userId != null;
    // 留出删除控件列的语境：桌面(hover 显 ✕)或移动 manage 态。该列内每行都占等宽前导槽位
    // ——可删的放 ✕，不可删的(本人)放等宽空 spacer——让所有成员头像左缘对齐。
    const showRemoveColumn = !isMobile || manageMode;
    return (
      <li key={m.id} className="group-settings-member">
        <div className="group-settings-member-main">
          {showRemoveColumn &&
            (removable && !confirming ? (
              <button
                type="button"
                className="group-settings-member-remove"
                aria-label={t("chat.groupSettings.removeMember", { name: m.displayName })}
                onClick={() => setConfirmingRemoveId(m.userId)}
              >
                ✕
              </button>
            ) : (
              <span className="group-settings-member-remove-slot" aria-hidden="true" />
            ))}
          {m.type === "agent" && !manageMode ? (
            <button
              type="button"
              className="group-settings-member-body group-settings-member-body--link"
              onClick={() => onOpenAgentConfig(m.id)}
            >
              {memberFace(m)}
            </button>
          ) : m.type === "user" && !m.isSelf && m.userId && !manageMode && props.onSelectHumanMember ? (
            <button
              type="button"
              className="group-settings-member-body group-settings-member-body--link"
              onClick={(event) => props.onSelectHumanMember?.(m.userId!, event.currentTarget)}
            >
              {memberFace(m)}
            </button>
          ) : (
            <div className="group-settings-member-body">{memberFace(m)}</div>
          )}
          {((m.type === "agent" && !manageMode) || (m.type === "user" && !m.isSelf && m.userId && !manageMode && props.onSelectHumanMember)) && (
            <span className="group-settings-chev" aria-hidden="true">›</span>
          )}
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
        : m.isSelf
        ? (m.username ? `@${m.username} · ${t("chat.groupSettings.self")}` : t("chat.groupSettings.self"))
        : (m.username ? `@${m.username}` : t("chat.contacts.person"));
    return (
      <>
        <span
          className={m.isStale ? "group-settings-av--stale" : undefined}
          title={m.isStale ? t("chat.groupSettings.stale") : undefined}
        >
          <Avatar id={m.userId ?? (m.type === "agent" ? agentAvatarId(m.id) : m.id)} size={34} />
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
  const dissolveBlock = readOnly ? <p>{t("tasks.readOnly")}</p> : !isCreator ? (
    <button type="button" className="group-settings-btn-danger-wide" disabled={isBusy} onClick={() => void runAction(() => onLeave?.())}>{t("chat.groupSettings.leave")}</button>
  ) : confirmingDissolve ? (
    <div className="group-settings-dissolve-confirm" data-testid="group-settings-dissolve-confirm">
<p>{t("tasks.dissolveConfirm")}</p>
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

  const settingsControls = (props.visibility || onPreferenceChange) && <div className="group-settings-controls">
    {props.visibility && <label className="group-settings-control group-settings-control--visibility">
      <span>{t('tasks.visibility')}</span>
      <select className="group-settings-select" aria-label={t('tasks.visibility')} value={props.visibility} disabled={!props.canChangeVisibility || readOnly || isBusy}
        onChange={e => void runAction(() => props.onVisibilityChange?.(e.target.value as 'public' | 'private'))}>
        <option value="public">{t('tasks.public')}</option><option value="private">{t('tasks.private')}</option>
      </select>
    </label>}
    {props.privateAgentLocked
      ? <p className="group-settings-meta" style={{ margin: "2px 0 6px" }}>{t("chat.groupSettings.privateAgentVisibilityLocked")}</p>
      : props.projectAgentLocked && <p className="group-settings-meta" style={{ margin: "2px 0 6px" }}>{t("chat.groupSettings.projectAgentVisibilityLocked")}</p>}
    {onPreferenceChange && <>
      <label className="group-settings-control"><span>{t('chat.preferences.pin')}</span><input className="group-settings-switch" type="checkbox" role="switch" disabled={readOnly || isBusy} checked={!!isPinned} onChange={e => void runAction(() => onPreferenceChange({is_pinned:e.target.checked}))} /></label>
      <label className="group-settings-control"><span>{t('chat.preferences.mute')}</span><input className="group-settings-switch" type="checkbox" role="switch" disabled={readOnly || isBusy} checked={!!isMuted} onChange={e => void runAction(() => onPreferenceChange({is_muted:e.target.checked}))} /></label>
    </>}
  </div>;

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
        {props.privateAgentLocked && <p className="group-settings-meta" style={{ padding: "8px 16px 0", margin: 0 }}>{t("chat.groupSettings.privateAgentVisibilityLocked")}</p>}
        {props.foreignProjectAgentMemberLocked && <p className="group-settings-meta" style={{ padding: "8px 16px 0", margin: 0 }}>{t("chat.groupSettings.foreignProjectAgentMemberLocked")}</p>}
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
            <div className="group-settings-meta">{t("chat.groupSettings.memberCount", { count: members.length })}</div>
          </div>
          <div className="group-settings-group">
            <div className="group-settings-group-label">
              {t("chat.groupSettings.members")} · {members.length}
            </div>
            <ul className="group-settings-card">
              {!manageMode && !readOnly && (
                <li className="group-settings-add-row">
                  <button type="button" className="group-settings-add-link" onClick={openAdd}>
                    <span className="group-settings-add-icon" aria-hidden="true">＋</span>
                    {t("chat.groupSettings.addMembers")}
                  </button>
                </li>
              )}
              {members.map(memberRow)}
            </ul>
          </div>
          <div className="group-settings-group">
            {settingsControls}
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
          <div className="group-settings-meta">{t("chat.groupSettings.memberCount", { count: members.length })}</div>
        </div>

        <div className="group-settings-content">
          {errorBanner}

          <div className="group-settings-section">
            <span className="group-settings-section-label">
              {t("chat.groupSettings.members")} · {members.length}
            </span>
            {!adding && !readOnly && (
              <button type="button" className="group-settings-add-link" onClick={openAdd}>
                ＋ {t("chat.groupSettings.addMembers")}
              </button>
            )}
          </div>

          {adding && (
            <div className="group-settings-addbox">
              <div className="group-settings-addbox-head">{t("chat.groupSettings.addMembersTitle")}</div>
              {props.foreignProjectAgentMemberLocked && (
                <p className="group-settings-meta" style={{ margin: "0 0 6px", padding: "6px 13px 0" }}>{t("chat.groupSettings.foreignProjectAgentMemberLocked")}</p>
              )}
              <div className="group-settings-pick-list">{pickerRows}</div>
              <div className="group-settings-addbox-foot">
                {addableAgents.length > 0 && (
                  <button
                    type="button"
                    className="chat-modal-btn-primary"
                    disabled={selectedAgentIds.length === 0 || isBusy}
                    onClick={submitAdd}
                  >
                    {t("chat.groupSettings.addCount", { count: selectedAgentIds.length })}
                  </button>
                )}
                <button type="button" className="chat-modal-btn-ghost" onClick={closeAdd}>
                  {t("chat.groupSettings.cancel")}
                </button>
              </div>
            </div>
          )}

          <ul className="group-settings-list">{members.map(memberRow)}</ul>

          {settingsControls}
        </div>
        <div className="group-settings-danger-zone">{dissolveBlock}</div>
      </aside>
    </>
  );
}
