import XCTest
@testable import NanoIM

@MainActor
final class ConventionsParityTests: XCTestCase {
    private let user = AuthUser(
        id: "owner",
        username: "owner",
        display_name: "Owner",
        owner_id: "owner",
        locale: "en",
        membership_status: "active",
        is_company_admin: true,
        owned_node_ids: [],
        created_at: "2026-10-20T00:00:00Z"
    )

    func testSharedUnreadBadgeGoldenVectorsMatchWebAndDesktop() throws {
        struct VectorFile: Decodable { let cases: [UnreadCase] }
        struct UnreadCase: Decodable {
            let id: String
            let conversations: [InputConv]
            let expected_row_unread: [String: Int]
            let expected_badge_total: Int
        }
        struct InputConv: Decodable {
            let id: String
            let unread_count: Int?
            let is_muted: Bool?
            let local_unseen: Bool?
        }

        let url = try XCTUnwrap(
            Bundle(for: Self.self).url(forResource: "unread-badge-test-cases", withExtension: "json")
        )
        let parsed = try JSONDecoder().decode(VectorFile.self, from: Data(contentsOf: url))

        for testCase in parsed.cases {
            var models: [Conversation] = []
            var unseenIDs = Set<String>()
            for raw in testCase.conversations {
                if raw.local_unseen == true { unseenIDs.insert(raw.id) }
                let conv = Conversation(
                    id: raw.id,
                    title: raw.id,
                    participants: [],
                    participant_ids: ["owner"],
                    type: "group",
                    owner_id: "owner",
                    creator_id: "owner",
                    is_pinned: false,
                    is_muted: raw.is_muted ?? false,
                    unread_count: raw.unread_count ?? 0,
                    created_at: "2026-10-20T00:00:00Z"
                )
                XCTAssertEqual(
                    conv.rowUnreadBadge(localUnseen: raw.local_unseen == true),
                    testCase.expected_row_unread[raw.id],
                    "\(testCase.id):\(raw.id)"
                )
                models.append(conv)
            }
            XCTAssertEqual(
                Conversation.totalUnreadBadge(models, localUnseenIDs: unseenIDs),
                testCase.expected_badge_total,
                testCase.id
            )
        }
    }

    func testSharedTimelineDividerGoldenVectorsMatchWebAcrossTimezones() throws {
        struct VectorFile: Decodable { let cases: [DividerCase] }
        struct DividerCase: Decodable {
            let id: String
            let timezone: String
            let items: [RawItem]
            let expected_divider_ids: [String]
        }
        struct RawItem: Decodable {
            let type: String
            let id: String
            let created_at: String?
            let has_system_notice: Bool?
        }

        let url = try XCTUnwrap(
            Bundle(for: Self.self).url(forResource: "timeline-divider-test-cases", withExtension: "json")
        )
        let parsed = try JSONDecoder().decode(VectorFile.self, from: Data(contentsOf: url))

        for testCase in parsed.cases {
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = try XCTUnwrap(TimeZone(identifier: testCase.timezone), testCase.id)
            let items: [TimelineItem] = try testCase.items.map { raw in
                if raw.type != "message" {
                    return TimelineItem(
                        type: raw.type,
                        boundaryID: raw.id,
                        before_message_id: nil,
                        applied_at: raw.created_at
                    )
                }
                var msgDict: [String: Any] = [
                    "id": raw.id,
                    "conversation_id": "chat",
                    "sender": ["type": "user", "id": "u1"],
                    "sender_user_id": "u1",
                    "sender_type": "user",
                    "content": raw.id,
                    "attachments": [],
                    "delivery_status": "completed",
                    "created_at": raw.created_at ?? "2026-10-20T00:00:00Z"
                ]
                if raw.has_system_notice == true {
                    msgDict["system_notice"] = ["kind": "task_graph"]
                }
                let payload: [String: Any] = ["type": "message", "message": msgDict]
                return try JSONDecoder().decode(
                    TimelineItem.self,
                    from: JSONSerialization.data(withJSONObject: payload)
                )
            }
            let actualSet = ChatTimelinePresentation.timestampMessageIDs(in: items, calendar: calendar)
            let orderedActual = testCase.items.map(\.id).filter { actualSet.contains($0) }
            XCTAssertEqual(orderedActual, testCase.expected_divider_ids, testCase.id)
        }
    }

