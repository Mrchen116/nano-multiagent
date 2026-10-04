import SwiftUI

func L(_ zh: String, _ en: String) -> String {
    (UserDefaults.standard.string(forKey: "nano.locale") ?? "zh").hasPrefix("zh") ? zh : en
}

struct ErrorNotice: View {
    let message: String
    var body: some View {
        Label(message, systemImage: "exclamationmark.circle")
            .font(.callout).foregroundStyle(.red).textSelection(.enabled)
            .accessibilityAddTraits(.isStaticText)
    }
}

struct JSONDetailView: View {
    let value: JSONValue
    var body: some View {
        ScrollView([.horizontal, .vertical]) {
            Text(value.prettyPrinted).font(.system(.caption, design: .monospaced))
                .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding()
        }.navigationTitle(L("详细信息", "Details"))
    }
}

struct AvatarView: View {
    let name: String
    var online: Bool = false
    var body: some View {
        Text(String(name.prefix(1))).font(.headline)
            .frame(width: 42, height: 42).background(.teal.opacity(0.12), in: RoundedRectangle(cornerRadius: 13))
            .overlay(alignment: .bottomTrailing) {
                if online { Circle().fill(.green).frame(width: 9, height: 9).overlay(Circle().stroke(.background, lineWidth: 2)) }
            }.accessibilityHidden(true)
    }
}

extension String {
    var pathComponent: String {
        addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/?#%"))) ?? self
    }
}
