import Foundation
import Observation

struct ModelServiceModel: Codable, Sendable, Equatable {
    // Model IDs remain editable; row identity must survive editing and removing adjacent rows.
    var editorID = UUID()
    var id: String
    var display_name: String?
    var context_window: Int?
    var max_tokens: Int?
    var input: [String]?
    private enum CodingKeys: String, CodingKey { case id, display_name, context_window, max_tokens, input }

    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.id == rhs.id && lhs.display_name == rhs.display_name && lhs.context_window == rhs.context_window &&
        lhs.max_tokens == rhs.max_tokens && lhs.input == rhs.input
    }
}

struct ModelService: Decodable, Sendable, Identifiable, Equatable {
    let provider: String
    let display_name: String
    let native: Bool
    let source: String
    let protocolName: String?
    let base_url: String?
    let credential_stored: Bool
    let models: [ModelServiceModel]
    var id: String { provider }
    private enum CodingKeys: String, CodingKey {
        case provider, display_name, native, source, base_url, credential_stored, models
        case protocolName = "protocol"
    }
}

struct ModelServiceCatalog: Decodable, Sendable, Identifiable, Equatable {
    struct Model: Decodable, Sendable, Identifiable, Equatable {
        let id: String
        let name: String?
        let contextWindow: Int?
        let maxTokens: Int?
        let inputModalities: [String]?
        var draft: ModelServiceModel {
            ModelServiceModel(id: id, display_name: name, context_window: contextWindow, max_tokens: maxTokens, input: inputModalities)
        }
    }
    let provider: String
    let display_name: String
    let models: [Model]
    var id: String { provider }
}

struct ModelServiceSetupError: Decodable, Sendable, Equatable {
    struct Dependency: Decodable, Sendable, Identifiable, Equatable {
        let agent_id: String
        let display_name: String
        var id: String { agent_id }
    }
    let code: String
    let message: String
    var dependencies: [Dependency]? = nil
}

struct ModelServiceOperation: Decodable, Sendable, Equatable {
    let id: String
    let state: String
    let message: String?
    let error: ModelServiceSetupError?
    var running: Bool { state == "waiting" || state == "testing" }
}

struct ModelServiceSetupStatus: Decodable, Sendable, Equatable {
    let revision: String
    let services: [ModelService]
    let catalog: [ModelServiceCatalog]
    let catalog_error: String?
    let operation: ModelServiceOperation?
    let error: ModelServiceSetupError?
}

struct ModelServiceSetupInput: Encodable, Sendable {
    enum Action: String, Encodable, Sendable { case status, save, remove }
    var action: Action
    var revision: String?
    var provider: String?
    var source: String?
    var display_name: String?
    var protocolName: String?
    var base_url: String?
    var models: [ModelServiceModel]?
    var api_key: String?
    private enum CodingKeys: String, CodingKey {
        case action, revision, provider, source, display_name, base_url, models, api_key
        case protocolName = "protocol"
    }
}

/// An editor owns a revision-bound copy. Status refreshes never write into this copy.
struct ModelServiceDraft: Equatable {
    var revision: String
    var provider: String?
    var source = "custom"
    var display_name = ""
    var protocolName: String? = "openai-completions"
    var base_url = ""
    var api_key = ""
    var credential_stored = false
    var models = [ModelServiceModel(id: "", input: ["text"])]

    init(revision: String) { self.revision = revision }

    init(service: ModelService, revision: String) {
        self.revision = revision; provider = service.provider; source = service.source
        display_name = service.display_name; protocolName = service.protocolName
        base_url = service.base_url ?? ""; credential_stored = service.credential_stored
        models = service.models
    }

    init(catalog: ModelServiceCatalog, revision: String) {
        self.revision = revision; source = catalog.provider; display_name = catalog.display_name
        protocolName = nil
        models = [catalog.models.first?.draft ?? ModelServiceModel(id: "", input: ["text"])]
    }