    func testGeneratedContractsDecodeUnknownValuesSafelyAndKeepNineTaskStatuses() throws {
        XCTAssertEqual(TaskStatusContract.allCases.count, 9)
        for status in TaskStatusContract.allCases {
            XCTAssertFalse(taskStatus(status.rawValue).isEmpty)
            XCTAssertNotEqual(taskStatusIcon(status.rawValue), "circle.dashed")
        }
        let future = try JSONDecoder().decode(
            WireEnum<UserNotificationKindContract>.self,
            from: Data(#""future_server_kind""#.utf8)
        )
        XCTAssertNil(future.knownValue)
        XCTAssertEqual(future.rawValue, "future_server_kind")
    }

    func testNotificationHintsFixHumanAndExternalBannersRouteThreadsAndWorkAndKeepBodyPrivate() async throws {
        let key = "nano.foregroundReminders"
        let previous = UserDefaults.standard.object(forKey: key)
        UserDefaults.standard.set(true, forKey: key)
        defer {
            if let previous { UserDefaults.standard.set(previous, forKey: key) }
            else { UserDefaults.standard.removeObject(forKey: key) }
        }

        let store = ChatStore(client: IMClient(baseURL: URL(string: "https://im.example.test")!), user: user)
        defer { store.resetProjection() }
        store.conversations = [
            Conversation(
                id: "chat-open", title: "Open Room", participants: [], participant_ids: ["owner"],
                type: "group", owner_id: "owner", creator_id: "owner", is_pinned: false,
                is_muted: false, unread_count: 1, created_at: "now"
            ),
            Conversation(
                id: "chat-muted", title: "Muted Room", participants: [], participant_ids: ["owner"],
                type: "group", owner_id: "owner", creator_id: "owner", is_pinned: false,
                is_muted: true, unread_count: 5, created_at: "now"
            )
        ]
        XCTAssertEqual(Conversation.totalUnreadBadge(store.conversations), 1)

        // 1. Ordinary human `message.created` with `notification_hint` raises banner without leaking body
        let humanFrame = Data(#"""
        {"op":"event","event_type":"message.created","event_id":1,"conversation_id":"chat-open",
         "data":{"conversation_id":"chat-open","message_id":"m-human","sender_type":"user","sender_user_id":"bob","content":"Top secret salary figure"},
         "notification_hint":{"eligible":true,"kind":"human_message","dedupe_key":"message:m-human","is_muted":false,"mentions_viewer":false,"conversation_id":"chat-open","conversation_unread":2,"sender_name":"Bob","preview_text":"Top secret salary figure","target_route":"/chat/chat-open"}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: humanFrame))
        XCTAssertEqual(store.banner?.conversationID, "chat-open")
        XCTAssertFalse(store.banner?.summaryLabel.contains("secret") ?? true)
        XCTAssertEqual(Conversation.totalUnreadBadge(store.conversations), 2)
        store.banner = nil

        // 2. Owner's own external Feishu/WeChat mirror (`eligible: false`) does NOT trigger banner
        let ownerMirror = Data(#"""
        {"op":"event","event_type":"message.created","event_id":2,"conversation_id":"chat-open",
         "data":{"conversation_id":"chat-open","message_id":"m-wx-self","sender_type":"user","sender_user_id":"owner"},
         "notification_hint":{"eligible":false,"dedupe_key":"message:m-wx-self","is_muted":false,"mentions_viewer":false,"conversation_id":"chat-open","target_route":"/chat/chat-open"}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: ownerMirror))
        XCTAssertNil(store.banner)

        // 3. External peer inbound (`sender_user_id == "owner"` in DB, `eligible: true` in hint) DOES trigger banner
        let peerInbound = Data(#"""
        {"op":"event","event_type":"message.created","event_id":3,"conversation_id":"chat-open",
         "data":{"conversation_id":"chat-open","message_id":"m-wx-peer","sender_type":"user","sender_user_id":"owner"},
         "notification_hint":{"eligible":true,"kind":"human_message","dedupe_key":"message:m-wx-peer","is_muted":false,"mentions_viewer":false,"conversation_id":"chat-open","sender_name":"External Peer","target_route":"/chat/chat-open"}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: peerInbound))
        XCTAssertEqual(store.banner?.conversationID, "chat-open")
        store.banner = nil

        // 4. Muted conversation suppresses ordinary reply, allows @mention with threadRootID
        let mutedOrdinary = Data(#"""
        {"op":"event","event_type":"message.completed","event_id":4,"conversation_id":"chat-muted",
         "data":{"conversation_id":"chat-muted","message_id":"m-muted-1"},
         "notification_hint":{"eligible":true,"kind":"message_completed","dedupe_key":"message:m-muted-1","is_muted":true,"mentions_viewer":false,"conversation_id":"chat-muted","target_route":"/chat/chat-muted"}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: mutedOrdinary))
        XCTAssertNil(store.banner)

        let mutedMention = Data(#"""
        {"op":"event","event_type":"message.created","event_id":5,"conversation_id":"chat-muted",
         "data":{"conversation_id":"chat-muted","message_id":"m-muted-at","thread_root_message_id":"root-88"},
         "notification_hint":{"eligible":true,"kind":"mention","dedupe_key":"message:m-muted-at","is_muted":true,"mentions_viewer":true,"conversation_id":"chat-muted","thread_root_message_id":"root-88","target_route":"/chat/chat-muted?thread=root-88"}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: mutedMention))
        XCTAssertEqual(store.banner?.conversationID, "chat-muted")
        XCTAssertEqual(store.banner?.threadRootID, "root-88")
        store.banner = nil

        // 5. Work `waiting_permission` routes to Agent Work and deduplicates same turn
        let workPerm = Data(#"""
        {"op":"event","event_type":"agent.work.updated",
         "data":{"agent_id":"pa_main","revision":9},
         "notification_hint":{"eligible":true,"kind":"work_permission","dedupe_key":"work-perm:pa_main:s1:t1","is_muted":false,"mentions_viewer":false,"agent_id":"pa_main","sender_name":"PA Assistant","target_route":"/settings/agents/pa_main?view=work"}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: workPerm))
        XCTAssertEqual(store.banner?.agentID, "pa_main")
        store.banner = nil
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: workPerm))
        XCTAssertNil(store.banner)

