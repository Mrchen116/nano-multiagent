import {
  chatAllowed,
  canAgentAccessConversation,
  groupHasPrivateAgent,
  groupHasProjectAgent,
  isFeishuBoundOwnerShadow,
  isOwnerInternalConversation,
  ownerDirect,
  providerFacts,
  publishCollaborationScopeTransitionEffects,
  reconcileProjectGroupLossInTx,
  snapshotProjectGroupDirects,
  storedProviderFacts,
} from './collaboration.js';
import { matchesExternalChannel } from './channels.js';
import { conversationName } from './conversation-name.js';
import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { chatTaskCards, interactiveResponse, modelInteractiveContent, type AgentPublication, type ChatPublicationReceipt, type TaskCardRef } from '@nano/product-contracts';
import { messageInput, messageMetadata, sendPrincipal, type MessageInput, type SendPrincipal, type SendMessageCommand } from './message-input.js';
import { MessageRecords, type MessageMetadata, type MessageEventFrame, type MessageRelayRecord } from './message-records.js';
import type { ChatAttachment, ChatMessage } from '@nano/product-contracts';
import { contactDetail, contactPage } from './contacts.js';
import { lifecycle, lifecycleAllows, requireLifecycle } from './agent-lifecycle.js';
import { captureTaskContextAccess, revokeLostTaskContextAccess, taskContextEligible, taskContextEntryAllowed, taskContextRevocation } from './task-context-access.js';
import {RelayDelivery} from './relay-delivery.js';
import { assertMessageAttempt, messageAttemptPayload } from './message-attempts.js';
import { executionCleanupRevision } from './agent-deletion.js';
import {
  defaultSpace,
  canAccessSpace,
  canActorAccess,
  agentAvailable,
  canAgentUseCompanySpace,
  canCollaborateWithAgent,
  canContactPersonalAgent,
  canTeamContactAgent,
  ownerAccount,
  sharesActivePrivateGroupWithAgent,
} from "./identity.js";
import { randomUUID } from "node:crypto";
import type { FastifyInstance, FastifyRequest } from "fastify";
import {
  all,
  one,
  now,
  chatId,
  fail,
  body,
  params,
  query,
  transaction,
  type Row,
  type ImContext,
} from "./context.js";
import { conversationAccess, conversationRowAccess, qualifiedUser, readableConversationIds } from "./conversation-access.js";
import { searchMessages } from './message-search.js';
import { assertThreadQuote, listUnread, markThreadRead, threadAddressesAgent, threadRelayMetadata, threadRootOrFail } from './threads.js';
import { validateTimeZone, type InteractionContext } from "@nano/product-contracts";
import { Interactions } from './interactions.js';
import { WorkerPermissionCards } from './worker-permission-cards.js';
import { InteractionBackground } from './interaction-background.js';

function readableMentions(content: string, members: Row[]): string {
  const names = new Map(members.map(user => [user.id, user.display_name || user.id]));
  return content.replace(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g,
    (_tag, targetId: string) => `@${names.get(targetId) || 'unknown'}`);
}

function assertProjectAgentCrossGroupShare(
  db: ImContext['db'],
  callerOwnerId: string,
  targetGroupId: string | null,
  finalMemberRows: Row[],
  confirmed: boolean,
): void {
  const globalProjectAgents = finalMemberRows.filter(
    m => m.agent_id && !m.is_stale && (m.collaboration_scope ?? 'team') === 'project' && m.work_mode === 'global',
  );
  if (!globalProjectAgents.length) return;
  const conflictingAgentIds: string[] = [];
  for (const projAgent of globalProjectAgents) {
    const targetExt = new Set(
      finalMemberRows
        .filter(
          m =>
            !m.agent_id &&
            !String(m.username).startsWith('agent:') &&
            !String(m.username).startsWith('shadow:') &&
            m.username !== 'system' &&
            m.user_owner_id !== projAgent.agent_owner_id,
        )
        .map(m => String(m.id)),
    );
    if (!targetExt.size) continue;
    const otherGroups = all(
      db,
      `SELECT c.id FROM conversations c
       JOIN conversation_participants cp ON cp.conversation_id=c.id
       JOIN users ua ON ua.id=cp.user_id
       WHERE ua.username=? AND c.id!=? AND c.type='group' AND c.visibility='private'
         AND c.external_source IS NULL AND c.dissolved_at IS NULL`,
      `agent:${projAgent.agent_id}`,
      targetGroupId ?? '',
    );
    const hasDifferentExternalGroup = otherGroups.some(og => {
      const otherExt = new Set(
        all(
          db,
          `SELECT u.id FROM conversation_participants cp
           JOIN users u ON u.id=cp.user_id
           WHERE cp.conversation_id=? AND u.username NOT LIKE 'agent:%' AND u.username NOT LIKE 'shadow:%'
             AND u.username!='system' AND u.owner_id!=?`,
          og.id,
          projAgent.agent_owner_id,
        ).map(r => String(r.id)),
      );
      if (!otherExt.size) return false;
      return otherExt.size !== targetExt.size || [...targetExt].some(uid => !otherExt.has(uid));
    });
    if (hasDifferentExternalGroup) {
      if (projAgent.agent_owner_id !== callerOwnerId || !confirmed) {
        conflictingAgentIds.push(String(projAgent.agent_id));
      }
    }
  }
  if (conflictingAgentIds.length) {
    fail(409, {
      code: 'project_agent_cross_group_confirmation_required',
      agent_ids: [...new Set(conflictingAgentIds)],
      message:
        'This global project assistant already participates in another private group with different external members. Confirm sharing its global memory and workspace context across groups.',
    });
  }
}

function broadcastRestoredProjectDirects(db: ImContext['db'], groupId: string, s: Messaging): void {
  const projectAgents = all(
    db,
    `SELECT ap.*, u.id AS agent_user_id FROM conversation_participants cp
     JOIN users u ON u.id=cp.user_id
     JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id
     WHERE cp.conversation_id=? AND ap.is_stale=0 AND ap.collaboration_scope='project'`,
    groupId,
  );
  for (const agent of projectAgents) {
    const directs = all(
      db,
      `SELECT c.* FROM conversations c
       JOIN conversation_participants p ON p.conversation_id=c.id
       WHERE p.user_id=? AND c.type='direct' AND c.external_source IS NULL AND c.dissolved_at IS NULL`,
      agent.agent_user_id,
    ).filter(c => !isOwnerInternalConversation(db, c.id, agent.owner_id) && canAgentAccessConversation(db, agent, c));
    for (const d of directs) {
      s.membership(d.id, s.members(d.id).map(u => u.id));
    }
  }
}
export class Messaging {
  readonly records: MessageRecords;
  readonly workerPermissions: WorkerPermissionCards;
  readonly interactions: Interactions;
  readonly background: InteractionBackground;
  readonly delivery:RelayDelivery;
  constructor(readonly ctx: ImContext) {
    this.workerPermissions=new WorkerPermissionCards(ctx);
    this.interactions=new Interactions(ctx);this.delivery=new RelayDelivery(ctx);
    this.background=new InteractionBackground(ctx.db, this.interactions);
    this.records=new MessageRecords(ctx.db,{interactions:this.interactions,agentUserId:id=>this.agentUser(id).id,
      messageWait:id=>this.ctx.updates?.messageWait(id),publish:(frame,enabled)=>this.publishEvent(frame,enabled)});
  }
  private publishEvent(frame:MessageEventFrame,publish:boolean):void {
    if(publish)this.publishCommitted(frame);
    // The PA source-event trigger does not observe streaming text.
    if(frame.event_type==='message.delta')return;
    for(const binding of all(this.db,"SELECT DISTINCT b.* FROM personal_agent_bindings b JOIN pa_source_events e ON e.binding_id=b.binding_id JOIN pa_policies p ON p.binding_id=b.binding_id WHERE e.source_event_id=?",frame.event_id))this.ctx.personal?.wake(binding);
  }
  /** Broadcast a frame whose durable event already committed, without repeating the wake policy.
   * Notes:
   *   Transaction owners that must not announce a rolled-back write call this after commit.
   */
  publishCommitted(frame:MessageEventFrame):void {
    this.ctx.gateway.broadcast('conversation-readers',frame);
  }
  get db() {
    return this.ctx.db;
  }
  principal(req: FastifyRequest): Row {
    const token = (req.headers.authorization ?? "").replace(/^Bearer\s+/i, "");
    const gateway = this.ctx.gateway.authenticate(token);
    return gateway ? { ...gateway, kind: "gateway" } : this.ctx.identity.authenticateRequest(req);
  }
  agentUser(agentId: string): Row {
    const a = one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0", agentId);
    if (!a) fail(404, "agent not found");
    let u = one(this.db, "SELECT * FROM users WHERE username=?", `agent:${agentId}`);
    if (!u) {
      const id = chatId("u_");
      this.db
        .prepare(
          `INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES(?,?,?,?,?,'active')`,
        )
        .run(id, `agent:${agentId}`, a.display_name, a.owner_id, now());
      u = one(this.db, "SELECT * FROM users WHERE id=?", id);
    }
    return { ...u!, owner_id: a.owner_id, space_id: a.space_id };
  }
  actor(u:Row) {return {...this.records.actor({id:u.id,username:u.username,display_name:u.display_name,is_stale:u.is_stale}), ...(u.is_deleted ? {is_deleted:true} : {})};}
  members(id: string): Row[] {
    return all(
      this.db,
      `SELECT u.*,ap.is_stale,d.state='deleted' AS is_deleted FROM conversation_participants cp JOIN users u ON u.id=cp.user_id LEFT JOIN agent_profiles ap ON u.username GLOB 'agent:*' AND ap.agent_id=substr(u.username,7) LEFT JOIN agent_deletions d ON d.agent_id=ap.agent_id WHERE cp.conversation_id=? ORDER BY cp.rowid`,
      id,
    );
  }
  mentionedUsers(conversationId:string,content:string):Row[] {
    const targets = new Set([...content.matchAll(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g)].map(match => match[1]));
    return this.members(conversationId).filter(user=>targets.has(user.id));
  }
  /** Resolve the same XML mention format used by Web and native clients. */
  mentionedAgents(conversationId: string, content: string): string[] {
    return this.mentionedUsers(conversationId,content).filter(user=>user.username.startsWith("agent:")).map(user=>user.username.slice(6));
  }
  access(principal: Row, id: string, agentId?: string, mode: "read" | "write" = "read"): Row {
    const c = one(this.db, "SELECT * FROM conversations WHERE id=?", id);
    if (!c) fail(404, "conversation_id not found");
    let uid = principal.id;
    if (principal.kind === "gateway") {
      const agent = agentId
        ? one(
            this.db,
            "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND owner_id=? AND is_stale=0",
            agentId,
            principal.node_id,
            principal.owner_id,
          )
        : undefined;
      const personal=agentId?one(this.db,"SELECT * FROM personal_agent_bindings WHERE agent_id=?",agentId):undefined;
      if(personal) {
        this.ctx.personal!.authority(principal,{agent_id:agentId});
        if(mode==="write" && !this.ctx.personal!.ownerConversation(personal,id))fail(403,"personal_reviewed_delivery_required");
        if(!this.ctx.personal!.sourceAllowed(personal,id,mode))fail(404,"conversation_id not found");
        return this.ctx.personal!.sourceAccess(personal,id,mode)!;
      }
      if (!agent || !agentAvailable(this.db, agent)) fail(404, "conversation_id not found");
      if ((agent.collaboration_scope ?? "team") === "owner_only" && !isOwnerInternalConversation(this.db, c.id, agent.owner_id) && !isFeishuBoundOwnerShadow(this.db, c, agent)) {
        if (mode === "write") fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Private and can only communicate with its owner and the owner's own assistants." });
        fail(404, "conversation_id not found");
      }
      if (!canAgentAccessConversation(this.db, agent, c)) {
        if (mode === "write" && (agent.collaboration_scope ?? "team") === "project") {
          fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Project scope and can only communicate within shared private groups and active project members." });
        }
        fail(404, "conversation_id not found");
      }
      uid = this.agentUser(agentId!).id;
    }
    if (principal.kind !== "gateway") this.ctx.identity.requireSpace(principal, c.space_id);
    const access = conversationRowAccess(this.db,c,uid);
    if (!access || (mode === "write" && !access.is_member)) fail(404,"conversation_id not found");
    if (mode === "write" && access.dissolved_at) fail(409,{code:"conversation_dissolved",message:"This conversation is read-only after dissolution"});
    if (mode === "write" && !access.can_write) {
      if (access.write_blocked_reason === "agent_private") {
        fail(403, { code: "agent_private", message: "This assistant is currently private and unavailable for external messages." });
      }
      if (access.write_blocked_reason === "agent_project_restricted") {
        fail(403, { code: "agent_project_restricted", message: "This assistant is only available to members sharing an active private group with it." });
      }
      fail(404, "conversation_id not found");
    }
    return access;
  }

