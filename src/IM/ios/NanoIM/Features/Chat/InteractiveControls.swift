import SwiftUI

struct InteractiveControl: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var type: String { node["typeName"].stringValue ?? "" }
    private var property: String { ["Chips", "OptionCards"].contains(type) ? "defaultValue" : "value" }
    private var value: JSONValue { runtime.fieldValue(node, form: form, property: property) }
    private var text: Binding<String> {
        Binding(get: { InteractiveNode.text(value) }, set: { runtime.edit(node, form: form, value: .string($0), property: property) })
    }
    private var label: String { props["label"].stringValue ?? props["placeholder"].stringValue ?? props["name"].stringValue ?? L("输入", "Input") }
    private var items: [JSONValue] { props["items"].arrayValue ?? [] }
    var body: some View { content.tint(NanoTheme.accent).disabled(runtime.busy) }
    private var content: AnyView {
        switch type {
        case "Input": return input
        case "TextArea":
            return AnyView(TextField(props["placeholder"].stringValue ?? "", text: text, axis: .vertical)
                .lineLimit(max(2, min(15, props["rows"].intValue ?? 4))...20)
                .textFieldStyle(.roundedBorder).accessibilityLabel(label))
        case "Select":
            return AnyView(Picker(selection: text) {
                Text(props["placeholder"].stringValue ?? L("请选择", "Choose")).tag("")
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    let p = InteractiveNode.props(item)
                    Text(InteractiveNode.text(p["label"])).tag(InteractiveNode.text(p["value"]))
                }
            } label: { Text(label) }.pickerStyle(.menu).font(InteractiveNode.font(props["size"].stringValue)).accessibilityLabel(label))
        case "DatePicker": return AnyView(InteractiveDateInput(node: node, runtime: runtime, form: form))
        case "Slider": return AnyView(InteractiveSlider(node: node, runtime: runtime, form: form))
        case "RadioGroup": return AnyView(radioGroup)
        case "CheckBoxGroup", "SwitchGroup": return AnyView(toggleGroup.interactiveSurface(props["variant"].stringValue ?? "clear"))
        case "Chips", "OptionCards": return AnyView(choices)
        default: return AnyView(EmptyView())
        }
    }
    private var input: AnyView {
        if props["type"].stringValue == "password" {
            return AnyView(SecureField(props["placeholder"].stringValue ?? "", text: text).textFieldStyle(.roundedBorder).accessibilityLabel(label))
        }
        let keyboard: UIKeyboardType
        switch props["type"].stringValue {
        case "email": keyboard = .emailAddress
        case "url": keyboard = .URL
        case "number": keyboard = .numbersAndPunctuation
        default: keyboard = .default
        }
        return AnyView(TextField(props["placeholder"].stringValue ?? "", text: text)
            .keyboardType(keyboard).textFieldStyle(.roundedBorder)
            .textInputAutocapitalization(keyboard == .default ? .sentences : .never)
            .autocorrectionDisabled(keyboard != .default).accessibilityLabel(label))
    }
    private var radioGroup: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                let p = InteractiveNode.props(item)
                let selected = value.stringValue == p["value"].stringValue
                Button { runtime.edit(node, form: form, value: p["value"]) } label: {
                    HStack(alignment: .top, spacing: 9) {
                        Image(systemName: selected ? "largecircle.fill.circle" : "circle").foregroundStyle(NanoTheme.accent)
                        optionLabel(p)
                    }.frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityAddTraits(selected ? .isSelected : [])
            }
        }
    }
    private var aggregate: [String: JSONValue] {
        var result = value.objectValue ?? [:]
        for item in items {
            let p = InteractiveNode.props(item), key = InteractiveNode.text(InteractiveNode.props(item)["name"])
            if result[key] == nil { result[key] = .bool(p["defaultChecked"].boolValue ?? false) }
        }
        return result
    }
    private var toggleGroup: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                let p = InteractiveNode.props(item), name = InteractiveNode.text(InteractiveNode.props(item)["name"])
                let binding = Binding(get: { aggregate[name]?.boolValue ?? false }, set: { checked in
                    var next = aggregate; next[name] = .bool(checked)
                    runtime.edit(node, form: form, value: .object(next))
                })
                if type == "SwitchGroup" { Toggle(isOn: binding) { optionLabel(p) } }
                else {
                    Button { binding.wrappedValue.toggle() } label: {
                        HStack(alignment: .top, spacing: 9) {
                            Image(systemName: binding.wrappedValue ? "checkmark.square.fill" : "square").foregroundStyle(NanoTheme.accent)
                            optionLabel(p)
                        }.frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityAddTraits(binding.wrappedValue ? .isSelected : [])
                }
            }
        }
    }
    private func optionLabel(_ p: JSONValue) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(InteractiveNode.text(p["label"]))
            if let description = p["description"].stringValue, !description.isEmpty { Text(description).font(.caption).foregroundStyle(NanoTheme.muted) }
        }
    }
    private var multiple: Bool { props["type"].stringValue == "multiple" || (type == "Chips" && props["type"] == .null) }
    private var selected: [String] { value.arrayValue?.compactMap(\.stringValue) ?? value.stringValue.map { [$0] } ?? [] }
    private func toggle(_ item: JSONValue) {
        let key = InteractiveNode.text(InteractiveNode.props(item)["value"])
        var next = selected
        if let index = next.firstIndex(of: key) { next.remove(at: index) }
        else if multiple { next.append(key) }
        else { next = [key] }
        runtime.edit(node, form: form, value: multiple ? .array(next.map(JSONValue.string)) : next.first.map(JSONValue.string) ?? .null, property: property)
    }
    private var choices: some View {
        Group {
            if type == "OptionCards" {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), alignment: .top)], alignment: .leading, spacing: 10) {
                    ForEach(Array(items.enumerated()), id: \.offset) { _, item in choice(item) }
                }
            } else {
                InteractiveFlowLayout(spacing: 8) { ForEach(Array(items.enumerated()), id: \.offset) { _, item in choice(item) } }
            }
        }
    }
    private func choice(_ item: JSONValue) -> AnyView {
        let p = InteractiveNode.props(item)
        let checked = selected.contains(InteractiveNode.text(p["value"]))
        return AnyView(Button { toggle(item) } label: {
            VStack(alignment: .leading, spacing: 7) {
                if type == "OptionCards", p["topContent"] != .null { AnyView(InteractiveNodeView(node: p["topContent"], runtime: runtime, form: form)) }
                HStack(alignment: .top, spacing: 7) {
                    if type == "Chips", p["icon"] != .null { AnyView(InteractiveNodeView(node: p["icon"], runtime: runtime, form: form)) }
                    Text(InteractiveNode.text(p[type == "Chips" ? "label" : "title"])).font(.subheadline.weight(checked ? .semibold : .regular))
                    if checked { Image(systemName: "checkmark").font(.caption.weight(.semibold)) }
                }
                if type == "OptionCards", p["subtitle"] != .null { Text(InteractiveNode.text(p["subtitle"])).font(.caption).foregroundStyle(NanoTheme.muted) }
            }.padding(11).frame(maxWidth: type == "OptionCards" ? .infinity : nil, alignment: .leading)
                .background(checked ? NanoTheme.softAccent : NanoTheme.canvas, in: RoundedRectangle(cornerRadius: type == "Chips" ? 18 : 10))
                .overlay { RoundedRectangle(cornerRadius: type == "Chips" ? 18 : 10).stroke(checked ? NanoTheme.accent : NanoTheme.border, lineWidth: 1) }
        }.buttonStyle(.plain).disabled(p["disabled"].boolValue ?? false).accessibilityAddTraits(checked ? .isSelected : []))
    }
}

