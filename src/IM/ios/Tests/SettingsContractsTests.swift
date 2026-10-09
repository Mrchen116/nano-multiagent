import Foundation
import Testing
@testable import NanoIM

struct SettingsContractsTests {
    @Test func bindingLinkRestrictsOriginAndFragmentSecret() throws {
        let server = URL(string: "https://im.nanoim.win")!
        #expect(try SettingsBindingLink.token(from: "https://IM.nanoim.win:443/bind/confirm#token=bind-secret", server: server) == "bind-secret")
        let rejected = [
            "https://other.example/bind/confirm#token=bind-secret",
            "http://im.nanoim.win/bind/confirm#token=bind-secret",
            "https://im.nanoim.win:8443/bind/confirm#token=bind-secret",
            "https://user@im.nanoim.win/bind/confirm#token=bind-secret",
            "https://im.nanoim.win/chat#token=bind-secret",
            "https://im.nanoim.win/bind/confirm?token=bind-secret",
            "https://im.nanoim.win/bind/confirm#token=one&token=two",
            "https://im.nanoim.win/bind/confirm#token="
        ]
        for link in rejected {
            #expect(throws: SettingsBindingLink.Invalid.self) {
                try SettingsBindingLink.token(from: link, server: server)
            }
        }
    }

    @Test func clearingDefaultDeviceSendsExplicitNullToAccountAPI() throws {
        let update = SettingsAccountUpdate(display_name: "测试用户", default_entry_node_id: nil, locale: "zh")
        let data = try JSONEncoder().encode(update)
        let body = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(body["default_entry_node_id"] is NSNull)
        #expect(body["display_name"] as? String == "测试用户")
        #expect(body["locale"] as? String == "zh")
        #expect(body["owner_id"] == nil)
    }

    @Test func bindingCancellationDecodesItsActualStateOnlyResponse() throws {
        // Decline does not return node metadata; using the inspect DTO breaks successful rejection.
        let result = try JSONDecoder().decode(SettingsBindingState.self, from: Data(#"{"state":"cancelled"}"#.utf8))
        #expect(result.state == "cancelled")
        let waiting = try JSONDecoder().decode(SettingsBinding.self, from: Data(#"{"node_id":"mini","node_name":"Mini","agents":["assistant"],"state":"awaiting_local_confirmation"}"#.utf8))
        #expect(waiting.state != "committed")
    }
}
