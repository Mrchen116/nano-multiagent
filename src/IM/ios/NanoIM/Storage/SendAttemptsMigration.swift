import Foundation
import GRDB

/// One-time import of durable send attempts from the legacy JSON directory.
///
/// The import runs inside the same transaction that records its marker: a crash either
/// leaves both or neither, and `INSERT OR IGNORE` plus the marker make a re-run a no-op.
/// The legacy directory is never renamed or deleted in this unit — previous builds still
/// read it by exact path, so removing it would break rollback for pre-upgrade attempts.
extension ChatRepository {
    static let sendAttemptMigrationKey = "migration.send_attempts_v1"
    static let sendAttemptMigrationSource = "send_attempts_v1"

    static func itemKey(conversationID: String, sourceMessageID: String?, attemptKey: String) -> String {
        "\(conversationID)\n\(sourceMessageID ?? "")\n\(attemptKey)"
    }

    static func importSendAttempts(db: Database, partition: ChatPartition, legacyAttemptRoot: URL, now: Date) throws {
        let marker = try String.fetchOne(db, sql: "SELECT value FROM cache_meta WHERE key=?", arguments: [sendAttemptMigrationKey])
        guard marker == nil else { return }
        let store = SendAttemptStore(directory: legacyAttemptRoot)
        var imported = 0
        var rejected = 0
        for file in store.attemptFiles(origin: partition.origin, userID: partition.userID) {
            let attempt: SendAttempt
            do {
                attempt = try store.attempt(at: file)
            } catch {
                rejected += 1
                try record(db: db, key: file.lastPathComponent, outcome: "rejected",
                           detail: "unreadable: \(error.localizedDescription)", now: now)
                continue
            }
            let key = itemKey(conversationID: attempt.conversationID,
                              sourceMessageID: attempt.sourceMessageID, attemptKey: attempt.draft.key)
            guard let body = attempt.draft.requestBody else {
                // The current writer refuses to persist an attempt without its frozen request,
                // so this is a defensive branch rather than an expected upgrade state.
                rejected += 1
                try record(db: db, key: key, outcome: "rejected", detail: "missing request body", now: now)
                continue
            }
            let attachments = (try? JSONEncoder().encode(attempt.draft.attachments)).map { String(decoding: $0, as: UTF8.self) } ?? "[]"
            try db.execute(sql: """
                INSERT OR IGNORE INTO pending_sends(conversation_id, source_message_id, attempt_key, content, attachments_json,
                    request_body, created_at, last_error, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """, arguments: [attempt.conversationID, attempt.sourceMessageID ?? "", attempt.draft.key,
                                 attempt.draft.content, attachments, body, migrationISO(now), nil, migrationISO(now)])
            imported += 1
            try record(db: db, key: key, outcome: "imported", detail: nil, now: now)
        }
        try db.execute(sql: "INSERT OR REPLACE INTO cache_meta(key, value) VALUES(?,?)",
                       arguments: [sendAttemptMigrationKey, "imported=\(imported);rejected=\(rejected)"])
    }

    private static func record(db: Database, key: String, outcome: String, detail: String?, now: Date) throws {
        try db.execute(sql: "INSERT INTO migration_report(id, source, item_key, outcome, detail, created_at) VALUES(?,?,?,?,?,?)",
                       arguments: [UUID().uuidString, sendAttemptMigrationSource, key, outcome, detail, migrationISO(now)])
    }

    private static func migrationISO(_ date: Date) -> String { ISO8601DateFormatter().string(from: date) }
}