private struct InteractiveDateInput: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var value: JSONValue { runtime.fieldValue(node, form: form) }
    private var range: Bool { props["mode"].stringValue == "range" }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if range {
                datePicker(L("开始日期", "From"), key: "from")
                datePicker(L("结束日期", "To"), key: "to")
            } else { datePicker(props["name"].stringValue ?? L("日期", "Date"), key: nil) }
            if value != .null { Button(L("清除日期", "Clear date")) { runtime.edit(node, form: form, value: .null) }.font(.caption) }
        }
    }
    private func datePicker(_ label: String, key: String?) -> some View {
        let current = key.map { value[$0] } ?? value
        let binding = Binding<Date>(get: { InteractiveDate.parse(current) ?? Date() }, set: { date in
            let encoded = InteractiveDate.encode(date)
            if let key {
                var next = value.objectValue ?? [:]; next[key] = encoded
                runtime.edit(node, form: form, value: .object(next))
            } else { runtime.edit(node, form: form, value: encoded) }
        })
        return VStack(alignment: .leading, spacing: 4) {
            if current == .null { Text(L("尚未选择", "No date selected")).font(.caption).foregroundStyle(NanoTheme.muted) }
            DatePicker(label, selection: binding, displayedComponents: .date).datePickerStyle(.compact)
            if current == .null { Button(L("选择今天", "Use today")) { binding.wrappedValue = Date() }.font(.caption) }
        }
    }
}

