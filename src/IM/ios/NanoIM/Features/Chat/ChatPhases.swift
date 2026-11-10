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
}

/// How the connection stands, independent of what is on screen.
///
/// `.online` is only entered after a successful `/sync`, never after a socket handshake.
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
