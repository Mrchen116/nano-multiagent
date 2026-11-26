import XCTest
import SwiftUI
@testable import NanoIM

final class AvatarTests: XCTestCase {
    func testSharedWebAndNativeAvatarCases() throws {
        struct Cases: Decodable { let agentSeeds: [String:Int]; let colors: [String:String] }
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "avatar-test-cases", withExtension: "json"))
        let cases = try JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
        for (id, variant) in cases.agentSeeds {
            XCTAssertEqual(PortraitPreview.defaultVariant(for: id), variant, id)
        }
        for (seed, background) in cases.colors {
            XCTAssertEqual(AvatarView.palette[AvatarView.paletteIndex(for: seed)].background, background, seed)
        }
    }

    func testReceiptsAndThreadParticipantsUseTheMessageSenderIdentityEvenAfterLeaving() throws {
        for (suffix, variant) in [("one", 0), ("two", 7)] {
            let id = "uuid-" + suffix
            let actor = ActorRef(type:"agent", id:"pa-" + suffix, display_name:"Milo", user_id:id, role:"personal", avatar_variant:variant)
            let receipt = try JSONDecoder().decode(MessageReceipt.self, from: Data("""
                {"recipient_id":"\(id)","display_name":"Milo","status":"read","recipient":
                 {"type":"agent","id":"pa-\(suffix)","display_name":"Milo","user_id":"\(id)","role":"personal","avatar_variant":\(variant)}}
                """.utf8))
            let thread = ThreadParticipant(actor:actor, id:id, display_name:"Milo")
            let directory = AvatarDirectory()
            let expected = AvatarFace.agent(id:actor.id, personal:true, variant:variant)
            for identity in [AvatarIdentity.actor(actor), .receipt(receipt), .threadParticipant(thread)] {
                XCTAssertEqual(identity.key, id)
                XCTAssertEqual(directory.resolve(identity), expected)
            }
            let current = Contact(user_id:id, kind:"agent", display_name:"Milo", agent_id:actor.id, role:"personal", avatar_variant:9)
            let updated = AvatarDirectory(contacts:[current])
            let legacy = MessageReceipt(recipient_id:id, display_name:"Milo", status:.read)
            XCTAssertEqual(updated.resolve(.receipt(legacy)), updated.resolve(.contact(current)))
            XCTAssertEqual(updated.resolve(.actor(actor)), .agent(id:actor.id, personal:true, variant:9))
        }
    }

    @MainActor
    func testMessageAndReceiptRenderTheSameSelectedFace() throws {
        func pixels(_ identity: AvatarIdentity, size: CGFloat) throws -> Data {
            let renderer = ImageRenderer(content: AvatarView(id: identity, size: size))
            renderer.scale = 1
            return try XCTUnwrap(renderer.uiImage?.pngData())
        }
        var previous: Data?
        for variant in [0, 7] {
            let id = "uuid-\(variant)"
            let actor = ActorRef(type: "agent", id: "pa-\(variant)", display_name: "Milo", user_id: id,
                                 role: "personal", avatar_variant: variant)
            let receipt = MessageReceipt(recipient: actor, recipient_id: id, display_name: "Milo", status: .read)
            let message = ChatMessage(id:"reply", conversation_id:"chat", sender:actor, sender_user_id:id, sender_type:"agent",
                                      content:"hello", attachments:[], delivery_status:"completed", created_at:"2026-11-26T01:00:00Z")
            for size: CGFloat in [24, 32] {
                XCTAssertEqual(try pixels(.receipt(receipt), size: size), try pixels(.sender(message), size: size))
            }
            let face = try pixels(.actor(actor), size: 32)
            XCTAssertNotEqual(previous, face)
            previous = face
        }
    }

    func testRenamedExternalSenderUsesTheLatestVisibleSnapshotRegardlessOfPageOrder() {
        let original = ActorRef(avatar_id:"external:peer", type:"user", id:"owner", display_name:"Lin", user_id:"owner")
        let first = ChatMessage(id:"first", conversation_id:"chat", sender:original, sender_user_id:"owner",
                                sender_type:"user", content:"one", attachments:[], delivery_status:"completed", created_at:"2026-11-25")
        var newer = first
        newer.id = "second"; newer.sender.display_name = "Milo"; newer.created_at = "2026-11-26"
        let directory = AvatarDirectory().includingHistory([newer, first])
        XCTAssertEqual(directory.resolve(.sender(first)), .person("Milo"))
        XCTAssertEqual(directory.resolve(.userID("external:peer")), .person("Milo"))
    }

    func testVisibleHistoryResolvesAnOlderNameOnlyReceiptAfterTheAgentLeaves() {
        let sender = ActorRef(type:"agent", id:"pa", display_name:"Milo", user_id:"uuid", role:"personal", avatar_variant:7)
        var message = ChatMessage(id:"reply", conversation_id:"chat", sender:sender, sender_user_id:"uuid", sender_type:"agent",
                                  content:"hello", attachments:[], delivery_status:"completed", created_at:"2026-11-25")
        let legacy = MessageReceipt(recipient_id:"uuid", display_name:"Milo", status:.read)
        message.receipts = [legacy]
        let directory = AvatarDirectory().includingHistory([message])
        XCTAssertEqual(directory.resolve(.receipt(legacy)), .agent(id:"pa", personal:true, variant:7))
    }

    func testPartialContactRefreshUpdatesExistingViewsByID() {
        var contacts: [String:Contact] = [:]
        var person = Contact(user_id:"user", kind:"human", display_name:"Lin")
        ContactDirectoryUpdate(userID:"me", contacts:[person], complete:true).apply(to:&contacts)
        let old = AvatarIdentity.contact(person)
        person.display_name = "Milo"
        ContactDirectoryUpdate(userID:"me", contacts:[person], complete:false).apply(to:&contacts)
        XCTAssertEqual(AvatarDirectory(contacts:Array(contacts.values)).resolve(old), .person("Milo"))
    }

    func testExternalDisplayIdentityDoesNotResolveToMirrorOwner() {
        let owner = Contact(user_id:"owner", kind:"human", display_name:"Ada")
        let sender = ActorRef(avatar_id:"external:opaque", type:"user", id:"owner", display_name:"Lin", user_id:"owner")
        XCTAssertEqual(AvatarDirectory(contacts:[owner]).resolve(.actor(sender)), .person("Lin"))
    }
}
