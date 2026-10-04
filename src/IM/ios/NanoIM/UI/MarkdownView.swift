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
        let images = node.children.compactMap { $0 as? Markdown.Image }
        return AnyView(VStack(alignment: .leading, spacing: 8) {
            SwiftUI.Text(inline(node)).font(.body).tint(.teal)
            ForEach(Array(images.enumerated()), id: \.offset) { _, image in
                if let source = image.source { ProtectedImageView(client: client, source: source, label: image.plainText) }
            }
        })
    }
    private func children(_ node: any Markup) -> some View {
        VStack(alignment: .leading, spacing: 8) { ForEach(Array(node.children.enumerated()), id: \.offset) { _, child in MarkdownBlockView(node: child, client: client) } }
    }
    private func inline(_ node: any Markup) -> AttributedString {
        if let text = node as? Markdown.Text { return AttributedString(text.string) }
        if let code = node as? InlineCode { var text = AttributedString(code.code); text.font = .system(.body, design: .monospaced); text.backgroundColor = .gray.opacity(0.12); return text }
        if node is SoftBreak { return AttributedString("\n") }
        if node is LineBreak { return AttributedString("\n") }
        if let html = node as? InlineHTML { return AttributedString(html.rawHTML) }
        if node is Markdown.Image { return AttributedString("") }
        var text = node.children.reduce(AttributedString()) { $0 + inline($1) }
        if node is Strong { text.inlinePresentationIntent = (text.inlinePresentationIntent ?? []).union(.stronglyEmphasized) }
        if node is Emphasis { text.inlinePresentationIntent = (text.inlinePresentationIntent ?? []).union(.emphasized) }
        if node is Strikethrough { text.strikethroughStyle = .single }
        if let link = node as? Markdown.Link, let destination = link.destination,
           let url = URL(string: destination, relativeTo: client.baseURL)?.absoluteURL,
           ["http", "https", "mailto", "tel"].contains(url.scheme?.lowercased() ?? "") { text.link = url }
        return text
    }
}
