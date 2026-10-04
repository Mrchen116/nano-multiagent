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
}
