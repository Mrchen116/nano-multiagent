import XCTest
import Markdown
import SwiftUI
@testable import NanoIM

final class MarkdownContentTests: XCTestCase {
    func testTextAndLinkedImagesKeepTheirReadingOrderAndFormatting() throws {
        let paragraph = try XCTUnwrap(Array(Document(parsing: "**before** ![one](https://example.com/one.png) between [![two](https://example.com/two.png)](https://example.com) after").children).first)
        let pieces = MarkdownContent.pieces(paragraph, baseURL: URL(string: "https://im.example.com")!)
        let order = pieces.map { piece -> String in
            switch piece {
            case .text(let text): return String(text.characters)
            case .image(let source, _): return source
            }
        }
        XCTAssertEqual(order, ["before ", "https://example.com/one.png", " between ", "https://example.com/two.png", " after"])
        if case .text(let text) = pieces.first { XCTAssertTrue(text.runs.first?.inlinePresentationIntent?.contains(.stronglyEmphasized) == true) }
    }
    func testMessageCopyUsesReadableTextListsLinksAndExactCodeInterior() {
        let markdown = """
        Intro **bold**

        - Alpha
        - Beta
          - Nested

        3. Third
        4. Fourth

        | Name | Value |
        | --- | --- |
        | Count | 2 |

        ```python
        if ready:

          run()
        ```

        [Docs](https://example.com/docs)
        """
        XCTAssertEqual(MarkdownContent.copy(markdown), "Intro bold\n\n- Alpha\n- Beta\n  - Nested\n\n3. Third\n4. Fourth\n\nName\tValue\nCount\t2\n\nif ready:\n\n  run()\n\nDocs (https://example.com/docs)")
    }
}
