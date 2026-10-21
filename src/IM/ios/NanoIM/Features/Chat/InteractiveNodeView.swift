import SwiftUI

/// Renders evaluated nano-1 elements; parsing, bindings and actions belong to the runtime.
struct InteractiveNodeView: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    var form: String? = nil

    var body: some View { content.foregroundStyle(NanoTheme.ink).tint(NanoTheme.accent) }

    private var props: JSONValue { InteractiveNode.props(node) }
    private func child(_ value: JSONValue) -> AnyView {
        AnyView(InteractiveNodeView(node: value, runtime: runtime, form: form))
    }
    private func children(_ value: JSONValue, form: String? = nil) -> AnyView {
        AnyView(InteractiveChildren(nodes: value.arrayValue ?? [], runtime: runtime, form: form ?? self.form))
    }
    private var content: AnyView {
        if let array = node.arrayValue { return AnyView(InteractiveChildren(nodes: array, runtime: runtime, form: form)) }
        if let text = node.stringValue { return AnyView(Text(text).textSelection(.enabled)) }
        if node == .null { return AnyView(EmptyView()) }
        let type = node["typeName"].stringValue ?? ""
        switch type {
        case "Card", "Stack":
            return AnyView(InteractiveStack(node: node, runtime: runtime, form: form)
                .interactiveSurface(type == "Card" ? props["variant"].stringValue ?? "card" : "clear"))
        case "TextContent", "MarkDownRenderer":
            let text = InteractiveNode.text(props[type == "TextContent" ? "text" : "textMarkdown"])
            return AnyView(MarkdownView(text: text, client: runtime.client, baseFont: InteractiveNode.font(props["size"].stringValue))
                .interactiveSurface(props["variant"].stringValue ?? "clear"))
        case "CardHeader", "InlineHeader":
            return AnyView(InteractiveHeading(title: InteractiveNode.text(props[type == "CardHeader" ? "title" : "heading"]),
                                              subtitle: InteractiveNode.text(props[type == "CardHeader" ? "subtitle" : "description"])))
        case "Label": return AnyView(Text(InteractiveNode.text(props["text"])).font(.subheadline.weight(.semibold)))
        case "Callout", "TextCallout": return AnyView(InteractiveCallout(node: node, runtime: runtime, form: form))
        case "Image", "ImageBlock":
            if let source = props["src"].stringValue, !source.isEmpty {
                return AnyView(InteractiveImage(client: runtime.client, source: source, label: InteractiveNode.text(props["alt"])))
            }
            return AnyView(Text(InteractiveNode.text(props["alt"])).font(.caption).foregroundStyle(NanoTheme.muted))
        case "ImageGallery":
            return AnyView(LazyVGrid(columns: [GridItem(.adaptive(minimum: 140), alignment: .top)], alignment: .leading, spacing: 12) {
                ForEach(Array((props["images"].arrayValue ?? []).enumerated()), id: \.offset) { _, image in
                    VStack(alignment: .leading, spacing: 5) {
                        InteractiveImage(client: runtime.client, source: InteractiveNode.text(image["src"]), label: InteractiveNode.text(image["alt"]))
                        if let details = image["details"].stringValue { Text(details).font(.caption).foregroundStyle(NanoTheme.muted) }
                    }
                }
            })
        case "CodeBlock":
            return AnyView(InteractiveCodeBlock(language: InteractiveNode.text(props["language"]), code: InteractiveNode.text(props["codeString"])))
        case "Separator":
            if props["orientation"].stringValue == "vertical" {
                return AnyView(Rectangle().fill(NanoTheme.border).frame(width: 1, height: 28).accessibilityHidden(props["decorative"].boolValue ?? true))
            }
            return AnyView(Divider().accessibilityHidden(props["decorative"].boolValue ?? true))
        case "Form":
            return AnyView(VStack(alignment: .leading, spacing: 16) {
                InteractiveChildren(nodes: props["fields"].arrayValue ?? [], runtime: runtime, form: props["name"].stringValue)
                InteractiveNodeView(node: props["buttons"], runtime: runtime, form: props["name"].stringValue)
            })
        case "FormControl":
            return AnyView(VStack(alignment: .leading, spacing: 7) {
                Text(InteractiveNode.text(props["label"])).font(.subheadline.weight(.semibold))
                child(props["input"]).accessibilityLabel(InteractiveNode.text(props["label"]))
                if let hint = props["hint"].stringValue { Text(hint).font(.caption).foregroundStyle(NanoTheme.muted) }
            })
        case "Input", "TextArea", "Select", "DatePicker", "Slider", "CheckBoxGroup", "RadioGroup", "SwitchGroup", "Chips", "OptionCards":
            return AnyView(InteractiveControl(node: node, runtime: runtime, form: form))
        case "EditableTable": return AnyView(InteractiveEditableTable(node: node, runtime: runtime, form: form))
        case "Button", "ContinueButton", "IconButton": return AnyView(InteractiveActionButton(node: node, runtime: runtime, form: form))
        case "Buttons":
            if props["direction"].stringValue == "column" { return children(props["buttons"]) }
            return AnyView(InteractiveFlowLayout(spacing: 8) {
                ForEach(Array((props["buttons"].arrayValue ?? []).enumerated()), id: \.offset) { _, button in child(button) }
            })
        case "Table": return AnyView(InteractiveTable(node: node, runtime: runtime, form: form))
        case "BarChart", "LineChart", "AreaChart", "RadarChart", "HorizontalBarChart", "PieChart", "RadialChart", "SingleStackedBarChart", "ScatterChart":
            return AnyView(InteractiveChart(node: node))
        case "Tabs": return AnyView(InteractiveTabs(node: node, runtime: runtime, form: form))
        case "Accordion":
            return AnyView(VStack(alignment: .leading, spacing: 12) {
                ForEach(Array((props["items"].arrayValue ?? []).enumerated()), id: \.offset) { _, item in
                    InteractiveDisclosure(node: item, runtime: runtime, form: form)
                }
            })
        case "Modal": return AnyView(InteractiveModal(node: node, runtime: runtime, form: form))
        case "Carousel":
            return AnyView(ScrollView(.horizontal) {
                HStack(alignment: .top, spacing: 12) {
                    ForEach(Array((props["children"].arrayValue ?? []).enumerated()), id: \.offset) { _, item in
                        child(item).frame(width: 260).interactiveSurface(props["variant"].stringValue ?? "card")
                    }
                }.padding(.vertical, 2)
            })
        case "Steps":
            return AnyView(VStack(alignment: .leading, spacing: 16) {
                ForEach(Array((props["items"].arrayValue ?? []).enumerated()), id: \.offset) { index, item in
                    HStack(alignment: .top, spacing: 10) {
                        Text("\(index + 1)").font(.caption.bold()).foregroundStyle(NanoTheme.accent)
                            .padding(7).background(NanoTheme.softAccent, in: Circle())
                        InteractiveHeading(title: InteractiveNode.text(InteractiveNode.props(item)["title"]), subtitle: InteractiveNode.text(InteractiveNode.props(item)["details"]))
                    }
                }
            })
        case "TagBlock":
            return AnyView(InteractiveFlowLayout(spacing: 6) {
                ForEach(Array((props["tags"].arrayValue ?? []).enumerated()), id: \.offset) { _, tag in
                    InteractiveTag(text: InteractiveNode.text(tag), size: props["size"].stringValue, variant: "neutral")
                }
            })
        case "Tag":
            return AnyView(HStack(spacing: 4) {
                if props["icon"] != .null { child(props["icon"]) }
                InteractiveTag(text: InteractiveNode.text(props["text"]), size: props["size"].stringValue, variant: props["variant"].stringValue ?? "neutral")
            })
        case "Icon": return AnyView(InteractiveIcon(node: node))
        case "EntityList": return AnyView(InteractiveEntityList(node: node))
        case "ListBlock": return AnyView(InteractiveList(node: node, runtime: runtime, form: form))
        case "ListItem": return AnyView(InteractiveListRow(node: node, runtime: runtime, form: form, index: nil))
        case "Text", "BoldText": return AnyView(InteractiveValueText(node: node))
        case "IconText", "ImageText", "ImageTextLarge": return AnyView(InteractiveMediaText(node: node, runtime: runtime, form: form))
        case "MetricIndicatorInline", "MetricIndicatorWithStrikethrough": return AnyView(InteractiveMetric(node: node))
        case "SnippetCardBlock", "OverviewCardBlock", "ContextCardBlock", "CompositeCardBlock", "VisualCardBlock":
            return AnyView(InteractiveCardCollection(node: node, runtime: runtime, form: form))
        case "SnippetCardItem":
            return AnyView(ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 10) { child(props["lhs"]); Spacer(minLength: 4); child(props["rhs"]) }
                VStack(alignment: .leading, spacing: 8) { child(props["lhs"]); child(props["rhs"]) }
            })
        case "OverviewCardItem":
            return AnyView(VStack(alignment: .leading, spacing: 12) { child(props["top"]); child(props["bottom"]) })
        case "ContextCardItem":
            return AnyView(VStack(alignment: .leading, spacing: 9) {
                if props["bgImageSrc"] != .null { InteractiveImage(client: runtime.client, source: InteractiveNode.text(props["bgImageSrc"]), label: InteractiveNode.text(props["bgImageAlt"])) }
                child(props["title"])
                MarkdownView(text: InteractiveNode.text(props["body"]), client: runtime.client).fontWeight(.semibold)
            }.interactiveSurface(props["bgColor"].stringValue == "gray" ? "sunk" : "clear"))
        case "CompositeCardItem":
            return AnyView(VStack(alignment: .leading, spacing: 12) {
                child(props["header"]); children(props["body"])
                child(props["footer"]["price"]); child(props["footer"]["button"])
            })
        case "VisualCardItem":
            return AnyView(VStack(alignment: .leading, spacing: 10) {
                if props["bgImageSrc"] != .null { InteractiveImage(client: runtime.client, source: InteractiveNode.text(props["bgImageSrc"]), label: InteractiveNode.text(props["bgImageAlt"])) }
                child(props["tag"]); child(props["body"])
            })
        // These are typed data slots. Their owning component consumes their props.
        case "Col", "Series", "Slice", "ScatterSeries", "Point", "SelectItem", "CheckBoxItem", "RadioItem", "SwitchItem", "ChipItem", "OptionCard", "TabItem", "AccordionItem", "StepsItem":
            return AnyView(EmptyView())
        default:
            return AnyView(ErrorNotice(message: L("无法显示组件：", "Unsupported component: ") + type))
        }
    }
}

