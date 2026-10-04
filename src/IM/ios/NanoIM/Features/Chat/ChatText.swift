import Foundation

struct ChatBanner: Identifiable, Equatable {
    let id = UUID()
    let conversationID: String
}

/// Keeps readable composer mentions separate from the relay's stable member identity.
enum ChatText {
    static func command(_ name: String, agentID: String?) -> String {
        (agentID.map { "@\($0) " } ?? "") + "/\(name) "
    }
    static func skill(_ name: String) -> String { "/skill:\(name) " }

    static func wire(_ text: String, participants: [ActorRef]) -> String {
        var result = text
        for actor in participants where actor.type == "agent" {
            guard let userID = actor.user_id else { continue }
            let pattern = "(?<!\\S)@" + NSRegularExpression.escapedPattern(for: actor.id) + "(?=\\s|$)"
            guard let regex = try? NSRegularExpression(pattern: pattern) else { continue }
            let tag = "<mention type=\"user\" target_id=\"\(userID)\"/>"
            result = regex.stringByReplacingMatches(in: result, range: NSRange(result.startIndex..., in: result), withTemplate: NSRegularExpression.escapedTemplate(for: tag))
        }
        return result
    }
    static func display(_ text: String, participants: [ActorRef]) -> String {
        guard let regex = try? NSRegularExpression(pattern: #"<mention\s+type="user"\s+target_id="([^"]+)"\s*/>"#) else { return text }
        var result = text
        for match in regex.matches(in: text, range: NSRange(text.startIndex..., in: text)).reversed() {
            guard let targetRange = Range(match.range(at: 1), in: text), let range = Range(match.range, in: result) else { continue }
            let target = String(text[targetRange])
            let actor = participants.first { $0.user_id == target }
            result.replaceSubrange(range, with: "@" + (actor?.display_name ?? actor?.id ?? target))
        }
        return result
    }
}
