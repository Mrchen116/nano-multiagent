import XCTest
@testable import NanoIM

/// The iOS draft model is hand-written, so the contract addition is pinned by decoding a
/// real server payload rather than by regenerating the JS bundle.
final class InteractionDraftFieldsTests: XCTestCase {
    func testDraftDecodesFieldLabelsAndNormalizedOptions() throws {
        let payload = """
        {"read_only":false,"superseded_by":null,"can_interact":true,"updated_at":"2026-11-05T09:41:02.145Z",
         "draft_revision":3,"state":{"$slot":"thu","$count":2},"submission_message_id":null,
         "fields":[
           {"name":"$slot","label":"时间","value":"thu","display_value":"周四 14:00",
            "options":[{"label":"周三 10:00","value":"wed"},{"label":"周四 14:00","value":"thu"}]},
           {"name":"$count","label":"参会人","value":2,"display_value":"2 人"}]}
        """.data(using: .utf8)!

        let draft = try JSONDecoder().decode(InteractionDraft.self, from: payload)

        XCTAssertEqual(draft.draft_revision, 3)
        XCTAssertEqual(draft.updated_at, "2026-11-05T09:41:02.145Z")
        let fields = try XCTUnwrap(draft.fields)
        XCTAssertEqual(fields.count, 2)
        XCTAssertEqual(fields[0].name, "$slot")
        XCTAssertEqual(fields[0].label, "时间")
        XCTAssertEqual(fields[0].value, .string("thu"))
        XCTAssertEqual(fields[0].display_value, "周四 14:00")
        XCTAssertEqual(fields[0].options, [InteractionDraftFieldOption(label: "周三 10:00", value: "wed"),
                                           InteractionDraftFieldOption(label: "周四 14:00", value: "thu")])
        XCTAssertEqual(fields[1].value, .number(2))
        XCTAssertNil(fields[1].options)
    }

    func testDraftWithoutFieldsStillDecodes() throws {
        let payload = """
        {"draft_revision":0,"state":{},"submission_message_id":null,"updated_at":null}
        """.data(using: .utf8)!

        let draft = try JSONDecoder().decode(InteractionDraft.self, from: payload)

        XCTAssertNil(draft.fields)
        XCTAssertEqual(draft.draft_revision, 0)
    }
}
