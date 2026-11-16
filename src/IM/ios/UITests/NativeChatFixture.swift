import XCTest

/// A read-only rendering fixture, bound by the host to its verified process and frozen corpus.
/// Authentication and navigation use the shipped UI; this helper never seeds or edits messages.
struct NativeChatFixture: Decodable {
    struct Conversation: Decodable {
        let kind: String
        let id: String
        let title: String
        let message_count: Int
        let text_tail_marker: String
        let card_tail_marker: String?
        var tail: String { card_tail_marker ?? text_tail_marker }
    }
    let fixture_id: String
    let origin: String
    let conversations: [Conversation]
    struct Frozen: Decodable { let version: String; let sha256: String }
    let frozen_dataset: Frozen

    static func load() throws -> Self {
        let fixture = try JSONDecoder().decode(Self.self, from: Data(required("NANO_UI_CONTINUITY_FIXTURE_JSON").utf8))
        let url = try XCTUnwrap(URL(string: fixture.origin))
        guard url.scheme == "http", url.host == "127.0.0.1", (url.port ?? 0) >= 49152,
              fixture.origin == (try required("NANO_UI_ORIGIN")),
              fixture.conversations.count == 2, fixture.conversations.allSatisfy({ $0.message_count == 300 }),
              fixture.frozen_dataset.sha256.count == 64 else {
            throw NSError(domain: "NativeChatFixture", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unbound frozen fixture"])
        }
        return fixture
    }
    static func required(_ key: String) throws -> String {
        guard let value = ProcessInfo.processInfo.environment[key], !value.isEmpty else {
            throw NSError(domain: "NativeChatFixture", code: 2, userInfo: [NSLocalizedDescriptionKey: "Missing input: \(key)"])
        }
        return value
    }
}

@MainActor
final class NativeChatDriver {
    let app = XCUIApplication()
    let test: XCTestCase
    let fixture: NativeChatFixture
    private(set) var lastTailCompletionUptime: TimeInterval?
    init(test: XCTestCase) throws {
        self.test = test
        fixture = try NativeChatFixture.load()
        app.launchEnvironment["NANO_IM_BASE_URL"] = fixture.origin
        app.launchArguments = ["-nano.locale", "en"]
    }
    func require(_ condition: @autoclosure () -> Bool, _ reason: String,
                 file: StaticString = #filePath, line: UInt = #line) throws {
        guard condition() else {
            capture("failure-" + reason)
            XCTFail(reason, file: file, line: line)
            throw NSError(domain: "NativeChatDriver", code: 3, userInfo: [NSLocalizedDescriptionKey: reason])
        }
    }
    func launchAndLogin() throws {
        app.launch()
        let username = app.textFields["Enter your username"]
        if username.waitForExistence(timeout: 3) {
            username.tap(); username.typeText(try NativeChatFixture.required("NANO_UI_USERNAME"))
            let password = app.secureTextFields["Enter your password"]
            password.tap(); password.typeText(try NativeChatFixture.required("NANO_UI_PASSWORD"))
            app.buttons["Sign in"].tap()
        }
        let chat = app.staticTexts[fixture.conversations[0].title].firstMatch
        try require(chat.waitForExistence(timeout: 25), "The real fixture conversation list must arrive")
        let sheet = app.sheets.matching(NSPredicate(format: "label IN %@", ["保存密码？", "Save Password?"])).firstMatch
        if sheet.waitForExistence(timeout: 2) {
            let later = sheet.buttons.matching(NSPredicate(format: "label IN %@", ["以后", "Not Now", "Later"])).firstMatch
            try require(later.exists, "Dismiss only the system save-password prompt")
            later.tap()
        }
    }
    func open(_ conversation: NativeChatFixture.Conversation) throws {
        let chat = app.staticTexts[conversation.title].firstMatch
        try require(chat.waitForExistence(timeout: 20), "Open the bound conversation")
        chat.tap()
        try require(app.textViews["Message"].waitForExistence(timeout: 10), "The real timeline composer must appear")
    }
    func backToChats() throws {
        app.navigationBars.buttons.element(boundBy: 0).tap()
        try require(app.tabBars.buttons["Chats"].waitForExistence(timeout: 5), "Return through the public Chats entry")
    }
    func text(_ marker: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", marker)).firstMatch
    }
    var viewport: CGRect {
        let top = app.navigationBars.firstMatch.frame.maxY
        // Conservatively exclude the composer's 10pt top padding, not just the text field.
        let bottom = app.textViews["Message"].frame.minY - 10
        return CGRect(x: app.frame.minX, y: top, width: app.frame.width, height: max(0, bottom - top))
    }
    func fullyVisible(_ element: XCUIElement) -> Bool {
        // LazyVStack can recycle a row between exists and frame. A single throwable
        // snapshot observes one AX generation; absence while moving is not a test failure.
        guard element.exists, let snapshot = try? element.snapshot() else { return false }
        let frame = snapshot.frame
        return frame.width > 0 && frame.height > 0 && viewport.contains(frame)
    }
    func capture(_ name: String, tree: Bool = false) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name; screenshot.lifetime = .keepAlways; test.add(screenshot)
        if tree {
            let attachment = XCTAttachment(string: app.debugDescription)
            attachment.name = name + "-AX"; attachment.lifetime = .keepAlways; test.add(attachment)
        }
    }
    func record(_ name: String, _ object: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]),
              let value = String(data: data, encoding: .utf8) else { return }
        let attachment = XCTAttachment(string: value)
        attachment.name = name; attachment.lifetime = .keepAlways; test.add(attachment)
        print("763_OBSERVATION \(name) \(value)")
    }
    func pause(_ seconds: TimeInterval) { RunLoop.current.run(until: Date().addingTimeInterval(seconds)) }
    func swipe(history: Bool) {
        // Identical outer-timeline gestures avoid scrolling an inner WK document.
        let area = viewport
        let x = area.minX + 12
        let start = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: x, dy: area.minY + area.height * (history ? 0.2 : 0.8)))
        let end = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: x, dy: area.minY + area.height * (history ? 0.8 : 0.2)))
        start.press(forDuration: 0.01, thenDragTo: end, withVelocity: .fast, thenHoldForDuration: 0)
    }
    func seekEarlier(maxSwipes: Int = 100) throws {
        let earlier = app.buttons["Earlier messages"]
        for _ in 0..<maxSwipes {
            if fullyVisible(earlier) && earlier.isHittable { return }
            swipe(history: true)
        }
        try require(false, "Earlier messages must become visible without injecting a scroll position")
    }
    func seekHistoryStart(marker: String = "H763-001") throws {
        // Native status-bar scroll-to-top is public UI, not a product scroll hook.
        // Tap the clock area rather than the Dynamic Island at screen centre.
        app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 80, dy: 30)).tap()
        pause(1)
        var swipes = 0
        while !fullyVisible(text(marker)) && swipes < 300 {
            swipe(history: true); swipes += 1
        }
        try require(fullyVisible(text(marker)), "The actual history anchor \(marker) must be visible")
        let frame = (try? text(marker).snapshot())?.frame ?? .zero
        record("history-anchor-setup", ["marker": marker, "fallbackSwipes": swipes,
                                       "y": frame.minY, "height": frame.height,
                                       "outsideMeasurement": true])
    }
    func loadAll300(_ conversation: NativeChatFixture.Conversation) throws {
        // Four actual public button taps, with each newly admitted page seen in the UI.
        for (page, first) in [181, 121, 61, 1].enumerated() {
            try seekEarlier()
            capture("\(conversation.kind)-earlier-before-page-\(page + 1)")
            app.buttons["Earlier messages"].tap()
            let marker = String(format: "H763-%03d", first)
            var found = false
            for _ in 0..<100 {
                if fullyVisible(text(marker)) { found = true; break }
                swipe(history: true)
            }
            try require(found, "The actual page head \(marker) must be visible")
            capture("\(conversation.kind)-loaded-\((page + 2) * 60)-\(marker)", tree: first == 1)
            record("pagination", ["kind": conversation.kind, "earlierTap": page + 1,
                                  "loaded": (page + 2) * 60, "visibleHead": marker,
                                  "frozenSHA256": fixture.frozen_dataset.sha256])
        }
    }
    private func firstSnapshot(in root: any XCUIElementSnapshot,
                               matching predicate: (any XCUIElementSnapshot) -> Bool) -> (any XCUIElementSnapshot)? {
        if predicate(root) { return root }
        for child in root.children {
            if let match = firstSnapshot(in: child, matching: predicate) { return match }
        }
        return nil
    }
    private func markerLeaves(in root: any XCUIElementSnapshot, marker: String) -> [any XCUIElementSnapshot] {
        let descendants = root.children.flatMap { markerLeaves(in: $0, marker: marker) }
        // A WK aggregate can contain the same text as its leaves; never use its large frame.
        if !descendants.isEmpty { return descendants }
        return root.elementType == .staticText && root.label.contains(marker) ? [root] : []
    }
    private func observeTail(_ marker: String) -> (frame: CGRect, area: CGRect, candidates: [[String: Any]], visible: Bool) {
        let tree = try? app.snapshot()
        let leaves = tree.map { markerLeaves(in: $0, marker: marker) } ?? []
        let exact = leaves.filter { $0.label.trimmingCharacters(in: .whitespacesAndNewlines) == marker }
        // The frozen card ends with a Title and a Text bearing the same marker. DOM/AX
        // order selects the final Text, not the first Title that may become visible sooner.
        let eligible = exact.isEmpty ? leaves : exact
        let tail = eligible.last
        let navigation = tree.flatMap { firstSnapshot(in: $0) { $0.elementType == .navigationBar } }
        let composer = tree.flatMap { firstSnapshot(in: $0) { $0.elementType == .textView && $0.label == "Message" } }
        let frame = tail?.frame ?? .zero
        let top = navigation?.frame.maxY ?? 0
        let bottom = (composer?.frame.minY ?? 0) - 10
        let area = CGRect(x: tree?.frame.minX ?? 0, y: top, width: tree?.frame.width ?? 0, height: max(0, bottom - top))
        let candidates: [[String: Any]] = leaves.enumerated().map { index, leaf in
            ["treeIndex": index, "exact": leaf.label.trimmingCharacters(in: .whitespacesAndNewlines) == marker,
             "x": leaf.frame.minX, "y": leaf.frame.minY, "width": leaf.frame.width,
             "height": leaf.frame.height, "maxY": leaf.frame.maxY]
        }
        return (frame, area, candidates,
                tail != nil && navigation != nil && composer != nil && frame.width > 0 && frame.height > 0 && area.contains(frame))
    }
    /// Three atomic AX generations; requesting a scroll is deliberately not a pass.
    func stableTail(_ marker: String, timeout: TimeInterval = 3, captureFrames: Bool = false) -> Bool {
        lastTailCompletionUptime = nil
        let deadline = Date().addingTimeInterval(timeout)
        var samples: [[String: Any]] = [], ys: [CGFloat] = []
        while Date() < deadline {
            let observationStartedAt = ProcessInfo.processInfo.systemUptime
            // All three frames come from one public XCTest snapshot, not independent
            // live queries that can span layout generations or add ~1s of AX round trips.
            let observation = observeTail(marker)
            let frame = observation.frame, area = observation.area, visible = observation.visible
            let observedAt = ProcessInfo.processInfo.systemUptime
            samples.append(["uptime": observedAt, "visible": visible,
                            "x": frame.minX, "y": frame.minY, "width": frame.width, "height": frame.height,
                            "navMaxY": area.minY, "composerMinY": area.maxY,
                             "selectedTailMaxY": frame.maxY, "markerCandidates": observation.candidates,
                             "selection": "last-exact-leaf-otherwise-last-containing-leaf"])
            if visible { ys.append(frame.minY) } else { ys.removeAll() }
            if captureFrames && visible { capture("tail-frame-\(marker)-observation-\(samples.count)") }
            if ys.count >= 3 {
                let last = Array(ys.suffix(3))
                if (last.max() ?? 0) - (last.min() ?? 0) <= 4 {
                    lastTailCompletionUptime = observedAt
                    record("stable-tail-" + marker, ["samples": samples, "stable": true]); return true
                }
            }
            // Aim for 200ms observation cadence including snapshot/capture work. If
            // automation is slower, preserve actual timestamps rather than fake spacing.
            pause(max(0, 0.2 - (ProcessInfo.processInfo.systemUptime - observationStartedAt)))
        }
        record("stable-tail-" + marker, ["samples": samples, "stable": false])
        capture("unstable-tail-" + marker, tree: true)
        return false
    }
    func reachTailForSetup(_ conversation: NativeChatFixture.Conversation) throws {
        // A baseline correction is allowed only outside measurement, and is recorded.
        let latest = app.buttons["Latest messages"]
        if latest.exists && latest.isHittable { latest.tap() }
        if stableTail(conversation.tail) { return }
        for _ in 0..<120 {
            swipe(history: false)
            if observeTail(conversation.tail).visible { break }
        }
        try require(stableTail(conversation.tail), "A measured sample must start at the true rendered tail")
        record("setup-tail-correction", ["kind": conversation.kind, "outsideMeasurement": true])
    }
}
