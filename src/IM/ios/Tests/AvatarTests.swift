import XCTest
@testable import NanoIM

final class AvatarTests: XCTestCase {
    func testPaletteMatchesWebNameSeedsIncludingWideHashAndUTF16() {
        // Expected values come from the Web avatar.tsx expression executed in JavaScript.
        let seeds = [("", 0), ("e2e-peer", 5), ("Personal Assistant", 4),
                     ("My Assistant", 0), ("Code Reviewer", 0), ("中文助理", 3), ("🧑‍💻 Agent", 1)]
        for (name, expected) in seeds {
            XCTAssertEqual(AvatarView.paletteIndex(for: name), expected, name)
        }
    }
}
