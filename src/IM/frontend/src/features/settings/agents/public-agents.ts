import { listContacts } from "../../chat/contacts-api";

export async function listPublicAgents() {
  return (await listContacts("", "agent")).map(c => ({
    agent_id: c.agent_id!, user_id: c.user_id, display_name: c.display_name,
    description: c.owner_display_name ?? "", owner_id: c.owner_id,
    node_name: c.node_name, node_status: c.status, work_mode: c.work_mode,
  }));
}