enum InteractiveDate {
    static func parse(_ value: JSONValue) -> Date? {
        guard let string = value.stringValue else { return nil }
        if let date = nanoDate(string) { return date }
        let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX"); formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: string)
    }
    static func encode(_ date: Date) -> JSONValue {
        let formatter = ISO8601DateFormatter(); formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return .string(formatter.string(from: Calendar.current.startOfDay(for: date)))
    }
}

private struct InteractiveSlider: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var lower: Double { props["min"].doubleValue ?? 0 }
    private var upper: Double { props["max"].doubleValue ?? 100 }
    private var values: [JSONValue] { runtime.fieldValue(node, form: form).arrayValue ?? props["defaultValue"].arrayValue ?? [.number(lower)] }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(0..<max(1, values.count), id: \.self) { index in
                let current = values.indices.contains(index) ? values[index].doubleValue ?? lower : lower
                let title = (props["label"].stringValue ?? props["name"].stringValue ?? L("数值", "Value")) + (values.count > 1 ? " \(index + 1)" : "")
                HStack(alignment: .firstTextBaseline) { Text(title).font(.subheadline); Spacer(minLength: 6); Text(current.formatted()).monospacedDigit().font(.subheadline.weight(.semibold)) }
                if upper > lower { slider(index, title: title) }
            }
            HStack { Text(lower.formatted()); Spacer(); Text(upper.formatted()) }.font(.caption).foregroundStyle(NanoTheme.muted)
        }
    }
    private func slider(_ index: Int, title: String) -> AnyView {
        let binding = Binding<Double>(get: { min(upper, max(lower, values.indices.contains(index) ? values[index].doubleValue ?? lower : lower)) }, set: { number in
            var next = values.isEmpty ? [.number(lower)] : values; next[index] = .number(number)
            runtime.edit(node, form: form, value: .array(next))
        })
        if props["variant"].stringValue == "discrete" {
            return AnyView(Slider(value: binding, in: lower...upper, step: max(0.000001, props["step"].doubleValue ?? 1)).accessibilityLabel(title))
        }
        return AnyView(Slider(value: binding, in: lower...upper).accessibilityLabel(title))
    }
}

struct InteractiveActionButton: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var type: String { node["typeName"].stringValue ?? "" }
    private var primary: Bool { type == "ContinueButton" || props["variant"].stringValue == "primary" || props["variant"] == .null }
    private var destructive: Bool { props["type"].stringValue == "destructive" }
    var body: some View {
        Button(role: destructive ? .destructive : nil) { runtime.activate(node, form: form) } label: {
            Group {
                if type == "IconButton" { InteractiveIcon(node: props["icon"]).frame(minWidth: 22, minHeight: 22) }
                else { Text(InteractiveNode.text(props["label"])).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true) }
            }.font(InteractiveNode.font(props["size"].stringValue))
                .padding(.horizontal, props["size"].stringValue == "extra-small" ? 9 : 14)
                .padding(.vertical, props["size"].stringValue == "extra-small" ? 7 : 11)
                .foregroundStyle(primary ? Color.white : destructive ? Color.red : NanoTheme.accent)
                .background(primary ? (destructive ? Color.red : NanoTheme.accent) : props["variant"].stringValue == "tertiary" ? .clear : NanoTheme.softAccent,
                            in: RoundedRectangle(cornerRadius: props["shape"].stringValue == "circle" ? 40 : 10))
        }.buttonStyle(.plain).disabled(runtime.busy)
            .accessibilityLabel(InteractiveNode.text(props[type == "IconButton" ? "name" : "label"]))
    }
}

