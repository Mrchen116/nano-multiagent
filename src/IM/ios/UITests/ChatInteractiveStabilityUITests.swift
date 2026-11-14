import XCTest

/// Observe the real native last message without scrolling or pressing Latest to repair entry.
/// The dedicated C corpus is read-only; expansion changes only its rendered WebKit state.
@MainActor
final class ChatInteractiveStabilityUITests: XCTestCase {
    private var driver: NativeChatDriver?
    private let nativeHeaderPrefix = "UI 10/10 · 收尾说明卡"

    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 180
    }

    override func tearDownWithError() throws { driver?.app.terminate() }

    func testMultipleInteractiveMessagesStayAlignedAndStableAtActualTail() throws {
        let (driver, tail) = try openC()
        try assertStableTail(driver, exactText: tail, stage: "initial-without-any-scroll-or-Latest")
    }

    func testTenthInteractiveMessageExpansionAndCollapseKeepActualTailStable() throws {
        let (driver, tail) = try openC()
        // A broken first entry must fail here, rather than be hidden by a corrective gesture.
        let initialFrame = try assertStableTail(driver, exactText: tail, stage: "dynamic-initial-without-repair")
        // A previous human interaction can persist expansion. Normalize only after the
        // untouched entry has passed, using an actually observed opposite control state.
        if try tenthIsExpanded(driver, stage: "untouched-control-state") {
            try tapControl(driver, command: "收起 10", stage: "normalize-persisted-expanded-tenth")
            try confirmControlState(driver, command: "展开 10", stage: "normalized-collapsed-state")
            if try tenthIsExpanded(driver, stage: "normalized-control-state") {
                try blocked(driver, stage: "normalize", reason: "Actual collapse action still exposes expanded state")
            }
            try assertStableTail(driver, exactText: tail, stage: "normalized-collapsed-tenth", referenceFrame: initialFrame)
        }
        try tapControl(driver, command: "展开 10", stage: "expand-tenth")
        try confirmControlState(driver, command: "收起 10", stage: "expanded-state")
        try assertStableTail(driver, exactText: tail, stage: "expanded-tenth", referenceFrame: initialFrame)
        // Do not swipe to an offscreen control: that would change followLatest to history
        // reading and make the collapse assertion test a different user intent.
        try tapControl(driver, command: "收起 10", stage: "collapse-tenth")
        try confirmControlState(driver, command: "展开 10", stage: "collapsed-state")
        try assertStableTail(driver, exactText: tail, stage: "collapsed-tenth", referenceFrame: initialFrame)
    }

    private func openC() throws -> (NativeChatDriver, String) {
        let driver = try NativeChatDriver(test: self)
        self.driver = driver
        driver.app.launchEnvironment["NANO_CHAT_SCROLL_TRACE"] = "1"
        driver.app.launchEnvironment["NANO_CHAT_STREAM_TRACE"] = "1"
        let title = try NativeChatFixture.required("NANO_UI_INTERACTIVE_TITLE")
        let tail = try NativeChatFixture.required("NANO_UI_INTERACTIVE_TAIL")
        try driver.launchAndLogin()
        let row = driver.app.staticTexts.matching(NSPredicate(format: "label == %@", title)).firstMatch
        try driver.require(row.waitForExistence(timeout: 8), "Dedicated C conversation must exist")
        row.tap()
        try driver.require(driver.app.textViews["Message"].waitForExistence(timeout: 10), "C native composer must load")
        let marker = driver.app.staticTexts.matching(NSPredicate(format: "label == %@", tail)).firstMatch
        try driver.require(marker.waitForExistence(timeout: 10), "C exact final ordinary message must load")
        driver.record("C-entry-method", ["scrollGestures": 0, "LatestTaps": 0, "exactNativeTail": tail])
        return (driver, tail)
    }

    private func allSnapshots(in root: any XCUIElementSnapshot) -> [any XCUIElementSnapshot] {
        [root] + root.children.flatMap { allSnapshots(in: $0) }
    }

    private func nativeTailLeaves(in root: any XCUIElementSnapshot, text: String) -> [any XCUIElementSnapshot] {
        // The marker is an ordinary native message, not a WebKit card or aggregate label.
        if root.elementType == .webView { return [] }
        let children = root.children.flatMap { nativeTailLeaves(in: $0, text: text) }
        if !children.isEmpty { return children }
        return root.elementType == .staticText && root.label == text ? [root] : []
    }

    private struct AlignmentSample {
        let valid: Bool
        let evidence: [String: Any]
    }

    private func nativeTextPaths(in root: any XCUIElementSnapshot, path: [Int] = [],
                                 matching predicate: (String) -> Bool) -> [[Int]] {
        if root.elementType == .webView { return [] }
        let children = root.children.enumerated().flatMap {
            nativeTextPaths(in: $0.element, path: path + [$0.offset], matching: predicate)
        }
        if !children.isEmpty { return children }
        return root.elementType == .staticText && predicate(root.label) ? [path] : []
    }

    private func sampleAlignment(root: any XCUIElementSnapshot, exactText: String, tailFrame: CGRect) -> AlignmentSample {
        let tails = nativeTextPaths(in: root) { $0 == exactText }
        let headers = nativeTextPaths(in: root) { $0.hasPrefix(nativeHeaderPrefix) }
        var evidence: [String: Any] = ["method": "deepest-shared-native-header-tail-ancestor-v1",
            "tailPaths": tails, "headerPaths": headers, "minGutter": 1, "maxGutterImbalance": 2, "maxCenterError": 1]
        func result(_ valid: Bool, _ reason: String) -> AlignmentSample {
            var value = evidence
            value["valid"] = valid; value["reason"] = reason
            return AlignmentSample(valid: valid, evidence: value)
        }
        guard tails.count == 1 && headers.count == 1 else { return result(false, "native-header-or-tail-not-unique") }
        var sharedPath: [Int] = []
        for (tailIndex, headerIndex) in zip(tails[0], headers[0]) {
            if tailIndex != headerIndex { break }
            sharedPath.append(tailIndex)
        }
        // Select only the actual deepest common ancestor. Never climb until a frame
        // happens to pass, and never infer a full-width wrapper from intrinsic Text width.
        var shared = root, path: [Int] = []
        var scroll: AXLocation?
        for index in sharedPath {
            if shared.elementType == .scrollView { scroll = AXLocation(path: path, snapshot: shared) }
            guard index < shared.children.count else { return result(false, "invalid-snapshot-path") }
            shared = shared.children[index]; path.append(index)
        }
        evidence["sharedPath"] = sharedPath; evidence["sharedNode"] = diagnosticNode(shared)
        guard (shared.elementType == .other || shared.elementType == .cell), let scroll else {
            return result(false, "shared-ancestor-is-not-a-native-wrapper-below-scroll")
        }
        let frame = shared.frame, container = scroll.snapshot.frame
        evidence["scrollViewPath"] = scroll.path; evidence["scrollViewport"] = diagnosticFrame(container)
        guard [frame.minX, frame.maxX, frame.width, container.minX, container.maxX, container.width]
            .allSatisfy({ $0.isFinite }), container.width > 0, tailFrame.width > 0 else {
            return result(false, "invalid-horizontal-geometry")
        }
        let left = frame.minX - container.minX, right = container.maxX - frame.maxX
        let imbalance = abs(left - right), centerError = abs(frame.midX - container.midX)
        evidence["leftGutter"] = Double(left); evidence["rightGutter"] = Double(right)
        evidence["gutterImbalance"] = Double(imbalance); evidence["centerError"] = Double(centerError)
        guard frame.width > tailFrame.width && frame.width < container.width else {
            return result(false, "shared-wrapper-is-not-wider-than-tail-and-narrower-than-viewport")
        }
        let valid = left >= 1 && right >= 1 && imbalance <= 2 && centerError <= 1
        return result(valid, valid ? "balanced-shared-wrapper" : "shared-wrapper-gutters-unbalanced-or-not-positive")
    }

    private struct TailSample {
        let uptime: TimeInterval
        let frame: CGRect
        let viewport: CGRect
        let tailCount: Int
        let visible: Bool
        let latestCount: Int
        let alignment: AlignmentSample
        var evidence: [String: Any] {
            ["uptime": uptime, "tailCount": tailCount, "visible": visible,
             "x": frame.minX, "y": frame.minY, "width": frame.width, "height": frame.height,
             "tailMaxY": frame.maxY, "navMaxY": viewport.minY,
             "effectiveComposerMinY": viewport.maxY, "LatestCount": latestCount, "alignment": alignment.evidence]
        }
    }

    private func sampleTail(_ driver: NativeChatDriver, exactText: String,
                            diagnosticStage: String? = nil) throws -> TailSample {
        // All geometry and button presence belong to the same public AX generation.
        let root = try driver.app.snapshot()
        let nodes = allSnapshots(in: root)
        let tails = nativeTailLeaves(in: root, text: exactText)
        let navigation = nodes.first { $0.elementType == .navigationBar }
        let composer = nodes.first { $0.elementType == .textView && $0.label == "Message" }
        let frame = tails.count == 1 ? tails[0].frame : .zero
        let top = navigation?.frame.maxY ?? 0
        let bottom = (composer?.frame.minY ?? 0) - 10
        let viewport = CGRect(x: root.frame.minX, y: top, width: root.frame.width, height: max(0, bottom - top))
        let latest = nodes.filter {
            $0.elementType == .button && ($0.identifier == "conversation.latest" || $0.label == "Latest messages")
        }
        let alignment = sampleAlignment(root: root, exactText: exactText, tailFrame: frame)
        let observedAt = ProcessInfo.processInfo.systemUptime
        if let diagnosticStage {
            recordAlignmentDiagnostic(driver, root: root, exactText: exactText, viewport: viewport,
                                      stage: diagnosticStage, observedAt: observedAt)
        }
        return TailSample(uptime: observedAt, frame: frame, viewport: viewport,
                          tailCount: tails.count,
                          visible: tails.count == 1 && navigation != nil && composer != nil &&
                              frame.width > 0 && frame.height > 0 && viewport.contains(frame),
                          latestCount: latest.count, alignment: alignment)
    }

    private struct AXLocation {
        let path: [Int]
        let snapshot: any XCUIElementSnapshot
    }

    private func diagnosticFrame(_ frame: CGRect) -> [String: Any] {
        var result: [String: Any] = [:]
        for (name, value) in [("x", frame.minX), ("y", frame.minY), ("width", frame.width),
                              ("height", frame.height), ("maxX", frame.maxX), ("maxY", frame.maxY)] {
            if value.isFinite { result[name] = Double(value) }
            else { result[name] = NSNull() }
        }
        return result
    }

    private func diagnosticNode(_ node: any XCUIElementSnapshot) -> [String: Any] {
        ["elementType": String(describing: node.elementType), "elementTypeRaw": node.elementType.rawValue,
         "identifier": node.identifier, "labelPrefix": String(node.label.prefix(160)),
         "labelCharacterCount": node.label.count, "labelTruncated": node.label.count > 160,
         "directChildCount": node.children.count, "frame": diagnosticFrame(node.frame)]
    }

    private func diagnosticLocation(_ location: AXLocation, ancestors: [AXLocation]) -> [String: Any] {
        let chain: [[String: Any]] = ancestors.map { ancestor in
            let index = location.path[ancestor.path.count]
            let children = ancestor.snapshot.children
            let nearPathChildren: [[String: Any]] = (max(0, index - 2)...min(children.count - 1, index + 2)).map {
                ["childIndex": $0, "node": diagnosticNode(children[$0])]
            }
            return ["path": ancestor.path, "node": diagnosticNode(ancestor.snapshot),
                    "pathChildIndex": index, "nearPathChildren": nearPathChildren]
        }
        return ["path": location.path, "node": diagnosticNode(location.snapshot),
                "ancestorsRootToParent": chain]
    }

    private func recordAlignmentDiagnostic(_ driver: NativeChatDriver, root: any XCUIElementSnapshot,
                                           exactText: String, viewport: CGRect, stage: String,
                                           observedAt: TimeInterval) {
        let headerPrefix = nativeHeaderPrefix
        var tails: [[String: Any]] = [], headers: [[String: Any]] = [], nearby: [[String: Any]] = []
        func visit(_ node: any XCUIElementSnapshot, path: [Int], ancestors: [AXLocation]) {
            // Prune WK descendants so native headers/avatars cannot be confused with
            // similarly labelled card DOM. Ancestor sibling summaries still identify WK.
            if node.elementType == .webView { return }
            let location = AXLocation(path: path, snapshot: node)
            if node.elementType == .staticText && node.label == exactText {
                tails.append(diagnosticLocation(location, ancestors: ancestors))
            }
            if node.elementType == .staticText && node.label.hasPrefix(headerPrefix) {
                headers.append(diagnosticLocation(location, ancestors: ancestors))
            }
            let scrollAncestors = ancestors.filter { $0.snapshot.elementType == .scrollView }
            let avatarNamed = node.label.localizedCaseInsensitiveContains("avatar") ||
                node.identifier.localizedCaseInsensitiveContains("avatar")
            if !scrollAncestors.isEmpty && node.frame.width > 0 && node.frame.height > 0 &&
                node.frame.intersects(viewport) &&
                (node.elementType == .image || node.elementType == .staticText || avatarNamed) {
                nearby.append(["path": path, "node": diagnosticNode(node),
                               "fullyInsideEffectiveViewport": viewport.contains(node.frame),
                               "scrollViewAncestors": scrollAncestors.map {
                                   ["path": $0.path, "node": diagnosticNode($0.snapshot)] as [String: Any]
                               }])
            }
            for (index, child) in node.children.enumerated() {
                visit(child, path: path + [index], ancestors: ancestors + [location])
            }
        }
        visit(root, path: [], ancestors: [])
        driver.record("C-native-alignment-diagnostic", ["schemaVersion": 1, "diagnosticOnly": true,
            "stage": stage, "observationUptime": observedAt,
            "source": "same public app.snapshot as this stage's first TailSample; no extra UI query",
            "app": diagnosticNode(root), "effectiveViewport": diagnosticFrame(viewport),
            "exactNativeTailNodes": tails, "nativeHeaderPrefix": headerPrefix, "nativeHeaderNodes": headers,
            "visibleNativeImageTextOrAvatarNamedCandidates": nearby,
            "interpretation": "Raw ancestor candidates only; no intrinsic Text width or avatar identity assumed. The separate per-sample criterion uses only the actual deepest common native header/tail ancestor."])
    }

    @discardableResult
    private func assertStableTail(_ driver: NativeChatDriver, exactText: String, stage: String,
                                  referenceFrame: CGRect? = nil) throws -> CGRect {
        var samples = [try sampleTail(driver, exactText: exactText, diagnosticStage: stage)]
        driver.capture("C-" + stage + "-first-observation")
        let began = samples[0].uptime
        // Keep a continuous window; never reset the reference after a drift/missing tail.
        // Actual timestamps expose AX/screenshot overhead instead of claiming fixed cadence.
        while (samples.last!.uptime - began) < 2.4 || samples.count < 13 {
            driver.pause(max(0, 0.2 - (ProcessInfo.processInfo.systemUptime - samples.last!.uptime)))
            samples.append(try sampleTail(driver, exactText: exactText))
        }
        // Include the untouched initial stage in later ranges: a permanent 16pt shift
        // after expansion must not pass merely because it has stopped moving.
        let reference = referenceFrame ?? samples[0].frame
        let xs = samples.map { $0.frame.minX } + [reference.minX]
        let ys = samples.map { $0.frame.minY } + [reference.minY]
        let xRange = (xs.max() ?? 0) - (xs.min() ?? 0)
        let yRange = (ys.max() ?? 0) - (ys.min() ?? 0)
        driver.record("C-native-tail-stability", ["stage": stage, "samples": samples.map(\.evidence),
            "observedSeconds": samples.last!.uptime - began, "requiredSeconds": 2.4,
            "xRange": xRange, "yRange": yRange, "maxXRange": 1, "maxYRange": 4,
            "referenceX": reference.minX, "referenceY": reference.minY,
            "comparesUntouchedInitialStage": referenceFrame != nil,
            "scrollGestures": 0, "LatestTaps": 0,
            "samplingLimit": "AX samples do not prove absence of pixel flicker between observations"])
        driver.capture("C-" + stage + "-last-observation", tree: true)
        try driver.require(samples.allSatisfy { $0.tailCount == 1 && $0.visible },
                           "C exact native tail must remain fully inside nav/composer throughout: " + stage)
        try driver.require(samples.allSatisfy { $0.latestCount == 0 },
                           "Latest must stay absent throughout the actual visible-tail window: " + stage)
        try driver.require(samples.allSatisfy { $0.alignment.valid },
                           "C actual shared header/tail wrapper must have positive balanced viewport gutters in every sample: " + stage)
        try driver.require(xRange <= 1, "C bubble text horizontal range must be <=1pt: " + stage)
        try driver.require(yRange <= 4, "C bubble text vertical range must be <=4pt: " + stage)
        return samples[0].frame
    }

    private func controlPredicate(_ command: String) -> NSPredicate {
        // The renderer's control source remains Chinese even when native nano.locale=en.
        // A digit boundary prevents accidentally accepting a different numbered card.
        NSPredicate(format: "label MATCHES %@", "(?s)^" + NSRegularExpression.escapedPattern(for: command) + "(?:[^0-9].*)?$")
    }

    private func semanticControlLeaves(in root: any XCUIElementSnapshot, command: String) -> [any XCUIElementSnapshot] {
        let children = root.children.flatMap { semanticControlLeaves(in: $0, command: command) }
        if !children.isEmpty { return children }
        let label = root.label.trimmingCharacters(in: .whitespacesAndNewlines)
        let allowed: [XCUIElement.ElementType] = [.button, .link, .staticText, .other]
        // A labelled leaf may be tappable without WebKit exposing a Button trait. A
        // multiline/large aggregate is not a safe control-sized semantic click target.
        guard allowed.contains(root.elementType), label.count <= command.count + 60,
              !label.contains("\n"), controlPredicate(command).evaluate(with: ["label": label]) else { return [] }
        return [root]
    }

    private func tenthIsExpanded(_ driver: NativeChatDriver, stage: String) throws -> Bool {
        let root = try driver.app.snapshot()
        // Count both real semantic states from one AX generation. Absence of Expand
        // alone never establishes Expanded, and duplicate/opposite states are blocked.
        let expand = semanticControlLeaves(in: root, command: "展开 10")
        let collapse = semanticControlLeaves(in: root, command: "收起 10")
        driver.record("C-tenth-observed-state", ["stage": stage, "expandCount": expand.count,
            "collapseCount": collapse.count, "expandNodes": expand.map { diagnosticNode($0) },
            "collapseNodes": collapse.map { diagnosticNode($0) }, "source": "one fresh public app.snapshot"])
        guard (expand.count == 1 && collapse.isEmpty) || (collapse.count == 1 && expand.isEmpty) else {
            try blocked(driver, stage: stage, reason: "No unique actual Expand/Collapse tenth-card semantic state")
        }
        return collapse.count == 1
    }

    private func tapControl(_ driver: NativeChatDriver, command: String, stage: String) throws {
        let buttons = driver.app.buttons.matching(controlPredicate(command)).allElementsBoundByIndex
            .filter { $0.exists && $0.isHittable }
        if buttons.count == 1 {
            driver.record("C-control-action", ["stage": stage, "command": command, "method": "semantic-Button.tap"])
            buttons[0].tap()
            return
        }
        if buttons.count > 1 { try blocked(driver, stage: stage, reason: "Ambiguous numbered WebKit buttons") }
        let root = try driver.app.snapshot()
        let nodes = allSnapshots(in: root)
        let top = nodes.first { $0.elementType == .navigationBar }?.frame.maxY ?? 0
        let bottom = (nodes.first { $0.elementType == .textView && $0.label == "Message" }?.frame.minY ?? 0) - 10
        let area = CGRect(x: root.frame.minX, y: top, width: root.frame.width, height: max(0, bottom - top))
        let candidates = semanticControlLeaves(in: root, command: command)
        let exact = candidates.filter { $0.label.trimmingCharacters(in: .whitespacesAndNewlines) == command }
        let eligible = exact.isEmpty ? candidates : exact
        let visible = eligible.filter { $0.frame.width > 0 && $0.frame.height > 0 && area.contains($0.frame) }
        guard visible.count == 1 else {
            try blocked(driver, stage: stage,
                        reason: "No unique fully visible semantic control for \(command); no history swipe or Latest repair allowed")
        }
        let target = visible[0].frame
        driver.record("C-control-action", ["stage": stage, "command": command,
            "method": "public-snapshot-semantic-leaf-centre", "label": visible[0].label,
            "x": target.minX, "y": target.minY, "width": target.width, "height": target.height])
        // Coordinates are derived only from the fresh semantic AX target, never from a
        // fixture/device-specific screen position. Verify the toggled state after tapping.
        driver.app.coordinate(withNormalizedOffset: .zero).withOffset(
            CGVector(dx: target.midX - root.frame.minX, dy: target.midY - root.frame.minY)).tap()
    }

    private func confirmControlState(_ driver: NativeChatDriver, command: String, stage: String) throws {
        let deadline = ProcessInfo.processInfo.systemUptime + 3
        repeat {
            let root = try driver.app.snapshot()
            if !semanticControlLeaves(in: root, command: command).isEmpty {
                driver.record("C-control-state-confirmed", ["stage": stage, "command": command])
                return
            }
            driver.pause(0.2)
        } while ProcessInfo.processInfo.systemUptime < deadline
        try blocked(driver, stage: stage, reason: "Tapped action did not expose its opposite semantic state: " + command)
    }

    private func blocked(_ driver: NativeChatDriver, stage: String, reason: String) throws -> Never {
        driver.record("C-dynamic-blocked", ["stage": stage, "reason": reason, "verdict": "blocked-not-pass",
                                          "scrollGestures": 0, "LatestTaps": 0])
        driver.capture("C-blocked-" + stage, tree: true)
        XCTFail("BLOCKED (not skipped/passed): " + reason)
        throw NSError(domain: "ChatInteractiveStabilityUITests.Blocked", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: reason])
    }
}
