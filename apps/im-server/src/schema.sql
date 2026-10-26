-- IM business schema; preserves existing center storage and identifiers.
CREATE TABLE IF NOT EXISTS task_graphs (
    graph_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    space_id TEXT NOT NULL DEFAULT 'company:default',
    root_title TEXT NOT NULL,
    revision INTEGER NOT NULL,
    document_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    default_entry_node_id TEXT,
    password_hash TEXT,
    locale TEXT NOT NULL DEFAULT 'en',
    timezone TEXT,
    created_at TEXT NOT NULL
, personal_space_enabled INTEGER NOT NULL DEFAULT 0, membership_status TEXT NOT NULL DEFAULT 'pending', is_company_admin INTEGER NOT NULL DEFAULT 0, auth_epoch INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings_policies (
    singleton_key TEXT PRIMARY KEY,
    default_model TEXT NOT NULL,
    max_turn_per_run INTEGER NOT NULL,
    max_attachment_size_mb INTEGER NOT NULL,
    retention_days INTEGER NOT NULL,
    audit_level TEXT NOT NULL,
    rate_limit_per_min INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_is_custom INTEGER NOT NULL DEFAULT 0,
    visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('public','private')),
    dissolved_at TEXT,
    type TEXT NOT NULL DEFAULT 'group',
    owner_id TEXT NOT NULL DEFAULT '',
    space_id TEXT NOT NULL DEFAULT 'company:default',
    creator_id TEXT NOT NULL DEFAULT '',
    direct_key TEXT UNIQUE,
    last_message_preview TEXT,
    last_message_at TEXT,
    config_agent_id TEXT,
    config_profile_version INTEGER,
    external_source TEXT,
    external_chat_id TEXT,
    target_node_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL DEFAULT 'company:default',
    owner_id TEXT NOT NULL,
    node_id TEXT,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    skills_json TEXT NOT NULL DEFAULT '[]',
    skills_selection_mode TEXT,
    tool_allowlist_json TEXT NOT NULL DEFAULT '[]',
    group_reply_policy TEXT NOT NULL DEFAULT 'manual',
    default_model TEXT,
    model_fallbacks_json TEXT NOT NULL DEFAULT '[]',
    reasoning_effort TEXT,
    approval_mode TEXT CHECK (approval_mode IS NULL OR approval_mode IN ('cc', 'codex')),
    work_mode TEXT NOT NULL DEFAULT 'single_thread',
    workspace_root TEXT,
    workspace_is_default INTEGER,
    registration_seed INTEGER NOT NULL DEFAULT 0,
    pending_create_operation_id TEXT,
    profile_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
, is_stale INTEGER NOT NULL DEFAULT 0, staled_at TEXT, features_json TEXT NOT NULL DEFAULT '{}', custom_prompt TEXT, heartbeat_json TEXT);
CREATE TABLE IF NOT EXISTS agent_create_operations (
    operation_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(owner_id, node_id, agent_id)
);
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    owner_id TEXT,
    node_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline',
    last_heartbeat_at TEXT NOT NULL DEFAULT '',
    agent_count INTEGER NOT NULL DEFAULT 0,
    version TEXT NOT NULL DEFAULT '',
    relay_enabled INTEGER NOT NULL DEFAULT 1,
    reporting_enabled INTEGER NOT NULL DEFAULT 1,
    alias TEXT,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS bind_requests (
    bind_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL,
    bind_token TEXT NOT NULL UNIQUE,
    bind_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT
);
CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_muted INTEGER NOT NULL DEFAULT 0,
    unread_count INTEGER NOT NULL DEFAULT 0,
    last_read_message_id TEXT,
    PRIMARY KEY (conversation_id, user_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    sender_user_id TEXT NOT NULL,
    sender_type TEXT NOT NULL DEFAULT 'user',
    lifecycle_revision INTEGER,
    content TEXT NOT NULL,
    attachments_json TEXT NOT NULL DEFAULT '[]',
    delivery_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tool_calls_json TEXT,
    timezone TEXT,
    token_usage_json TEXT,
    interaction_reply_json TEXT,
    -- feat-439-M2: 整轮多段思考（过程时间线），nullable JSON。无思考的轮 / 旧行为 NULL。
    thinking_json TEXT,
    -- feat-517: terminal subagent/workflow results shown as process items.
    background_returns_json TEXT,
    reply_process_json TEXT,
    -- feat-414: 本轮 agent 处理墙钟耗时（毫秒）。turn_start 建行时为 NULL，
    -- on_message_completed 写入 elapsed_ms = round((T1 − T0) * 1000)。
    elapsed_ms INTEGER,
    sender_display_name TEXT,
    sender_source_id TEXT,
    caller_idempotency_key TEXT,
    system_notice_json TEXT, permission_request_json TEXT, awaiting_permission_at TEXT, kernel_message_id TEXT,
    UNIQUE(conversation_id, caller_idempotency_key),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS message_images (
    image_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    storage_name TEXT NOT NULL,
    UNIQUE(conversation_id, source_key),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS conversation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    message_id TEXT,
    event_type TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS message_delta_idempotency (
    message_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    PRIMARY KEY (message_id, idempotency_key),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS agent_config_boundaries (
    boundary_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    before_message_id TEXT NOT NULL,
    runtime_fingerprint TEXT NOT NULL,
    fingerprint_schema TEXT NOT NULL,
    profile_version INTEGER,
    applied_at TEXT NOT NULL,
    event_id INTEGER NOT NULL UNIQUE,
    UNIQUE(conversation_id, before_message_id, runtime_fingerprint),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (before_message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES conversation_events(event_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS agent_config_operations (
    operation_id TEXT PRIMARY KEY,
    root_operation_id TEXT,
    agent_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    operation_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    candidate_json TEXT NOT NULL,
    previous_candidate_json TEXT,
    candidate_fingerprint TEXT NOT NULL,
    expected_previous_fingerprint TEXT,
    expected_profile_version INTEGER,
    gateway_result_json TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relay_tasks (
    relay_task_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    receipt_status TEXT,
    receipt_detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS agent_message_dispatch_log (
    dispatch_request_key TEXT PRIMARY KEY,
    source_agent_id TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS node_credential_keys (
    node_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    key_id TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    public_key TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channel_manifest_heads (
    node_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    manifest_revision INTEGER NOT NULL DEFAULT 0,
    applied_manifest_revision INTEGER NOT NULL DEFAULT 0,
    last_apply_error_json TEXT,
    applied_at TEXT,
    initialized_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_channels (
    channel_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    provider_identity_fingerprint TEXT NOT NULL,
    provider_identity_revision INTEGER NOT NULL,
    provider_runtime_json TEXT NOT NULL DEFAULT '{}',
    credential_envelope_json TEXT NOT NULL,
    credential_key_id TEXT NOT NULL,
    credential_revision INTEGER NOT NULL,
    channel_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(owner_id, agent_id, provider)
);
CREATE TABLE IF NOT EXISTS agent_channel_removals (
    channel_id TEXT PRIMARY KEY,
    removal_token TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    display_config_json TEXT NOT NULL,
    deleted_channel_revision INTEGER NOT NULL,
    deletion_manifest_revision INTEGER NOT NULL,
    apply_state TEXT NOT NULL,
    apply_error_code TEXT,
    apply_error_message TEXT,
    applied_at TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_channel_status (
    channel_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    observed_revision INTEGER NOT NULL,
    runtime_incarnation TEXT NOT NULL,
    status_sequence INTEGER NOT NULL,
    connection_state TEXT NOT NULL,
    diagnostics_state TEXT NOT NULL,
    status_code TEXT,
    status_message TEXT,
    checks_json TEXT NOT NULL DEFAULT '[]',
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            epoch INTEGER NOT NULL,
            refresh_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        );
CREATE TABLE IF NOT EXISTS auth_ws_tickets (
            ticket_hash TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES auth_sessions(session_id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        );
CREATE TABLE IF NOT EXISTS auth_rate_limits (
            bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at INTEGER NOT NULL
        );
CREATE TABLE IF NOT EXISTS company_member_events (
            id INTEGER PRIMARY KEY,
            actor_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS company_initialization (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            admin_id TEXT NOT NULL,
            active_ids TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS task_graph_mutation_receipts (
            space_id TEXT NOT NULL DEFAULT 'company:default',
            actor_key TEXT NOT NULL, request_key TEXT NOT NULL, operation_hash TEXT NOT NULL,
            graph_id TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            PRIMARY KEY(actor_key,request_key));
CREATE TABLE IF NOT EXISTS task_node_chat_activity (
        graph_id TEXT NOT NULL REFERENCES task_graphs(graph_id) ON DELETE CASCADE,
        node_id TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        updated_at TEXT NOT NULL, PRIMARY KEY(graph_id,node_id,conversation_id));
CREATE TABLE IF NOT EXISTS node_binding_state (
            node_id TEXT PRIMARY KEY, node_epoch INTEGER NOT NULL DEFAULT 0,
            runtime_token_hash TEXT, owner_id TEXT NOT NULL DEFAULT ''
        );
CREATE TABLE IF NOT EXISTS node_installations (
  node_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, node_epoch INTEGER NOT NULL,
  release_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS node_update_operations (
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL, node_id TEXT NOT NULL,
  owner_id TEXT NOT NULL, node_epoch INTEGER NOT NULL, target_json TEXT NOT NULL,
  previous_json TEXT NOT NULL, state TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0,
  relay_gated INTEGER NOT NULL DEFAULT 0, error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(node_id,owner_id,node_epoch,request_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS node_update_one_active ON node_update_operations(node_id)
  WHERE state IN ('requested','downloading','installing','waiting','switching','verifying','rolling_back');
CREATE TABLE IF NOT EXISTS node_update_requests (
  node_id TEXT NOT NULL, owner_id TEXT NOT NULL, node_epoch INTEGER NOT NULL,
  request_id TEXT NOT NULL, operation_id TEXT NOT NULL REFERENCES node_update_operations(id),
  PRIMARY KEY(node_id,owner_id,node_epoch,request_id)
);
CREATE TABLE IF NOT EXISTS node_binding_operations (
            operation_id TEXT PRIMARY KEY, node_id TEXT NOT NULL,
            node_name TEXT NOT NULL, expected_owner TEXT NOT NULL,
            expected_epoch INTEGER NOT NULL, key_id TEXT NOT NULL,
            public_key TEXT NOT NULL, challenge_hash TEXT NOT NULL,
            operation_token_hash TEXT NOT NULL, browser_token_hash TEXT NOT NULL,
            expires_at REAL NOT NULL, state TEXT NOT NULL,
            target_user_id TEXT, target_owner TEXT, snapshot_json TEXT,
            runtime_token TEXT
        );
CREATE TABLE IF NOT EXISTS attachment_storage (
            storage_name TEXT PRIMARY KEY,
            owner_id TEXT,
            byte_size INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL CHECK (state IN ('reserved', 'stored'))
        );
CREATE TABLE IF NOT EXISTS agent_work_query_snapshots (
 snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_work_journals (
 node_id TEXT, journal_id TEXT, through_seq INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(node_id,journal_id));
CREATE TABLE IF NOT EXISTS agent_work_events (
 revision INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, journal_id TEXT, seq INTEGER,
 event_id TEXT UNIQUE NOT NULL, root_agent_id TEXT NOT NULL, session_id TEXT NOT NULL,
 turn_id TEXT, type TEXT NOT NULL, observed_at TEXT, payload TEXT NOT NULL,
 UNIQUE(node_id,journal_id,seq));
CREATE TABLE IF NOT EXISTS agent_work_sessions (
 session_id TEXT PRIMARY KEY, root_agent_id TEXT NOT NULL, node_id TEXT NOT NULL,
 scope TEXT NOT NULL, parent_session_id TEXT, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_work_turns (
 session_id TEXT, turn_id TEXT, seq INTEGER, payload TEXT NOT NULL,
 PRIMARY KEY(session_id,turn_id));
CREATE TABLE IF NOT EXISTS agent_work_items (
 session_id TEXT, turn_id TEXT, item_id TEXT, seq INTEGER, kind TEXT,
 observed_at TEXT, payload TEXT NOT NULL, revision INTEGER,
 PRIMARY KEY(session_id,turn_id,item_id));
CREATE INDEX IF NOT EXISTS task_graphs_owner ON task_graphs(owner_id,updated_at DESC,graph_id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_config_operation_per_agent
ON agent_config_operations(agent_id)
WHERE status IN ('pending', 'gateway_applied');
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_removal_per_provider
ON agent_channel_removals(owner_id, agent_id, provider)
WHERE apply_state != 'applied';
CREATE INDEX IF NOT EXISTS auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS auth_rate_expiry ON auth_rate_limits(expires_at);
-- Replay scans only outstanding tasks for one node, regardless of saved history.
CREATE INDEX IF NOT EXISTS relay_tasks_pending_node
ON relay_tasks(target_node_id,updated_at,created_at)
WHERE receipt_status IS NULL AND status IN ('queued','sent','accepted');
CREATE INDEX IF NOT EXISTS relay_tasks_message ON relay_tasks(message_id,status);
CREATE INDEX IF NOT EXISTS conversation_events_message ON conversation_events(message_id,event_type);
CREATE INDEX IF NOT EXISTS idx_conversations_external_identity
        ON conversations(external_source, external_chat_id, config_agent_id, owner_id)
        ;
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_external_identity_unique
        ON conversations(external_source, external_chat_id, config_agent_id, owner_id)
        WHERE external_source IS NOT NULL AND external_source <> ''
          AND external_chat_id IS NOT NULL AND external_chat_id <> ''
          AND config_agent_id IS NOT NULL AND config_agent_id <> ''
          AND owner_id IS NOT NULL AND owner_id <> ''
        ;
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_conversation_caller_idempotency_key ON messages(conversation_id, caller_idempotency_key) WHERE caller_idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS task_graph_delete_receipt_expiry
        ON task_graph_mutation_receipts(created_at)
        WHERE json_type(result_json,'$.deleted_ids')='array';

-- Personal identity is issued by IM, independent from editable Agent configuration.
CREATE TABLE IF NOT EXISTS personal_agent_bindings (
 binding_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL UNIQUE, owner_user_id TEXT NOT NULL,
 agent_id TEXT NOT NULL UNIQUE, node_id TEXT NOT NULL, node_epoch INTEGER NOT NULL,
 conversation_id TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, request_key TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', initial_goal TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pa_policies (
 binding_id TEXT PRIMARY KEY REFERENCES personal_agent_bindings(binding_id),
 revision INTEGER NOT NULL DEFAULT 1,
 excluded_json TEXT NOT NULL DEFAULT '[]', disclosure_revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS conversation_participation_history (
 conversation_id TEXT NOT NULL, user_id TEXT NOT NULL, PRIMARY KEY(conversation_id,user_id)
);
INSERT OR IGNORE INTO conversation_participation_history SELECT conversation_id,user_id FROM conversation_participants;
CREATE TRIGGER IF NOT EXISTS remember_conversation_participation AFTER INSERT ON conversation_participants BEGIN
 INSERT OR IGNORE INTO conversation_participation_history VALUES(NEW.conversation_id,NEW.user_id);
END;
CREATE TABLE IF NOT EXISTS pa_source_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT, binding_id TEXT NOT NULL, source_event_id INTEGER,
 kind TEXT NOT NULL, conversation_id TEXT, message_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}',
 policy_revision INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
 UNIQUE(binding_id,source_event_id)
);
CREATE TRIGGER IF NOT EXISTS personal_observation_event AFTER INSERT ON conversation_events
WHEN NEW.event_type IN ('message.created','message.completed','conversation.membership_changed','task_graph.changed')
BEGIN
 INSERT OR IGNORE INTO pa_source_events(binding_id,source_event_id,kind,conversation_id,message_id,policy_revision,created_at)
 SELECT b.binding_id,NEW.event_id,NEW.event_type,NEW.conversation_id,NEW.message_id,p.revision,NEW.created_at
 FROM personal_agent_bindings b JOIN pa_policies p ON p.binding_id=b.binding_id
 WHERE b.status='active' AND NEW.conversation_id!=b.conversation_id
 AND EXISTS(SELECT 1 FROM conversation_participants cp WHERE cp.conversation_id=NEW.conversation_id AND cp.user_id=b.owner_user_id)
 AND NOT EXISTS(SELECT 1 FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE m.id=NEW.message_id AND u.username='agent:'||b.agent_id)
 AND NOT EXISTS(SELECT 1 FROM pa_delegated_messages d WHERE d.message_id=NEW.message_id AND d.agent_id=b.agent_id AND d.representation_operation_id IS NOT NULL)
 AND NOT EXISTS(SELECT 1 FROM json_each(p.excluded_json) WHERE value=NEW.conversation_id);
END;
CREATE TABLE IF NOT EXISTS pa_operations (
 operation_id TEXT PRIMARY KEY, binding_id TEXT NOT NULL, request_key TEXT NOT NULL,
 policy_revision INTEGER NOT NULL,
 disclosure_revision INTEGER NOT NULL, conversation_id TEXT NOT NULL, audience_json TEXT NOT NULL,
 payload_json TEXT NOT NULL, payload_digest TEXT NOT NULL, evidence_json TEXT NOT NULL,
 verdict_json TEXT, verdict_ref TEXT, expires_at TEXT, state TEXT NOT NULL DEFAULT 'prepared',
 message_id TEXT, result_json TEXT, created_at TEXT NOT NULL, UNIQUE(binding_id,request_key)
);
CREATE TABLE IF NOT EXISTS pa_delegated_messages (
 message_id TEXT PRIMARY KEY, binding_id TEXT NOT NULL, agent_id TEXT NOT NULL,
 authorized_by TEXT NOT NULL, display_name TEXT NOT NULL,
 representation_operation_id TEXT REFERENCES pa_operations(operation_id)
);
CREATE TABLE IF NOT EXISTS pa_source_reads (
 binding_id TEXT NOT NULL, message_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 policy_revision INTEGER NOT NULL, PRIMARY KEY(binding_id,message_id)
);
CREATE TABLE IF NOT EXISTS pa_incidents (
 id TEXT PRIMARY KEY, binding_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 conversation_id TEXT NOT NULL, source_message_id TEXT NOT NULL, category TEXT NOT NULL,
 reason TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'open',
 owner_notice_message_id TEXT, peer_notice_message_id TEXT,
 UNIQUE(binding_id,source_message_id,category)
);
CREATE TABLE IF NOT EXISTS pa_contact_blocks (
 binding_id TEXT NOT NULL, actor_id TEXT NOT NULL, PRIMARY KEY(binding_id,actor_id)
);
CREATE TRIGGER IF NOT EXISTS personal_membership_revoked AFTER DELETE ON conversation_participants BEGIN
 INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at)
 SELECT b.binding_id,'source.revoked',json_object('conversation_id',OLD.conversation_id),p.revision,strftime('%Y-%m-%dT%H:%M:%fZ','now')
 FROM personal_agent_bindings b JOIN pa_policies p ON p.binding_id=b.binding_id WHERE (b.owner_user_id=OLD.user_id OR EXISTS(SELECT 1 FROM users WHERE id=OLD.user_id AND username='agent:'||b.agent_id))
 AND NOT EXISTS(SELECT 1 FROM conversation_participants cp JOIN users u ON u.id=cp.user_id WHERE cp.conversation_id=OLD.conversation_id AND (cp.user_id=b.owner_user_id OR u.username='agent:'||b.agent_id));
 UPDATE pa_operations SET state='invalidated',verdict_ref=NULL WHERE conversation_id=OLD.conversation_id AND state IN ('prepared','allowed');
END;
CREATE TABLE IF NOT EXISTS pa_node_residencies (
 node_id TEXT NOT NULL, owner_id TEXT NOT NULL, PRIMARY KEY(node_id,owner_id)
);
INSERT OR IGNORE INTO pa_node_residencies SELECT node_id,owner_id FROM personal_agent_bindings;
CREATE TABLE IF NOT EXISTS pa_incident_evidence (
 binding_id TEXT NOT NULL, message_id TEXT NOT NULL, category TEXT NOT NULL, incident_id TEXT NOT NULL,
 PRIMARY KEY(binding_id,message_id,category)
);

CREATE TABLE IF NOT EXISTS pa_runtime_status (
 binding_id TEXT PRIMARY KEY, node_epoch INTEGER NOT NULL, available INTEGER NOT NULL
);
-- Immutable Agent UI and private per-viewer drafts; only submissions become messages.
CREATE TABLE IF NOT EXISTS message_interactive (
    message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    format TEXT NOT NULL,
    catalog_version TEXT NOT NULL,
    source TEXT NOT NULL,
    registry_json TEXT NOT NULL,
    publication_json TEXT,
    supersedes_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
    superseded_by TEXT REFERENCES messages(id) ON DELETE SET NULL,
    read_only INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS interaction_drafts (
    source_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    draft_revision INTEGER NOT NULL DEFAULT 0,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT,
    submission_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
    PRIMARY KEY(source_message_id,user_id)
);
CREATE TABLE IF NOT EXISTS interaction_submissions (
    source_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    semantic_json TEXT NOT NULL
);

-- Navigation metadata only; editable draft content belongs to interaction_drafts.
CREATE TABLE IF NOT EXISTS pa_reply_drafts (
 message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
 target_conversation_id TEXT NOT NULL, source_message_id TEXT NOT NULL,
 field_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_execution_stops (agent_id TEXT NOT NULL, request_key TEXT NOT NULL, conversation_id TEXT NOT NULL, result_json TEXT NOT NULL, PRIMARY KEY(agent_id,request_key));

CREATE TABLE IF NOT EXISTS agent_settings_snapshots (
  agent_id TEXT NOT NULL REFERENCES agent_profiles(agent_id) ON DELETE CASCADE,
  section TEXT NOT NULL CHECK(section IN ('configuration','plugins','cron','usage')),
  owner_id TEXT NOT NULL, node_id TEXT NOT NULL, node_epoch INTEGER NOT NULL,
  workspace_root TEXT, profile_version INTEGER NOT NULL, captured_at TEXT NOT NULL,
  data_json TEXT NOT NULL, PRIMARY KEY(agent_id,section)
);

-- Human lifecycle intent is independent of registration and profile configuration.
CREATE TABLE IF NOT EXISTS agent_lifecycle (
  agent_id TEXT PRIMARY KEY REFERENCES agent_profiles(agent_id) ON DELETE CASCADE,
  desired TEXT NOT NULL DEFAULT 'enabled', revision INTEGER NOT NULL DEFAULT 1,
  disabled_through_revision INTEGER NOT NULL DEFAULT 0,
  request_id TEXT, actor_user_id TEXT, requested_at TEXT NOT NULL,
  applied_revision INTEGER NOT NULL DEFAULT 0, observed TEXT NOT NULL DEFAULT 'enabling',
  process_instance_id TEXT, confirmed_at TEXT, error_code TEXT, error_detail TEXT
);
CREATE TABLE IF NOT EXISTS agent_lifecycle_requests (
  agent_id TEXT NOT NULL REFERENCES agent_profiles(agent_id) ON DELETE CASCADE,
  request_id TEXT NOT NULL, intent TEXT NOT NULL, revision INTEGER NOT NULL,
  PRIMARY KEY(agent_id,request_id)
);
CREATE TABLE IF NOT EXISTS task_lifecycle_freezes (
  graph_id TEXT NOT NULL REFERENCES task_graphs(graph_id) ON DELETE CASCADE,
  node_id TEXT NOT NULL, agent_id TEXT NOT NULL, revision INTEGER NOT NULL,
  PRIMARY KEY(graph_id,node_id)
);
CREATE TRIGGER IF NOT EXISTS agent_lifecycle_created AFTER INSERT ON agent_profiles BEGIN
  INSERT OR IGNORE INTO agent_lifecycle(agent_id,requested_at) VALUES(NEW.agent_id,NEW.created_at);
END;
INSERT OR IGNORE INTO agent_lifecycle(agent_id,requested_at) SELECT agent_id,created_at FROM agent_profiles;

CREATE TRIGGER IF NOT EXISTS personal_observation_lifecycle AFTER INSERT ON pa_source_events BEGIN
  UPDATE pa_source_events SET payload_json=json_set(payload_json,'$.lifecycle_revision',
    (SELECT l.revision FROM agent_lifecycle l JOIN personal_agent_bindings b ON b.agent_id=l.agent_id WHERE b.binding_id=NEW.binding_id))
  WHERE event_id=NEW.event_id;
END;

CREATE TABLE IF NOT EXISTS task_lifecycle_schedules (agent_id TEXT NOT NULL,schedule_id TEXT NOT NULL,graph_id TEXT NOT NULL,node_id TEXT NOT NULL,PRIMARY KEY(agent_id,schedule_id));

-- Private discovery state belongs to the existing PA binding, never to a Task copy.
CREATE TABLE IF NOT EXISTS pa_attention_settings (
 binding_id TEXT PRIMARY KEY REFERENCES personal_agent_bindings(binding_id),
 revision INTEGER NOT NULL DEFAULT 1, settings_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pa_context_receipts (
 id TEXT PRIMARY KEY, binding_id TEXT NOT NULL REFERENCES personal_agent_bindings(binding_id),
 policy_revision INTEGER NOT NULL, request_json TEXT NOT NULL, coverage_json TEXT NOT NULL,
 message_ids_json TEXT NOT NULL, cursor_row INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pa_attention_items (
 id TEXT PRIMARY KEY, binding_id TEXT NOT NULL REFERENCES personal_agent_bindings(binding_id),
 dedup_key TEXT NOT NULL, revision INTEGER NOT NULL, data_json TEXT NOT NULL,
 query_receipt_id TEXT, exploration_batch_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(binding_id,dedup_key)
);
CREATE TABLE IF NOT EXISTS pa_attention_mutations (
 binding_id TEXT NOT NULL, request_key TEXT NOT NULL, payload_json TEXT NOT NULL,
 result_json TEXT NOT NULL, PRIMARY KEY(binding_id,request_key)
);
CREATE TABLE IF NOT EXISTS pa_attention_deliveries (
 operation_id TEXT PRIMARY KEY, binding_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 item_id TEXT, item_revision INTEGER, classification TEXT NOT NULL,
 request_json TEXT NOT NULL, message_id TEXT UNIQUE, created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS pa_attention_delivery_version
 ON pa_attention_deliveries(item_id,item_revision) WHERE item_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS pa_attention_publications (
 message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
 binding_id TEXT NOT NULL, item_id TEXT NOT NULL, item_revision INTEGER NOT NULL,
 actions_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pa_attention_feedback (
 source_message_id TEXT NOT NULL, user_id TEXT NOT NULL, action_key TEXT NOT NULL,
 message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
 PRIMARY KEY(source_message_id,user_id,action_key)
);
