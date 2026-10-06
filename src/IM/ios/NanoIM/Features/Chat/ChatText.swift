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

    static func mention(_ actor: ActorRef, participants: [ActorRef]) -> String {
        let name = actor.display_name ?? actor.id
        return "@" + (mentionTargets(participants)[name] == targetID(actor) ? name : actor.id)
    }
    private static func targetID(_ actor: ActorRef) -> String? {
        actor.user_id ?? (actor.type == "user" ? actor.id : nil)
    }
    private static func mentionTargets(_ participants: [ActorRef]) -> [String: String] {
        var targets: [String: String] = [:]
        for actor in participants { if let id = targetID(actor) { targets[actor.id] = id } }
        for (name, actors) in Dictionary(grouping: participants, by: { $0.display_name ?? $0.id }) {
            let ids = Set(actors.compactMap(targetID))
            if !name.isEmpty, ids.count == 1, let id = ids.first, targets[name] == nil || targets[name] == id { targets[name] = id }
        }
        return targets
    }
    static func wire(_ text: String, participants: [ActorRef]) -> String {
        let targets = mentionTargets(participants)
        guard !targets.isEmpty else { return text }
        // Match longer names first, so “Plan Two” never resolves as “Plan”.
        let names = targets.keys.sorted { $0.count > $1.count }.map(NSRegularExpression.escapedPattern).joined(separator: "|")
        guard let regex = try? NSRegularExpression(pattern: "(?<!\\S)@(" + names + ")(?=\\s|$)") else { return text }
        var result = text
        for match in regex.matches(in: text, range: NSRange(text.startIndex..., in: text)).reversed() {
            guard let nameRange = Range(match.range(at: 1), in: text), let range = Range(match.range, in: result), let id = targets[String(text[nameRange])] else { continue }
            result.replaceSubrange(range, with: "<mention type=\"user\" target_id=\"\(id)\"/>")
        }
        return result
    }
    static func display(_ text: String, participants: [ActorRef]) -> String {
        guard let regex = try? NSRegularExpression(pattern: #"<mention\s+type="user"\s+target_id="([^"]+)"\s*/>"#) else { return text }
        var result = text
        for match in regex.matches(in: text, range: NSRange(text.startIndex..., in: text)).reversed() {
            guard let targetRange = Range(match.range(at: 1), in: text), let range = Range(match.range, in: result) else { continue }
            let target = String(text[targetRange])
            let actor = participants.first { targetID($0) == target }
            result.replaceSubrange(range, with: "@" + (actor?.display_name ?? actor?.id ?? target))
        }
        return result
    }

    struct Completion: Equatable {
        enum Kind: Equatable { case mention, command }
        let kind: Kind
        let query: String
        let range: NSRange
    }
    /// Uses UIKit's UTF-16 caret range and replaces the current token, preserving the rest of the draft.
    static func completion(_ text: String, selection: NSRange, mentions: Bool) -> Completion? {
        let string = text as NSString
        guard selection.length == 0, selection.location <= string.length else { return nil }
        let prefix = string.substring(to: selection.location)
        let pattern = mentions ? #"(?<!\S)@([^\s@]*)\z|^/([^\s/]*)\z"# : #"^/([^\s/]*)\z"#
        guard let regex = try? NSRegularExpression(pattern: pattern), let match = regex.firstMatch(in: prefix, range: NSRange(location: 0, length: (prefix as NSString).length)) else { return nil }
        let start = match.range.location
        let kind: Completion.Kind = string.substring(with: NSRange(location: start, length: 1)) == "@" ? .mention : .command
        let whitespace = string.rangeOfCharacter(from: .whitespacesAndNewlines, range: NSRange(location: selection.location, length: string.length - selection.location)).location
        let end = whitespace == NSNotFound ? string.length : whitespace
        return Completion(kind: kind, query: (prefix as NSString).substring(from: start + 1), range: NSRange(location: start, length: end - start))
    }
    static func replacing(_ text: String, completion: Completion, with value: String) -> (text: String, selection: NSRange) {
        let string = text as NSString
        let existingSpace = NSMaxRange(completion.range) < string.length && string.substring(with: NSRange(location: NSMaxRange(completion.range), length: 1)) == " "
        let replacement = value + (existingSpace ? "" : " ")
        return (string.replacingCharacters(in: completion.range, with: replacement), NSRange(location: completion.range.location + (value as NSString).length + 1, length: 0))
    }
}
