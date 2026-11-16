import Foundation

/// Whether anything can be shown. Deliberately orthogonal to `ConnectionState`: mixing
/// "have content" with "reachable" produces illegal states such as "loaded but empty but
/// offline" and is what made an offline launch replace the whole list with a spinner.
enum ChatListPhase: Equatable, Sendable {
    /// Nothing to show yet: first install, or just purged.
    case loadingFirst
    /// Content exists (local or network — rendered identically).
    case loaded
    /// A successful full sync explicitly reported no conversations and nothing is left locally.
    case empty
    /// Nothing to show and the first attempt failed. Never rendered as "no conversations".
    case failed
}

/// A successful empty message response is content, not a request still in flight. No-cache
/// offline failure remains a different claim, so the screen never presents it as an empty chat.
enum ChatTimelinePhase: Equatable, Sendable {
    case loadingFirst
    case loaded
    case empty
    case needsConnection
    /// A completed protocol/local read failure is not an ongoing load or a network diagnosis.
    case failed
}

/// How the connection stands, independent of what is on screen.
///
/// `.online` requires both successful content sync and a confirmed live WebSocket.
enum ConnectionState: Equatable, Sendable {
    case starting
    case localOnly
    case syncing
    case online
    case offline(attempt: Int, nextRetryAt: Date?)
    case unavailable(status: Int)
    case unauthorized
    case deactivated

    var isOnline: Bool { self == .online }

    /// Leaves the chat surface entirely; the caller purges the partition.
    var requiresSignOut: Bool { self == .unauthorized || self == .deactivated }
}

/// Read/write failures seen by the correction path, classified in one place.
///
/// Only `.unauthorized` and `.deactivated` remove local content. A transport failure keeps
/// every row and only changes the connection line.
enum ChatFailure: Equatable, Sendable {
    case offline
    case unavailable(status: Int)
    case unauthorized
    case forbidden
    case deactivated

    static func from(_ error: Error) -> ChatFailure {
        if error is URLError { return .offline }
        if let api = error as? APIError {
            switch api.status {
            case 0: return .offline
            case 401: return .unauthorized
            case 403, 404: return .forbidden
            case 408, 429, 500...599: return .unavailable(status: api.status)
            default: return .unavailable(status: api.status)
            }
        }
        return .offline
    }

    /// The connection state this failure implies, or nil when it stays conversation-scoped.
    var connection: ConnectionState? {
        switch self {
        case .offline: return .offline(attempt: 0, nextRetryAt: nil)
        case .unavailable(let status): return .unavailable(status: status)
        case .unauthorized: return .unauthorized
        case .forbidden: return nil
        case .deactivated: return .deactivated
        }
    }
}

/// Lifecycle of the local partition for the signed-in account.
///
/// `.opening` is not a downgrade: the account simply has not finished opening its store yet,
/// so the UI must not claim there is no local cache. Only `.degraded` says that.
enum ChatStorageState: Sendable {
    case opening
    case ready(ChatRepository)
    case degraded(reason: String)
}

enum ChatConnectionText {
    /// Non-empty exactly when the connection is not `.online` (design D7 invariant ①).
    static func describe(_ state: ConnectionState, lastFullAt: String?) -> String {
        switch state {
        case .online: return ""
        case .starting, .syncing: return L("正在连接…", "Connecting…")
        case .localOnly: return withUpdate(L("未连接，正在重试", "Offline. Retrying"), lastFullAt)
        case .offline: return withUpdate(L("未连接，正在重试", "Offline. Retrying"), lastFullAt)
        case .unavailable: return withUpdate(L("服务暂时不可用，稍后重试", "Service unavailable. Retrying soon"), lastFullAt)
        case .unauthorized: return L("需要重新登录。", "Please sign in again.")
        case .deactivated: return L("账号当前不可用。", "This account is unavailable.")
        }
    }

    /// The body under "无法加载聊天". A transport failure and a server-side status are two
    /// different claims: the first can only be about the network, the second is not the user's
    /// connection.
    static func loadFailureBody(_ state: ConnectionState) -> String {
        switch state {
        case .unavailable:
            return L("服务暂时不可用，稍后重试。", "The service is temporarily unavailable. Try again later.")
        default:
            return L("网络似乎不可用。检查网络后重试。", "The network seems unavailable. Check your connection and retry.")
        }
    }

    private static func withUpdate(_ text: String, _ lastFullAt: String?) -> String {
        guard let stamp = absoluteTimestamp(lastFullAt) else { return text }
        return "\(text) · " + L("上次更新 \(stamp)", "Updated \(stamp)")
    }