enum InteractiveNode {
    static func props(_ node: JSONValue) -> JSONValue { node["type"].stringValue == "element" ? node["props"] : node }
    static func text(_ value: JSONValue) -> String {
        switch value {
        case .string(let text): return text
        case .number(let number): return number.formatted(.number.precision(.fractionLength(0...8)))
        case .bool(let bool): return bool ? L("是", "Yes") : L("否", "No")
        case .array(let array): return array.map(text).joined(separator: ", ")
        case .object: return value.prettyPrinted
        case .null: return ""
        }
    }
    static func gap(_ value: JSONValue) -> CGFloat {
        if let number = value.doubleValue { return max(0, number) }
        return ["none": 0.0, "xs": 4, "s": 8, "m": 12, "l": 16, "xl": 24, "2xl": 32][value.stringValue ?? "m"] ?? 12
    }
    static func font(_ size: String?) -> Font {
        switch size {
        case "xs": return .caption2
        case "small", "sm": return .caption
        case "small-heavy": return .caption.weight(.semibold)
        case "large", "lg": return .title3
        case "large-heavy": return .title3.weight(.bold)
        default: return .body
        }
    }
    static func color(_ variant: String) -> Color {
        switch variant {
        case "error", "danger": return .red
        case "warning": return .orange
        case "success": return NanoTheme.accent
        case "info": return .blue
        default: return NanoTheme.muted
        }
    }
}

