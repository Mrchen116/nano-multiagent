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

enum NanoTheme {
    static let ink = Color("Ink")
    static let muted = Color("Muted")
    static let accent = Color("Accent")
    static let border = Color("Border")
    static let canvas = Color("Canvas")
    static let surface = Color("Surface")
    static let softAccent = Color("SoftAccent")
}

struct AvatarView: View {
    let name: String
    var online: Bool = false
    var kind: String = "person"
    var body: some View {
        Group {
            if kind == "group" { Image(systemName: "person.2.fill") }
            else if kind == "agent" { Image(systemName: "sparkle") }
            else { Text(String(name.prefix(1))).fontWeight(.semibold) }
        }
        .font(.system(size: 18, weight: .medium)).foregroundStyle(kind == "person" ? NanoTheme.ink : NanoTheme.accent)
        .frame(width: 44, height: 44)
        .background(kind == "person" ? NanoTheme.canvas : NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 14))
        .overlay(alignment: .bottomTrailing) {
            if online { Circle().fill(NanoTheme.accent).frame(width: 9, height: 9).overlay(Circle().stroke(NanoTheme.surface, lineWidth: 2)) }
        }.accessibilityHidden(true)
    }
}

struct NanoSearchField: View {
    @Binding var text: String
    let prompt: String
    var body: some View {
        HStack(spacing: 9) {
            Image(systemName: "magnifyingglass").foregroundStyle(NanoTheme.muted)
            TextField(prompt, text: $text).font(.subheadline).submitLabel(.search)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
            if !text.isEmpty {
                Button { text = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(NanoTheme.muted) }
                    .buttonStyle(.plain).accessibilityLabel(L("清除搜索", "Clear search"))
            }
        }.padding(.horizontal, 12).padding(.vertical, 11)
            .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct NanoRootTitle: ViewModifier {
    let title: String
    func body(content: Content) -> some View {
        content.navigationTitle(title).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .principal) { Text(title).font(.title2.bold()).foregroundStyle(NanoTheme.ink).accessibilityAddTraits(.isHeader) } }
    }
}
extension View {
    func nanoRootTitle(_ title: String) -> some View { modifier(NanoRootTitle(title: title)) }
    func nanoList() -> some View {
        listStyle(.plain).scrollContentBackground(.hidden).background(NanoTheme.surface)
            .environment(\.defaultMinListRowHeight, 60)
            .listRowSeparatorTint(NanoTheme.border)
    }
}

func nanoDate(_ value: String) -> Date? {
    let parser = ISO8601DateFormatter()
    parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = parser.date(from: value) { return date }
    parser.formatOptions = [.withInternetDateTime]
    return parser.date(from: value)
}

struct NanoTimestamp: View {
    let value: String
    var body: some View {
        if let date = nanoDate(value) {
            Text(date, format: Calendar.current.isDateInToday(date) ? .dateTime.hour().minute() : .dateTime.month(.twoDigits).day())
                .font(.caption2).foregroundStyle(NanoTheme.muted).lineLimit(1)
        }
    }
}

extension String {
    var pathComponent: String {
        addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/?#%"))) ?? self
    }
}