    /// Same clock format the conversation list already uses (hour:minute, no seconds);
    /// yesterday and older dates stay absolute instead of inventing relative wording.
    /// A fixed `HH:mm` (not the locale's 12-hour style) matches the signed-off copy and keeps
    /// the line short enough to sit next to the connection text.
    static func absoluteTimestamp(_ value: String?, now: Date = Date(), calendar: Calendar = .current) -> String? {
        guard let value, let date = nanoDate(value) else { return nil }
        let time = clock(date, calendar: calendar)
        if calendar.isDate(date, inSameDayAs: now) { return time }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: now),
           calendar.isDate(date, inSameDayAs: yesterday) {
            return L("昨天 \(time)", "Yesterday \(time)")
        }
        let day = dayStamp(date, calendar: calendar)
        return L("\(day) \(time)", "\(day) \(time)")
    }

    private static func clock(_ date: Date, calendar: Calendar) -> String {
        formatter("HH:mm", calendar: calendar).string(from: date)
    }

    private static func dayStamp(_ date: Date, calendar: Calendar) -> String {
        formatter("MM-dd", calendar: calendar).string(from: date)
    }

    private static func formatter(_ format: String, calendar: Calendar) -> DateFormatter {
        let formatter = DateFormatter()
        formatter.calendar = calendar
        formatter.timeZone = calendar.timeZone
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = format
        return formatter
    }
}


/// Correction failures have their own owners; a healthy stream is not evidence that an
/// unrelated history request succeeded (and an HTTP response cannot heal a socket).
enum ChatReadScope: Hashable, Sendable {
    case list
    case detail(String)
    case timeline(String)
    case earlier(String)
    case access(String)

    func belongs(to surface: ChatConnectionSurface) -> Bool {
        switch (self, surface) {
        case (.list, .list): return true
        case (.detail(let id), .conversation(let target)),
             (.timeline(let id), .conversation(let target)),
             (.earlier(let id), .conversation(let target)),
             (.access(let id), .conversation(let target)): return id == target
        default: return false
        }
    }
}

enum ChatConnectionSurface: Equatable, Sendable {
    case list
    case conversation(String)
}

enum ChatConnectionPresentation: Equatable, Sendable {
    case transport
    case read

    var text: String {
        switch self {
        case .transport: return L("连接暂不可用，自动重试中", "Connection unavailable. Retrying automatically")
        case .read: return L("暂时无法更新，轻点重试", "Unable to update. Tap to retry")
        }
    }
}

struct ChatScopedReadFailure: Equatable, Sendable {
    let since: Date
    var failure: ChatFailure
    var message: String
    var isTemporary: Bool
}

/// A value policy owns continuous failure periods, not retry attempts or view lifetimes.
/// No periodic ticking is needed: the adapter only wakes at the earliest silent deadline.
struct ChatConnectionContinuity: Sendable {
    static let quietInterval: TimeInterval = 5
    private(set) var transportSince: Date?
    private(set) var readFailures: [ChatReadScope: ChatScopedReadFailure] = [:]
    private var terminal = false

    mutating func updateTransport(_ state: ConnectionState, now: Date) {
        terminal = state.requiresSignOut
        if state.isOnline || terminal { transportSince = nil }
        else if transportSince == nil { transportSince = now }
        if terminal { readFailures = [:] }
    }

    mutating func readFailed(_ scope: ChatReadScope, failure: ChatFailure, message: String, now: Date, isTemporary: Bool = true) {
        guard !terminal else { return }
        readFailures[scope] = ChatScopedReadFailure(since: readFailures[scope]?.since ?? now,
                                                   failure: failure, message: message, isTemporary: isTemporary)
    }

    mutating func readSucceeded(_ scope: ChatReadScope) { readFailures[scope] = nil }

    func presentation(surface: ChatConnectionSurface, now: Date, hasContent: Bool) -> ChatConnectionPresentation? {
        guard hasContent, !terminal else { return nil }
        if let transportSince, now.timeIntervalSince(transportSince) >= Self.quietInterval { return .transport }
        if readFailures.contains(where: { $0.key.belongs(to: surface) && now.timeIntervalSince($0.value.since) >= Self.quietInterval }) { return .read }
        return nil
    }

    func nextDeadline(after now: Date) -> Date? {
        ([transportSince].compactMap { $0 } + readFailures.values.map(\.since))
            .map { $0.addingTimeInterval(Self.quietInterval) }.filter { $0 > now }.min()
    }
}

/// Private scheduling seam lets tests advance time and release cancelled callbacks without
/// sleeping five seconds or adding a production test hook.
struct ChatContinuityTiming: Sendable {
    var now: @Sendable () -> Date = { Date() }
    var sleep: @Sendable (TimeInterval) async throws -> Void = { try await Task.sleep(for: .seconds($0)) }
}