struct InteractiveChildren: View {
    let nodes: [JSONValue]
    let runtime: InteractiveRuntime
    var form: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(Array(nodes.enumerated()), id: \.offset) { _, node in
                AnyView(InteractiveNodeView(node: node, runtime: runtime, form: form))
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct InteractiveSurface: ViewModifier {
    let variant: String
    func body(content: Content) -> some View {
        content.padding(variant == "clear" ? 0 : 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(variant == "sunk" ? NanoTheme.canvas : variant == "card" ? NanoTheme.surface : .clear, in: RoundedRectangle(cornerRadius: 12))
            .overlay { if variant == "card" { RoundedRectangle(cornerRadius: 12).stroke(NanoTheme.border, lineWidth: 1) } }
    }
}
extension View {
    func interactiveSurface(_ variant: String) -> some View { modifier(InteractiveSurface(variant: variant)) }
}

private struct InteractiveStack: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var nodes: [JSONValue] { props["children"].arrayValue ?? [] }
    private var spacing: CGFloat { InteractiveNode.gap(props["gap"]) }
    private var horizontal: HorizontalAlignment {
        switch props["align"].stringValue { case "center": return .center; case "end": return .trailing; default: return .leading }
    }
    private var vertical: VerticalAlignment {
        switch props["align"].stringValue { case "center": return .center; case "end": return .bottom; case "baseline": return .firstTextBaseline; default: return .top }
    }
    var body: some View {
        if props["direction"].stringValue == "row" {
            if props["wrap"].boolValue == true {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), alignment: .top)], alignment: horizontal, spacing: spacing) { contents }
            } else {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: vertical, spacing: spacing) {
                        if ["around", "evenly", "end"].contains(props["justify"].stringValue ?? "") { Spacer(minLength: 0) }
                        ForEach(Array(nodes.enumerated()), id: \.offset) { index, node in
                            AnyView(InteractiveNodeView(node: node, runtime: runtime, form: form))
                            if index < nodes.count - 1 && ["between", "around", "evenly"].contains(props["justify"].stringValue ?? "") { Spacer(minLength: 0) }
                        }
                        if ["around", "evenly", "start"].contains(props["justify"].stringValue ?? "start") { Spacer(minLength: 0) }
                    }
                    VStack(alignment: horizontal, spacing: spacing) { contents }
                }
            }
        } else { VStack(alignment: horizontal, spacing: spacing) { contents } }
    }
    private var contents: some View {
        ForEach(Array(nodes.enumerated()), id: \.offset) { _, node in AnyView(InteractiveNodeView(node: node, runtime: runtime, form: form)) }
    }
}

