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
    var size: CGFloat = 44
    private var initials: String {
        let value = String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(2)).uppercased()
        return value.isEmpty ? "AG" : value
    }
    private var palette: (background: Color, foreground: Color) {
        if kind == "group" { return (color(0x35464f), color(0xc5d8df)) }
        // Same name seed, 32-bit hash and palette as Web's shared avatar.tsx.
        let colors: [(UInt32, UInt32)] = [(0xe4dbcf, 0x6b5945), (0xd9dfd1, 0x506345), (0xdfd8e8, 0x69567b), (0xe7d7dc, 0x79525f), (0xcbdedb, 0x2f5954), (0xd5ddea, 0x485c7d)]
        let hash = name.utf16.reduce(UInt32(0)) { ($0 &* 31) &+ UInt32($1) }
        let pair = colors[Int(abs(Int64(Int32(bitPattern: hash)))) % colors.count]
        return (color(pair.0), color(pair.1))
    }
    private func color(_ hex: UInt32) -> Color {
        Color(red: Double((hex >> 16) & 255) / 255, green: Double((hex >> 8) & 255) / 255, blue: Double(hex & 255) / 255)
    }
    var body: some View {
        Group {
            if kind == "group" { Image(systemName: "person.2.fill") }
            else { Text(initials) }
        }
        .font(.system(size: size * 0.35, weight: .semibold)).foregroundStyle(palette.foreground)
        .frame(width: size, height: size)
        .background(palette.background, in: RoundedRectangle(cornerRadius: kind == "group" ? size * 0.275 : size / 2))
        .overlay(alignment: .bottomTrailing) {
            if online { Circle().fill(NanoTheme.accent).frame(width: size * 0.23, height: size * 0.23).overlay(Circle().stroke(NanoTheme.surface, lineWidth: 2)) }
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
    func nanoUnsavedChanges(_ dirty: Bool) -> some View { modifier(NanoUnsavedChanges(dirty: dirty)) }
}

private struct NanoUnsavedChanges: ViewModifier {
    let dirty: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var confirmLeave = false
    func body(content: Content) -> some View {
        content.navigationBarBackButtonHidden(dirty)
            .toolbar { if dirty { ToolbarItem(placement: .navigation) { Button(L("返回", "Back")) { confirmLeave = true } } } }
            .confirmationDialog(L("放弃未保存的修改？", "Discard unsaved changes?"), isPresented: $confirmLeave, titleVisibility: .visible) {
                Button(L("放弃并返回", "Discard and go back"), role: .destructive) { dismiss() }
            }
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

struct NanoDateTime: View {
    let value: String
    var body: some View {
        if let date = nanoDate(value) { Text(date, format: .dateTime.year().month().day().hour().minute()).foregroundStyle(NanoTheme.muted) }
        else { Text(value).foregroundStyle(NanoTheme.muted) }
    }
}

extension String {
    var pathComponent: String {
        addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/?#%"))) ?? self
    }
}
