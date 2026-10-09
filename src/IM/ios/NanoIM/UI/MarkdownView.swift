import SwiftUI
import Markdown

/// Native blocks from the CommonMark/GFM AST; HTML is text and never executed.
struct MarkdownView: View {
    let text: String
    let client: IMClient
    var body: some View {
        let document = Document(parsing: text)
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(document.children.enumerated()), id: \.offset) { _, child in
                MarkdownBlockView(node: child, client: client)
            }
        }.frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
    }
}

enum MarkdownContent {
    enum Piece { case text(AttributedString), image(source: String, label: String) }
    /// Splits at images before rendering, keeping text and nested linked images in source order.
    static func pieces(_ node: any Markup, baseURL: URL) -> [Piece] {
        if let image = node as? Markdown.Image { return image.source.map { [.image(source: $0, label: image.plainText)] } ?? [] }
        if node.childCount == 0 { return [.text(inline(node, baseURL: baseURL))] }
        var result: [Piece] = []
        for child in node.children {
            for piece in pieces(child, baseURL: baseURL) {
                if case .text(let text) = piece {
                    let styled = style(text, node: node, baseURL: baseURL)
                    if case .text(let previous) = result.last { result[result.count - 1] = .text(previous + styled) }
                    else { result.append(.text(styled)) }
                } else { result.append(piece) }
            }
        }
        return result
    }
    static func inline(_ node: any Markup, baseURL: URL) -> AttributedString {
        if let text = node as? Markdown.Text { return AttributedString(text.string) }
        if let code = node as? InlineCode { var text = AttributedString(code.code); text.font = .system(.body, design: .monospaced); text.backgroundColor = .gray.opacity(0.12); return text }
        if node is SoftBreak || node is LineBreak { return AttributedString("\n") }
        if let html = node as? InlineHTML { return AttributedString(html.rawHTML) }
        if node is Markdown.Image { return AttributedString("") }
        return style(node.children.reduce(AttributedString()) { $0 + inline($1, baseURL: baseURL) }, node: node, baseURL: baseURL)
    }
    private static func style(_ original: AttributedString, node: any Markup, baseURL: URL) -> AttributedString {
        var text = original
        if node is Strong { text.inlinePresentationIntent = (text.inlinePresentationIntent ?? []).union(.stronglyEmphasized) }
        if node is Emphasis { text.inlinePresentationIntent = (text.inlinePresentationIntent ?? []).union(.emphasized) }
        if node is Strikethrough { text.strikethroughStyle = .single }
        if let link = node as? Markdown.Link, let destination = link.destination,
           let url = URL(string: destination, relativeTo: baseURL)?.absoluteURL,
           ["http", "https", "mailto", "tel"].contains(url.scheme?.lowercased() ?? "") { text.link = url }
        return text
    }
    static func copy(_ text: String) -> String { plain(Document(parsing: text)) }
    private static func plain(_ node: any Markup, depth: Int = 0) -> String {
        if let code = node as? CodeBlock { return code.code.hasSuffix("\n") ? String(code.code.dropLast()) : code.code }
        if node is Markdown.Image { return "" }
        if let link = node as? Markdown.Link {
            let label = link.children.map { plain($0, depth: depth) }.joined()
            guard !label.isEmpty, let destination = link.destination else { return label }
            return label == destination ? label : label + " (" + destination + ")"
        }
        if node is SoftBreak || node is LineBreak { return "\n" }
        if let table = node as? Markdown.Table {
            return ([Array(table.head.cells)] + table.body.rows.map { Array($0.cells) }).map { $0.map { plain($0) }.joined(separator: "\t") }.joined(separator: "\n")
        }
        if node is UnorderedList || node is OrderedList {
            let start = (node as? OrderedList)?.startIndex ?? 1
            return node.children.enumerated().map { index, item in
                let bullet = node is OrderedList ? "\(Int(start) + index). " : "- "
                let check = (item as? ListItem)?.checkbox.map { $0 == .checked ? "[x] " : "[ ] " } ?? ""
                return String(repeating: "  ", count: depth) + bullet + check + item.children.map { child in plain(child, depth: child is UnorderedList || child is OrderedList ? depth + 1 : depth) }.joined(separator: "\n")
            }.joined(separator: "\n")
        }
        if let text = node as? Markdown.Text { return text.string }
        if let code = node as? InlineCode { return code.code }
        if let html = node as? InlineHTML { return html.rawHTML }
        if let html = node as? HTMLBlock { return html.rawHTML }
        return node.children.map { plain($0, depth: depth) }.joined(separator: node is Document || node is BlockQuote ? "\n\n" : "")
    }
}
private struct MarkdownBlockView: View {
    let node: any Markup
    let client: IMClient
    var body: some View { block(node) }
    private func block(_ node: any Markup) -> AnyView {
        if let code = node as? CodeBlock {
            return AnyView(VStack(alignment: .leading, spacing: 6) {
                HStack { SwiftUI.Text(code.language ?? L("代码", "Code")).font(.caption).foregroundStyle(.secondary); Spacer(); Button { UIPasteboard.general.string = code.code } label: { Label(L("复制", "Copy"), systemImage: "doc.on.doc") }.font(.caption) }
                ScrollView(.horizontal) { SwiftUI.Text(code.code).font(.system(.callout, design: .monospaced)).textSelection(.enabled).fixedSize(horizontal: true, vertical: false) }
            }.padding(12).background(.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 10)))
        }
        if let heading = node as? Heading {
            return AnyView(SwiftUI.Text(inline(heading)).font(heading.level <= 2 ? .title3.bold() : .headline).accessibilityAddTraits(.isHeader))
        }
        if node is ThematicBreak { return AnyView(Divider()) }
        if node is BlockQuote { return AnyView(HStack(alignment: .top, spacing: 10) { Rectangle().fill(.teal.opacity(0.4)).frame(width: 3); children(node) }.fixedSize(horizontal: false, vertical: true)) }
        if node is UnorderedList || node is OrderedList {
            let start = (node as? OrderedList)?.startIndex ?? 1
            return AnyView(VStack(alignment: .leading, spacing: 8) {
                ForEach(Array(node.children.enumerated()), id: \.offset) { index, child in
                    HStack(alignment: .top, spacing: 8) {
                        if let checkbox = (child as? ListItem)?.checkbox {
                            Image(systemName: checkbox == .checked ? "checkmark.square" : "square")
                                .accessibilityLabel(checkbox == .checked ? L("已完成", "Completed") : L("未完成", "Incomplete"))
                        } else { SwiftUI.Text(node is OrderedList ? "\(Int(start) + index)." : "•").foregroundStyle(.secondary) }
                        children(child)
                    }
                }
            })
        }
        if let table = node as? Markdown.Table {
            let rows = [Array(table.head.cells)] + table.body.rows.map { Array($0.cells) }
            return AnyView(ScrollView(.horizontal) {
                Grid(alignment: .topLeading, horizontalSpacing: 14, verticalSpacing: 10) {
                    ForEach(Array(rows.enumerated()), id: \.offset) { rowIndex, cells in
                        GridRow { ForEach(Array(cells.enumerated()), id: \.offset) { _, cell in
                            SwiftUI.Text(inline(cell)).fontWeight(rowIndex == 0 ? .semibold : .regular).frame(minWidth: 80, maxWidth: 220, alignment: .leading)
                        } }
                        if rowIndex == 0 { Divider().gridCellColumns(max(1, cells.count)) }
                    }
                }.padding(10)
            }.background(.gray.opacity(0.06), in: RoundedRectangle(cornerRadius: 8)))
        }
        if let html = node as? HTMLBlock { return AnyView(SwiftUI.Text(html.rawHTML).font(.body)) }
        return AnyView(VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(MarkdownContent.pieces(node, baseURL: client.baseURL).enumerated()), id: \.offset) { _, piece in
                switch piece {
                case .text(let text): SwiftUI.Text(text).font(.body).tint(.teal)
                case .image(let source, let label): ProtectedImageView(client: client, source: source, label: label)
                }
            }
        })
    }
    private func children(_ node: any Markup) -> some View {
        VStack(alignment: .leading, spacing: 8) { ForEach(Array(node.children.enumerated()), id: \.offset) { _, child in MarkdownBlockView(node: child, client: client) } }
    }
    private func inline(_ node: any Markup) -> AttributedString {
        MarkdownContent.inline(node, baseURL: client.baseURL)
    }
}