        // 6. `conversation.read` zeroes unread badge immediately
        let readFrame = Data(#"""
        {"op":"event","event_type":"conversation.read","conversation_id":"chat-open",
         "data":{"conversation_id":"chat-open","unread_count":0,"is_muted":false}}
        """#.utf8)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: readFrame))
        XCTAssertEqual(Conversation.totalUnreadBadge(store.conversations), 0)
    }

    func testPendingThreadTargetScopesToConversationAndDecodesMessageDetailEnvelope() async throws {
        let pair = try JSONEncoder().encode(TokenPair(access_token: "tok", refresh_token: "ref", user: user))
        let transport = ThreadDetailMockTransport(pair: pair)
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: dir) }
        let session = Session(
            baseURL: URL(string: "https://im.example.test")!,
            transport: transport,
            credentials: EmptyCredentials(),
            sendAttempts: SendAttemptStore(directory: dir)
        )
        _ = try await session.login(username: "owner", password: "pw")
        let store = ChatStore(client: IMClient(baseURL: session.baseURL, session: session), user: user)
        defer { store.resetProjection() }

        store.pendingThreadTarget = .init(conversationID: "chat-muted", rootMessageID: "root-88")

        // Opening another conversation neither fetches nor clears `chat-muted`'s target
        let wrongChat = await store.resolvePendingThreadRoot(conversationID: "chat-open")
        XCTAssertNil(wrongChat)
        XCTAssertEqual(store.pendingThreadTarget, .init(conversationID: "chat-muted", rootMessageID: "root-88"))
        let pathsBefore = await transport.requestedPaths
        XCTAssertTrue(pathsBefore.isEmpty)

        // Opening `chat-muted` fetches `/im/v1/conversations/chat-muted/messages/root-88`,
        // decodes `{ message, execution_cleanup_revision }`, and clears `pendingThreadTarget`
        let resolved = await store.resolvePendingThreadRoot(conversationID: "chat-muted")
        XCTAssertEqual(resolved?.id, "root-88")
        XCTAssertEqual(resolved?.content, "Older thread root outside latest 50")
        XCTAssertNil(store.pendingThreadTarget)
        let pathsAfter = await transport.requestedPaths
        XCTAssertEqual(pathsAfter, ["/im/v1/conversations/chat-muted/messages/root-88"])
    }
}

private struct EmptyCredentials: CredentialStore {
    func load() throws -> StoredSession? { nil }
    func save(_ value: StoredSession) throws {}
    func remove() throws {}
}

private actor ThreadDetailMockTransport: HTTPTransport {
    let pair: Data
    var requestedPaths: [String] = []
    init(pair: Data) { self.pair = pair }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let url = request.url!
        if url.path.contains("/auth/") {
            return (pair, HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: [:])!)
        }
        requestedPaths.append(url.path)
        let envelope = Data(#"""
        {"message":{"id":"root-88","conversation_id":"chat-muted","sender_type":"user","sender_user_id":"bob","sender":{"type":"user","id":"bob","display_name":"Bob"},"content":"Older thread root outside latest 50","attachments":[],"delivery_status":"completed","created_at":"2026-04-17T08:00:00.000Z"},"execution_cleanup_revision":3}
        """#.utf8)
        return (envelope, HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: [:])!)
    }
}
