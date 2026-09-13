import { authFetchJson } from "../auth/auth-fetch";
import type { Actor } from "./chat-types";

/** Public chat identity; management configuration is deliberately separate. */
export interface Contact {
  user_id: string;
  kind: "human" | "agent";
  display_name: string;
  agent_id?: string;
  owner_id?: string;
  owner_display_name?: string;
  node_name?: string;
  status?: "online" | "offline";
  work_mode?: "global" | "single_thread";
}

export function contactActor(contact: Contact): Actor {
  return { type: contact.kind === "human" ? "user" : "agent", id: contact.agent_id ?? contact.user_id };
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