/// Intrinsic-width controls and tags wrap without clipping at accessibility text sizes.
struct InteractiveFlowLayout: Layout {
    var spacing: CGFloat = 8
    private func rows(_ proposal: ProposedViewSize, _ subviews: Subviews) -> (CGSize, [CGRect]) {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0, usedWidth: CGFloat = 0
        var frames: [CGRect] = []
        for subview in subviews {
            let size = subview.sizeThatFits(ProposedViewSize(width: width.isFinite ? width : nil, height: nil))
            if x > 0 && x + size.width > width { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            frames.append(CGRect(origin: CGPoint(x: x, y: y), size: size))
            usedWidth = max(usedWidth, x + size.width); x += size.width + spacing; rowHeight = max(rowHeight, size.height)
        }
        return (CGSize(width: usedWidth, height: y + rowHeight), frames)
    }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize { rows(proposal, subviews).0 }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        for (index, frame) in rows(ProposedViewSize(width: bounds.width, height: nil), subviews).1.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY), proposal: ProposedViewSize(frame.size))
        }
    }
}

private struct InteractiveHeading: View {
    let title: String
    let subtitle: String
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            if !title.isEmpty { Text(title).font(.headline).accessibilityAddTraits(.isHeader) }
            if !subtitle.isEmpty { Text(subtitle).font(.subheadline).foregroundStyle(NanoTheme.muted) }
        }.textSelection(.enabled)
    }
}

