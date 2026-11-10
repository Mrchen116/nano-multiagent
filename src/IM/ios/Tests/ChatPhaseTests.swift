import XCTest
@testable import NanoIM

/// The two orthogonal phases and the error classification that feeds them. These are pure
/// values on purpose: a single wrong mapping here is what turns "offline" into a login form.
final class ChatPhaseTests: XCTestCase {
    private let allStates: [ConnectionState] = [.starting, .localOnly, .syncing, .online,
                                                .offline(attempt: 2, nextRetryAt: nil),
                                                .unavailable(status: 503), .unauthorized, .deactivated]

    func testConnectionTextIsNonEmptyExactlyWhenNotOnline() {
        for state in allStates {
            let text = ChatConnectionText.describe(state, lastFullAt: nil)
            XCTAssertEqual(text.isEmpty, state == .online, "invariant ①: \(state)")
        }
    }

    func testOnlyTerminalStatesLeaveTheChatSurface() {
        for state in allStates {
            XCTAssertEqual(state.requiresSignOut, state == .unauthorized || state == .deactivated, "\(state)")
        }
    }

    func testFailureClassification() {
        XCTAssertEqual(ChatFailure.from(URLError(.notConnectedToInternet)), .offline)
        XCTAssertEqual(ChatFailure.from(APIError(status: 0, detail: "bad origin")), .offline)
        XCTAssertEqual(ChatFailure.from(APIError(status: 401, detail: "expired")), .unauthorized)
        XCTAssertEqual(ChatFailure.from(APIError(status: 403, detail: "gone")), .forbidden)
        XCTAssertEqual(ChatFailure.from(APIError(status: 404, detail: "gone")), .forbidden)
        for status in [408, 429, 500, 502, 503] {
            XCTAssertEqual(ChatFailure.from(APIError(status: status, detail: "later")), .unavailable(status: status))
        }
        // A conversation-scoped refusal never changes the connection phase.
        XCTAssertNil(ChatFailure.forbidden.connection)
        XCTAssertEqual(ChatFailure.unauthorized.connection, .unauthorized)
        XCTAssertEqual(ChatFailure.unavailable(status: 503).connection, .unavailable(status: 503))
    }

    func testLoadFailureBodySplitsNetworkFromService() {
        XCTAssertEqual(ChatConnectionText.loadFailureBody(.offline(attempt: 0, nextRetryAt: nil)),
                       L("网络似乎不可用。检查网络后重试。", "The network seems unavailable. Check your connection and retry."))
        XCTAssertEqual(ChatConnectionText.loadFailureBody(.unavailable(status: 503)),
                       L("服务暂时不可用，稍后重试。", "The service is temporarily unavailable. Try again later."))
    }

    func testAbsoluteTimestampUsesHoursAndMinutesOnly() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try XCTUnwrap(TimeZone(identifier: "Asia/Shanghai"))
        let now = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-11-05T12:00:00Z"))  // 20:00 local
        let today = ChatConnectionText.absoluteTimestamp("2026-11-05T15:40:00Z", now: now, calendar: calendar)
        XCTAssertNotNil(today)
        XCTAssertEqual(today?.count, 5, "hour:minute, no seconds: \(today ?? "nil")")
        XCTAssertEqual(today, "23:40")

        let yesterday = ChatConnectionText.absoluteTimestamp("2026-11-04T15:40:00Z", now: now, calendar: calendar)
        XCTAssertNotNil(yesterday)
        XCTAssertTrue(yesterday?.hasSuffix("23:40") == true, "\(yesterday ?? "nil")")
        XCTAssertTrue(yesterday?.count ?? 0 > 5, "yesterday carries a day marker, not only a clock")
        XCTAssertEqual(yesterday, L("昨天 23:40", "Yesterday 23:40"), "Use the injected calendar day, not the test host's date")

        let older = ChatConnectionText.absoluteTimestamp("2026-11-03T15:40:00Z", now: now, calendar: calendar)
        XCTAssertEqual(older, "11-03 23:40")

        XCTAssertNil(ChatConnectionText.absoluteTimestamp(nil, now: now, calendar: calendar))
        XCTAssertNil(ChatConnectionText.absoluteTimestamp("not a date", now: now, calendar: calendar))
    }

    func testLastFullAtIsShownAsRecordedNotAsNow() {
        let text = ChatConnectionText.describe(.offline(attempt: 1, nextRetryAt: nil),
                                               lastFullAt: "2026-11-05T15:40:00Z")
        XCTAssertTrue(text.hasPrefix(L("未连接，正在重试", "Offline. Retrying")))
        XCTAssertTrue(text.contains(L("上次更新", "Updated")), "invariant ③: the stamp comes from the store: \(text)")
        XCTAssertTrue(ChatConnectionText.describe(.online, lastFullAt: "2026-11-05T15:40:00Z").isEmpty,
                      "invariant ①: a healthy connection says nothing")
    }

    @MainActor
    func testProjectionResetReturnsToLoadingFirst() async throws {
        let user = AuthUser(id: "user", username: "user", display_name: "User", owner_id: "user", locale: "en",
                            membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")
        let store = ChatStore(client: IMClient(baseURL: URL(string: "https://im.example.test")!), user: user)
        store.listPhase = .loaded
        store.connection = .online
        store.conversations = [try JSONDecoder().decode(Conversation.self, from: Data(#"{"id":"a","title":"A","participants":[],"participant_ids":[],"type":"group","owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}"#.utf8))]
        store.resetProjection()
        XCTAssertEqual(store.listPhase, .loadingFirst, "purge returns the content phase, not `empty`")
        XCTAssertEqual(store.connection, .starting)
        XCTAssertTrue(store.conversations.isEmpty)
        guard case .opening = store.storage else {
            return XCTFail("storage state is owned by the controller and is not reset here")
        }
    }
}
