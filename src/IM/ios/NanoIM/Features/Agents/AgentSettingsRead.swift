import SwiftUI

struct AgentSettingsRead<Value: Decodable & Sendable>: Decodable, Sendable {
    struct Failure: Decodable, Sendable { let message: String }
    let source: String, captured_at: String?, data: Value?, error: Failure?
}

struct AgentSettingsNotice<Value: Decodable & Sendable>: View {
    let read: AgentSettingsRead<Value>
    var body: some View {
        if read.source != "current" {
            VStack(alignment: .leading, spacing: 5) {
                Label(read.source == "last_known" ? L("上次读取的结果", "Last known results") : L("电脑尚未报告", "Unavailable from computer"), systemImage: "clock")
                if let date = read.captured_at { NanoDateTime(value: date).font(.caption) }
                if let message = read.error?.message { Text(message).font(.caption) }
            }.foregroundStyle(.secondary)
        }
    }
}