private struct InteractiveCallout: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var visible: Bool { runtime.fieldValue(node, form: form, property: "visible").boolValue ?? true }
    var body: some View {
        if visible {
            let color = InteractiveNode.color(props["variant"].stringValue ?? "neutral")
            HStack(alignment: .top, spacing: 9) {
                Image(systemName: ["warning": "exclamationmark.triangle", "error": "exclamationmark.circle", "danger": "exclamationmark.circle", "success": "checkmark.circle"][props["variant"].stringValue ?? ""] ?? "info.circle").foregroundStyle(color)
                InteractiveHeading(title: InteractiveNode.text(props["title"]), subtitle: InteractiveNode.text(props["description"]))
            }.padding(12).frame(maxWidth: .infinity, alignment: .leading).background(color.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                .task(id: visible) {
                    guard node["typeName"].stringValue == "Callout", props["visible"] != .null else { return }
                    do { try await Task.sleep(for: .seconds(3)); runtime.edit(node, form: form, value: .bool(false), property: "visible") } catch {}
                }
        }
    }
}

private struct InteractiveCodeBlock: View {
    let language: String
    let code: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(language).font(.caption).foregroundStyle(NanoTheme.muted)
                Spacer()
                Button { UIPasteboard.general.string = code } label: { Label(L("复制", "Copy"), systemImage: "doc.on.doc") }.font(.caption)
            }
            ScrollView(.horizontal) { Text(highlighted).font(.system(.callout, design: .monospaced)).textSelection(.enabled).fixedSize(horizontal: true, vertical: false) }
        }.interactiveSurface("sunk")
    }
    private var highlighted: AttributedString {
        var result = AttributedString(code)
        guard !language.isEmpty, !["text", "plain", "plaintext"].contains(language.lowercased()) else { return result }
        let tokens: [(String, Color)] = [
            (#"\b(?:if|else|for|while|return|func|function|let|var|const|class|struct|enum|import|from|def|async|await|try|catch|throw|true|false|null|nil|None|True|False|public|private|static|switch|case|break|continue|new|in|as)\b"#, .purple),
            (#"\b[0-9]+(?:\.[0-9]+)?\b"#, .orange),
            (#""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'"#, NanoTheme.accent),
            (#"//[^\n]*|/\*[\s\S]*?\*/"#, NanoTheme.muted)
        ]
        for (pattern, color) in tokens {
            guard let regex = try? NSRegularExpression(pattern: pattern) else { continue }
            for match in regex.matches(in: code, range: NSRange(code.startIndex..., in: code)) {
                if let range = Range(match.range, in: code), let attributed = Range(range, in: result) { result[attributed].foregroundColor = color }
            }
        }
        return result
    }
}

private struct InteractiveTabs: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    @State private var selection: String?
    private var items: [JSONValue] { InteractiveNode.props(node)["items"].arrayValue ?? [] }
    private func key(_ item: JSONValue) -> String { InteractiveNode.text(InteractiveNode.props(item)["value"]) }
    private var selected: JSONValue? { items.first { key($0) == selection } ?? items.first }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            InteractiveFlowLayout(spacing: 8) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    Button { selection = key(item) } label: {
                        Text(InteractiveNode.text(InteractiveNode.props(item)["trigger"]))
                            .font(.subheadline.weight(key(item) == selected.map(key) ? .semibold : .regular))
                            .padding(.horizontal, 12).padding(.vertical, 9)
                            .background(key(item) == selected.map(key) ? NanoTheme.softAccent : NanoTheme.canvas, in: Capsule())
                    }.buttonStyle(.plain).accessibilityAddTraits(key(item) == selected.map(key) ? .isSelected : [])
                }
            }
            if let selected { InteractiveChildren(nodes: InteractiveNode.props(selected)["content"].arrayValue ?? [], runtime: runtime, form: form) }
        }
    }
}

