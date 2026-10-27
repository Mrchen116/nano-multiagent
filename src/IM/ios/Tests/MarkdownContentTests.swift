import XCTest
import Markdown
import SwiftUI
@testable import NanoIM

final class MarkdownContentTests: XCTestCase {
    func testProtectedAttachmentLinksUseNativeDownloadWhileExternalLinksRemainText() throws {
        let base = URL(string: "https://im.example.com")!
        let path = "/im/v1/conversations/chat/attachments/file"
        let paragraph = try XCTUnwrap(Array(Document(parsing: "Before [report.md](\(path)) after").children).first)
        let pieces = MarkdownContent.pieces(paragraph, baseURL: base)
        XCTAssertEqual(pieces.count, 3)
        if case .attachment(let attachment) = pieces[1] {
            XCTAssertEqual(attachment.url, "https://im.example.com\(path)")
            XCTAssertEqual(attachment.file_name, "report.md")
        } else { XCTFail("Protected resources must use the authenticated native attachment view") }
        for destination in ["https://other.example.com\(path)", "https://im.example.com/docs"] {
            let external = try XCTUnwrap(Array(Document(parsing: "[Link](\(destination))").children).first)
            let pieces = MarkdownContent.pieces(external, baseURL: base)
            XCTAssertEqual(pieces.count, 1)
            if case .text(let text) = pieces[0] { XCTAssertEqual(text.runs.first?.link?.absoluteString, destination) }
            else { XCTFail("Ordinary links must keep their normal URL handling") }
        }
    }
    func testTextAndLinkedImagesKeepTheirReadingOrderAndFormatting() throws {
        let paragraph = try XCTUnwrap(Array(Document(parsing: "**before** ![one](https://example.com/one.png) between [![two](https://example.com/two.png)](https://example.com) after").children).first)
        let pieces = MarkdownContent.pieces(paragraph, baseURL: URL(string: "https://im.example.com")!)
        let order = pieces.map { piece -> String in
            switch piece {
            case .text(let text): return String(text.characters)
            case .image(let source, _): return source
            case .attachment(let attachment): return attachment.url
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