  /** Project an authorized conversation for a reader.
   *
   * Args:
   *   id: Stable conversation ID.
   *   userId: Identity whose access and preferences are checked.
   *   readerId: Identity used only for the display name; PA reads may use owner access.
   * Returns:
   *   Conversation metadata with a reader-relative title and unchanged access flags.
   */
  conversation(id: string, userId: string, readerId = userId): Row {
    const c = one(this.db, "SELECT * FROM conversations WHERE id=?", id)!;
    const access = c && conversationRowAccess(this.db,c,userId);
    if (!access) fail(404,"conversation_id not found");
    const members = this.members(id);
    const lastMessage = c.last_message_at ? one(this.db,
      `SELECT m.content, m.system_notice_json, m.sender_type, m.sender_display_name, m.sender_source_id,
              u.display_name AS account_display_name, i.message_id AS card_id, i.preview_title,
              CASE WHEN i.message_id IS NOT NULL THEN json_extract(m.attachments_json, '$[0].file_name') END AS card_attachment_name
       FROM messages m LEFT JOIN message_interactive i ON i.message_id=m.id
       LEFT JOIN users u ON u.id=m.sender_user_id
       WHERE m.conversation_id=? AND m.thread_root_id IS NULL AND m.created_at=? ORDER BY m.rowid DESC LIMIT 1`,
      id, c.last_message_at,
    ) : undefined;
    // Stored previews can end inside a mention tag. Resolve from the full message
    // before truncating so existing conversations also recover on refresh.
    const storedPreview = c.last_message_preview || lastMessage?.card_attachment_name || c.last_message_preview;
    const preview = lastMessage?.content ? readableMentions(lastMessage.content.trim(), members).slice(0, 120) || storedPreview : storedPreview;
    const senderName = c.type === "group" && !lastMessage?.system_notice_json
      && (lastMessage?.sender_type === "user" || lastMessage?.sender_type === "agent")
      ? lastMessage.sender_display_name?.trim() || lastMessage.sender_source_id || lastMessage.account_display_name?.trim() || null
      : null;
    const prefs =
      one(
        this.db,
        "SELECT * FROM conversation_participants WHERE conversation_id=? AND user_id=?",
        id,
        userId,
      ) ?? {};
    const agents = members.filter((u) => u.username.startsWith("agent:"));
    return {
      ...Object.fromEntries(
        [
          "id",
          "title",
          "type",
          "owner_id",
          "space_id",
          "creator_id",
          "last_message_preview",
          "last_message_at",
          "config_agent_id",
          "config_profile_version",
          "external_source",
          "external_chat_id",
          "created_at",
        ].map((key) => [key, c[key]]),
      ),
      title: conversationName(c, members, readerId),
      visibility:c.visibility, dissolved_at:c.dissolved_at,
      is_member:access.is_member,is_observer:access.is_observer,can_write:access.can_write,write_blocked_reason:access.write_blocked_reason ?? null,can_join:access.can_join,can_change_visibility:access.can_change_visibility,
      execution_cleanup_revision: executionCleanupRevision(this.ctx,id),
      participants: members.map((u) => this.actor(u)),
      participant_ids: members.map((u) => u.id),
      direct_kind:
        c.type === "direct"
          ? agents.length === 2
            ? "agent-agent"
            : agents.length
              ? "user-agent"
              : "user-user"
          : null,
      is_pinned: !!prefs.is_pinned,
      is_muted: !!prefs.is_muted,
      unread_count: prefs.unread_count ?? 0,
      last_message_preview: preview,
      last_message_sender_name: senderName,
      last_message_card: !preview && lastMessage?.card_id ? {title: lastMessage.preview_title} : null,
      last_message_system_notice: JSON.parse(lastMessage?.system_notice_json ?? "null"),
      run_state: one(
        this.db,
        "SELECT 1 FROM messages WHERE conversation_id=? AND delivery_status='running'",
        id,
      )
        ? "running"
        : "idle",
      source_agent_id:
        c.config_agent_id ?? (agents.length === 1 ? (agents[0]?.username.slice(6) ?? null) : null),
      source_node_id:
        c.config_agent_id || agents.length === 1
          ? (one(
              this.db,
              "SELECT node_id FROM agent_profiles WHERE agent_id=?",
              c.config_agent_id ?? agents[0]!.username.slice(6),
            )?.node_id ?? null)
          : null,
    };
  }
  conversations(userId: string, scope = "joined"): Row[] {
    if (!["joined","public"].includes(scope)) fail(400,"invalid scope");
    if (!qualifiedUser(this.db,userId)) fail(403,"account access required");
    if (scope === "public") return all(this.db,"SELECT id FROM conversations WHERE space_id='company:default' AND type='group' AND visibility='public' AND dissolved_at IS NULL ORDER BY COALESCE(last_message_at,created_at) DESC").filter(c=>conversationAccess(this.db,c.id,userId)).map(c=>this.conversation(c.id,userId));
    return all(this.db, `SELECT c.id FROM conversations c
      LEFT JOIN conversation_participants p ON p.conversation_id=c.id AND p.user_id=?
      WHERE c.dissolved_at IS NULL AND (p.user_id IS NOT NULL OR (c.type='direct' AND EXISTS (
        SELECT 1 FROM conversation_participants cp JOIN users u ON u.id=cp.user_id
        JOIN agent_profiles a ON u.username GLOB 'agent:*' AND a.agent_id=substr(u.username,7) WHERE cp.conversation_id=c.id AND (a.owner_id=? OR EXISTS(SELECT 1 FROM personal_agent_bindings b WHERE b.agent_id=a.agent_id AND b.owner_user_id=?)))))
      ORDER BY COALESCE(p.is_pinned,0) DESC,COALESCE(c.last_message_at,c.created_at) DESC`,userId,userId,userId)
      .filter(c => conversationAccess(this.db,c.id,userId)).map(c => this.conversation(c.id,userId));
  }

