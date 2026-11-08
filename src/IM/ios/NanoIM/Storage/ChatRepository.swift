import Foundation
import GRDB

enum ChatRevokeReason: String, Sendable {
    case snapshotAbsent = "snapshot_absent"
    case detailForbidden = "detail_forbidden"
    case membershipDenied = "membership_denied"
}

/// Values the launch path needs before any network call. Pending records are exposed as a
/// count only: the migration runs before the first `/sync`, so those rows have no
/// conversation to attach to yet (design D12).
struct ChatBootstrapSeed: Sendable {
    var conversations: [Conversation]
    var drafts: [String: String]
    var pendingCount: Int
    var connection: ChatConnectionSeed
}

struct ChatConnectionSeed: Sendable, Equatable {
    var lastFullAt: String?
    var maxEventID: Int
    var snapshotSeq: Int
}

struct ChatTimelinePage: Sendable {
    var items: [TimelineItem]
    var nextBefore: String?
    var isAtLocalStart: Bool
    /// The local window was trimmed, so older messages exist on the server but not here.
    var olderNeedsNetwork: Bool
}

struct ChatSnapshotResult: Sendable {
    var conversations: [Conversation]
    var revoked: [String]
    var pendingCount: Int
    var snapshotSeq: Int
    var maxEventID: Int
}

/// One line of the one-time import ledger, exposed for diagnostics and evidence.
struct ChatMigrationRecord: Sendable, Equatable {
    var itemKey: String
    var outcome: String
    var detail: String?
}

enum ChatEventResult: Sendable, Equatable {
    case ignored
    case refresh(conversationID: String?)
    case revoked(conversationID: String)
}

