import { authFetchJson } from "../auth/auth-fetch";
import type { Actor } from "./chat-types";

/** Public chat identity; management configuration is deliberately separate. */
export interface Contact {
  user_id: string;
  kind: "human" | "agent";
  username?: string;
  role?: "personal";
  lifecycle_disabled?: boolean;
  avatar_variant?: number | null;
  avatar_version?: string | null;
  display_name: string;
  agent_id?: string;
  owner_id?: string;
  owner_user_id?: string;
  space_id?: string;
  owner_display_name?: string;
  node_name?: string;
  status?: "online" | "offline";
  work_mode?: "global" | "single_thread";
  collaboration_scope?: "team" | "project" | "owner_only";
}

export function contactActor(contact: Contact): Actor {
  return {
    type: contact.kind === "human" ? "user" : "agent",
    id: contact.agent_id ?? contact.user_id,
    user_id: contact.user_id,
    display_name: contact.display_name,
    ...(contact.role ? { role: contact.role } : {}),
    ...(contact.avatar_variant !== undefined ? { avatar_variant: contact.avatar_variant } : {}),
    ...(contact.avatar_version !== undefined ? { avatar_version: contact.avatar_version } : {}),
  };
}

export async function listContacts(q = "", kind?: Contact["kind"]): Promise<Contact[]> {
  const items: Contact[] = [];
  let cursor: string | null = null;
  do {
    const params = new URLSearchParams({ q });
    if (kind) params.set("kind", kind);
    if (cursor) params.set("cursor", cursor);
    const page: { items: Contact[]; next_cursor: string | null } = await authFetchJson(`/im/v1/contacts?${params}`);
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}

export function getContact(userId: string): Promise<Contact> {
  return authFetchJson(`/im/v1/contacts/${encodeURIComponent(userId)}`);
}