  resolveParticipants(principal: Row, actors: Row[], ids: string[] = [], group = true, space?: string): string[] {
    let result = ids.map((id) =>
      id.startsWith("agent:") ? this.agentUser(id.slice(6)).id : id.replace(/^user:/, ""),
    );
    const actorAccount = principal.kind === "agent" ? ownerAccount(this.db, principal.owner_id) : principal;
    for (const a of actors) {
      if (a.type === "agent") {
        const profile = one(
          this.db,
          "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0",
          a.id,
        );
        if (!profile) fail(404, "agent not accessible");
        if (group && profile.owner_id !== principal.owner_id) {
          if (canCollaborateWithAgent(this.db, actorAccount, profile)) {
            fail(403, { code: "agent_owner_required", message: "Only the assistant owner can add this assistant to a group (agent not accessible)." });
          }
          fail(404, "agent not accessible");
        }
        result.push(this.agentUser(a.id).id);
      } else if (a.type === "user") result.push(a.id);
      else fail(400, "invalid actor type");
    }
    result = [...new Set(result)];
    const callerAgentProfile = principal.kind === "agent" && principal.username?.startsWith("agent:")
      ? one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=?", principal.username.slice(6))
      : undefined;
    for (const id of result) {
      const u = one(this.db, "SELECT * FROM users WHERE id=?", id);
      if (!u) fail(404, "participant not found");
      const profile = u.username.startsWith("agent:")
        ? one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=?", u.username.slice(6)) : undefined;
      const callerScope = callerAgentProfile?.collaboration_scope ?? "team";
      if (callerAgentProfile && (profile ? profile.owner_id : u.owner_id) !== principal.owner_id) {
        if (callerScope === "owner_only") {
          const ownerCouldSee = profile
            ? canCollaborateWithAgent(this.db, actorAccount, profile)
            : canAccessSpace(actorAccount, "company:default") && u.membership_status === "active";
          if (ownerCouldSee) {
            fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Private and can only communicate with its owner and the owner's own assistants." });
          }
        } else if (callerScope === "project" && !sharesActivePrivateGroupWithAgent(this.db, id, callerAgentProfile.agent_id)) {
          const ownerCouldSee = profile
            ? canCollaborateWithAgent(this.db, actorAccount, profile)
            : canAccessSpace(actorAccount, "company:default") && u.membership_status === "active";
          if (ownerCouldSee) {
            fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Project scope and can only communicate with members sharing an active private group with it." });
          }
        }
      }
      const sameOwnerAgent = !!profile && profile.owner_id === principal.owner_id && agentAvailable(this.db, profile);
      const visible = profile
        ? (sameOwnerAgent && (canAccessSpace(actorAccount, profile.space_id) || principal.kind === "agent")) || canCollaborateWithAgent(this.db, actorAccount, profile)
        : u.id === principal.id || u.owner_id === principal.owner_id || (canActorAccess(this.db, principal.id, "company:default") && u.membership_status === "active");
      if (!visible || (space && !canActorAccess(this.db, id, space))) fail(404, "participant not found");
      if (group && u.username.startsWith("agent:") && !one(this.db,
        "SELECT 1 FROM agent_profiles WHERE agent_id=? AND owner_id=? AND is_stale=0", u.username.slice(6), principal.owner_id)) {
        fail(403, { code: "agent_owner_required", message: "Only the assistant owner can add this assistant to a group (agent not accessible)." });
      }
    }
    return result;
  }
  createConversation(p: Row, b: Row, force = false, inheritedSpace?: string): Row {
    if (!b.title?.trim() || !["direct", "group"].includes(b.type))
      fail(422, "title and valid type required");
    const ids = this.resolveParticipants(
      p,
      b.participants ?? [],
      b.participant_ids ?? [],
      b.type === "group",
    );
    if (!ids.length && b.type !== "group") fail(422, "participants required");
    if (b.visibility !== undefined && !["public","private"].includes(b.visibility)) fail(422,"invalid visibility");
    if (p.kind === "agent" && ids.some(id=>id !== p.id && one(this.db,"SELECT username FROM users WHERE id=?",id)?.username.startsWith("agent:")))
      fail(403,"An Agent can add only itself, not other Agents");
    if(b.type==='direct' && ids.filter(id=>id!==p.id).length===1) {
      const canonical=one(this.db,"SELECT b.* FROM personal_agent_bindings b JOIN users u ON u.username='agent:'||b.agent_id WHERE b.owner_user_id=? AND u.id=? AND b.status='active'",p.id,ids.find(id=>id!==p.id)!);
      if(canonical)return this.conversation(canonical.conversation_id,p.id);
    }
    const fullIds = ids.includes(p.id) ? [...ids] : [p.id, ...ids];
    const memberRows = fullIds.map(id => one(this.db, `SELECT u.id,u.username,u.owner_id AS user_owner_id,ap.agent_id,ap.owner_id,ap.owner_id AS agent_owner_id,ap.space_id,ap.collaboration_scope,ap.work_mode,ap.profile_version,ap.is_stale
      FROM users u LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id WHERE u.id=?`, id)).filter(Boolean) as Row[];
    const profiles = memberRows.filter(row => !!row.agent_id);
    const callerProfile = p.kind === "agent" ? profiles.find(row => row.id === p.id) : undefined;
    const hasPrivateAgent = profiles.some(row => (row.collaboration_scope ?? "team") === "owner_only");
    const hasProjectAgent = profiles.some(row => (row.collaboration_scope ?? "team") === "project");
    const allSameOwner = memberRows.every(row => (row.agent_id ? row.agent_owner_id : row.user_owner_id) === p.owner_id);
    if (callerProfile && (callerProfile.collaboration_scope ?? "team") === "owner_only" && (!allSameOwner || b.visibility === "public")) {
      fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Private and can only communicate with its owner and the owner's own assistants." });
    }
    if (callerProfile && (callerProfile.collaboration_scope ?? "team") === "project" && b.visibility === "public") {
      fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Project scope and cannot create public groups." });
    }
    if (b.type === "group" && hasPrivateAgent) {
      if (!allSameOwner) {
        fail(409, { code: "private_agent_in_group", message: "Private assistants can only share groups with their owner and same-owner assistants." });
      }
      if (b.visibility === "public") {
        fail(409, { code: "private_agent_in_group", message: "Groups containing a private assistant must be private." });
      }
    }
    if (b.type === "group" && hasProjectAgent && b.visibility === "public") {
      fail(409, { code: "project_agent_requires_private_group", message: "Groups containing a project assistant must be private." });
    }
    if (b.type === "group" && hasProjectAgent) {
      assertProjectAgentCrossGroupShare(this.db, p.owner_id, null, memberRows, b.confirm_project_context_share === true && p.kind !== "agent");
    }
    const actorAccount = p.kind === "agent" ? ownerAccount(this.db, p.owner_id) : p;
    const contactingTeamAgent = profiles.some(profile => profile.agent_owner_id !== p.owner_id && canCollaborateWithAgent(this.db, actorAccount, profile));
    const sharedTeamGroup = b.type === "group" && !allSameOwner && profiles.some(profile => canAgentUseCompanySpace(this.db, profile)
      && fullIds.some(id => !canActorAccess(this.db, id, profile.space_id)));
    const mixedOwnerSpaces = allSameOwner && profiles.length > 0 && (
      new Set(profiles.map(profile => profile.space_id)).size > 1
      || (b.type === "group" && (hasPrivateAgent || hasProjectAgent) && !!ownerAccount(this.db, p.owner_id)?.personal_space_enabled)
    );
    const explicitPublicCompanyGroup = b.type === "group" && b.visibility === "public" && !hasPrivateAgent && !hasProjectAgent && !profiles.length && canAccessSpace(actorAccount, "company:default");
    const ownerDefaultSpace = defaultSpace(ownerAccount(this.db, p.owner_id) ?? p);
    const space = inheritedSpace ?? (
      contactingTeamAgent || sharedTeamGroup || explicitPublicCompanyGroup
        ? "company:default"
        : mixedOwnerSpaces
          ? ownerDefaultSpace
          : profiles[0]?.space_id ?? (ids.some(id => id !== p.id) && !profiles.length && !allSameOwner ? "company:default" : ownerDefaultSpace)
    );
    // Runtime users carry no human membership; their live profile and owner confer scope.
    if (p.kind === "agent") {
      if (!canActorAccess(this.db, p.id, space)) fail(404, "resource not accessible");
    } else this.ctx.identity.requireSpace(p, space);
    if (ids.some(id => !canActorAccess(this.db, id, space))) fail(404, "participant not found");
    if (!ids.includes(p.id)) ids.unshift(p.id);
    if (b.type === "direct" && ids.length !== 2)
      fail(400, "direct conversation requires two participants");
    const pairKey = [...ids].sort().join("|");
    const key = b.type === "direct" && !force ? `${space}|${pairKey}` : null;
    if (key) {
      const candidateSpaces = allSameOwner
        ? [...new Set([space, `personal:${p.owner_id}`, "company:default"])]
        : [space];
      for (const candidateSpace of candidateSpaces) {
        const existing = one(this.db, "SELECT id FROM conversations WHERE space_id=? AND (direct_key=? OR direct_key=?)", candidateSpace, `${candidateSpace}|${pairKey}`, pairKey);
        if (existing && conversationAccess(this.db, existing.id, p.id)) return this.conversation(existing.id, p.id);
      }
    }
    const id = chatId("c_");
    const effectiveVisibility = b.type === "group" && space === "company:default" && !hasPrivateAgent && !hasProjectAgent ? b.visibility ?? "public" : "private";
    transaction(this.db, () => {
      this.db
        .prepare(
          "INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at,space_id,visibility) VALUES(?,?,?,?,?,?,?,?,?)",
        )
        .run(id, b.title.trim(), b.type, p.owner_id, p.id, key, now(), space, effectiveVisibility);
      for (const uid of ids)
        this.db
          .prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)")
          .run(id, uid);
      const profiles = ids
        .map((uid) =>
          one(
            this.db,
            "SELECT ap.agent_id,ap.profile_version FROM agent_profiles ap JOIN users u ON u.username='agent:'||ap.agent_id WHERE u.id=?",
            uid,
          ),
        )
        .filter(Boolean);
      if (profiles.length === 1)
        this.db
          .prepare("UPDATE conversations SET config_agent_id=?,config_profile_version=? WHERE id=?")
          .run(profiles[0]!.agent_id, profiles[0]!.profile_version, id);
    });
    this.membership(id, ids);
    if (b.type === "group" && effectiveVisibility === "private" && hasProjectAgent) {
      broadcastRestoredProjectDirects(this.db, id, this);
    }
    return this.conversation(id, p.id);
  }
  membership(id: string, recipients: string[]) {
    this.ctx.gateway.broadcast(recipients, {
      op: "event",
      event_type: "conversation.membership_changed",
      data: { conversation_id: id },
    });
  }
  /** Read the public projection through its persistence owner. */
  message(id:string):ChatMessage {return this.records.message(id);}
  /** Persist and publish an event using the established recipient/wake policy. */
  event(id:string,messageId:string|null,type:string,data:object,status='completed',publish=true):MessageEventFrame {return this.records.event(id,messageId,type,data,status,publish);}
  /** Insert controlled message metadata after the caller has authorized the sender. */
  insertMessage(cId:string,sender:string,type:string,content:string,attachments:ChatAttachment[]=[],key:string|null=null,status='completed',extra:MessageMetadata={}):ChatMessage {
    return this.records.insert(cId,sender,type,content,attachments,key,status,extra);
  }
  copyReferences(source: string, target: string, value: string): string {
    return value.replace(
      /\/im\/v1\/conversations\/([^/\s]+)\/(images|attachments)\/([\w-]+)/g,
      (match, cId, kind, imageId) => {
        if (cId !== source || source === target) return match;
        const old = one(
          this.db,
          "SELECT * FROM message_images WHERE conversation_id=? AND image_id=?",
          source,
          imageId,
        );
        if (!old) fail(404, "resource not found");
        const key = `fork:${source}:${imageId}`;
        let resource = one(
          this.db,
          "SELECT * FROM message_images WHERE conversation_id=? AND source_key=?",
          target,
          key,
        );
        if (!resource) {
          const id = randomUUID().replaceAll("-", "");
          this.db
            .prepare("INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)")
            .run(
              id,
              target,
              key,
              old.sha256,
              old.content_type,
              old.file_name,
              old.byte_size,
              old.storage_name,
            );
          resource = { image_id: id };
        }
        return `/im/v1/conversations/${target}/${kind}/${resource.image_id}`;
      },
    );
  }
  validateReferences(p: Row, cId: string, value: string, agentId?: string): string {
    return value.replace(
      /(?:(https?:\/\/[^\s/]+))?(\/im\/v1\/conversations\/([^/\s]+)\/(?:images|attachments)\/([\w-]+))/g,
      (match, origin, path, source, image) => {
        if (origin && new URL(origin).origin !== new URL(this.ctx.publicUrl).origin) return match;
        this.access(p, source, agentId);
        if (
          !one(
            this.db,
            "SELECT 1 FROM message_images WHERE conversation_id=? AND image_id=?",
            source,
            image,
          )
        )
          fail(404, "resource not found");
        return source === cId ? match : this.copyReferences(source, cId, path);
      },
    );
  }
  /** Authenticate private provider ingestion separately from outward message delivery. */
  incomingExternalSource(principal:Row,id:string,agentId:string):Row {
    if(principal.kind!=='gateway')fail(403,'gateway_credential_required');
    const binding=this.ctx.personal!.authority(principal,{agent_id:agentId});
    const c=one(this.db,'SELECT * FROM conversations WHERE id=? AND config_agent_id=? AND owner_id=?',id,agentId,binding.owner_id);
    const channel=c?all(this.db,'SELECT * FROM agent_channels WHERE agent_id=? AND node_id=? AND owner_id=? AND provider=? AND enabled=1',agentId,binding.node_id,binding.owner_id,c.external_source)
      .find(row=>matchesExternalChannel(row,c)):undefined;
    if(!c||!channel||!this.ctx.personal!.sourceAllowed(binding,id))fail(403,'incoming_source_not_verified');
    return {...c,owner_user_id:binding.owner_user_id};
  }
  /** Mirror authenticated provider input only into its private owner/Agent shadow. */
  incomingExternal(req:FastifyRequest):ChatMessage {
    const p=this.principal(req),id=params(req).conversation_id,b=messageInput(req.body),agentId=query(req).agent_id;
    const c=this.incomingExternalSource(p,id,agentId);
    if(typeof b.sender_source_id!=='string'||!b.sender_source_id||typeof b.content!=='string')fail(422,'incoming_source_required');
    if(c.type==='direct'&&!c.external_chat_id.endsWith(`:dm:${b.sender_source_id}`))fail(403,'incoming_actor_mismatch');
    const attachments=b.attachments??[];
    if(!Array.isArray(attachments)||attachments.length>5)fail(422,'invalid_attachments');
    const key=req.headers['idempotency-key'];if(typeof key!=='string'||!key.startsWith('shadow:'))fail(422,'incoming_receipt_required');
    const old=one(this.db,'SELECT id FROM messages WHERE conversation_id=? AND caller_idempotency_key=?',id,key);if(old)return this.message(old.id);
    const content=this.validateReferences(p,id,b.content,agentId);
    const safeAttachments=attachments.map(a=>({url:this.validateReferences(p,id,a.url!,agentId),content_type:a.content_type,file_name:a.file_name}));
    return this.insertMessage(id,c.owner_user_id,'user',content,safeAttachments,key,'completed',{
      sender_source_id:b.sender_source_id,sender_display_name:b.sender_display_name,created_at:b.created_at,timezone:b.timezone,provider_facts:providerFacts(b.provider_facts),trackReceipts:true,
    });
  }
  /** Resolve an original message only inside the caller's authorized destination.
   *
   * Args:
   *   conversationId: Destination whose access was already checked by the caller.
   *   messageId: Optional original IM message identity.
   * Returns:
   *   Server-owned original content and sender, or undefined for an ordinary message.
   * Raises:
   *   Error: The target is absent, belongs to another chat, or cannot be replied to.
   */
  replyReference(conversationId:string,messageId?:string):ChatMessage['reply_to'] {
    if(messageId===undefined)return;
    if(typeof messageId!=='string'||!messageId)fail(422,'invalid reply target');
    const original=this.records.find(messageId);
    if(!original||original.conversation_id!==conversationId)fail(404,'reply target not found');
    if(!['user','agent'].includes(original.sender_type)||!['completed','sent','pending'].includes(original.delivery_status))fail(422,'reply target is not available');
    const source=this.message(original.id);
    return {message_id:source.id,sender:source.sender,content:source.content,attachments:source.attachments,
      ...(source.interactive ? {interactive:modelInteractiveContent(source.interactive)} : {})};
  }

  private publicationAttachments(id: string, attachments: AgentPublication['attachments']) {
    const submitted = attachments ?? [];
    if (submitted.length > 5) fail(422, 'too many attachments');
    return submitted.map(({url}) => {
      const match = url?.match(/^\/im\/v1\/conversations\/([^/]+)\/(?:images|attachments)\/([\w-]+)$/);
      if (!match || match[1] !== id) fail(422, 'attachment must belong to the destination conversation');
      const row = one(this.db, 'SELECT file_name,content_type FROM message_images WHERE conversation_id=? AND image_id=?', id, match[2]);
      if (!row) fail(404, 'attachment not found');
      return {url, file_name:row.file_name, content_type:row.content_type};
    });
  }

  private validateTaskCardRefs(principal: Row, agentId: string | undefined, refs: TaskCardRef[] | null | undefined): TaskCardRef[] | undefined {
    if (!refs?.length) return undefined;
    let validated: TaskCardRef[];
    try { validated = chatTaskCards(refs); } catch (error) { fail(422, (error as Error).message); }
    for (const ref of validated!) {
      const row = one(this.db, 'SELECT conversation_id, document_json FROM task_graphs WHERE graph_id=?', ref.graph_id);
      if (!row) fail(404, 'task card target not found');
      this.access(principal, row.conversation_id, agentId, 'read');
      const doc = JSON.parse(row.document_json);
      if (!Array.isArray(doc.nodes) || !doc.nodes.some((n: Row) => n.id === ref.node_id)) {
        fail(404, 'task card node not found');
      }
    }
    return validated!;
  }

  /** Commit a validated explicit publication under its existing dispatch identity. */
  publishAgent(principal:Extract<SendPrincipal,{kind:'gateway'}>,agentId:string,operationId:string|undefined,p:AgentPublication):ChatPublicationReceipt {
    const db=this.db;
    const key = operationId ? `${agentId}:${operationId}` : null;
    let interactive;
    try { interactive = interactiveResponse(p.interactive); } catch (error) { fail(422, (error as Error).message); }
    const previous = key
      ? this.records.publication(key)
      : undefined;
    if (previous) {
      this.access(principal, previous.conversation_id, agentId);
      const saved = this.message(previous.message_id);
      const savedInteractive = this.interactions.publication(previous.message_id);
      if (saved.reply_to?.message_id !== p.reply_to_message_id || saved.thread_root_message_id !== p.in_thread_of || saved.content !== p.text.trim() || sortedJsonAscii(saved.attachments.map(item => item.url)) !== sortedJsonAscii((p.attachments ?? []).map(item => item.url))
        || sortedJsonAscii(saved.task_cards ?? []) !== sortedJsonAscii(p.task_cards ?? [])
        || sortedJsonAscii(savedInteractive ?? null) !== sortedJsonAscii(interactive ?? null)
        || this.resolveTarget(agentId, p.to) !== previous.conversation_id) fail(409, 'Agent publication identity conflict');
      return {
        conversation_id: previous.conversation_id,
        message_id: previous.message_id,
        target_kind: previous.target_kind,
        target_id: previous.target_id,
        source_agent_id: agentId,
      };
    }
    const id = this.resolveTarget(agentId, p.to);
    const personal=one(db,"SELECT * FROM personal_agent_bindings WHERE agent_id=?",agentId);
    if(personal && id!==personal.conversation_id) fail(403,"personal_reviewed_delivery_required");
    this.access(principal, id, agentId, "write");
    const attachments = this.publicationAttachments(id, p.attachments);
    const taskCards = this.validateTaskCardRefs(principal, agentId, p.task_cards);
    const threadRoot=threadRootOrFail(db,id,p.in_thread_of);
    const replyTo=this.replyReference(id,p.reply_to_message_id);
    assertThreadQuote(db,id,threadRoot,replyTo?.message_id);
    const rawTarget = p.to.replace(/^(?:conversation|agent|user):/, "");
    const targetUser = one(
      db,
      "SELECT * FROM users WHERE id=? OR username=?",
      rawTarget,
      `agent:${rawTarget}`,
    );
    const targetKind =
      p.to.startsWith("conversation:") || rawTarget === id
        ? "conversation_id"
        : targetUser?.username.startsWith("agent:")
        ? "agent_id"
        : "user_id";
    const targetId = targetKind === "agent_id" ? targetUser!.username.slice(6) : rawTarget;
    const m = transaction(db, () => {
    const created = this.insertMessage(
      id,
      this.agentUser(agentId).id,
      "agent",
      p.text.trim(),
      attachments,
      key,
      'completed',
      { interactive, ...(taskCards ? { task_cards: taskCards } : {}), reply_to:replyTo, thread_root_id:threadRoot, publish: false },
    );
    if (p.background_returns)
      this.records.background(created.id,p.background_returns);
    if(key)this.records.savePublication({dispatch_request_key:key,source_agent_id:agentId,target_kind:targetKind,target_id:targetId,conversation_id:id,message_id:created.id,created_at:now()});
    return created;
    });
    this.publishMessages([m]);
    this.records.chatEvent(id,m.id,{type:'message.completed',data:{content:m.content,token_usage:null}},'completed');
    if (targetKind === "agent_id") {
      const target = one(db, "SELECT * FROM agent_profiles WHERE agent_id=?", targetId);
      if (target) this.ctx.gateway.relayMessage(m, target, `agent-dm:${m.id}:${targetId}`);
    }
    this.ctx.gateway.groupReply(m.id);
    return {
      conversation_id: id,
      message_id: m.id,
      target_kind: targetKind,
      target_id: targetId,
      source_agent_id: agentId,
    };
  }
  /** Decode an authenticated HTTP send and run its transactional business command. */
  async sendMessage(req:FastifyRequest, actor=this.principal(req)):Promise<ChatMessage> {
    const q=query(req),id=params(req).conversation_id;
    const principal=sendPrincipal(actor);
    const key=req.headers['idempotency-key'];
    if(typeof id!=='string'||q.agent_id!==undefined&&typeof q.agent_id!=='string'||key!==undefined&&typeof key!=='string')fail(422,'invalid message route');
    return this.send({principal,conversationId:id,agentId:q.agent_id,key:key??null,input:messageInput(req.body)});
  }
  private send(command:SendMessageCommand):ChatMessage {
    const {principal:p,conversationId:id,agentId,key,input:b}=command,c=this.access(p,id,agentId,'write');
    let sender = p.kind!=='gateway'?p.id:p.owner_id,
      type = "user";
    if (p.kind === "gateway") {
      requireLifecycle(this.db,agentId!,b.lifecycle_revision);
      if(one(this.db,"SELECT 1 FROM personal_agent_bindings WHERE agent_id=?",agentId) && (b.sender?.type??b.sender_type)!=="agent")fail(403,"owner_identity_cannot_be_delegated");
      sender =
        b.sender?.type === "agent" || b.sender_type === "agent"
          ? this.agentUser(agentId!).id
          : p.owner_id;
      type = b.sender?.type ?? b.sender_type ?? "user";
    } else if (
      (b.sender?.id ?? b.sender_user_id) !== p.id ||
      (b.sender?.type ?? b.sender_type ?? "user") !== "user"
    )
      fail(403, "sender does not match authenticated user");
    if (typeof b.content !== "string" && b.content !== undefined) fail(422, "invalid content");
    if (b.interaction_contexts !== undefined && c.type !== 'direct') fail(422, 'Private interaction background is only supported in direct chats');
    if (c.type === 'group' && b.interaction_reply && !b.interaction_reply.action_id && !b.interaction_reply.event)
      fail(422, 'Group interaction state requires an explicit card action');
    if (b.interaction_reply !== undefined && b.reply_to_message_id !== undefined) fail(422, 'Send quoted replies separately from card actions');
    if (b.interaction_reply !== undefined) return this.sendInteraction(p, id, b, key);
    if (b.interactive !== undefined && (p.kind !== 'gateway' || type !== 'agent')) fail(403, 'Only Agent messages may contain interactive replies');
    const attachments = b.attachments ?? [];
    if (attachments.length > 5) fail(400, "too many attachments");
    if (!b.content?.trim() && !attachments.length && !b.interactive && !b.task_cards?.length)
      fail(400, "message content, attachments or interactive reply required");
    const taskCards = this.validateTaskCardRefs(p, agentId, b.task_cards);
    b.content = this.validateReferences(p, id, b.content ?? "", agentId);
    for (const a of attachments) a.url = this.validateReferences(p, id, a.url!, agentId);
    const old=key?this.records.attempt(id,key):undefined;
    if (old) {assertMessageAttempt(old,sender,type,messageAttemptPayload(b));return this.message(old.id);}
    const threadRoot=threadRootOrFail(this.db,id,b.thread_root_message_id ?? b.in_thread_of);
    const replyTo=this.replyReference(id,b.reply_to_message_id);
    assertThreadQuote(this.db,id,threadRoot,replyTo?.message_id);
    // Must stay after the attempt hit: a retry returns the original message, so a carried
    // background can never reappear as a second injection or vanish from a retried send.
    // Client-supplied `interaction_contexts` are accepted but ignored; the centre decides.
    const contexts = this.background.pending(p, id);
    // Retries and history retain the timezone captured by the original send.
    const timezone = p.kind === "gateway" ? b.timezone ?? null
      : b.timezone === undefined ? one(this.db, "SELECT timezone FROM users WHERE id=?", p.id)?.timezone ?? null
      : this.updateUserTimezone(p.id, b.timezone);
    const agents = b.suppress_relay ? [] : this.relayAgents(id).filter(a=>type!=='agent' || a.agent_id!==agentId);
    const origin = p.kind==='gateway' && (c.external_source==='feishu' || c.external_source==='wechat') && c.config_agent_id===agentId && type==='user' && b.sender_source_id
      ? providerFacts(b.provider_facts) : undefined;
    // Freeze private background with its message; publish only after both are durable.
    const {m} = transaction(this.db, () => {
      const m = this.insertMessage(id,sender,type,b.content ?? "",attachments,key,
        agents.length ? "pending" : "completed",{ ...(p.kind === "gateway" ? messageMetadata(b) : {}), ...(taskCards ? { task_cards: taskCards } : {}), provider_facts:origin,pendingRelayAgents:agents.map(a=>a.agent_id), timezone, reply_to:replyTo, thread_root_id:threadRoot, publish:false, trackReceipts:type==='user' && (p.kind!=='gateway' || Boolean(origin)) });
      this.records.saveAttempt(m.id,messageAttemptPayload(b));
      return {m,relays:this.enqueueRelays(m,key,agents,contexts)};
    });
    this.publishMessages([m]);
    if (!b.suppress_relay) {
      const wait = this.ctx.updates?.messageWait(m.id);
      if (wait) this.event(m.conversation_id, m.id, 'node.update_wait_changed', {update_wait: wait}, 'pending');
    }
    return this.message(m.id);
  }
  private sendInteraction(p:SendPrincipal,id:string,b:MessageInput,rawKey:string|null):ChatMessage {
    if(p.kind==='gateway')fail(403,'Human viewer required');
    if (b.attachments?.length) fail(422, 'Send attachments in a separate message');
    const key = rawKey ? `interaction:${p.id}:${String(rawKey)}` : null;
    const prepared = this.interactions.prepare(p, id, b, key);
    const source=this.records.find(prepared.snapshot.source_message_id!)!;
    const root=threadRootOrFail(this.db,id,b.thread_root_message_id ?? b.in_thread_of ?? source.thread_root_id ?? undefined);
    assertThreadQuote(this.db,id,root,source.id);
    if (prepared.existing) {
      const existing=this.message(prepared.existing);
      if(existing.thread_root_message_id!==root) fail(409,'interaction destination changed');
      return existing;
    }
    // Preserve handwritten text exactly, including reference syntax and whitespace.
    const content = this.validateReferences(p, id, prepared.content);
    const timezone = b.timezone === undefined ? one(this.db, 'SELECT timezone FROM users WHERE id=?', p.id)?.timezone ?? null : this.updateUserTimezone(p.id, b.timezone);
    const message = transaction(this.db, () => {
      const agents=this.relayAgents(id);
      const m = this.insertMessage(id, p.id, 'user', content, [], key, 'pending', { pendingRelayAgents:agents.map(a=>a.agent_id), timezone, thread_root_id:root, interaction_reply: prepared.snapshot, publish: false, trackReceipts: true });
      this.interactions.submit(p.id, m.id, prepared);
      this.enqueueRelays(m, key,agents);
      return m;
    });
    this.publishMessages([message]);
    return this.message(message.id);
  }
  /** Save a foreground client's timezone and notify this user's connected Gateways.
   *
   * Args:
   *   userId: Authenticated human account, never a client-selected target.
   *   value: System timezone reported by the browser or native app.
   * Returns:
   *   The saved timezone; unchanged values do not write or broadcast.
   */
  updateUserTimezone(userId: string, value: unknown): string {
    let timezone: string;
    try { timezone = validateTimeZone(value); } catch { fail(422, "invalid timezone"); }
    const previous = one(this.db, "SELECT timezone FROM users WHERE id=?", userId)?.timezone;
    if (previous !== timezone) {
      this.db.prepare("UPDATE users SET timezone=? WHERE id=?").run(timezone, userId);
      for (const node of all(this.db, "SELECT node_id FROM nodes WHERE owner_id=?", userId))
        this.ctx.gateway.send(node.node_id, { type: "user.timezone", payload: { timezone } });
    }
    return timezone;
  }
  /** Persist a task event inside the caller's graph transaction; never publish early. */
  persistTaskNotice(id: string, sender: string, content: string, metadata: Row, contextOnlyAgentId?: string): ChatMessage {
    const m = this.insertMessage(id,sender,"system",content,[],null,"completed",{system_notice:metadata,publish:false});
    this.enqueueRelays(m,null,this.relayAgents(id),[],contextOnlyAgentId);
    for(const agentId of metadata.attention_actor_ids ?? [])if(taskContextEligible(this.db,agentId,id))
      this.db.prepare('INSERT OR IGNORE INTO task_context_index(agent_id,message_id,conversation_id,projection_kind) VALUES(?,?,?,?)').run(agentId,m.id,id,'full');
    return m;
  }
  /** Read one fixed authority range; the index contains references, never a second message body. */
  syncTaskContext(agentId:string, after:number, through:number|undefined, limit:number, allowedSource?:((id:string)=>boolean), pending:string[]=[]):Row {
    if(!Number.isSafeInteger(after)||after<0||through!==undefined&&(!Number.isSafeInteger(through)||through<after))fail(422,'Invalid task context cursor');
    if(!Array.isArray(pending)||pending.length>64||pending.some(id=>typeof id!=='string'))fail(422,'Invalid task context revalidation batch');
    return transaction(this.db,()=>{
      const bound=through??one(this.db,'SELECT coalesce(max(seq),0) AS seq FROM task_context_index WHERE agent_id=?',agentId)!.seq;
      const rows=all(this.db,'SELECT * FROM task_context_index WHERE agent_id=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?',agentId,after,bound,Math.max(1,Math.min(64,limit||32)));
      const items=rows.map(row=>{
        const allowed=row.projection_kind==='revoked'||row.projection_kind==='full'&&taskContextEntryAllowed(this.db,row)&&(!allowedSource||allowedSource(row.conversation_id));
        const ref={seq:row.seq,message_id:row.message_id,conversation_id:row.conversation_id,projection_kind:row.projection_kind,allowed};
        if(!allowed)return ref;
        const m=row.projection_kind==='revoked'?taskContextRevocation(this.db,row.message_id):this.message(row.message_id);
        if(!m)return {...ref,allowed:false};
        const c=one(this.db,'SELECT type FROM conversations WHERE id=?',row.conversation_id);
        return {...ref,input:{agent_id:agentId,conversation_id:row.conversation_id,relay_task_id:'task-context:'+row.message_id+':'+agentId,idempotency_key:row.message_id+':'+agentId,
          lifecycle_revision:lifecycle(this.db,agentId).revision,message:m,sender:m.sender,participants:row.projection_kind==='revoked'?[]:this.members(row.conversation_id).map(u=>this.actor(u)),metadata:{conversation_type:c?.type??'direct',mentioned_agent_ids:[agentId],participant_agent_ids:[agentId],task_context:true}}};
      });
      const revoked_message_ids=pending.filter(messageId=>{
        const entry=one(this.db,'SELECT * FROM task_context_index WHERE agent_id=? AND message_id=?',agentId,messageId);
        return !entry||entry.projection_kind!=='revoked'&&(!taskContextEntryAllowed(this.db,entry)||!!allowedSource&&!allowedSource(entry.conversation_id));
      });
      return {through:bound,next:rows.length<Math.max(1,Math.min(64,limit||32))?bound:rows.at(-1)!.seq,items,revoked_message_ids};
    });
  }
  private relayAgents(id: string): Row[] {
    return this.members(id).filter(u=>u.username.startsWith("agent:") && conversationAccess(this.db,id,u.id)?.can_write)
      .map(u=>one(this.db,"SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0",u.username.slice(6))).filter(Boolean).filter(a=>lifecycle(this.db,a!.agent_id).desired==='enabled') as Row[];
  }
  private enqueueRelays(m: ChatMessage, key: string | null = null, agents = this.relayAgents(m.conversation_id), contexts: InteractionContext[] = [], contextOnlyAgentId?: string): Pick<MessageRelayRecord,'relay_task_id'|'target_node_id'|'payload_json'|'conversation_id'>[] {
    const c = one(this.db,"SELECT * FROM conversations WHERE id=?",m.conversation_id)!;
    const relays: Pick<MessageRelayRecord,'relay_task_id'|'target_node_id'|'payload_json'|'conversation_id'>[] = [];
    for (const a of agents) {
      if ((m.sender.type==='agent' && m.sender.id===a.agent_id) || !chatAllowed(this.db,a.agent_id,m.id) || !threadAddressesAgent(this.db,m.id,a.agent_id)) continue;
      const background = contexts.filter(context => context.agent_id === a.agent_id);
      const id = randomUUID().replaceAll("-",""), relayKey = `${key ?? m.id}:${a.agent_id}`;
      const mentioned = [...new Set([...this.mentionedAgents(c.id,m.content), ...(m.interaction_reply ? [m.interaction_reply.agent_id] : []), ...(m.reply_to?.sender.type==='agent' ? [m.reply_to.sender.id] : [])])];
      const agentReceipt = m.receipts_requested && this.db.prepare(`
        SELECT 1 FROM message_receipts r JOIN users u ON u.id=r.recipient_id
        WHERE r.message_id=? AND u.username=?
      `).get(m.id,'agent:'+a.agent_id);
      const payload = {lifecycle_revision:lifecycle(this.db,a.agent_id).revision,relay_task_id:id,idempotency_key:relayKey,conversation_id:c.id,agent_id:a.agent_id,
        message:m,sender:m.sender,participants:this.members(c.id).map(u=>this.actor(u)),metadata:{
          conversation_type:c.type,mentioned_agent_ids:mentioned,participant_agent_ids:agents.map(a=>a.agent_id),
          ...(agentReceipt ? {agent_receipt:true} : {}),
          ...this.deliveryFacts(a.agent_id,m),
          ...threadRelayMetadata(this.db, m.id, a.agent_id),
          ...(m.thread_root_message_id && c.type==='group' ? {addressed_to_agent:true} : {}),
          config_profile_version:a.profile_version,node_epoch:one(this.db,"SELECT node_epoch FROM node_binding_state WHERE node_id=?",a.node_id)?.node_epoch ?? 0,
          ...(background.length ? {interaction_contexts:background} : {}),
          ...(a.agent_id===contextOnlyAgentId ? {context_only:true} : {}),
          ...(c.external_source ? {external_source:c.external_source,external_chat_id:c.external_chat_id,trigger_source:"im"} : {})}};
      this.db.prepare("INSERT INTO relay_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)").run(id,m.id,c.id,a.node_id,JSON.stringify(payload),relayKey,"queued",null,null,now(),now());
      relays.push({relay_task_id:id,target_node_id:a.node_id,payload_json:JSON.stringify(payload),conversation_id:c.id});
    }
    return relays;
  }
  /** Queue represented user input for current participants without echoing to its PA. */
  queueRepresentedRelays(message:ChatMessage,agentId:string):void {
    this.enqueueRelays(message,null,this.relayAgents(message.conversation_id).filter(agent=>agent.agent_id!==agentId));
  }
  /** Queue other direct-chat Agents in the same transaction as a reviewed PA message. */
  queueDirectAgentRelays(message:ChatMessage):void {
    if(one(this.db,'SELECT type FROM conversations WHERE id=?',message.conversation_id)?.type!=='direct')return;
    this.enqueueRelays(message,null,this.relayAgents(message.conversation_id).filter(agent=>`agent:${agent.agent_id}`!==one(this.db,'SELECT username FROM users WHERE id=?',message.sender_user_id)?.username));
  }
  /** Resolve authenticated provider targets or actual Web message recipients. */
  deliveryFacts(agentId:string, message:Row) {
    const b=one(this.db,'SELECT * FROM personal_agent_bindings WHERE agent_id=?',agentId);
    if(b && this.ctx.personal)return this.ctx.personal.sourceFacts(b,message);
    const provider=storedProviderFacts(this.db,message.id);
    const chat=one(this.db,'SELECT * FROM conversations WHERE id=?',message.conversation_id)!;
    const profile=one(this.db,'SELECT * FROM agent_profiles WHERE agent_id=?',agentId);
    const explicit=provider ? (provider.mentioned_bot?[agentId]:[]) : this.mentionedAgents(message.conversation_id,message.content);
    return {owner_direct:ownerDirect(this.db,agentId,message.id),
      owner_internal:!!profile && isOwnerInternalConversation(this.db,message.conversation_id,profile.owner_id),
      ...(profile && !chat.external_source
        ? {project_allowed:canAgentAccessConversation(this.db,{...profile,collaboration_scope:'project'},chat)}
        : {}),
      addressed_to_agent:chat.type==='direct'||explicit.includes(agentId)||provider?.replied_to_bot===true||message.reply_to?.sender.id===agentId||message.interaction_reply?.agent_id===agentId,
      addressed_to_owner:false,explicit_mentioned_agent_ids:explicit,
      ...(provider||message.sender_source_id?{provider_source_time:provider?.source_time??null,context_only:provider?.context_only===true}:{})};
  }
  /** Recheck membership and lifecycle before either immediate or reconnect delivery. */
  relayEligible(task: Row, payload: Row = JSON.parse(task.payload_json)): boolean {
    const agent = one(this.db,"SELECT a.node_id,u.id FROM agent_profiles a JOIN users u ON u.username='agent:'||a.agent_id WHERE a.agent_id=? AND a.is_stale=0",payload.agent_id);
    if(!lifecycleAllows(this.db,payload.agent_id,payload.lifecycle_revision))return false;
    const epoch = one(this.db, 'SELECT node_epoch FROM node_binding_state WHERE node_id=?', task.target_node_id)?.node_epoch ?? 0;
    if (payload.metadata?.node_epoch !== undefined && payload.metadata.node_epoch !== epoch) return false;
    if(!agent||agent.node_id!==task.target_node_id)return false;
    const entry=one(this.db,'SELECT * FROM task_context_index WHERE agent_id=? AND message_id=?',payload.agent_id,task.message_id);
    if(entry?.projection_kind==='revoked')return !!taskContextRevocation(this.db,task.message_id);
    if(entry)return taskContextEntryAllowed(this.db,entry);
    return chatAllowed(this.db,payload.agent_id,task.message_id) && !!conversationAccess(this.db,task.conversation_id,agent.id)?.can_write;
  }
  deliverRelays(relays: Row[]): boolean {
    let sent=false;
    for (const node of new Set(relays.map(task=>String(task.target_node_id)))) sent=this.delivery.drain(node)||sent;
    return sent;
  }
  /** Publish committed system messages and attempt their already durable relay rows. */
  publishMessages(messages: ChatMessage[], options: {deferDelivery?: boolean} = {}) {
    let delivered = false;
    for (const m of messages) {
      const e = this.records.createdEvent(m.id);
      const data = JSON.parse(e.payload_json);
      this.ctx.gateway.broadcast('conversation-readers',{op:"event",event_id:e.event_id,conversation_id:m.conversation_id,message_id:m.id,event_type:e.event_type,delivery_status:e.delivery_status,created_at:e.created_at,data:{...data,...this.message(m.id),message_id:m.id,event_id:e.event_id}});
      if (!options.deferDelivery) delivered = this.deliverRelays(this.records.queuedRelays(m.id)) || delivered;
    }
    return delivered;
  }
  /** Join only the caller, without changing invitation authority for other Agents. */
  joinConversation(userId: string, id: string): Row {
    const actor = one(this.db, "SELECT username FROM users WHERE id=?", userId);
    if (actor?.username.startsWith("agent:")) {
      const profile = one(this.db, "SELECT collaboration_scope FROM agent_profiles WHERE agent_id=?", actor.username.slice(6));
      if (["owner_only", "project"].includes(profile?.collaboration_scope ?? "team")) {
        fail(403, { code: "collaboration_scope_restricted", message: "This assistant cannot join public groups under its current collaboration scope." });
      }
    }
    const c = conversationAccess(this.db,id,userId);
    if (!c || c.type !== "group" || c.visibility !== "public") fail(404,"conversation_id not found");
    if (c.dissolved_at) fail(409,{code:"conversation_dissolved",message:"This conversation has been dissolved"});
    this.db.prepare("INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES(?,?)").run(id,userId);
    this.membership(id,this.members(id).map(u=>u.id));
    return this.conversation(id,userId);
  }
  /** Delete Direct history while retaining the new minimal withdrawal originals. */
  deleteDirectConversation(userId:string,id:string):void {
    const c=conversationAccess(this.db,id,userId);
    if(!c || (!c.can_write && !(c.is_member && ['agent_private','agent_project_restricted'].includes(String(c.write_blocked_reason)))) || c.type!=='direct')fail(404,'conversation_id not found');
    transaction(this.db,()=>{
      const before=captureTaskContextAccess(this.db,{conversationIds:[id]});
      this.db.prepare('DELETE FROM conversations WHERE id=?').run(id);
      revokeLostTaskContextAccess(this.db,before,userId);
    });
  }
  /** Freeze group history and close unfinished records without erasing consumed history. */
  dissolveConversation(userId: string, id: string) {
    const c = conversationAccess(this.db,id,userId);
    if (!c?.can_write) fail(404,"conversation_id not found");
    if (c.creator_id !== userId) fail(403,"only creator can delete group");
    let notices: ChatMessage[] = [];
    let projectEffects = new Map<string, import('./collaboration.js').ScopeTransitionEffects>();
    const graphIds = transaction(this.db,()=>{
      const projSnap = c.visibility === 'private' ? snapshotProjectGroupDirects(this.db, id) : undefined;
      const before=captureTaskContextAccess(this.db,{conversationIds:[id, ...(projSnap?.allDirectConversationIds ?? [])]});
      const at = now();
      this.db.prepare("UPDATE conversations SET dissolved_at=? WHERE id=?").run(at,id);
      const graphIds = this.ctx.gateway.tasks.closeForConversationDissolution(id,userId,at);
      this.db.prepare("UPDATE relay_tasks SET status='cancelled',updated_at=? WHERE conversation_id=? AND status IN ('queued','sent','accepted')").run(at,id);
      if (projSnap) {
        projectEffects = reconcileProjectGroupLossInTx(this.db, id, projSnap);
      }
      notices = revokeLostTaskContextAccess(this.db,before,userId);
      return graphIds;
    });
    for (const graphId of graphIds) this.ctx.gateway.tasks.notifyChange(undefined,graphId);
    if (notices.length) this.publishMessages(notices);
    for (const [agentId, effects] of projectEffects) {
      publishCollaborationScopeTransitionEffects(this.ctx, agentId, `dissolve:${id}:${agentId}`, effects);
    }
    this.ctx.gateway?.trajectory?.check();
    this.membership(id,this.members(id).map(u=>u.id));
  }
  /** Resolve an authorized send target.
   *
   * Args:
   *   agentId: Sending Agent identity used for membership and space checks.
   *   target: Conversation, user or Agent address accepted by message delivery.
   *   create: False for lookup without creating an empty direct conversation.
   *
   * Returns:
   *   Authorized conversation ID, or undefined for a new direct target in lookup mode.
   *
   * Side Effects:
   *   Creates a direct conversation only in the default delivery mode.
   */
  resolveTarget(agentId: string, target: string): string;
  resolveTarget(agentId: string, target: string, create: false): string | undefined;
  resolveTarget(agentId: string, target: string, create = true): string | undefined {
    const a = this.agentUser(agentId);
    const agentProfile = one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0", agentId);
    if (!agentProfile || !agentAvailable(this.db, agentProfile)) fail(404, "target not accessible");
    const callerScope = agentProfile.collaboration_scope ?? "team";
    const isPrivateAgent = callerScope === "owner_only";
    const isProjectAgent = callerScope === "project";
    const personal=one(this.db,'SELECT * FROM personal_agent_bindings WHERE agent_id=?',agentId);
    if(personal && [personal.owner_id,personal.owner_user_id,`user:${personal.owner_user_id}`,`user:${personal.owner_id}`,personal.conversation_id,`conversation:${personal.conversation_id}`].includes(target))return personal.conversation_id;
    const c = one(
      this.db,
      "SELECT * FROM conversations WHERE id=?",
      target.replace(/^conversation:/, ""),
    );
    if (c) {
      const isParticipant = !!one(
        this.db,
        "SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?",
        c.id,
        a.id,
      );
      if (isPrivateAgent && !isOwnerInternalConversation(this.db, c.id, agentProfile.owner_id) && !isFeishuBoundOwnerShadow(this.db, c, agentProfile)) {
        fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Private and can only communicate with its owner and the owner's own assistants." });
      }
      if (isProjectAgent && !canAgentAccessConversation(this.db, agentProfile, c)) {
        if (isParticipant || c.visibility === "public") {
          fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Project scope and can only communicate within shared private groups and active project members." });
        }
        fail(404, "target not accessible");
      }
      if (!isParticipant || !canAgentAccessConversation(this.db, agentProfile, c)) fail(404, "target not accessible");
      return c.id;
    }
    const uid = target.replace(/^(?:user|agent):/, "");
    const u = one(this.db, "SELECT * FROM users WHERE id=? OR username=?", uid, `agent:${uid}`);
    if (!u || u.username.startsWith("shadow:") || u.username === "system") fail(404, "target not accessible");
    const targetProfile = u.username.startsWith("agent:")
      ? one(this.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0", u.username.slice(6))
      : undefined;
    const targetOwnerId = targetProfile ? targetProfile.owner_id : u.owner_id;
    const sameOwner = targetOwnerId === agentProfile.owner_id;
    if (!sameOwner) {
      if (isPrivateAgent) {
        fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Private and can only communicate with its owner and the owner's own assistants." });
      }
      if (isProjectAgent && !sharesActivePrivateGroupWithAgent(this.db, u.id, agentProfile.agent_id)) {
        fail(403, { code: "collaboration_scope_restricted", message: "This assistant is set to Project scope and can only communicate with members sharing an active private group with it." });
      }
      if (targetProfile && !canCollaborateWithAgent(this.db, a, targetProfile)) {
        fail(404, "target not accessible");
      }
      const space = "company:default";
      if (!canActorAccess(this.db, a.id, space) || !canActorAccess(this.db, u.id, space)) {
        fail(404, "target not accessible");
      }
      const pairKey = [a.id, u.id].sort().join("|");
      const key = `${space}|${pairKey}`;
      const old = one(this.db, "SELECT id FROM conversations WHERE space_id=? AND (direct_key=? OR direct_key=?)", space, key, pairKey);
      if (old) return old.id;
      if (!create) return;
      const id = chatId("c_");
      this.db
        .prepare("INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at,space_id) VALUES(?,?,?,?,?,?,?,?)")
        .run(id, u.display_name, "direct", a.owner_id, a.id, key, now(), space);
      for (const member of [a.id, u.id])
        this.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)").run(id, member);
      return id;
    }
    const owner = ownerAccount(this.db, agentProfile.owner_id);
    if (targetProfile ? !agentAvailable(this.db, targetProfile) : !owner || (u.membership_status !== "active" && !u.personal_space_enabled)) {
      fail(404, "target not accessible");
    }
    const pairKey = [a.id, u.id].sort().join("|");
    const candidateSpaces = [...new Set([
      agentProfile.space_id,
      targetProfile?.space_id,
      owner?.personal_space_enabled ? `personal:${agentProfile.owner_id}` : undefined,
      "company:default",
    ].filter((s): s is string => !!s))];
    for (const candidateSpace of candidateSpaces) {
      const old = one(this.db, "SELECT id FROM conversations WHERE space_id=? AND (direct_key=? OR direct_key=?)", candidateSpace, `${candidateSpace}|${pairKey}`, pairKey);
      if (old) return old.id;
    }
    if (!create) return;
    const space = targetProfile && targetProfile.space_id !== agentProfile.space_id
      ? defaultSpace(owner!)
      : agentProfile.space_id;
    if (!canActorAccess(this.db, a.id, space) || !canActorAccess(this.db, u.id, space)) {
      fail(404, "target not accessible");
    }
    const key = `${space}|${pairKey}`;
    const id = chatId("c_");
    this.db
      .prepare(
        "INSERT INTO conversations(id,title,type,owner_id,creator_id,direct_key,created_at,space_id) VALUES(?,?,?,?,?,?,?,?)",
      )
      .run(id, u.display_name, "direct", a.owner_id, a.id, key, now(), space);
    for (const member of [a.id, u.id])
      this.db
        .prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)")
        .run(id, member);
    return id;
  }
}
export function registerMessagingRoutes(app: FastifyInstance, ctx: ImContext) {
  const s = ctx.messaging,
    db = ctx.db;
  app.get('/im/v1/messages/search', req => {
    const user = ctx.identity.authenticateRequest(req), q = query(req);
    if (typeof q.q !== 'string' || !q.q.trim()) fail(400, 'search_query_required');
    const kind = q.kind ?? 'all', limit = q.limit === undefined ? 20 : Number(q.limit);
    if (!['all','direct-user','direct-agent','group','agent-network'].includes(kind) || !Number.isInteger(limit) || limit < 1 || limit > 50) fail(400, 'invalid_arguments');
    let cursor: {created_at:string; id:string} | undefined;
    if (q.cursor) {
      try {
        cursor = JSON.parse(Buffer.from(q.cursor, 'base64url').toString());
        if (!cursor || typeof cursor.id !== 'string' || typeof cursor.created_at !== 'string' || !Number.isFinite(Date.parse(cursor.created_at))) throw Error();
      } catch { fail(400, 'invalid_cursor'); }
    }
    const targets = [...readableConversationIds(db, user)];
    const term = q.q.trim(), needle = term.toLowerCase();
    const matches = searchMessages(db, {targets, kind, terms:[term], action:'search', sort:'recent', cursor, limit:limit+1});
    const conversations = new Map<string, Row>();
    const messages = matches.slice(0,limit).map(row => {
      const message = s.message(row.id), id = message.conversation_id;
      let chat = conversations.get(id);
      if (!chat) {
        chat = s.conversation(id, user.id);
        conversations.set(id, chat);
      }
      const content = !message.content.toLowerCase().includes(needle) && row.interactive_search_text
        ? String(row.interactive_search_text)
        : readableMentions(message.content, chat.participants.map((p: Row) => ({id:p.user_id ?? p.id, display_name:p.display_name})));
      const position = Math.max(0, content.toLowerCase().indexOf(needle));
      const start = Math.max(0, position - 40), end = Math.min(content.length, position + term.length + 80);
      return {message_id:message.id, conversation_id:message.conversation_id, conversation_name:chat.title,
        ...(message.thread_root_message_id ? {thread_root_message_id:message.thread_root_message_id} : {}),
        sender_name:row.sender_source_id ? row.sender_display_name || row.sender_source_id : message.sender.display_name, created_at:message.created_at,
        snippet:`${start ? '…' : ''}${content.slice(start,end)}${end < content.length ? '…' : ''}`};
    });
    const last = matches[limit-1];
    return {messages, ...(matches.length > limit && last ? {next_cursor:Buffer.from(JSON.stringify({created_at:last.created_at,id:last.id})).toString('base64url')} : {})};
  });
  app.get("/im/v1/contacts", (req) => {
    const viewer = ctx.identity.authenticateRequest(req), q = query(req);
    if (q.kind && !["human", "agent"].includes(q.kind)) fail(400, "invalid kind");
    return contactPage(db, viewer, q);
  });
  app.get("/im/v1/contacts/:user_id", (req) => {
    const viewer = ctx.identity.authenticateRequest(req);
    const contact = contactDetail(db, viewer, params(req).user_id);
    if (!contact) fail(404, "contact not found");
    return contact;
  });
  app.post("/im/v1/conversations", (req, reply) => {
    const p = ctx.identity.authenticateRequest(req);
    reply.code(201);
    return s.createConversation(p, body(req));
  });
  app.get("/im/v1/conversations", (req) => {
    const p = s.principal(req);
    const uid = p.kind === "gateway" ? s.agentUser(query(req).agent_id).id : p.id;
    if (p.kind === "gateway") {
      const a = one(db, "SELECT node_id FROM agent_profiles WHERE agent_id=?", query(req).agent_id);
      if (a?.node_id !== p.node_id) fail(404, "agent not found");
    }
    return { items: s.conversations(uid,query(req).scope ?? "joined") };
  });
  app.get("/im/v1/sync", (req) => {
    const p = ctx.identity.authenticateRequest(req);
    const cursorOnly = query(req).view === "cursor";
    if (cursorOnly && !qualifiedUser(db, p.id)) fail(403, "account access required");
    const max_event_id = one(db, "SELECT COALESCE(MAX(event_id),0) AS n FROM conversation_events")!.n;
    const cleanup = all(db,'SELECT * FROM conversation_execution_cleanup').filter(row=>conversationAccess(db,row.conversation_id,p.id));
    const snapshot = {max_event_id,...(cleanup.length ? {execution_cleanup_revisions:Object.fromEntries(cleanup.map(row=>[row.conversation_id,row.revision]))} : {})};
    return cursorOnly ? snapshot : {items:s.conversations(p.id),...snapshot};
  });
  app.get("/im/v1/conversations/:conversation_id", (req) => {
    const p = s.principal(req),
      id = params(req).conversation_id;
    s.access(p, id, query(req).agent_id);
    return s.conversation(id, p.id ?? s.agentUser(query(req).agent_id).id);
  });
  app.post("/im/v1/conversations/:conversation_id/join",req=>{
    const p=ctx.identity.authenticateRequest(req);
    return s.joinConversation(p.id,params(req).conversation_id);
  });
  app.patch("/im/v1/conversations/:conversation_id", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      b = body(req);
    const prefsOnly = b.title === undefined && b.visibility === undefined;
    const c = s.access(p, id, undefined, prefsOnly ? "read" : "write");
    if (prefsOnly && (!c.is_member || c.dissolved_at)) fail(404, "conversation_id not found");
    if (b.visibility !== undefined) {
      if (!["public","private"].includes(b.visibility)) fail(400,"invalid visibility");
      if (b.visibility === "public" && groupHasPrivateAgent(db, id)) {
        fail(409, { code: "private_agent_in_group", message: "Groups containing a private assistant cannot be made public." });
      }
      if (b.visibility === "public" && groupHasProjectAgent(db, id)) {
        fail(409, { code: "project_agent_requires_private_group", message: "Groups containing a project assistant cannot be made public." });
      }
      if (!c.can_change_visibility) fail(403,"Only a joined company administrator can change visibility");
    }
    if (b.title !== undefined) {
      if (!b.title.trim()) fail(400, "title must be non-empty");
      db.prepare("UPDATE conversations SET title=?,title_is_custom=1 WHERE id=?").run(
        b.title.trim(),
        id,
      );
    }
    if (b.visibility !== undefined) transaction(db,()=>{
      const before=captureTaskContextAccess(db,{conversationIds:[id]});
      db.prepare("UPDATE conversations SET visibility=? WHERE id=?").run(b.visibility,id);
      revokeLostTaskContextAccess(db,before,p.id);
    });
    for (const key of ["is_pinned", "is_muted"])
      if (b[key] !== undefined)
        db.prepare(
          `UPDATE conversation_participants SET ${key}=? WHERE conversation_id=? AND user_id=?`,
        ).run(b[key] ? 1 : 0, id, p.id);
    s.membership(
      id,
      s.members(id).map((u) => u.id),
    );
    return s.conversation(id, p.id);
  });
  app.delete("/im/v1/conversations/:conversation_id", (req, reply) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id;
    const readable = s.access(p, id, undefined, "read");
    const c = readable.type === "direct" && readable.is_member && ["agent_private", "agent_project_restricted"].includes(String(readable.write_blocked_reason))
      ? readable
      : s.access(p, id, undefined, "write");
    if (c.type === "group" && c.creator_id !== p.id) fail(403, "only creator can delete group");
    const recipients = s.members(id).map((u) => u.id);
    if (c.type === "group") s.dissolveConversation(p.id,id);
    else s.deleteDirectConversation(p.id,id);
    s.membership(id, recipients);
    reply.code(204).send();
  });
  app.post("/im/v1/conversations/:conversation_id/participants", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id,
      reqBody = body(req),
      c = s.access(p, id, undefined, "write");
    if (c.type !== "group") fail(400, "group required");
    const ids = s.resolveParticipants(p, reqBody.participants ?? [], [], true);
    if (!ids.length) fail(400, "participants required");
    const currentMembers = all(db, `SELECT u.id,u.username,u.owner_id AS user_owner_id,ap.agent_id,ap.owner_id AS agent_owner_id,ap.node_id,ap.collaboration_scope,ap.work_mode,ap.is_stale
      FROM conversation_participants cp JOIN users u ON u.id=cp.user_id
      LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id AND ap.is_stale=0
      WHERE cp.conversation_id=?`, id);
    const currentMemberIds = new Set(currentMembers.map(m => String(m.id)));
    const incomingMembers = ids.map(uid => one(db, `SELECT u.id,u.username,u.owner_id AS user_owner_id,ap.agent_id,ap.owner_id AS agent_owner_id,ap.collaboration_scope,ap.work_mode,ap.is_stale
      FROM users u LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id AND ap.is_stale=0
      WHERE u.id=?`, uid)).filter(Boolean) as Row[];
    const newlyAddedMembers = incomingMembers.filter(m => !currentMemberIds.has(String(m.id)));
    const existingPrivateOwners = [...new Set(currentMembers.filter(m => m.agent_id && (m.collaboration_scope ?? "team") === "owner_only").map(m => m.agent_owner_id))];
    if (existingPrivateOwners.length > 0) {
      const allowedOwner = existingPrivateOwners[0]!;
      if (incomingMembers.some(m => (m.agent_id ? m.agent_owner_id : m.user_owner_id) !== allowedOwner)) {
        fail(409, { code: "private_agent_in_group", message: "Cannot add external members to a group containing a private assistant." });
      }
    }
    const incomingPrivateAgents = incomingMembers.filter(m => m.agent_id && (m.collaboration_scope ?? "team") === "owner_only");
    if (incomingPrivateAgents.length > 0) {
      const privateOwner = incomingPrivateAgents[0]!.agent_owner_id;
      const hasExternal = c.visibility === "public"
        || [...currentMembers, ...incomingMembers].some(m => (m.agent_id ? m.agent_owner_id : m.user_owner_id) !== privateOwner);
      if (hasExternal) {
        fail(409, { code: "private_agent_group_external_members", message: "Private assistants cannot be added to public groups or groups with external members." });
      }
    }
    const incomingProjectAgents = incomingMembers.filter(m => m.agent_id && (m.collaboration_scope ?? "team") === "project");
    if (incomingProjectAgents.length > 0 && c.visibility === "public") {
      fail(409, { code: "project_agent_requires_private_group", message: "Project assistants can only be added to private groups." });
    }
    const existingProjectAgents = currentMembers.filter(m => m.agent_id && (m.collaboration_scope ?? "team") === "project");
    for (const projAgent of existingProjectAgents) {
      const addsExternalHuman = newlyAddedMembers.some(
        m => !m.agent_id && !String(m.username).startsWith("agent:") && m.user_owner_id !== projAgent.agent_owner_id,
      );
      if (addsExternalHuman && p.owner_id !== projAgent.agent_owner_id) {
        fail(403, {
          code: "project_agent_owner_required",
          message: "Only the project assistant owner can add external members to a private group containing it.",
        });
      }
    }
    if (c.visibility === "private" && newlyAddedMembers.length > 0) {
      const finalMembers = [...currentMembers, ...newlyAddedMembers];
      assertProjectAgentCrossGroupShare(db, p.owner_id, id, finalMembers, reqBody.confirm_project_context_share === true);
    }
    const allOwnerExclusive = c.visibility !== "public"
      && [...currentMembers, ...incomingMembers].every(m => (m.agent_id ? m.agent_owner_id : m.user_owner_id) === p.owner_id);
    for (const m of incomingMembers) {
      const allowedInSpace = m.agent_id
        ? (allOwnerExclusive || canActorAccess(db, m.id, c.space_id))
        : canActorAccess(db, m.id, c.space_id);
      if (!allowedInSpace) fail(404, "participant not found");
    }
    const internalAgentsBefore = currentMembers.filter(m => m.agent_id && isOwnerInternalConversation(db, id, m.agent_owner_id));
    for (const uid of ids)
      db.prepare(
        "INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES(?,?)",
      ).run(id, uid);
    for (const agentMember of internalAgentsBefore) {
      if (!isOwnerInternalConversation(db, id, agentMember.agent_owner_id) && agentMember.node_id) {
        ctx.gateway.send(agentMember.node_id, {
          type: "agent.conversation.externalized",
          payload: { agent_id: agentMember.agent_id, conversation_id: id },
        });
      }
    }
    s.membership(
      id,
      s.members(id).map((u) => u.id),
    );
    if (c.visibility === "private" && newlyAddedMembers.length > 0 && (existingProjectAgents.length > 0 || incomingProjectAgents.length > 0)) {
      broadcastRestoredProjectDirects(db, id, s);
    }
    return s.conversation(id, p.id);
  });
  app.delete("/im/v1/conversations/:conversation_id/participants/:user_id", (req, reply) => {
    const p = ctx.identity.authenticateRequest(req),
      { conversation_id: id, user_id: uid } = params(req),
      c = s.access(p, id, undefined, "write");
    if (c.type !== "group" || uid === c.creator_id) fail(403, "creator cannot be removed");
    const recipients = s.members(id).map((u) => u.id);
    const removedUser = one(db, "SELECT username FROM users WHERE id=?", uid);
    const removedAgentId = removedUser?.username?.startsWith("agent:") ? String(removedUser.username).slice(6) : undefined;
    let projectEffects = new Map<string, import('./collaboration.js').ScopeTransitionEffects>();
    const notices = transaction(db, () => {
      const projSnap = c.visibility === "private" ? snapshotProjectGroupDirects(db, id) : undefined;
      const before = captureTaskContextAccess(db, { conversationIds: [id, ...(projSnap?.allDirectConversationIds ?? [])] });
      db.prepare("DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?").run(id, uid);
      db.prepare("DELETE FROM thread_follows WHERE conversation_id=? AND user_id=?").run(id, uid);
      if (projSnap || removedAgentId) {
        projectEffects = reconcileProjectGroupLossInTx(
          db,
          id,
          projSnap ?? { projectAgentIds: [], accessibleDirectsByAgent: new Map(), allDirectConversationIds: [] },
          removedAgentId,
        );
      }
      return revokeLostTaskContextAccess(db, before, p.id);
    });
    s.publishMessages(notices);
    for (const [agentId, effects] of projectEffects) {
      publishCollaborationScopeTransitionEffects(ctx, agentId, `participant-removed:${id}:${uid}:${agentId}`, effects);
    }
    ctx.gateway?.trajectory?.check();
    s.membership(id, recipients);
    reply.code(204).send();
  });
  app.post("/im/v1/conversations/:conversation_id/read", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id;
    s.access(p, id);
    const m = one(
      db,
      "SELECT rowid,thread_root_id FROM messages WHERE id=? AND conversation_id=?",
      body(req).last_read_message_id, id,
    );
    if (!m) fail(400, "message not found");
    const grouped = one(db,'SELECT type FROM conversations WHERE id=?',id)?.type==='group';
    const topic = grouped ? m.thread_root_id : null;
    const lastRead = body(req).last_read_message_id;
    const changed = transaction(db, () => {
      if(topic) markThreadRead(db,id,topic,p.id,lastRead,m.rowid);
      else db.prepare(`UPDATE conversation_participants SET last_read_message_id=?,unread_count=?
        WHERE conversation_id=? AND user_id=? AND coalesce((SELECT rowid FROM messages WHERE id=last_read_message_id),0)<=?`)
        .run(lastRead,listUnread(db,id,p.id,m.rowid),id,p.id,m.rowid);
      return db.prepare(`UPDATE message_receipts SET status=2 WHERE recipient_id=? AND status<2 AND message_id IN
        (SELECT id FROM messages WHERE conversation_id=? AND rowid<=?${grouped ? ' AND thread_root_id IS ?' : ''})`)
        .run(p.id,id,m.rowid,...(grouped ? [topic] : [])).changes;
    });
    if(changed) s.event(id,null,'message.receipts_changed',{});
    return s.conversation(id, p.id);
  });
  app.post('/im/v1/message-receipts', req => {
    const p = ctx.identity.authenticateRequest(req);
    const ids: unknown = body(req).message_ids;
    if (!Array.isArray(ids) || ids.length>100 || !ids.every(id=>typeof id==='string')) fail(400,'invalid message IDs');
    const changed = transaction(db, () => all(db,`
      UPDATE message_receipts SET status=1 WHERE recipient_id=? AND status=0
        AND message_id IN (SELECT value FROM json_each(?))
        AND EXISTS (SELECT 1 FROM messages m JOIN conversation_participants cp
          ON cp.conversation_id=m.conversation_id AND cp.user_id=? WHERE m.id=message_id)
      RETURNING message_id
    `,p.id,JSON.stringify(ids),p.id));
    const conversations = new Set(changed.map(row=>s.records.find(row.message_id)?.conversation_id));
    for (const id of conversations) if (id) s.event(id,null,'message.receipts_changed',{});
    return {ok:true};
  });
  app.post("/im/v1/conversations/:conversation_id/messages", async (req, reply) => {
    reply.code(201);
    const principal = s.principal(req);
    const message = await s.sendMessage(req,principal);
    return principal.kind==='gateway' ? message : s.records.senderView(message,principal.id);
  });
  app.get('/im/v1/conversations/:conversation_id/messages/:message_id/interaction-state', req => s.interactions.readDraft(req));
  app.put('/im/v1/conversations/:conversation_id/messages/:message_id/interaction-state', req => s.interactions.writeDraft(req));
  app.post('/im/v1/conversations/:conversation_id/interaction-background/discard', (req, reply) => {
    const p = s.principal(req), cid = params(req).conversation_id;
    if (p.kind === 'gateway' || p.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    s.access(p, cid, undefined, 'write');
    // Group and shadow conversations never hold a pending background.
    if (one(db, 'SELECT type FROM conversations WHERE id=?', cid)?.type !== 'direct') { reply.code(204).send(); return; }
    const result = s.background.discard(p, cid, body(req).through);
    if (!result.applied) { reply.code(204).send(); return; }
    return {discarded_through: result.discarded_through};
  });
  app.get('/im/v1/conversations/:conversation_id/messages/:message_id', req => {
    const {conversation_id, message_id}=params(req);
    const principal = s.principal(req);
    s.access(principal,conversation_id,query(req).agent_id);
    return {message:s.records.senderView(s.records.conversationMessage(conversation_id,message_id),principal.id),execution_cleanup_revision:executionCleanupRevision(ctx,conversation_id)};
  });
  app.get('/im/v1/conversations/:conversation_id/threads/:root_id', (req) => {
    const p = s.principal(req), id = params(req).conversation_id, root = params(req).root_id;
    s.access(p, id, query(req).agent_id);
    threadRootOrFail(db, id, root);
    const reader = p.kind==='gateway' ? s.agentUser(query(req).agent_id).id : p.id;
    const rows = all(db, 'SELECT id FROM messages WHERE conversation_id=? AND thread_root_id=? ORDER BY rowid', id, root);
    const follow = one(db, 'SELECT following FROM thread_follows WHERE conversation_id=? AND root_message_id=? AND user_id=?', id, root, reader);
    return {root:s.records.senderView(s.message(root),reader), following:follow?.following===1, items: rows.map(row => ({type:'message', message:s.records.senderView(s.message(row.id),reader)}))};
  });
  app.post('/im/v1/conversations/:conversation_id/threads/:root_id/follow', (req) => {
    const p = s.principal(req), id = params(req).conversation_id, root = params(req).root_id;
    if (p.kind==='gateway') fail(403, 'Human viewer required');
    s.access(p, id, undefined, 'write');
    threadRootOrFail(db, id, root);
    const follow = body(req).following !== false;
    db.prepare(`INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following,unread_count) VALUES(?,?,?,?,0)
      ON CONFLICT(conversation_id,root_message_id,user_id) DO UPDATE SET following=excluded.following`).run(id, root, p.id, follow ? 1 : 0);
    return {following: follow};
  });
  app.get("/im/v1/conversations/:conversation_id/messages", (req) => {
    const p = s.principal(req),
      id = params(req).conversation_id,
      q = query(req);
    s.access(p, id, q.agent_id);
    const directReadThrough = !q.before_message_id && one(db,
      "SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.id=? AND c.type='direct' ORDER BY m.rowid DESC LIMIT 1",id)?.id;
    const limit = Math.min(100, Math.max(1, Number(q.limit ?? 50)));
    const before = q.before_message_id
      ? one(
          db,
          "SELECT rowid FROM messages WHERE id=? AND conversation_id=?",
          q.before_message_id,
          id,
        )?.rowid
      : undefined;
    const rows = all(
      db,
      "SELECT id,rowid FROM messages WHERE conversation_id=? AND thread_root_id IS NULL AND rowid<? ORDER BY rowid DESC LIMIT ?",
      id,
      before ?? Number.MAX_SAFE_INTEGER,
      limit + 1,
    );
    const more = rows.length > limit;
    const page = rows.slice(0, limit).reverse();
    const items: Row[] = [];
    for (const row of page) {
      for (const b of all(
        db,
        "SELECT * FROM agent_config_boundaries WHERE conversation_id=? AND before_message_id=?",
        id,
        row.id,
      ))
        items.push({
          type: "agent_config_changed",
          id: b.boundary_id,
          conversation_id: id,
          agent_id: b.agent_id,
          before_message_id: row.id,
          applied_at: b.applied_at,
        });
      const message = q.view === "summary" ? s.records.historySummary(id,row.id) : s.message(row.id);
      items.push({ type: "message", message: s.records.senderView(message,p.id) });
    }
    return { items, ...(directReadThrough ? {direct_read_through_message_id:directReadThrough} : {}), next_before_message_id: more ? page[0]!.id : null, execution_cleanup_revision:executionCleanupRevision(ctx,id) };
  });
}