private struct InteractiveDisclosure: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    @State private var expanded = false
    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            InteractiveChildren(nodes: InteractiveNode.props(node)["content"].arrayValue ?? [], runtime: runtime, form: form).padding(.top, 8)
        } label: { Text(InteractiveNode.text(InteractiveNode.props(node)["trigger"])).font(.subheadline.weight(.semibold)) }
    }
}

private struct InteractiveModal: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var open: Binding<Bool> {
        Binding(get: { runtime.fieldValue(node, form: form, property: "open").boolValue ?? false }, set: { runtime.edit(node, form: form, value: .bool($0), property: "open") })
    }
    var body: some View {
        Color.clear.frame(height: 0).sheet(isPresented: open) {
            NavigationStack {
                ScrollView { InteractiveChildren(nodes: props["children"].arrayValue ?? [], runtime: runtime, form: form).padding() }
                    .background(NanoTheme.surface).navigationTitle(InteractiveNode.text(props["title"]))
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { open.wrappedValue = false } } }
            }.presentationDetents(props["size"].stringValue == "sm" ? [.medium, .large] : [.large])
        }
    }
}

private struct InteractiveTag: View {
    let text: String
    let size: String?
    let variant: String
    var body: some View {
        Text(text).font(InteractiveNode.font(size)).foregroundStyle(InteractiveNode.color(variant))
            .padding(.horizontal, 8).padding(.vertical, 4).background(InteractiveNode.color(variant).opacity(0.1), in: Capsule())
    }
}

struct InteractiveIcon: View {
    let node: JSONValue
    private var props: JSONValue { InteractiveNode.props(node) }
    private var symbol: String {
        let icons = ["circle-check": "checkmark.circle", "check": "checkmark", "x": "xmark", "plus": "plus", "minus": "minus", "arrow-right": "arrow.right", "arrow-left": "arrow.left", "arrow-up": "arrow.up", "arrow-down": "arrow.down", "trending-up": "chart.line.uptrend.xyaxis", "trending-down": "chart.line.downtrend.xyaxis", "info": "info.circle", "circle-alert": "exclamationmark.circle", "triangle-alert": "exclamationmark.triangle", "star": "star", "heart": "heart", "calendar": "calendar", "clock": "clock", "search": "magnifyingglass", "settings": "gearshape", "user": "person", "users": "person.2", "mail": "envelope", "file": "doc", "folder": "folder", "book": "book", "home": "house", "house": "house", "globe": "globe", "link": "link", "external-link": "arrow.up.right.square", "download": "arrow.down.to.line", "upload": "arrow.up.to.line", "image": "photo", "chart-bar": "chart.bar", "bar-chart": "chart.bar", "chart-line": "chart.xyaxis.line", "dollar-sign": "dollarsign.circle", "credit-card": "creditcard", "briefcase": "briefcase", "map-pin": "mappin", "zap": "bolt", "sparkles": "sparkles", "lightbulb": "lightbulb", "target": "target", "shield": "shield", "lock": "lock", "unlock": "lock.open", "trash": "trash", "pencil": "pencil", "copy": "doc.on.doc", "check-circle": "checkmark.circle", "chevron-right": "chevron.right", "chevron-down": "chevron.down", "menu": "line.3.horizontal", "more-horizontal": "ellipsis", "phone": "phone", "message-circle": "bubble.left", "bell": "bell", "code": "chevron.left.forwardslash.chevron.right"]
        if let known = icons[props["name"].stringValue ?? ""] { return known }
        return ["finance": "dollarsign.circle", "health": "heart", "education": "book", "travel": "airplane", "technology": "cpu", "food": "fork.knife", "business": "briefcase"][props["category"].stringValue ?? ""] ?? "sparkle"
    }
    var body: some View { Image(systemName: symbol).accessibilityLabel(InteractiveNode.text(props["name"])) }
}