struct InteractiveTable: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    private var columns: [JSONValue] { InteractiveNode.props(node)["columns"].arrayValue ?? [] }
    private var rowCount: Int { columns.map { InteractiveNode.props($0)["data"].arrayValue?.count ?? 0 }.max() ?? 0 }
    var body: some View {
        if columns.isEmpty { Text(L("暂无表格数据", "No table data")).font(.caption).foregroundStyle(NanoTheme.muted) }
        else {
            ScrollView(.horizontal) {
                Grid(alignment: .topLeading, horizontalSpacing: 14, verticalSpacing: 10) {
                    GridRow { ForEach(Array(columns.enumerated()), id: \.offset) { _, column in
                        Text(InteractiveNode.text(InteractiveNode.props(column)["label"])).font(.subheadline.weight(.semibold)).frame(minWidth: 90, maxWidth: 240, alignment: .leading)
                    } }
                    Divider().gridCellColumns(columns.count)
                    ForEach(0..<rowCount, id: \.self) { index in
                        GridRow { ForEach(Array(columns.enumerated()), id: \.offset) { _, column in cell(column, row: index) } }
                    }
                }.padding(10)
            }.interactiveSurface("sunk")
        }
    }
    private func cell(_ column: JSONValue, row: Int) -> AnyView {
        let data = InteractiveNode.props(column)["data"].arrayValue ?? []
        let value = data.indices.contains(row) ? data[row] : .null
        if value["type"].stringValue == "element" { return AnyView(InteractiveNodeView(node: value, runtime: runtime, form: form).frame(minWidth: 90, maxWidth: 240, alignment: .leading)) }
        return AnyView(Text(InteractiveNode.text(value)).font(.subheadline).monospacedDigit().textSelection(.enabled).frame(minWidth: 90, maxWidth: 240, alignment: .leading))
    }
}