/// The single writer for one `(origin, userID)` chat partition.
///
/// Every SQL statement runs here; `ChatStore` and views only see value types. Reads and
/// writes share one `DatabaseQueue` on purpose: the invariant this unit relies on is a
/// single writer, so concurrent reads are not offered as an accidental capability.
actor ChatRepository {
    /// Page size the message endpoint asks for; the retained window is derived from it.
    static let pageSize = 60
    /// Local window: at least five pages, so scrolling "two screens back" stays offline-readable.
    static var retentionLimit: Int { max(300, pageSize * 5) }
    /// Hard ceiling so repeated paging cannot grow the file without bound.
    static var retentionHardLimit: Int { retentionLimit * 4 }

    nonisolated let partition: ChatPartition
    nonisolated let location: ChatStorageLocation
    /// Regenerated when the partition is opened; every write must carry the current value.
    nonisolated let epoch = UUID()

    private let queue: DatabaseQueue
    private var closed = false

    private init(partition: ChatPartition, location: ChatStorageLocation, queue: DatabaseQueue) {
        self.partition = partition
        self.location = location
        self.queue = queue
    }

    /// Open (and migrate) the partition, rebuilding once if the file is unusable.
    ///
    /// A corrupt or half-written database is moved aside rather than deleted: the legacy
    /// send-attempt JSON stays untouched, so the recreated database re-imports it.
    static func open(_ partition: ChatPartition,
                     location: ChatStorageLocation,
                     legacyAttemptRoot: URL = ChatStorageLocation.legacyAttemptRoot,
                     now: Date = Date()) throws -> ChatRepository {
        try location.prepare()
        do {
            return try openOnce(partition: partition, location: location, legacyAttemptRoot: legacyAttemptRoot, now: now)
        } catch {
            // IO, protection, full-disk and schema errors do not prove corruption. Rebuilding
            // for those failures would silently replace recoverable local pending requests.
            guard let databaseError = error as? DatabaseError,
                  databaseError.resultCode == .SQLITE_CORRUPT || databaseError.resultCode == .SQLITE_NOTADB,
                  location.quarantineCorruptDatabase() != nil else {
                throw ChatRepositoryError.databaseUnavailable(error.localizedDescription)
            }
            do {
                return try openOnce(partition: partition, location: location, legacyAttemptRoot: legacyAttemptRoot, now: now, rebuilt: true)
            } catch {
                throw ChatRepositoryError.databaseUnavailable(error.localizedDescription)
            }
        }
    }

    private static func openOnce(partition: ChatPartition,
                                 location: ChatStorageLocation,
                                 legacyAttemptRoot: URL,
                                 now: Date,
                                 rebuilt: Bool = false) throws -> ChatRepository {
        var configuration = Configuration()
        // A wiped database would hide migration defects; tests ask for a clean file explicitly.
        configuration.foreignKeysEnabled = true
        let queue = try DatabaseQueue(path: location.databaseURL.path, configuration: configuration)
        var migrator = DatabaseMigrator()
        migrator.eraseDatabaseOnSchemaChange = false
        migrator.registerMigration("v1") { db in try createSchema(db) }
        migrator.registerMigration("v2_discarded_messages") { db in
            // Discard can precede a cached conversation or overlap an older page. Keep its
            // identity independently of messages so neither case can resurrect the row.
            try db.execute(sql: """
                CREATE TABLE discarded_messages(
                    conversation_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    PRIMARY KEY(conversation_id, message_id));
                """)
        }
        try migrator.migrate(queue)
        let repository = ChatRepository(partition: partition, location: location, queue: queue)
        try queue.write { db in
            try db.execute(sql: "INSERT OR REPLACE INTO cache_meta(key, value) VALUES('schema.version', '2')")
            try db.execute(sql: "INSERT OR REPLACE INTO cache_meta(key, value) VALUES('partition.origin', ?)", arguments: [partition.origin.absoluteString])
            try db.execute(sql: "INSERT OR REPLACE INTO cache_meta(key, value) VALUES('partition.user_id', ?)", arguments: [partition.userID])
            try importSendAttempts(db: db, partition: partition, legacyAttemptRoot: legacyAttemptRoot, now: now)
        }
        try location.protectDatabaseFile()
        return repository
    }

    // MARK: - Schema

    private static func createSchema(_ db: Database) throws {
        try db.execute(sql: """
            CREATE TABLE cache_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE sync_cursor(
                id INTEGER PRIMARY KEY CHECK(id = 1),
                max_event_id INTEGER NOT NULL,
                snapshot_seq INTEGER NOT NULL,
                updated_at TEXT);
            CREATE TABLE conversations(
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                direct_kind TEXT,
                owner_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                is_pinned INTEGER NOT NULL,
                is_muted INTEGER NOT NULL,
                unread_count INTEGER NOT NULL,
                last_message_preview TEXT,
                last_message_at TEXT,
                created_at TEXT NOT NULL,
                run_state TEXT,
                source_agent_id TEXT,
                source_node_id TEXT,
                external_source TEXT,
                external_chat_id TEXT,
                visibility TEXT,
                dissolved_at TEXT,
                is_member INTEGER,
                can_write INTEGER,
                is_observer INTEGER,
                can_change_visibility INTEGER,
                participant_ids_json TEXT NOT NULL DEFAULT '[]',
                sort_at TEXT NOT NULL,
                refreshed_at TEXT,
                trimmed_at TEXT);
            CREATE TABLE actors(
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                display_name TEXT,
                user_id TEXT,
                is_stale INTEGER,
                updated_at TEXT);
            CREATE TABLE conversation_members(
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                actor_id TEXT NOT NULL REFERENCES actors(id),
                position INTEGER NOT NULL,
                PRIMARY KEY(conversation_id, actor_id));
            CREATE TABLE messages(
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                sort_key TEXT NOT NULL,
                sender_type TEXT,
                sender_actor_id TEXT,
                sender_user_id TEXT,
                sender_display_name TEXT,
                delivery_status TEXT,
                kernel_message_id TEXT,
                pa_agent_id TEXT,
                content TEXT,
                attachments_json TEXT,
                payload_json TEXT NOT NULL,
                written_at TEXT NOT NULL);
            CREATE TABLE conversation_boundaries(
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                agent_id TEXT,
                before_message_id TEXT NOT NULL,
                applied_at TEXT);
            CREATE TABLE drafts(
                conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                updated_at TEXT NOT NULL);
            CREATE TABLE read_state(
                conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
                last_read_message_id TEXT,
                reported_at TEXT);
            CREATE TABLE pending_sends(
                conversation_id TEXT NOT NULL,
                source_message_id TEXT NOT NULL DEFAULT '',
                attempt_key TEXT NOT NULL,
                content TEXT NOT NULL,
                attachments_json TEXT NOT NULL,
                request_body BLOB NOT NULL,
                created_at TEXT,
                last_error TEXT,
                updated_at TEXT,
                PRIMARY KEY(conversation_id, source_message_id, attempt_key));
            CREATE TABLE revoked_conversations(
                conversation_id TEXT PRIMARY KEY,
                revoked_at TEXT NOT NULL,
                reason TEXT NOT NULL);
            CREATE TABLE migration_report(
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                item_key TEXT NOT NULL,
                outcome TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL);
            CREATE INDEX conversations_order ON conversations(is_pinned DESC, sort_at DESC);
            CREATE INDEX messages_window ON messages(conversation_id, sort_key DESC);
            CREATE INDEX boundaries_anchor ON conversation_boundaries(conversation_id, before_message_id);
            CREATE INDEX pending_by_conversation ON pending_sends(conversation_id);
            INSERT INTO sync_cursor(id, max_event_id, snapshot_seq, updated_at) VALUES(1, 0, 0, NULL);
            """)
    }

    // MARK: - Reading

    func writeContext() throws -> ChatWriteContext {
        try read { db in
            ChatWriteContext(epoch: epoch, snapshotSeq: try Self.snapshotSeq(db))
        }
    }

    func bootstrapSeed() throws -> ChatBootstrapSeed {
        try read { db in
            let conversations = try Self.loadConversations(db)
            var drafts: [String: String] = [:]
            for row in try Row.fetchAll(db, sql: "SELECT conversation_id, body FROM drafts") {
                let id: String = row["conversation_id"]
                drafts[id] = row["body"]
            }
            let pending = try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM pending_sends") ?? 0
            return ChatBootstrapSeed(conversations: conversations, drafts: drafts, pendingCount: pending,
                                     connection: try Self.connectionSeed(db))
        }
    }

    func conversations() throws -> [Conversation] {
        try read { db in try Self.loadConversations(db) }
    }

    func conversation(_ id: String) throws -> Conversation? {
        try read { db in try Self.loadConversations(db, only: id).first }
    }

    func connectionSeed() throws -> ChatConnectionSeed {
        try read { db in try Self.connectionSeed(db) }
    }

    func revokedConversations() throws -> Set<String> {
        try read { db in Set(try String.fetchAll(db, sql: "SELECT conversation_id FROM revoked_conversations")) }
    }

    func pendingCount() throws -> Int {
        try read { db in try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM pending_sends") ?? 0 }
    }

    /// The one-time import ledger, in insertion order. Nothing in the app reads it; it exists
    /// so the upgrade path can be inspected (and proven) without opening the database by hand.
    func migrationReport() throws -> [ChatMigrationRecord] {
        try read { db in
            try Row.fetchAll(db, sql: "SELECT item_key, outcome, detail FROM migration_report ORDER BY rowid")
                .map { ChatMigrationRecord(itemKey: $0["item_key"], outcome: $0["outcome"], detail: $0["detail"]) }
        }
    }

    func pendingAttempts() throws -> [SendAttempt] {
        try read { db in
            try Row.fetchAll(db, sql: "SELECT * FROM pending_sends ORDER BY conversation_id, source_message_id, attempt_key")
                .compactMap { row in
                    guard let body: Data = row["request_body"], let content: String = row["content"] else { return nil }
                    let source: String = row["source_message_id"]
                    let attachments = (try? Self.decode([ChatAttachment].self, from: row["attachments_json"] as String? ?? "[]")) ?? []
                    let draft = PendingSend(key: row["attempt_key"], content: content, attachments: attachments, requestBody: body)
                    return SendAttempt(conversationID: row["conversation_id"], sourceMessageID: source.isEmpty ? nil : source, draft: draft)
                }
        }
    }

    func draft(_ id: String) throws -> String? {
        try read { db in
            try String.fetchOne(db, sql: "SELECT body FROM drafts WHERE conversation_id=?", arguments: [id])
        }
    }

    /// The whole locally retained window, ascending. `nextBefore` is only offered when the
    /// window was trimmed: otherwise the caller's network cursor decides whether more exists.
    func timeline(_ id: String, limit: Int = ChatRepository.retentionLimit) throws -> ChatTimelinePage {
        try read { db in try Self.timelinePage(db, id: id, limit: limit) }
    }

    // MARK: - Snapshot

    func applySnapshot(_ items: [Conversation], maxEventID: Int, snapshotSeq: Int,
                       write context: ChatWriteContext) throws -> ChatSnapshotResult {
        try write { db in
            try validate(context, db: db)
            let current = try Self.snapshotSeq(db)
            guard snapshotSeq > current else { throw ChatRepositoryError.staleWrite }
            let authoritative = Set(items.map(\.id))
            // Identities, not conversation rows: a migrated pending record may have no row yet.
            var identities = Set(try String.fetchAll(db, sql: "SELECT id FROM conversations"))
            identities.formUnion(try String.fetchAll(db, sql: "SELECT DISTINCT conversation_id FROM pending_sends"))
            identities.formUnion(try String.fetchAll(db, sql: "SELECT conversation_id FROM revoked_conversations"))
            identities.formUnion(try String.fetchAll(db, sql: "SELECT DISTINCT conversation_id FROM discarded_messages"))
            var revoked: [String] = []
            for id in identities.subtracting(authoritative).sorted() {
                // Only newly revoked conversations are reported: a tombstone is revisited by
                // every later snapshot, and reporting it again would re-clear a row the store
                // already dropped (or, worse, tell the UI something disappeared twice).
                let known = try Self.isRevoked(id, db: db)
                try Self.revokeRows(id, reason: .snapshotAbsent, db: db, now: Date())
                if !known { revoked.append(id) }
            }
            for item in items {
                try Self.upsertConversation(item, db: db)
                try db.execute(sql: "DELETE FROM revoked_conversations WHERE conversation_id=?", arguments: [item.id])
            }
            for item in items where item.can_write == false || item.dissolved_at != nil {
                try Self.deletePendingRows(item.id, db: db)
            }
            let stored = try Int.fetchOne(db, sql: "SELECT max_event_id FROM sync_cursor WHERE id=1") ?? 0
            try db.execute(sql: "UPDATE sync_cursor SET max_event_id=?, snapshot_seq=?, updated_at=? WHERE id=1",
                           arguments: [max(stored, maxEventID), snapshotSeq, Self.iso(Date())])
            try db.execute(sql: "INSERT OR REPLACE INTO cache_meta(key, value) VALUES('sync.last_full_at', ?)", arguments: [Self.iso(Date())])
            return ChatSnapshotResult(conversations: try Self.loadConversations(db), revoked: revoked,
                                      pendingCount: try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM pending_sends") ?? 0,
                                      snapshotSeq: snapshotSeq, maxEventID: max(stored, maxEventID))
        }
    }

    func applyConversation(_ value: Conversation, members: [ActorRef],
                           write context: ChatWriteContext) throws -> Conversation {
        try write { db in
            try validate(context, db: db)
            try Self.upsertConversation(value, members: members, db: db)
            try db.execute(sql: "DELETE FROM revoked_conversations WHERE conversation_id=?", arguments: [value.id])
            return value
        }
    }

    /// A `/conversations` page may add rows but is never authority for absence, so nothing is
    /// deleted here. It may, however, prove access again (a tombstone the server contradicts).
    func applyConversationList(_ items: [Conversation],
                               write context: ChatWriteContext) throws -> [Conversation] {
        try write { db in
            try validate(context, db: db)
            for item in items {
                try Self.upsertConversation(item, db: db)
                try db.execute(sql: "DELETE FROM revoked_conversations WHERE conversation_id=?", arguments: [item.id])
            }
            return try Self.loadConversations(db)
        }
    }

    /// Explicit pending-row removal for a conversation that can no longer be written to.
    /// A conversation that stays visible (read-only or dissolved) keeps its row and gains no
    /// tombstone; only the unconfirmed sends lose their conclusion path.
    func deletePending(conversationID: String, write context: ChatWriteContext) throws {
        try write { db in
            try validate(context, db: db)
            try Self.deletePendingRows(conversationID, db: db)
        }
    }

    func applyPage(_ id: String, items: [TimelineItem], write context: ChatWriteContext) throws -> ChatTimelinePage {
        try write { db in
            try validate(context, db: db)
            guard try Self.isRevoked(id, db: db) == false else { throw ChatRepositoryError.revokedConversation(id) }
            let writtenAt = Self.iso(Date())
            var incoming = Set<String>()
            let discarded = Set(try String.fetchAll(db, sql: "SELECT message_id FROM discarded_messages WHERE conversation_id=?", arguments: [id]))
            for item in items {
                if let message = item.message {
                    guard !discarded.contains(message.id) else { continue }
                    try Self.upsertMessage(message, writtenAt: writtenAt, db: db)
                    incoming.insert(message.id)
                } else if let boundaryID = item.boundaryID, !discarded.contains(item.before_message_id ?? "") {
                    try db.execute(sql: """
                        INSERT OR REPLACE INTO conversation_boundaries(id, conversation_id, type, agent_id, before_message_id, applied_at)
                        VALUES(?,?,?,?,?,?)
                        """, arguments: [boundaryID, id, item.type, item.agent_id, item.before_message_id, item.applied_at])
                }
            }
            try Self.refreshConversationProjection(id, db: db)
            try Self.trim(id, protecting: incoming, db: db)
            return try Self.timelinePage(db, id: id, limit: Self.retentionLimit)
        }
    }

    /// Live events only advance the high-water mark and ask the caller to reload the
    /// affected conversation: the event payload is not a complete message DTO, so writing
    /// message rows from it would store a projection the server never confirmed.
    func applyEvent(_ event: UserEvent, write context: ChatWriteContext) throws -> ChatEventResult {
        try write { db in
            try validate(context, db: db)
            let conversation = event.data?["conversation_id"].stringValue
            if let conversation, try Self.isRevoked(conversation, db: db) {
                return .revoked(conversationID: conversation)
            }
            if event.event_type == "message.discarded", let conversation,
               let messageID = event.data?["message_id"].stringValue {
                try db.execute(sql: "INSERT OR IGNORE INTO discarded_messages(conversation_id, message_id) VALUES(?,?)",
                               arguments: [conversation, messageID])
                try Self.deleteMessages([messageID], conversationID: conversation, db: db)
                try db.execute(sql: "DELETE FROM conversation_boundaries WHERE conversation_id=? AND before_message_id=?",
                               arguments: [conversation, messageID])
                try Self.refreshConversationProjection(conversation, db: db)
                if try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM messages WHERE conversation_id=?", arguments: [conversation]) == 0 {
                    try db.execute(sql: "UPDATE conversations SET last_message_preview=NULL, last_message_at=NULL, sort_at=created_at WHERE id=?",
                                   arguments: [conversation])
                }
            }
            if let eventID = event.event_id {
                let stored = try Int.fetchOne(db, sql: "SELECT max_event_id FROM sync_cursor WHERE id=1") ?? 0
                if eventID > stored {
                    try db.execute(sql: "UPDATE sync_cursor SET max_event_id=? WHERE id=1", arguments: [eventID])
                }
            }
            return event.event_type == nil ? .ignored : .refresh(conversationID: conversation)
        }
    }

    func revoke(_ id: String, reason: ChatRevokeReason, write context: ChatWriteContext) throws {
        try write { db in
            try validate(context, db: db)
            try Self.revokeRows(id, reason: reason, db: db, now: Date())
            // Detail denial is as authoritative as snapshot absence. Invalidate contexts
            // captured by older successful detail/list/page requests in this transaction.
            try db.execute(sql: "UPDATE sync_cursor SET snapshot_seq=snapshot_seq+1 WHERE id=1")
        }
    }

    func setDraft(_ id: String, body: String) throws {
        try write { db in
            if body.isEmpty {
                try db.execute(sql: "DELETE FROM drafts WHERE conversation_id=?", arguments: [id])
            } else {
                try db.execute(sql: "INSERT OR REPLACE INTO drafts(conversation_id, body, updated_at) VALUES(?,?,?)",
                               arguments: [id, body, Self.iso(Date())])
            }
        }
    }

    func upsertPending(_ attempt: SendAttempt, write context: ChatWriteContext) throws {
        try write { db in
            try validate(context, db: db)
            guard try Self.isRevoked(attempt.conversationID, db: db) == false else {
                throw ChatRepositoryError.revokedConversation(attempt.conversationID)
            }
            guard let body = attempt.draft.requestBody else { throw ChatRepositoryError.staleWrite }
            let attachments = (try? Self.encode(attempt.draft.attachments)) ?? Data("[]".utf8)
            try db.execute(sql: """
                INSERT OR REPLACE INTO pending_sends(conversation_id, source_message_id, attempt_key, content, attachments_json, request_body, created_at, last_error, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """, arguments: [attempt.conversationID, attempt.sourceMessageID ?? "", attempt.draft.key,
                                 attempt.draft.content, String(decoding: attachments, as: UTF8.self), body,
                                 Self.iso(Date()), nil, Self.iso(Date())])
            // The composer text moves into the frozen request, so keeping the draft too would
            // show the same content twice while the send stays unconfirmed.
            try db.execute(sql: "DELETE FROM drafts WHERE conversation_id=?", arguments: [attempt.conversationID])
        }
    }

    func removePending(_ attempt: SendAttempt, write context: ChatWriteContext) throws {
        try write { db in
            try validate(context, db: db)
            try db.execute(sql: "DELETE FROM pending_sends WHERE conversation_id=? AND source_message_id=? AND attempt_key=?",
                           arguments: [attempt.conversationID, attempt.sourceMessageID ?? "", attempt.draft.key])
        }
    }

    /// U1 records the boundary the server confirmed and never reads it back; unread stays the
    /// server projection until U3 owns the rules.
    func markReadBoundary(_ id: String, messageID: String) throws {
        try write { db in
            try db.execute(sql: "INSERT OR REPLACE INTO read_state(conversation_id, last_read_message_id, reported_at) VALUES(?,?,?)",
                           arguments: [id, messageID, Self.iso(Date())])
        }
    }

    /// Partition-level cleanup: rows first (so a failed file removal cannot leave readable
    /// content), then the connection, then the directory.
    func purge() throws {
        guard !closed else { return }
        try queue.write { db in
            for table in ["messages", "conversation_boundaries", "conversation_members", "actors", "drafts",
                          "read_state", "pending_sends", "revoked_conversations", "discarded_messages", "migration_report", "conversations"] {
                try db.execute(sql: "DELETE FROM \(table)")
            }
            try db.execute(sql: "UPDATE sync_cursor SET max_event_id=0, snapshot_seq=snapshot_seq+1, updated_at=NULL WHERE id=1")
            try db.execute(sql: "DELETE FROM cache_meta WHERE key LIKE 'sync.%'")
        }
        closed = true
        try queue.close()
        try location.removeAll()
    }

    /// Release an unusable connection without deleting recoverable local requests.
    func close() throws {
        guard !closed else { return }
        try queue.close()
        closed = true
    }

    /// Diagnostics and tests: empty rows, keep the file.
    func reset() throws {
        try queue.write { db in
            for table in ["messages", "conversation_boundaries", "conversation_members", "actors", "drafts",
                          "read_state", "pending_sends", "revoked_conversations", "discarded_messages", "migration_report", "conversations"] {
                try db.execute(sql: "DELETE FROM \(table)")
            }
            try db.execute(sql: "UPDATE sync_cursor SET max_event_id=0, snapshot_seq=0, updated_at=NULL WHERE id=1")
        }
    }

    // MARK: - Internals

    private func validate(_ context: ChatWriteContext, db: Database) throws {
        guard !closed, context.epoch == epoch else { throw ChatRepositoryError.staleWrite }
        guard context.snapshotSeq == (try Self.snapshotSeq(db)) else { throw ChatRepositoryError.staleWrite }
    }

    private func read<T>(_ body: (Database) throws -> T) throws -> T {
        guard !closed else { throw ChatRepositoryError.databaseUnavailable("closed") }
        return try queue.read(body)
    }

    private func write<T>(_ body: (Database) throws -> T) throws -> T {
        guard !closed else { throw ChatRepositoryError.databaseUnavailable("closed") }
        return try queue.write(body)
    }

    private static func snapshotSeq(_ db: Database) throws -> Int {
        try Int.fetchOne(db, sql: "SELECT snapshot_seq FROM sync_cursor WHERE id=1") ?? 0
    }

    private static func connectionSeed(_ db: Database) throws -> ChatConnectionSeed {
        let row = try Row.fetchOne(db, sql: "SELECT max_event_id, snapshot_seq FROM sync_cursor WHERE id=1")
        let lastFullAt = try String.fetchOne(db, sql: "SELECT value FROM cache_meta WHERE key='sync.last_full_at'")
        return ChatConnectionSeed(lastFullAt: lastFullAt,
                                  maxEventID: row?["max_event_id"] ?? 0,
                                  snapshotSeq: row?["snapshot_seq"] ?? 0)
    }

    private static func isRevoked(_ id: String, db: Database) throws -> Bool {
        try Bool.fetchOne(db, sql: "SELECT EXISTS(SELECT 1 FROM revoked_conversations WHERE conversation_id=?)", arguments: [id]) ?? false
    }

    /// The only delete primitive for pending rows. Callers must have decided that the
    /// conversation is unusable; a dismissed tombstone drops its reason, a repeat keeps it.
    private static func revokeRows(_ id: String, reason: ChatRevokeReason, db: Database, now: Date) throws {
        try deletePendingRows(id, db: db, reason: reason)
        try db.execute(sql: "DELETE FROM discarded_messages WHERE conversation_id=?", arguments: [id])
        try db.execute(sql: "DELETE FROM conversations WHERE id=?", arguments: [id])
        let exists = try isRevoked(id, db: db)
        if !exists {
            try db.execute(sql: "INSERT INTO revoked_conversations(conversation_id, revoked_at, reason) VALUES(?,?,?)",
                           arguments: [id, iso(now), reason.rawValue])
        }
    }

    /// Deletes every pending row of one conversation and books the loss only for rows that
    /// actually came from the JSON migration, so a repeated snapshot cannot append rows.
    @discardableResult
    private static func deletePendingRows(_ id: String, db: Database, reason: ChatRevokeReason? = nil) throws -> Int {
        let rows = try Row.fetchAll(db, sql: "SELECT source_message_id, attempt_key FROM pending_sends WHERE conversation_id=?", arguments: [id])
        guard !rows.isEmpty else { return 0 }
        try db.execute(sql: "DELETE FROM pending_sends WHERE conversation_id=?", arguments: [id])
        guard let reason else { return rows.count }
        for row in rows {
            let source: String = row["source_message_id"]
            let key: String = row["attempt_key"]
            let itemKey = "\(id)\n\(source)\n\(key)"
            let imported = try Bool.fetchOne(db, sql: """
                SELECT EXISTS(SELECT 1 FROM migration_report WHERE source='send_attempts_v1' AND item_key=? AND outcome='imported')
                """, arguments: [itemKey]) ?? false
            guard imported else { continue }
            try db.execute(sql: """
                INSERT INTO migration_report(id, source, item_key, outcome, detail, created_at) VALUES(?,?,?,?,?,?)
                """, arguments: [UUID().uuidString, "send_attempts_v1", itemKey, "orphaned", reason.rawValue, iso(Date())])
        }
        return rows.count
    }

    /// Updates an existing row instead of replacing it: `INSERT OR REPLACE` deletes the old
    /// row first, and `messages` / `conversation_boundaries` / `drafts` / `read_state` cascade
    /// from `conversations(id)`, so a title refresh would silently drop the whole timeline.
    /// `trimmed_at` keeps its first value; everything else follows the freshest projection.
    private static func upsertConversation(_ item: Conversation, members: [ActorRef]? = nil, db: Database) throws {
        let participantIDs = (try? encode(item.participant_ids)).map { String(decoding: $0, as: UTF8.self) } ?? "[]"
        try db.execute(sql: """
            INSERT INTO conversations(id, title, type, direct_kind, owner_id, creator_id, is_pinned, is_muted,
                unread_count, last_message_preview, last_message_at, created_at, run_state, source_agent_id, source_node_id,
                external_source, external_chat_id, visibility, dissolved_at, is_member, can_write, is_observer,
                can_change_visibility, participant_ids_json, sort_at, refreshed_at, trimmed_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, type=excluded.type, direct_kind=excluded.direct_kind,
                owner_id=excluded.owner_id, creator_id=excluded.creator_id, is_pinned=excluded.is_pinned,
                is_muted=excluded.is_muted, unread_count=excluded.unread_count,
                last_message_preview=excluded.last_message_preview, last_message_at=excluded.last_message_at,
                created_at=excluded.created_at, run_state=excluded.run_state,
                source_agent_id=excluded.source_agent_id, source_node_id=excluded.source_node_id,
                external_source=excluded.external_source, external_chat_id=excluded.external_chat_id,
                visibility=excluded.visibility, dissolved_at=excluded.dissolved_at,
                is_member=excluded.is_member, can_write=excluded.can_write, is_observer=excluded.is_observer,
                can_change_visibility=excluded.can_change_visibility,
                participant_ids_json=excluded.participant_ids_json,
                sort_at=MAX(conversations.sort_at, excluded.sort_at),
                refreshed_at=excluded.refreshed_at
            """, arguments: [item.id, item.title, item.type, item.direct_kind, item.owner_id, item.creator_id,
                             item.is_pinned ? 1 : 0, item.is_muted ? 1 : 0, item.unread_count,
                             item.last_message_preview, item.last_message_at, item.created_at, item.run_state,
                             item.source_agent_id, item.source_node_id, item.external_source, item.external_chat_id,
                             item.visibility, item.dissolved_at, item.is_member.map { $0 ? 1 : 0 },
                             item.can_write.map { $0 ? 1 : 0 }, item.is_observer.map { $0 ? 1 : 0 },
                             item.can_change_visibility.map { $0 ? 1 : 0 }, participantIDs,
                             item.last_message_at ?? item.created_at, iso(Date())])
        let participants = members ?? item.participants
        for (position, actor) in participants.enumerated() {
            // Same reason as above: an actor row is referenced by `conversation_members`, so a
            // REPLACE would have to delete a row that other conversations still point at.
            try db.execute(sql: """
                INSERT INTO actors(id, type, display_name, user_id, is_stale, updated_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET type=excluded.type, display_name=excluded.display_name,
                    user_id=excluded.user_id, is_stale=excluded.is_stale, updated_at=excluded.updated_at
                """, arguments: [actor.id, actor.type, actor.display_name, actor.user_id, actor.is_stale.map { $0 ? 1 : 0 }, iso(Date())])
            try db.execute(sql: "INSERT OR REPLACE INTO conversation_members(conversation_id, actor_id, position) VALUES(?,?,?)",
                           arguments: [item.id, actor.id, position])
        }
        if participants.isEmpty {
            try db.execute(sql: "DELETE FROM conversation_members WHERE conversation_id=?", arguments: [item.id])
        }
        // Members removed by a title/participant update must not survive as @-targets.
        let keep = Set(participants.map(\.id))
        for row in try String.fetchAll(db, sql: "SELECT actor_id FROM conversation_members WHERE conversation_id=?", arguments: [item.id])
        where !keep.contains(row) {
            try db.execute(sql: "DELETE FROM conversation_members WHERE conversation_id=? AND actor_id=?", arguments: [item.id, row])
        }
    }

    private static func upsertMessage(_ message: ChatMessage, writtenAt: String, db: Database) throws {
        let payload = (try? encode(message)).map { String(decoding: $0, as: UTF8.self) } ?? "{}"
        let attachments = (try? encode(message.attachments)).map { String(decoding: $0, as: UTF8.self) } ?? "[]"
        try db.execute(sql: """
            INSERT OR REPLACE INTO messages(id, conversation_id, created_at, sort_key, sender_type, sender_actor_id,
                sender_user_id, sender_display_name, delivery_status, kernel_message_id, pa_agent_id, content,
                attachments_json, payload_json, written_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, arguments: [message.id, message.conversation_id, message.created_at, sortKey(createdAt: message.created_at, id: message.id),
                             message.sender_type, message.sender.id, message.sender_user_id, message.sender.display_name,
                             message.delivery_status, message.kernel_message_id, message.pa_agent_id, message.content,
                             attachments, payload, writtenAt])
    }

    /// Keeps the list row consistent with a freshly loaded page without inventing unread state.
    private static func refreshConversationProjection(_ id: String, db: Database) throws {
        guard let row = try Row.fetchOne(db, sql: """
            SELECT payload_json, created_at FROM messages WHERE conversation_id=? ORDER BY sort_key DESC LIMIT 1
            """, arguments: [id]) else { return }
        guard let message = try? decode(ChatMessage.self, from: row["payload_json"] as String) else { return }
        try db.execute(sql: """
            UPDATE conversations SET last_message_at=?, last_message_preview=COALESCE(?, last_message_preview),
                sort_at=MAX(sort_at, ?), refreshed_at=? WHERE id=?
            """, arguments: [message.created_at, preview(of: message), message.created_at, iso(Date()), id])
    }

    private static func preview(of message: ChatMessage) -> String? {
        let text = message.content.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty { return text }
        guard let first = message.attachments.first else { return nil }
        return first.file_name ?? first.content_type ?? "attachment"
    }

    private static func trim(_ id: String, protecting incoming: Set<String>, db: Database) throws {
        var total = try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM messages WHERE conversation_id=?", arguments: [id]) ?? 0
        guard total > retentionLimit else { return }
        var removed: [String] = []
        let candidates = try String.fetchAll(db, sql: "SELECT id FROM messages WHERE conversation_id=? ORDER BY sort_key ASC", arguments: [id])
        // An older page that was just fetched must survive the trim it triggers; otherwise
        // scrolling back online would delete the rows it just received.
        let deletable = candidates.filter { !incoming.contains($0) }.prefix(total - retentionLimit)
        removed.append(contentsOf: deletable)
        if !removed.isEmpty {
            try deleteMessages(removed, conversationID: id, db: db)
            total -= removed.count
        }
        if total > retentionHardLimit {
            let overflow = total - retentionHardLimit
            let oldest = try String.fetchAll(db, sql: "SELECT id FROM messages WHERE conversation_id=? ORDER BY sort_key ASC LIMIT ?",
                                             arguments: [id, overflow])
            try deleteMessages(oldest, conversationID: id, db: db)
            removed.append(contentsOf: oldest)
        }
        guard !removed.isEmpty else { return }
        // A boundary whose anchor row is gone would be re-anchored above the whole window by
        // TimelineMerge, so it is deleted in the same transaction.
        try db.execute(sql: "DELETE FROM conversation_boundaries WHERE conversation_id=? AND before_message_id IN (\(placeholders(removed.count)))",
                       arguments: StatementArguments([id] + removed))
        try db.execute(sql: "UPDATE conversations SET trimmed_at=? WHERE id=? AND trimmed_at IS NULL",
                       arguments: [iso(Date()), id])
    }

    private static func deleteMessages(_ ids: [String], conversationID: String, db: Database) throws {
        guard !ids.isEmpty else { return }
        try db.execute(sql: "DELETE FROM messages WHERE conversation_id=? AND id IN (\(placeholders(ids.count)))",
                       arguments: StatementArguments([conversationID] + ids))
    }

    private static func timelinePage(_ db: Database, id: String, limit: Int) throws -> ChatTimelinePage {
        let rows = try Row.fetchAll(db, sql: "SELECT payload_json FROM messages WHERE conversation_id=? ORDER BY sort_key DESC LIMIT ?",
                                    arguments: [id, limit])
        let messages = rows.reversed().compactMap { row in (try? decode(ChatMessage.self, from: row["payload_json"] as String)) }
        let ids = messages.map(\.id)
        var boundaries: [String: [TimelineItem]] = [:]
        if !ids.isEmpty {
            for row in try Row.fetchAll(db, sql: """
                SELECT * FROM conversation_boundaries WHERE conversation_id=? AND before_message_id IN (\(placeholders(ids.count))) ORDER BY id
                """, arguments: StatementArguments([id] + ids)) {
                let item = TimelineItem(type: row["type"], message: nil, boundaryID: row["id"],
                                        conversation_id: row["conversation_id"], agent_id: row["agent_id"],
                                        before_message_id: row["before_message_id"], applied_at: row["applied_at"])
                boundaries[item.before_message_id ?? "", default: []].append(item)
            }
        }
        var items: [TimelineItem] = []
        for message in messages {
            items.append(contentsOf: boundaries[message.id] ?? [])
            items.append(TimelineItem(type: "message", message: message))
        }
        let trimmedAt = try String.fetchOne(db, sql: "SELECT trimmed_at FROM conversations WHERE id=?", arguments: [id])
        return ChatTimelinePage(items: items,
                                nextBefore: trimmedAt == nil ? nil : messages.first?.id,
                                isAtLocalStart: trimmedAt == nil,
                                olderNeedsNetwork: trimmedAt != nil)
    }

    private static func loadConversations(_ db: Database, only id: String? = nil) throws -> [Conversation] {
        let rows: [Row]
        if let id {
            rows = try Row.fetchAll(db, sql: "SELECT * FROM conversations WHERE id=?", arguments: [id])
        } else {
            rows = try Row.fetchAll(db, sql: "SELECT * FROM conversations ORDER BY is_pinned DESC, sort_at DESC")
        }
        guard !rows.isEmpty else { return [] }
        var members: [String: [(Int, ActorRef)]] = [:]
        for row in try Row.fetchAll(db, sql: """
            SELECT m.conversation_id, m.position, a.id, a.type, a.display_name, a.user_id, a.is_stale
            FROM conversation_members m JOIN actors a ON a.id = m.actor_id
            """) {
            let actor = ActorRef(type: row["type"], id: row["id"], display_name: row["display_name"],
                                 user_id: row["user_id"], is_stale: (row["is_stale"] as Int?).map { $0 == 1 })
            members[row["conversation_id"], default: []].append((row["position"], actor))
        }
        return rows.map { row in
            let chatID: String = row["id"]
            let participants = (members[chatID] ?? []).sorted { $0.0 < $1.0 }.map(\.1)
            let participantIDs = (try? decode([String].self, from: row["participant_ids_json"] as String? ?? "[]")) ?? []
            func flag(_ key: String) -> Bool? { (row[key] as Int?).map { $0 == 1 } }
            return Conversation(id: chatID, title: row["title"], participants: participants,
                                participant_ids: participantIDs, type: row["type"], direct_kind: row["direct_kind"],
                                owner_id: row["owner_id"], creator_id: row["creator_id"],
                                is_pinned: (row["is_pinned"] as Int? ?? 0) == 1, is_muted: (row["is_muted"] as Int? ?? 0) == 1,
                                unread_count: row["unread_count"] ?? 0, last_message_preview: row["last_message_preview"],
                                last_message_at: row["last_message_at"], created_at: row["created_at"],
                                run_state: row["run_state"], source_agent_id: row["source_agent_id"],
                                source_node_id: row["source_node_id"], external_source: row["external_source"],
                                external_chat_id: row["external_chat_id"], visibility: row["visibility"],
                                dissolved_at: row["dissolved_at"], is_member: flag("is_member"),
                                can_write: flag("can_write"), is_observer: flag("is_observer"),
                                can_change_visibility: flag("can_change_visibility"))
        }
    }

    // MARK: - Helpers

    private static func placeholders(_ count: Int) -> String {
        Array(repeating: "?", count: count).joined(separator: ",")
    }

    /// Mirrors `TimelineMerge`'s `(created_at, id)` ordering so the local first paint and the
    /// network merge cannot disagree about order.
    private static func sortKey(createdAt: String, id: String) -> String {
        createdAt + "\u{1}" + id
    }

    private static func iso(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }

    private static func encode<T: Encodable>(_ value: T) throws -> Data {
        try JSONEncoder().encode(value)
    }

    private static func decode<T: Decodable>(_ type: T.Type, from value: String) throws -> T {
        guard let data = value.data(using: .utf8) else { throw ChatRepositoryError.databaseUnavailable("undecodable column") }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

extension ChatRepositoryError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .staleWrite: return L("这次结果已过期，已被较新的同步结果取代。", "This result is stale and was superseded by a newer sync.")
        case .revokedConversation: return L("你已无法访问此聊天。", "You no longer have access to this conversation.")
        case .databaseUnavailable(let reason): return reason
        }
    }
}
