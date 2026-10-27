import Foundation
import Testing
@testable import NanoIM

struct ModelServiceContractsTests {
    @Test func editingSnapshotPreservesModelMetadataAndOmitsBlankStoredKey() throws {
        let status = try snapshot(revision: "original")
        var draft = ModelServiceDraft(service: try #require(status.services.first), revision: status.revision)
        draft.display_name = "  新服务名称  "
        let data = try JSONEncoder().encode(draft.payload)
        let body = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(body["revision"] as? String == "original")
        #expect(body["provider"] as? String == "team")
        #expect(body["display_name"] as? String == "新服务名称")
        #expect(body["protocol"] as? String == "openai-responses")
        #expect(body["api_key"] == nil)
        let models = try #require(body["models"] as? [[String: Any]])
        #expect(models.first?["id"] as? String == "research-model")
        #expect(models.first?["context_window"] as? Int == 128_000)
        #expect(models.first?["max_tokens"] as? Int == 8_000)
        #expect(models.first?["input"] as? [String] == ["text", "image"])
        #expect(models.first?["name"] == nil)
        #expect(draft.api_key.isEmpty)
        #expect(draft.credential_stored)
        let catalog = try #require(status.catalog.first?.models.first?.draft)
        #expect(catalog.context_window == 64_000)
        #expect(catalog.max_tokens == 4_000)
        #expect(catalog.input == ["text", "image"])
    }

    @MainActor @Test func conflictChoicesPreserveDraftOrReplaceEntireSelectedService() throws {
        let state = ModelServicesState(client: IMClient(baseURL: URL(string: "https://im.example.test")!), nodeID: "node")
        state.status = try snapshot(revision: "old")
        state.open(try #require(state.status?.services.first))
        state.draft?.display_name = "旅行模型"
        state.draft?.base_url = "https://travel.example/v1"
        state.draft?.models = [.init(id: "travel-model", input: ["text"])]
        state.draft?.api_key = "replacement"
        state.status = try snapshot(revision: "latest")
        state.comparison = state.status
        #expect(state.conflict)
        state.keepDraft()
        #expect(state.draft?.revision == "latest")
        #expect(state.draft?.models.map(\.id) == ["travel-model"])
        #expect(state.draft?.api_key == "replacement")
        state.comparison = state.status
        state.replaceDraft()
        #expect(state.draft?.display_name == "团队模型")
        #expect(state.draft?.base_url == "https://team.example/v1")
        #expect(state.draft?.models.map(\.id) == ["research-model", "fast-model"])
        #expect(state.draft?.protocolName == "openai-responses")
        #expect(state.draft?.models.first?.context_window == 128_000)
        #expect(state.draft?.api_key == "")
        #expect(state.draft?.revision == "latest")
        state.closeEditor(); state.open()
        #expect(state.draft?.provider == nil)
        #expect(state.draft?.display_name.isEmpty == true)
        #expect(state.draft?.models.map(\.id) == [""])
    }

    @MainActor @Test func stoppingWaitPreservesDraftAndReloadsOwnFailure() async throws {
        let transport = ModelServiceTestTransport(responses: [
            try snapshotData(revision: "r1", operation: #"{"id":"own","state":"testing"}"#),
            try snapshotData(revision: "r1", operation: #"{"id":"own","state":"failed","error":{"code":"connection_failed","message":"Failed"}}"#),
            try snapshotData(revision: "r2", operation: #"{"id":"retry","state":"succeeded"}"#)
        ])
        let origin = URL(string: "https://im.example.test")!
        let session = Session(baseURL: origin, transport: transport, credentials: ModelServiceTestCredentials())
        _ = try await session.login(username: "test", password: "test")
        let state = ModelServicesState(client: IMClient(baseURL: origin, session: session), nodeID: "node")
        state.status = try snapshot(revision: "r1")
        state.open(try #require(state.status?.services.first))
        state.draft?.display_name = "新名称"
        await state.save()
        #expect(state.trackedID == "own")
        state.stopWaiting()
        #expect(!state.shouldPoll)
        #expect(!state.canWrite)
        await state.load()
        #expect(state.draft?.display_name == "新名称")
        #expect(state.error?.code == "connection_failed")
        #expect(!state.pending)
        #expect(state.canWrite)
        await state.save()
        #expect(state.draft == nil)
        #expect(state.trackedID == nil)
        #expect(state.notice != nil)
        let actions = await transport.actions
        #expect(actions == ["save", "status", "save"])
    }

    @MainActor @Test func overwrittenOperationRequiresReviewAndCanRecoverWithoutClaimingSuccess() async throws {
        let transport = ModelServiceTestTransport(responses: [
            try snapshotData(revision: "r1", operation: #"{"id":"own","state":"testing"}"#),
            try snapshotData(revision: "r2", operation: #"{"id":"later","state":"testing"}"#),
            try snapshotData(revision: "r2", operation: #"{"id":"later","state":"succeeded"}"#)
        ])
        let origin = URL(string: "https://im.example.test")!
        let session = Session(baseURL: origin, transport: transport, credentials: ModelServiceTestCredentials())
        _ = try await session.login(username: "test", password: "test")
        let state = ModelServicesState(client: IMClient(baseURL: origin, session: session), nodeID: "node")
        state.status = try snapshot(revision: "r1")
        state.open(try #require(state.status?.services.first))
        state.draft?.display_name = "保留的草稿"
        await state.save(); state.stopWaiting()
        await state.load()
        #expect(state.trackedID == nil)
        #expect(state.pending) // The later operation still runs on the computer.
        #expect(state.needsReview)
        #expect(state.comparison == nil)
        #expect(state.draft?.display_name == "保留的草稿")
        await state.load(compare: true)
        #expect(!state.pending)
        #expect(state.conflict)
        #expect(state.draft != nil) // Foreign success never claims this draft was saved.
        state.keepDraft()
        #expect(!state.conflict)
        #expect(state.canWrite)
        #expect(state.draft?.revision == "r2")
        #expect(state.draft?.display_name == "保留的草稿")
    }

    private func snapshot(revision: String) throws -> ModelServiceSetupStatus {
        try JSONDecoder().decode(ModelServiceSetupStatus.self, from: snapshotData(revision: revision))
    }
    private func snapshotData(revision: String, operation: String? = nil) throws -> Data {
        let base = #"{"revision":"REVISION","services":[{"provider":"team","display_name":"团队模型","native":false,"source":"custom","protocol":"openai-responses","base_url":"https://team.example/v1","credential_stored":true,"models":[{"name":"team/research-model","id":"research-model","display_name":"研究模型","context_window":128000,"max_tokens":8000,"input":["text","image"]},{"name":"team/fast-model","id":"fast-model"}]}],"catalog":[{"provider":"openai","display_name":"OpenAI","models":[{"id":"catalog-model","name":"Catalog","contextWindow":64000,"maxTokens":4000,"inputModalities":["text","image"]}]}]}"#
        var object = try #require(JSONSerialization.jsonObject(with: Data(base.replacingOccurrences(of: "REVISION", with: revision).utf8)) as? [String: Any])
        if let operation { object["operation"] = try JSONSerialization.jsonObject(with: Data(operation.utf8)) }
        return try JSONSerialization.data(withJSONObject: object)
    }
}

private final class ModelServiceTestCredentials: CredentialStore, @unchecked Sendable {
    private var value: StoredSession?
    func load() throws -> StoredSession? { value }
    func save(_ value: StoredSession) throws { self.value = value }
    func remove() throws { value = nil }
}

private actor ModelServiceTestTransport: HTTPTransport {
    var responses: [Data]
    var actions: [String] = []
    init(responses: [Data]) { self.responses = responses }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let data: Data
        if request.url?.path == "/im/v1/auth/login" {
            data = Data(#"{"access_token":"access","refresh_token":"refresh","user":{"id":"test","username":"test","display_name":"Test","owner_id":"test","locale":"zh","membership_status":"active","is_company_admin":false,"owned_node_ids":[],"created_at":"2026-10-22"}}"#.utf8)
        } else {
            let input = try JSONDecoder().decode([String: JSONValue].self, from: request.httpBody ?? Data())
            actions.append(input["action"]?.stringValue ?? "")
            data = responses.removeFirst()
        }
        return (data, HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: [:])!)
    }
}
