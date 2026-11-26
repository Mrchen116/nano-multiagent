import AVATAR_PALETTE from "../../../../../shared/avatar-palette.json";
import { createContext, useContext, useMemo, useLayoutEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { AssistantPortrait } from "./assistant-portrait";
import type { Actor, Conversation } from "../chat-types";



/** Deterministic color from a curated palette, seeded by the full display name. */
export function colorForAgentSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash << 5) - hash + seed.charCodeAt(i);
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length].background;
}

/** Soft palette backgrounds use dark lettering; explicit colors retain white. */
export function foregroundForAvatar(background: string): string {
  return AVATAR_PALETTE.find((color) => color.background === background)?.foreground ?? "#fff";
}

/** Avatar color for an agent, seeded by display_name (id fallback). */
export function colorForAgent(agent: { display_name?: string | null; agent_id?: string | null }): string {
  return colorForAgentSeed(agent.display_name || agent.agent_id || "");
}

/** Initials for an agent display name. The same name must render the same
 *  initials on every surface (settings list, detail, chat), so the rule lives
 *  here once instead of being copied per call site. */
export function initialsOf(displayName: string): string {
  const trimmed = displayName.trim();
  if (!trimmed) return "AG";
  return trimmed.slice(0, 2).toUpperCase();
}

// Every mounted surface reads the same account-scoped directory, including portals.
class IdentityDirectory {
  private sources = new Map<ReadonlyMap<string, Actor>, number>();
  private listeners = new Set<() => void>();

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  register(actors: ReadonlyMap<string, Actor>, priority: number) {
    this.sources.set(actors, priority);
    this.listeners.forEach(listener => listener());
    return () => {
      this.sources.delete(actors);
      this.listeners.forEach(listener => listener());
    };
  }

  get(id: string) {
    let result: Actor | undefined;
    let best = -1;
    for (const [actors, priority] of this.sources) {
      const actor = actors.get(id);
      if (actor && priority > best) {
        best = priority;
        result = actor;
      }
    }
    return result;
  }
}

const emptyDirectory = new IdentityDirectory();
const AvatarDirectory = createContext<IdentityDirectory | null>(null);

/** Agent-only APIs use logical IDs. Keep them separate from IM user UUIDs. */
export function agentAvatarId(id: string): string {
  return `agent:${id}`;
}

export function actorAvatarId(actor: Actor): string {
  return actor.avatar_id ?? actor.user_id ?? (actor.type === "agent" ? agentAvatarId(actor.id) : actor.id);
}

export function directAvatarId(chat: Conversation, self: string | null): string {
  const peer = chat.participants.find(actor => actor.type === "agent")
    ?? chat.participants.find(actor => actor.id !== self);
  return peer ? actorAvatarId(peer) : "";
}

/** Publish already-authorized identity data to every avatar in the account. */
export function AvatarIdentities({ actors, source = "history", children }: {
  actors: Actor[]; source?: "contacts" | "members" | "history" | "names"; children: ReactNode;
}) {
  const parent = useContext(AvatarDirectory);
  const [local] = useState(() => new IdentityDirectory());
  const directory = parent ?? local;
  const entries = useMemo(() => {
    const map = new Map<string, Actor>();
    for (const actor of actors) {
      map.set(actorAvatarId(actor), actor);
      if (actor.type === "agent") map.set(agentAvatarId(actor.id), actor);
    }
    return map;
  }, [actors]);
  useLayoutEffect(() => directory.register(entries, { contacts: 3, members: 2, history: 1, names: 0 }[source]),
    [directory, entries, source]);
  return <AvatarDirectory.Provider value={directory}>{children}</AvatarDirectory.Provider>;
}

/** Illustration for onboarding and the create-assistant action before an identity exists. */
export function AssistantIllustration({ size }: { size: number }) {
  return <AssistantPortrait size={size} />;
}

/** Display an IM identity. An unresolved ID gets a neutral placeholder. */
export function Avatar({ id, size = 32, status }: {
  id: string; size?: number; status?: "online" | "offline" | "running" | null;
}) {
  const directory = useContext(AvatarDirectory) ?? emptyDirectory;
  const actor = useSyncExternalStore(directory.subscribe, () => directory.get(id));
  const name = actor?.display_name || actor?.id || "?";
  const agentId = actor?.type === "agent" ? actor.id : undefined;
  const personal = actor?.role === "personal";
  const avatarVariant = actor?.avatar_variant;
  const initials = initialsOf(name);
  const bg = colorForAgentSeed(name);
  const dotSize = size * 0.28;
  return (
    <span className="chat-avatar" style={{ width: size, height: size }}>
      <span
        className="chat-avatar-face"
        style={{
          width: size,
          height: size,
          background: personal || agentId ? "transparent" : bg,
          color: foregroundForAvatar(bg),
          fontWeight: 600,
          fontSize: size * 0.35,
          letterSpacing: "-0.02em"
        }}
        aria-hidden="true"
      >
        {(personal || agentId) ? <AssistantPortrait personal={personal} seed={agentId} variant={avatarVariant} size={size} /> : initials.slice(0, 2).toUpperCase()}
      </span>
      {status && (
        <span
          className={`chat-avatar-status chat-avatar-status--${status}`}
          aria-label={status}
          style={{
            width: dotSize,
            height: dotSize,
            bottom: 1,
            right: 1,
            borderWidth: 2,
          }}
        />
      )}
    </span>
  );
}

/** Group mark shared by the sidebar and chat header. */
export function GroupAvatar({ size = 36, label, groupId }: { size?: number; label: string; groupId: string }) {
  const color = colorForAgentSeed(groupId);
  return (
    <span role="img" aria-label={label} style={{
      width: size, height: size, flexShrink: 0, display: "inline-flex",
      alignItems: "center", justifyContent: "center",
      borderRadius: size * 0.275, background: color, color: foregroundForAvatar(color)
    }}>
      <svg width={size * 0.525} height={size * 0.525} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 21a8 8 0 0 0-16 0" />
        <circle cx="10" cy="8" r="5" />
        <path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3" />
      </svg>
    </span>
  );
}

/* Lucide users-round, v0.468.0 — ISC License.
 * Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part
 * of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */
