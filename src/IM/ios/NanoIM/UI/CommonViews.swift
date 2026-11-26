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

/// Embeddable content has no navigation side effects and wraps to its container.
struct JSONDetailView: View {
    let value: JSONValue
    var body: some View {
        Group {
            if case .string(let text) = value { Text(text).font(.callout) }
            else { Text(value.prettyPrinted).font(.system(.caption, design: .monospaced)) }
        }.textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct JSONDetailPage: View {
    let value: JSONValue
    var body: some View {
        ScrollView { JSONDetailView(value: value).padding() }
            .navigationTitle(L("详细信息", "Details"))
            .navigationBarTitleDisplayMode(.inline)
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
            .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 10))
            .overlay { RoundedRectangle(cornerRadius: 10).stroke(NanoTheme.border, lineWidth: 1) }
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

struct NanoDateParser {
    private let fractionalSeconds = Self.formatter([.withInternetDateTime, .withFractionalSeconds])
    private lazy var wholeSeconds = Self.formatter([.withInternetDateTime])

    mutating func date(from value: String) -> Date? {
        fractionalSeconds.date(from: value) ?? wholeSeconds.date(from: value)
    }

    private static func formatter(_ options: ISO8601DateFormatter.Options) -> ISO8601DateFormatter {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = options
        return formatter
    }
}

func nanoDate(_ value: String) -> Date? {
    var parser = NanoDateParser()
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

struct CrewdenDestination: View {
    let title: String
    let symbol: String
    var detail: String? = nil
    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol).font(.title3).frame(width: 28).accessibilityHidden(true)
            Text(title).font(.body.weight(.medium))
            Spacer()
            if let detail { Text(detail).font(.subheadline).foregroundStyle(.secondary) }
            Image(systemName: "chevron.right").font(.caption.bold()).foregroundStyle(.tertiary)
        }.foregroundStyle(NanoTheme.ink).padding(.vertical, 16).contentShape(Rectangle())
    }
}