    var validationError: String? {
        if display_name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return L("请填写服务名称。", "Enter a service name.")
        }
        if source == "custom" && base_url.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return L("请填写 API 地址。", "Enter an API URL.")
        }
        let ids = models.map { $0.id.trimmingCharacters(in: .whitespacesAndNewlines) }
        if ids.isEmpty || ids.contains("") || Set(ids).count != ids.count {
            return L("至少填写一个模型 ID，同一服务内不能重复。", "Add at least one model ID; IDs must be unique within a service.")
        }
        if models.contains(where: { ($0.context_window.map { $0 <= 0 } ?? false) || ($0.max_tokens.map { $0 <= 0 } ?? false) }) {
            return L("上下文窗口和最大输出须为正整数，或留空使用默认值。", "Token limits must be positive integers, or blank for defaults.")
        }
        return nil
    }

    var payload: ModelServiceSetupInput {
        let trimmedKey = api_key.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedURL = base_url.trimmingCharacters(in: .whitespacesAndNewlines)
        return ModelServiceSetupInput(action: .save, revision: revision, provider: provider, source: source,
            display_name: display_name.trimmingCharacters(in: .whitespacesAndNewlines), protocolName: protocolName,
            base_url: trimmedURL.isEmpty ? nil : trimmedURL,
            models: models.map { model in
                var value = model
                value.id = model.id.trimmingCharacters(in: .whitespacesAndNewlines)
                value.display_name = model.display_name?.trimmingCharacters(in: .whitespacesAndNewlines)
                if value.display_name?.isEmpty == true { value.display_name = nil }
                return value
            }, api_key: trimmedKey.isEmpty ? nil : trimmedKey)
    }
}

extension IMClient {
    func modelServices(nodeID: String, input: ModelServiceSetupInput = .init(action: .status)) async throws -> ModelServiceSetupStatus {
        try await send("/im/v1/nodes/\(nodeID.pathComponent)/setup", body: input)
    }
}

/// One page follows only the operation it submitted; remote work outlives local polling.
@MainActor @Observable final class ModelServicesState {
    let client: IMClient
    let nodeID: String
    var status: ModelServiceSetupStatus?
    var draft: ModelServiceDraft?
    var originalDraft: ModelServiceDraft?
    var comparison: ModelServiceSetupStatus?
    var error: ModelServiceSetupError?
    var readError: String?
    var notice: String?
    var busy = false
    var reading = false
    var needsReview = false
    var stoppedWaiting = false
    var uncertainSubmission = false
    private(set) var trackedID: String?
    private var trackedAction: ModelServiceSetupInput.Action?

    init(client: IMClient, nodeID: String) { self.client = client; self.nodeID = nodeID }
    var dirty: Bool { draft != originalDraft }
    var pending: Bool { trackedID != nil || uncertainSubmission || status?.operation?.running == true }
    var shouldPoll: Bool { status?.operation?.running == true && !stoppedWaiting && readError == nil }
    var conflict: Bool {
        guard let draft else { return false }
        return needsReview || error?.code == "conflict" || (status.map { $0.revision != draft.revision } ?? false)
    }
    var canWrite: Bool { status != nil && readError == nil && !busy && !reading && !pending }
    var catalog: [ModelServiceCatalog] { (status?.catalog ?? []).filter { $0.provider != "openai-codex" } }
    var availableCatalog: [ModelServiceCatalog] {
        catalog.filter { item in !(status?.services.contains { $0.provider == item.provider } ?? false) }
    }

    func open(_ service: ModelService? = nil) {
        guard let status, canWrite else { return }
        clearFeedback()
        let value = service.map { ModelServiceDraft(service: $0, revision: status.revision) } ?? ModelServiceDraft(revision: status.revision)
        draft = value; originalDraft = value
    }

    func closeEditor() { draft = nil; originalDraft = nil; comparison = nil; needsReview = false; error = nil }

    func clearFeedback() { error = nil; notice = nil; comparison = nil; needsReview = false }

