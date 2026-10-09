import XCTest
@testable import NanoIM

final class ChatTextTests: XCTestCase {
    private let members = [ActorRef(type: "agent", id: "planner", display_name: "Plan", user_id: "u_one"), ActorRef(type: "agent", id: "planner2", display_name: "Plan Two", user_id: "u_two")]
    func testGroupCommandTargetsOnlySelectedMemberDespiteAgentIDPrefix() {
        let draft = ChatText.command("new", agentID: "planner2")
        XCTAssertEqual(draft, "@planner2 /new ")
        let wire = ChatText.wire(draft, participants: members)
        XCTAssertEqual(wire, #"<mention type="user" target_id="u_two"/> /new "#)
        XCTAssertFalse(wire.contains("@planner"))
        XCTAssertEqual(ChatText.command("compact", agentID: nil), "/compact ")
    }
    func testSkillUsesCommandNameAndStructuredMentionsDisplayMemberName() {
        XCTAssertEqual(ChatText.skill("review"), "/skill:review ")
        XCTAssertEqual(ChatText.display(#"<mention type="user" target_id="u_two"/> check this"#, participants: members), "@Plan Two check this")
    }
    func testReadableMentionsRouteToMembersWithoutMatchingNamePrefixesOrEmail() {
        let people = members + [ActorRef(type: "user", id: "u_person", display_name: "小陈", user_id: nil)]
        XCTAssertEqual(ChatText.wire("@Plan Two 和 @小陈 hello a@Plan", participants: people),
                       #"<mention type="user" target_id="u_two"/> 和 <mention type="user" target_id="u_person"/> hello a@Plan"#)
    }
    func testAmbiguousDisplayNamesDoNotRouteToAnArbitraryMember() {
        let people = [ActorRef(type: "agent", id: "one", display_name: "Helper", user_id: "u_one"),
                      ActorRef(type: "agent", id: "two", display_name: "Helper", user_id: "u_two")]
        XCTAssertEqual(ChatText.wire("@Helper @two ", participants: people), #"@Helper <mention type="user" target_id="u_two"/> "#)
        XCTAssertEqual(ChatText.mention(people[1], participants: people), "@two")
    }
    func testMentionSelectionAtCaretPreservesEmojiPrefixAndFollowingText() throws {
        let text = "👋 @planner tail"
        let caret = NSRange(location: ("👋 @pl" as NSString).length, length: 0)
        let completion = try XCTUnwrap(ChatText.completion(text, selection: caret, mentions: true))
        XCTAssertEqual(completion.query, "pl")
        let result = ChatText.replacing(text, completion: completion, with: ChatText.mention(members[1], participants: members))
        XCTAssertEqual(result.text, "👋 @Plan Two tail")
        XCTAssertEqual(result.selection.location, ("👋 @Plan Two " as NSString).length)
        XCTAssertEqual(ChatText.wire(result.text, participants: members), #"👋 <mention type="user" target_id="u_two"/> tail"#)
    }
    func testCompletionOnlyUsesActualTriggersAndCollapsedSelection() throws {
        for text in ["hello a@pl", "hello /new", "@pl\n"] {
            XCTAssertNil(ChatText.completion(text, selection: NSRange(location: (text as NSString).length, length: 0), mentions: true))
        }
        XCTAssertNil(ChatText.completion("@pl", selection: NSRange(location: 0, length: 3), mentions: true))
        XCTAssertNil(ChatText.completion("@pl", selection: NSRange(location: 3, length: 0), mentions: false))
        let completion = try XCTUnwrap(ChatText.completion("/ne later", selection: NSRange(location: 3, length: 0), mentions: false))
        XCTAssertEqual(completion.kind, .command)
        XCTAssertEqual(completion.query, "ne")
        XCTAssertEqual(ChatText.replacing("/ne later", completion: completion, with: "@planner2 /new").text, "@planner2 /new later")
    }
}
