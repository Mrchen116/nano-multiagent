import Foundation

/// Values whose server schema is intentionally open, such as tool diagnostics.
indirect enum JSONValue: Codable, Sendable, Equatable {
    case object([String: JSONValue]), array([JSONValue]), string(String), number(Double), bool(Bool), null
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let value = try? c.decode(Bool.self) { self = .bool(value) }
        else if let value = try? c.decode(Double.self) { self = .number(value) }
        else if let value = try? c.decode(String.self) { self = .string(value) }
        else if let value = try? c.decode([String: JSONValue].self) { self = .object(value) }
        else { self = .array(try c.decode([JSONValue].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
    subscript(_ key: String) -> JSONValue { objectValue?[key] ?? .null }
    var objectValue: [String: JSONValue]? { if case .object(let v) = self { return v }; return nil }
    var arrayValue: [JSONValue]? { if case .array(let v) = self { return v }; return nil }
    var stringValue: String? { if case .string(let v) = self { return v }; return nil }
    var doubleValue: Double? { if case .number(let v) = self { return v }; return nil }
    var intValue: Int? { doubleValue.map(Int.init) }
    var boolValue: Bool? { if case .bool(let v) = self { return v }; return nil }
    var prettyPrinted: String {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return (try? encoder.encode(self)).flatMap { String(data: $0, encoding: .utf8) } ?? ""
    }
}

struct EmptyResponse: Codable, Sendable {}
struct ItemsPage<T: Decodable & Sendable>: Decodable, Sendable {
    let items: [T]
    let next_cursor: String?
}