private struct InteractiveValueText: View {
    let node: JSONValue
    private var props: JSONValue { InteractiveNode.props(node) }
    private var subColor: Color {
        guard props["subtextVariant"].stringValue == "metric" else { return NanoTheme.muted }
        return InteractiveNode.text(props["subtext"]).hasPrefix("-") ? .red : NanoTheme.accent
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(InteractiveNode.text(props["value"])).font(InteractiveNode.font(props["size"].stringValue))
                .fontWeight(node["typeName"].stringValue == "BoldText" ? .bold : .regular)
                .monospacedDigit()
            if props["subtext"] != .null { Text(InteractiveNode.text(props["subtext"])).font(.caption).foregroundStyle(subColor).monospacedDigit() }
        }.textSelection(.enabled)
    }
}

private struct InteractiveMediaText: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var vertical: Bool { props["layout"].stringValue == "vertical" || node["typeName"].stringValue == "ImageTextLarge" }
    var body: some View {
        if vertical { VStack(alignment: .leading, spacing: 8) { media; texts } }
        else { HStack(alignment: .top, spacing: 10) { media; texts } }
    }
    private var texts: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(InteractiveNode.text(props["title"])).fontWeight(props["bold"].boolValue == true ? .bold : .regular)
            if props["subtitle"] != .null { Text(InteractiveNode.text(props["subtitle"])).font(.caption).foregroundStyle(NanoTheme.muted) }
        }.textSelection(.enabled)
    }
    private var media: AnyView {
        if node["typeName"].stringValue == "IconText" {
            return AnyView(InteractiveNodeView(node: props["icon"], runtime: runtime, form: form)
                .font(InteractiveNode.font(props["iconSize"].stringValue))
                .foregroundStyle(InteractiveNode.color(props["iconVariant"].stringValue ?? "neutral"))
                .padding(8).background(InteractiveNode.color(props["iconVariant"].stringValue ?? "neutral").opacity(0.1), in: RoundedRectangle(cornerRadius: 8)))
        }
        let image = InteractiveImage(client: runtime.client, source: InteractiveNode.text(props["src"]), label: InteractiveNode.text(props["alt"]))
        if node["typeName"].stringValue == "ImageTextLarge" { return AnyView(image) }
        return AnyView(image.frame(width: props["imageSize"].doubleValue ?? 44).clipped())
    }
}

private struct InteractiveMetric: View {
    let node: JSONValue
    private var props: JSONValue { InteractiveNode.props(node) }
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            InteractiveFlowLayout(spacing: 7) {
                Text(InteractiveNode.text(props["value"])).font(.title2.bold()).monospacedDigit()
                if props["previousValue"] != .null { Text(InteractiveNode.text(props["previousValue"])).strikethrough().foregroundStyle(NanoTheme.muted).monospacedDigit() }
                if let value = props["trend"]["value"].doubleValue {
                    let up = props["trend"]["direction"].stringValue == "up"
                    Label((up ? "+" : "−") + abs(value).formatted() + "%", systemImage: up ? "arrow.up" : "arrow.down")
                        .font(.caption.weight(.semibold)).foregroundStyle(up ? NanoTheme.accent : .red)
                }
            }
            if props["subtext"] != .null { Text(InteractiveNode.text(props["subtext"])).font(.caption).foregroundStyle(NanoTheme.muted) }
        }.textSelection(.enabled)
    }
}

