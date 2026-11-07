import Foundation
import Observation

struct DraftFlushResult: Sendable {
    enum Reason: Sendable { case transient, conflict }
    var updatedAt: String?
    var reason: Reason?
}

struct DraftConflictColumn: Identifiable, Equatable {
    let name: String
    let label: String
    let remote: String
    let local: String
    var id: String { name }
}

struct DraftFailure: Identifiable {
    let id: String
    let title: String
    let reason: DraftFlushResult.Reason
    let offline: Bool
}

/// Coordinates private writes, not background selection. Only successful local PUTs own watermarks.
@MainActor @Observable
final class InteractionDraftCoordinator {
    private struct WeakRuntime { weak var value: InteractiveRuntime? }
    @MainActor private final class Departure {
        let id = UUID()
        let cutoffs: [ObjectIdentifier: Int]
        var through: String?
        var baselineStarted = false
        init(_ runtimes: [InteractiveRuntime], through: String?) {
            cutoffs = Dictionary(uniqueKeysWithValues: runtimes.map { (ObjectIdentifier($0), $0.editSerial) })
            self.through = through
        }
    }
    let client: IMClient
    let userID: String
    private(set) var watermarks: [String: String]
    private(set) var failures: [String: [String: DraftFailure]] = [:]
    @ObservationIgnored private var runtimes: [String: [String: WeakRuntime]] = [:]
    // Preserve unresolved offscreen edits until explicit recovery, not just until row recycling.
    @ObservationIgnored private var retained: [String: [String: InteractiveRuntime]] = [:]
    @ObservationIgnored private var departures: [String: [Departure]] = [:]
    @ObservationIgnored private var leaves: [String: (UUID, Task<Void, Never>)] = [:]
    @ObservationIgnored private var lateDiscards: [UUID: (String, Task<Void, Never>)] = [:]
    @ObservationIgnored private var removed: Set<String> = []
    @ObservationIgnored private var epoch = UUID()
    var leaveTimeout: Duration = .seconds(10)

