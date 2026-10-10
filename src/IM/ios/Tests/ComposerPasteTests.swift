import UIKit
import XCTest
@testable import NanoIM

@MainActor
final class ComposerPasteTests: XCTestCase {
    func testImageOnlyClipboardOffersPasteAndStagesWithoutReplacingDraft() {
        // This test owns the separate test simulator's synthetic clipboard.
        defer { UIPasteboard.general.items = [] }
        let image = UIGraphicsImageRenderer(size: CGSize(width: 2, height: 2)).image { context in
            UIColor.orange.setFill()
            context.fill(CGRect(x: 0, y: 0, width: 2, height: 2))
        }
        UIPasteboard.general.image = image
        let view = ComposerTextView.PasteTextView()
        view.text = "keep this draft"
        var staged: [UIImage] = []
        view.imagePasted = { staged.append($0) }
        let action = #selector(UIResponderStandardEditActions.paste(_:))

        XCTAssertTrue(UIPasteboard.general.hasImages)
        XCTAssertFalse(UIPasteboard.general.hasStrings)
        XCTAssertTrue(view.canPerformAction(action, withSender: nil))
        view.paste(nil)
        XCTAssertEqual(staged.count, 1)
        XCTAssertEqual(view.text, "keep this draft")

        view.isEditable = false
        XCTAssertFalse(view.canPerformAction(action, withSender: nil))
    }
}
