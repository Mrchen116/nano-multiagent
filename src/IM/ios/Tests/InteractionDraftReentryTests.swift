import XCTest
@testable import NanoIM

extension InteractionDraftLifecycleTests {
    func testReattachingSavedCardRestoresRendererAndRejectsDetachedPage() async throws {
        let (runtime, _) = try await fixture()
        defer { runtime.chat.clear() }
        let detached = runtime.webID
        runtime.leave()
        await runtime.load()
        let ready = try await runtime.webRequest(.object(["type": .string("ready")]), generation: runtime.webID)
        XCTAssertEqual(ready["state"]["$slot"], .string("wed"))
        try await edit(runtime, "thu")
        XCTAssertEqual(runtime.state["$slot"], .string("thu"))
        do {
            _ = try await runtime.webRequest(.object(["type": .string("ready")]), generation: detached)
            XCTFail("The detached page regained access after reattachment")
        } catch {}
        _ = await runtime.flush()
    }

    func testReattachingTransientCardKeepsLocalDraftAndAllowsRetry() async throws {
        try await checkUnresolvedReentry(status: 503)
    }

    func testReattachingConflictedCardKeepsExplicitComparisonAndAdoption() async throws {
        try await checkUnresolvedReentry(status: 409)
    }

    private func checkUnresolvedReentry(status: Int) async throws {
        let (runtime, transport) = try await fixture()
        defer { runtime.chat.clear() }
        await transport.setStatus(status)
        try await edit(runtime, "fri")
        _ = await runtime.flush()
        let detached = runtime.webID
        runtime.leave()
        await runtime.load()
        let ready = try await runtime.webRequest(.object(["type": .string("ready")]), generation: runtime.webID)
        XCTAssertEqual(ready["state"]["$slot"], .string("fri"), "Reattachment must not adopt the remote draft")
        XCTAssertEqual(ready["disabled"], .bool(status == 409))
        XCTAssertNotNil(runtime.chat.interactionDrafts.failure("chat"))
        XCTAssertTrue(runtime.chat.interactionDrafts.runtime("chat", messageID: "card") === runtime)
        do {
            _ = try await runtime.webRequest(.object(["type": .string("state"), "sequence": .number(100), "touched": .bool(true), "state": .object(["$slot": .string("wed")])]), generation: detached)
            XCTFail("A detached page replaced the unresolved local edit")
        } catch {}
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        await transport.setStatus(200)
        if status == 409 {
            let premature = await runtime.adoptRemote()
            XCTAssertFalse(premature, "Comparison is required before adoption")
            _ = try await runtime.describeConflict()
            let adopted = await runtime.adoptRemote()
            XCTAssertTrue(adopted)
            XCTAssertEqual(runtime.state["$slot"], .string("wed"))
        } else {
            _ = await runtime.flush()
            XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        }
        XCTAssertNil(runtime.chat.interactionDrafts.failure("chat"))
    }

    func testDetachingDuringActionSaveRejectsTheOldPageAndReleasesBusyState() async throws {
        let (runtime, transport) = try await fixture()
        defer { runtime.chat.clear() }
        await transport.gateNextSave(timestamp: "2026-11-01T10:00:00.002Z")
        try await edit(runtime, "thu")
        let detached = runtime.webID
        let action = Task {
            try await runtime.webRequest(.object(["type": .string("tool"), "name": .string("SendToChat"), "args": .object(["message": .string("do not send from a detached page")])]), generation: detached)
        }
        let started = await transport.waitForGatedSave()
        XCTAssertTrue(started)
        XCTAssertTrue(runtime.busy)
        runtime.leave()
        await runtime.load()
        await transport.releaseSave()
        do {
            _ = try await action.value
            XCTFail("The detached page submitted its action after saving")
        } catch {}
        XCTAssertFalse(runtime.busy, "Revoking the renderer must not strand the draft operation's busy flag")
        XCTAssertFalse(runtime.composing)
        let ready = try await runtime.webRequest(.object(["type": .string("ready")]), generation: runtime.webID)
        XCTAssertEqual(ready["disabled"], .bool(false))
        let posts = await transport.posts
        XCTAssertTrue(posts.isEmpty)
    }

    func testReattachingDuringSavePreservesItsSuccessfulOwnershipWatermark() async throws {
        let (runtime, transport) = try await fixture()
        defer { runtime.chat.clear() }
        let savedAt = "2026-11-01T10:00:00.002Z"
        await transport.gateNextSave(timestamp: savedAt)
        try await edit(runtime, "thu")
        let saving = Task { await runtime.flush() }
        let started = await transport.waitForGatedSave()
        XCTAssertTrue(started)
        let detached = runtime.webID
        runtime.leave()
        await runtime.load()
        do {
            let ready = try await runtime.webRequest(.object(["type": .string("ready")]), generation: runtime.webID)
            XCTAssertEqual(ready["state"]["$slot"], .string("thu"))
            do {
                _ = try await runtime.webRequest(.object(["type": .string("ready")]), generation: detached)
                XCTFail("The old page remained active during the pending save")
            } catch {}
        } catch {
            await transport.releaseSave()
            _ = await saving.value
            throw error
        }
        await transport.releaseSave()
        _ = await saving.value
        XCTAssertEqual(runtime.chat.interactionDrafts.watermarks["chat"], savedAt, "Reattachment must not invalidate a real PUT acknowledgement")
        let discarded = await transport.discards
        XCTAssertTrue(discarded.isEmpty, "Recycling a row is not a conversation departure")
        XCTAssertNil(runtime.chat.interactionDrafts.failure("chat"))
    }
}