    init(client: IMClient, userID: String) {
        self.client = client; self.userID = userID
        watermarks = (try? client.session.sendAttempts.loadDraftWatermarks(origin: client.baseURL, userID: userID)) ?? [:]
    }
    func register(_ runtime: InteractiveRuntime) {
        guard runtime.isCurrentStore else { return }
        removed.remove(runtime.message.conversation_id)
        runtimes[runtime.message.conversation_id, default: [:]][runtime.message.id] = WeakRuntime(value: runtime)
    }
    func retainUnresolved(_ runtime: InteractiveRuntime) {
        guard runtime.isCurrentStore, !removed.contains(runtime.message.conversation_id) else { return }
        retained[runtime.message.conversation_id, default: [:]][runtime.message.id] = runtime
    }
    func runtime(_ cid: String, messageID: String) -> InteractiveRuntime? { runtimes[cid]?[messageID]?.value }
    func failure(_ cid: String) -> DraftFailure? {
        failures[cid]?.values.sorted {
            if $0.reason != $1.reason { return $0.reason == .conflict }
            return $0.id < $1.id
        }.first
    }
    func record(_ runtime: InteractiveRuntime, reason: DraftFlushResult.Reason?, offline: Bool = false) {
        guard runtime.isCurrentStore else { return }
        let cid = runtime.message.conversation_id, id = runtime.message.id
        if let reason {
            failures[cid, default: [:]][id] = DraftFailure(id: id, title: String(runtime.message.content.prefix(80)), reason: reason, offline: offline)
        } else {
            failures[cid]?[id] = nil; retained[cid]?[id] = nil
        }
    }
    func noteSaved(_ runtime: InteractiveRuntime, serial: Int, updatedAt: String, revision: Int) async {
        let token = epoch, cid = runtime.message.conversation_id
        guard !removed.contains(cid) else { return }
        do {
            _ = try await client.session.noteDraftSaved(cid, updatedAt: updatedAt, userID: userID, revision: revision)
            guard token == epoch, !removed.contains(cid) else { return }
            watermarks[cid] = max(watermarks[cid] ?? "", updatedAt)
            watermarks = Dictionary(uniqueKeysWithValues: watermarks.sorted {
                $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value
            }.prefix(128).map { ($0.key, $0.value) })
        } catch { return } // Logout must never recreate another account's private state.
        for departure in departures[cid] ?? [] where serial <= (departure.cutoffs[ObjectIdentifier(runtime)] ?? -1) {
            departure.through = max(departure.through ?? "", updatedAt)
            if departure.baselineStarted {
                // This PUT belongs to that departure. Never infer ownership from a later GET.
                let id = UUID()
                lateDiscards[id] = (cid, Task { [self] in
                    await discard(cid, through: updatedAt, token: token)
                    lateDiscards[id] = nil
                })
            }
        }
    }
    func flush(_ cid: String) async -> Bool {
        await awaitPendingDiscard(cid)
        let values = liveRuntimes(cid)
        for runtime in values {
            let result = await runtime.flush()
            if let reason = result.reason, failures[cid]?[runtime.message.id] == nil { record(runtime, reason: reason) }
        }
        return failures[cid]?.isEmpty != false
    }
    func awaitPendingDiscard(_ cid: String) async {
        if let pending = leaves[cid]?.1 { await pending.value }
        // Late-success cleanup is also part of the send barrier.
        for (conversation, task) in Array(lateDiscards.values) where conversation == cid { await task.value }
    }
    func leave(_ cid: String) {
        let values = liveRuntimes(cid)
        let departure = Departure(values, through: watermarks[cid])
        departures[cid, default: []].append(departure)
        let previous = leaves[cid]?.1, token = epoch, timeout = leaveTimeout
        let task = Task { [self] in
            if let previous { await previous.value }
            guard token == epoch else { return }
            let writes = Task { @MainActor in
                for runtime in values { _ = await runtime.flush(through: departure.cutoffs[ObjectIdentifier(runtime)]) }
            }
            _ = await waitWithoutCancelling(writes, timeout: timeout)
            guard token == epoch else { return }
            departure.baselineStarted = true
            await discard(cid, through: departure.through, token: token)
            if leaves[cid]?.0 == departure.id { leaves[cid] = nil }
            // Keep the departure alive only while its own PUTs can still report success.
            Task { @MainActor [self] in
                await writes.value
                departures[cid]?.removeAll { $0.id == departure.id }
            }
        }
        leaves[cid] = (departure.id, task)
    }
    /// Retry explicit bounded leave intents, never infer a departure from a saved draft.
    func foreground(activeConversation: String?) async {
        let pending = (try? client.session.sendAttempts.loadDraftDiscards(origin: client.baseURL, userID: userID)) ?? [:]
        for (cid, through) in pending { await discard(cid, through: through, token: epoch) }
    }
    func remove(_ cid: String) {
        removed.insert(cid)
        runtimes[cid] = nil; retained[cid] = nil; failures[cid] = nil; watermarks[cid] = nil
        leaves[cid] = nil; departures[cid] = nil
    }
    func clear() {
        epoch = UUID(); runtimes = [:]; retained = [:]; failures = [:]; watermarks = [:]
        departures = [:]; leaves = [:]; lateDiscards = [:]; removed = []
    }
    private func liveRuntimes(_ cid: String) -> [InteractiveRuntime] { runtimes[cid]?.values.compactMap(\.value) ?? [] }
    private func discard(_ cid: String, through: String?, token: UUID) async {
        guard token == epoch, !removed.contains(cid), let through else { return }
        let revision = await client.session.revision()
        guard (try? await client.session.assertOwner(userID, revision: revision)) != nil, token == epoch else { return }
        do {
            try await client.session.updateDraftDiscard(cid, through: through, userID: userID, revision: revision)
            guard token == epoch, !removed.contains(cid) else { return }
            if try await client.discardInteractionBackground(cid, through: through) {
                try await client.session.updateDraftDiscard(cid, through: through, confirmed: true, userID: userID, revision: revision)
            }
        } catch { /* A failed discard retains its explicit durable intent for the next foreground. */ }
    }
}

/// A timeout bounds the UI wait, not the lifetime of an already authenticated PUT.
@MainActor
private func waitWithoutCancelling(_ task: Task<Void, Never>, timeout: Duration) async -> Bool {
    final class Gate { var continuation: CheckedContinuation<Bool, Never>? }
    let gate = Gate()
    return await withCheckedContinuation { continuation in
        gate.continuation = continuation
        let timer = Task { @MainActor in
            do { try await Task.sleep(for: timeout) } catch { return }
            gate.continuation?.resume(returning: false); gate.continuation = nil
        }
        Task { @MainActor in
            await task.value
            timer.cancel()
            gate.continuation?.resume(returning: true); gate.continuation = nil
        }
    }
}