    func load(compare: Bool = false) async {
        guard !reading, !busy else { return }
        reading = true
        defer { reading = false }
        do {
            let result = try await client.modelServices(nodeID: nodeID)
            try Task.checkCancellation()
            status = result; readError = nil
            if compare { comparison = result }
            if uncertainSubmission && result.operation?.running != true { uncertainSubmission = false }
            receive(result)
        } catch is CancellationError {} catch {
            readError = settingsError(error)
            if draft != nil { needsReview = true }
        }
    }

    func save() async {
        guard let draft, canWrite, !conflict else { return }
        if let message = draft.validationError { error = .init(code: "invalid", message: message); return }
        await submit(draft.payload)
    }

    func remove(_ service: ModelService, revision: String) async {
        guard canWrite else { return }
        await submit(.init(action: .remove, revision: revision, provider: service.provider))
    }

    private func submit(_ input: ModelServiceSetupInput) async {
        busy = true; error = nil; notice = nil; comparison = nil
        defer { busy = false }
        do {
            let result = try await client.modelServices(nodeID: nodeID, input: input)
            // Keep the accepted operation identity even if the view leaves during the request.
            status = result; readError = nil
            if let issue = result.error {
                error = issue
                if issue.code == "conflict" { needsReview = true }
                return
            }
            guard let operation = result.operation else {
                uncertainSubmission = true; needsReview = true
                notice = L("电脑尚未确认结果。请重读状态，草稿已保留。", "The computer has not confirmed the result. Reload status; your draft is preserved.")
                return
            }
            trackedID = operation.id; trackedAction = input.action; stoppedWaiting = false
            receive(result)
        } catch {
            uncertainSubmission = true; needsReview = true
            readError = settingsError(error)
        }
    }

    private func receive(_ result: ModelServiceSetupStatus) {
        guard let trackedID, let operation = result.operation else { return }
        if operation.id != trackedID {
            // The node keeps only the latest operation, so the old result cannot be fetched again.
            self.trackedID = nil; trackedAction = nil; stoppedWaiting = false
            needsReview = true; comparison = nil
            notice = L("电脑已开始后续操作，无法再确认本次结果。草稿已保留，请读取最新配置并核对后继续。", "The computer has moved on to another operation, so this result can no longer be confirmed. Your draft is preserved; read and review the latest configuration before continuing.")
            return
        }
        guard !operation.running else { return }
        switch operation.state {
        case "succeeded":
            closeEditor(); error = nil
            notice = trackedAction == .remove ? L("服务已移除。", "Service removed.") : L("连接验证成功，已保存。可在助手配置中选择模型。", "Connection verified and saved. Choose the model in assistant settings.")
        case "failed":
            error = operation.error ?? .init(code: "connection_failed", message: L("连接验证失败，请检查地址、模型和密钥后重试。", "Connection verification failed. Check the URL, models and key, then retry."))
        case "cancelled":
            notice = L("电脑已取消操作。草稿已保留，未保存修改。", "The computer cancelled the operation. Your draft is preserved; changes were not saved.")
        default: return
        }
        self.trackedID = nil; trackedAction = nil; stoppedWaiting = false
    }

    func stopWaiting() {
        stoppedWaiting = true
        notice = L("已停止本页等待。电脑上的验证可能仍在进行；重读终态前不能再次保存。", "This page stopped waiting. Verification may continue on the computer; reload its final state before saving again.")
    }

    func keepDraft() {
        guard let comparison, comparison.operation?.running != true, var draft,
              draft.provider == nil || comparison.services.contains(where: { $0.provider == draft.provider }) else { return }
        draft.revision = comparison.revision
        self.draft = draft; clearFeedback()
        notice = L("已核对最新版本，草稿保留。可测试并保存。", "Latest version reviewed; your draft is preserved. You can test and save.")
    }

    func replaceDraft() {
        guard let comparison, let provider = draft?.provider,
              let latest = comparison.services.first(where: { $0.provider == provider }) else { return }
        let value = ModelServiceDraft(service: latest, revision: comparison.revision)
        draft = value; originalDraft = value; clearFeedback()
    }
}