struct InteractiveEditableTable: View {
    let node: JSONValue
    let runtime: InteractiveRuntime
    let form: String?
    @State private var localRows: [JSONValue]?
    @State private var baseline: [JSONValue]?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var columns: [JSONValue] { props["columns"].arrayValue ?? [] }
    private var saved: [JSONValue] { runtime.fieldValue(node, form: props["name"].stringValue, property: "data").arrayValue ?? props["data"].arrayValue ?? [] }
    private var rows: [JSONValue] { localRows ?? saved }
    private var changed: Int {
        let original = baseline ?? saved
        return rows.enumerated().reduce(0) { count, entry in
            let previous = original.indices.contains(entry.offset) ? original[entry.offset]["values"].arrayValue ?? [] : []
            return count + (entry.element["values"].arrayValue ?? []).enumerated().filter { !previous.indices.contains($0.offset) || previous[$0.offset] != $0.element }.count
        }
    }
    private var invalidNumber: Bool {
        rows.contains { row in
            let values = row["values"].arrayValue ?? []
            return columns.enumerated().contains { index, column in
                InteractiveNode.props(column)["type"].stringValue == "number" && values.indices.contains(index) && Double(InteractiveNode.text(values[index])) == nil
            }
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if columns.isEmpty || rows.isEmpty { Text(L("暂无可编辑数据", "No editable data")).font(.caption).foregroundStyle(NanoTheme.muted) }
            else {
                ScrollView(.horizontal) {
                    Grid(alignment: .topLeading, horizontalSpacing: 10, verticalSpacing: 10) {
                        GridRow { ForEach(Array(columns.enumerated()), id: \.offset) { _, column in
                            Text(InteractiveNode.text(InteractiveNode.props(column)["header"])).font(.subheadline.weight(.semibold)).frame(width: width(column), alignment: .leading)
                        } }
                        Divider().gridCellColumns(max(1, columns.count))
                        ForEach(Array(rows.enumerated()), id: \.offset) { rowIndex, _ in
                            GridRow { ForEach(Array(columns.enumerated()), id: \.offset) { columnIndex, column in editor(rowIndex, column: columnIndex, definition: column) } }
                        }
                    }.padding(10)
                }.interactiveSurface("sunk")
            }
            if changed > 0 {
                Text(String(format: L("已修改 %d 个单元格", "%d changed cells"), changed)).font(.caption).foregroundStyle(NanoTheme.muted)
                if invalidNumber { ErrorNotice(message: L("请在数字列输入有效数字", "Enter valid numbers in numeric columns")) }
                InteractiveFlowLayout(spacing: 8) {
                    Button(L("重置修改", "Reset changes")) { localRows = nil; baseline = nil }.buttonStyle(.bordered)
                    Button(L("保存修改", "Save changes")) {
                        runtime.edit(node, form: props["name"].stringValue, value: .array(rows), property: "data")
                        runtime.activate(node, form: props["name"].stringValue)
                        localRows = nil; baseline = nil
                    }.buttonStyle(.borderedProminent).disabled(runtime.busy || invalidNumber)
                }
            }
        }.onChange(of: saved) { _, _ in localRows = nil; baseline = nil }
    }
    private func width(_ column: JSONValue) -> CGFloat { max(100, min(360, InteractiveNode.props(column)["width"].doubleValue ?? 150)) }
    private func binding(_ row: Int, column: Int) -> Binding<String> {
        Binding(get: {
            let values = rows[row]["values"].arrayValue ?? []
            return values.indices.contains(column) ? InteractiveNode.text(values[column]) : ""
        }, set: { text in
            if baseline == nil { baseline = saved }
            var next = rows, rowObject = rows[row].objectValue ?? [:], values = rows[row]["values"].arrayValue ?? []
            while values.count <= column { values.append(.string("")) }
            let numeric = InteractiveNode.props(columns[column])["type"].stringValue == "number"
            values[column] = numeric ? Double(text).map(JSONValue.number) ?? .string(text) : .string(text)
            rowObject["values"] = .array(values); next[row] = .object(rowObject); localRows = next
        })
    }
    private func editor(_ row: Int, column: Int, definition: JSONValue) -> AnyView {
        let p = InteractiveNode.props(definition), value = binding(row, column: column)
        let label = InteractiveNode.text(p["header"]) + " " + L("第", "row ") + "\(row + 1)"
        switch p["type"].stringValue {
        case "select":
            return AnyView(Picker(label, selection: value) {
                ForEach(Array((p["options"].arrayValue ?? []).enumerated()), id: \.offset) { _, option in Text(InteractiveNode.text(option["label"])).tag(InteractiveNode.text(option["value"])) }
            }.pickerStyle(.menu).frame(width: width(definition), alignment: .leading))
        case "date-single":
            let date = Binding(get: { InteractiveDate.parse(.string(value.wrappedValue)) ?? Date() }, set: { value.wrappedValue = InteractiveDate.encode($0).stringValue ?? "" })
            return AnyView(DatePicker(label, selection: date, displayedComponents: .date).labelsHidden().frame(width: width(definition), alignment: .leading).accessibilityLabel(label))
        default:
            return AnyView(TextField(label, text: value, axis: .vertical).lineLimit(1...4).textFieldStyle(.roundedBorder)
                .keyboardType(p["type"].stringValue == "number" ? .numbersAndPunctuation : p["type"].stringValue == "url" ? .URL : .default)
                .frame(width: width(definition), alignment: .leading).accessibilityLabel(label))
        }
    }
}
