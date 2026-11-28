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
        let owner = Contact(user_id:"owner", kind:"human", display_name:"Ada", avatar_version:"owner-ver-1")
        let sender = ActorRef(avatar_id:"external:opaque", type:"user", id:"owner", display_name:"Lin", user_id:"owner", avatar_version:"owner-ver-1")
        XCTAssertEqual(AvatarDirectory(contacts:[owner]).resolve(.actor(sender)), .person("Lin", avatar: nil))
    }

    @MainActor
    func testHumanCustomAvatarResolutionMemberFallbackAndMemoryStoreEviction() throws {
        let pendingMember = SettingsMember(
            id: "u-pending",
            username: "pending",
            display_name: "赵敏",
            avatar_version: "ver-pending-1",
            membership_status: "pending",
            is_company_admin: false,
            node_count: 0,
            agent_count: 0
        )
        let directory = AvatarDirectory()
        XCTAssertEqual(
            directory.resolve(.member(pendingMember)),
            .person("赵敏", avatar: UserAvatarRef(userID: "u-pending", version: "ver-pending-1"))
        )

        let store = AvatarImageStore()
        let ref1 = UserAvatarRef(userID: "u-pending", version: "ver-pending-1")
        let ref2 = UserAvatarRef(userID: "u-pending", version: "ver-pending-2")
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let sample = UIGraphicsImageRenderer(size: CGSize(width: 64, height: 64), format: format).image { ctx in
            UIColor.systemBlue.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 64, height: 64))
        }

        // Before image loads: falls back to initials circle without crashing.
        let fallbackRenderer = ImageRenderer(
            content: AvatarView(id: .member(pendingMember), size: 36).environment(\.avatarImageStore, store)
        )
        fallbackRenderer.scale = 1
        let fallbackPixels = try XCTUnwrap(fallbackRenderer.uiImage?.pngData())

        store.installForTesting(sample, for: ref1)
        XCTAssertEqual(store.cachedCount, 1)
        let photoRenderer = ImageRenderer(
            content: AvatarView(id: .member(pendingMember), size: 36).environment(\.avatarImageStore, store)
        )
        photoRenderer.scale = 1
        let photoPixels = try XCTUnwrap(photoRenderer.uiImage?.pngData())
        XCTAssertNotEqual(photoPixels, fallbackPixels)

        // Evicting for new version removes old cached entry while keeping target version if present.
        store.installForTesting(sample, for: ref2)
        store.evict(userID: "u-pending", keepingVersion: "ver-pending-2")
        XCTAssertNil(store.image(for: ref1))
        XCTAssertNotNil(store.image(for: ref2))

        // Sign-out / account switch clears all memory entries immediately.
        store.clear()
        XCTAssertEqual(store.cachedCount, 0)
        XCTAssertNil(store.image(for: ref2))
    }

    func testAvatarImageProcessorRejectsGifAndDownscalesOversizedDimensions() throws {
        let gif = Data(base64Encoded: "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")!
        XCTAssertThrowsError(try AvatarImageProcessor.prepareWorkingImage(from: gif)) { err in
            XCTAssertEqual(err as? AvatarImageProcessor.ValidationError, .unsupported)
        }

        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let huge = UIGraphicsImageRenderer(size: CGSize(width: 3000, height: 2000), format: format).pngData { ctx in
            UIColor.orange.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 3000, height: 2000))
        }
        let downscaled = try AvatarImageProcessor.prepareWorkingImage(from: huge)
        XCTAssertLessThanOrEqual(max(downscaled.size.width, downscaled.size.height), 2048)
        let (cropped, mime) = try AvatarImageProcessor.exportCroppedAvatar(source: downscaled, zoom: 1.2, pan: .zero)
        XCTAssertEqual(mime, "image/png")
        let decoded = try XCTUnwrap(UIImage(data: cropped))
        XCTAssertEqual(decoded.size, CGSize(width: 512, height: 512))
    }
}