private struct InteractiveEntityList: View {
    let node: JSONValue
    private var props: JSONValue { InteractiveNode.props(node) }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if props["size"].stringValue != "small", props["header"] != .null { row(props["header"]).fontWeight(.semibold); Divider() }
            ForEach(Array((props["rows"].arrayValue ?? []).enumerated()), id: \.offset) { _, item in row(item) }
            if props["size"].stringValue != "small", props["footer"] != .null { Divider(); row(props["footer"]).fontWeight(.semibold) }
        }.font(props["size"].stringValue == "small" ? .caption : .subheadline).textSelection(.enabled)
    }
    private func row(_ item: JSONValue) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 12) { Text(InteractiveNode.text(item["left"])); Spacer(minLength: 8); Text(InteractiveNode.text(item["right"])).monospacedDigit() }
            VStack(alignment: .leading, spacing: 4) { Text(InteractiveNode.text(item["left"])); Text(InteractiveNode.text(item["right"])).monospacedDigit() }
        }
    }
}

private struct InteractiveList: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    var body: some View {
        VStack(alignment: .leading, spacing: props["size"].stringValue == "small" ? 8 : 14) {
            ForEach(Array((props["items"].arrayValue ?? []).enumerated()), id: \.offset) { index, item in
                InteractiveListRow(node: item, runtime: runtime, form: form, index: props["variant"].stringValue == "number" ? index + 1 : nil)
            }
        }.font(props["size"].stringValue == "small" ? .caption : .body)
    }
}

private struct InteractiveListRow: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    let index: Int?
    private var props: JSONValue { InteractiveNode.props(node) }
    var body: some View {
        if props["action"] != .null { Button { runtime.activate(node, form: form) } label: { content }.buttonStyle(.plain).disabled(runtime.busy) }
        else { content }
    }
    private var content: some View {
        HStack(alignment: .top, spacing: 10) {
            if let index { Text("\(index). ").foregroundStyle(NanoTheme.muted) }
            else if props["image"]["src"] != .null { InteractiveImage(client: runtime.client, source: InteractiveNode.text(props["image"]["src"]), label: InteractiveNode.text(props["image"]["alt"])).frame(width: 44) }
            VStack(alignment: .leading, spacing: 4) {
                Text(InteractiveNode.text(props["title"])).fontWeight(.medium)
                if props["subtitle"] != .null { Text(InteractiveNode.text(props["subtitle"])).font(.caption).foregroundStyle(NanoTheme.muted) }
                if props["actionLabel"] != .null { Text(InteractiveNode.text(props["actionLabel"])).font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.accent) }
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct InteractiveCardCollection: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var items: [JSONValue] { props["items"].arrayValue ?? [] }
    var body: some View {
        if props["layout"].stringValue == "carousel" {
            ScrollView(.horizontal) { HStack(alignment: .top, spacing: InteractiveNode.gap(props["gap"])) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in card(item).frame(width: 260) }
            }.padding(.vertical, 2) }
        } else {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: props["responsive"].boolValue == false ? 140 : 220), alignment: .top)], alignment: .leading, spacing: InteractiveNode.gap(props["gap"])) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in card(item) }
            }
        }
    }
    private func card(_ item: JSONValue) -> AnyView {
        let content = AnyView(InteractiveNodeView(node: item, runtime: runtime, form: form).interactiveSurface("card"))
        guard props["action"] != .null else { return content }
        return AnyView(Button { runtime.activate(node, form: form) } label: { content }.buttonStyle(.plain).disabled(runtime.busy))
    }
}

/// Public card images never receive the authenticated IM transport.
private struct InteractiveImage: View {
    let client: IMClient
    let source: String
    let label: String
    var body: some View {
        if let url = URL(string: source), let scheme = url.scheme, ["http", "https"].contains(scheme.lowercased()), !ServerOrigin.same(client.baseURL, url) {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image): image.resizable().scaledToFit().frame(maxHeight: 260)
                case .failure: Label(label.isEmpty ? L("图片暂不可用", "Image unavailable") : label, systemImage: "photo").font(.caption)
                default: ProgressView().frame(minHeight: 44)
                }
            }.accessibilityLabel(label)
        } else { ProtectedImageView(client: client, source: source, label: label) }
    }
}
