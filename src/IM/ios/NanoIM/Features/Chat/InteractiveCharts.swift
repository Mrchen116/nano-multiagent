import SwiftUI
import Charts

/// Charts consume the evaluated Series/ScatterSeries child props, never synthetic data.
struct InteractiveChart: View {
    let node: JSONValue
    @State private var selectedCategory: String?
    private var props: JSONValue { InteractiveNode.props(node) }
    private var type: String { node["typeName"].stringValue ?? "" }
    private var labels: [String] { (props["labels"].arrayValue ?? []).map(InteractiveNode.text) }
    private var points: [InteractiveChartPoint] {
        var result: [InteractiveChartPoint] = []
        for (seriesIndex, series) in (props["series"].arrayValue ?? []).enumerated() {
            let p = InteractiveNode.props(series), values = InteractiveNode.props(series)["values"].arrayValue ?? []
            let name = InteractiveNode.text(p["category"])
            for (index, label) in labels.enumerated() {
                guard values.indices.contains(index), let value = values[index].doubleValue else { continue }
                result.append(InteractiveChartPoint(id: "\(seriesIndex):\(index)", category: label, series: name, value: value, index: index))
            }
        }
        return result
    }
    private var slices: [InteractiveChartPoint] {
        let values = props["values"].arrayValue ?? []
        return labels.enumerated().compactMap { index, label in
            guard values.indices.contains(index), let value = values[index].doubleValue else { return nil }
            return InteractiveChartPoint(id: "\(index)", category: label, series: label, value: value, index: index)
        }
    }
    private var scatter: [InteractiveScatterPoint] {
        var result: [InteractiveScatterPoint] = []
        for (seriesIndex, series) in (props["datasets"].arrayValue ?? []).enumerated() {
            let p = InteractiveNode.props(series)
            for (index, point) in (p["points"].arrayValue ?? []).enumerated() {
                let data = InteractiveNode.props(point)
                guard let x = data["x"].doubleValue, let y = data["y"].doubleValue else { continue }
                result.append(InteractiveScatterPoint(id: "\(seriesIndex):\(index)", series: InteractiveNode.text(p["name"]), x: x, y: y, z: data["z"].doubleValue))
            }
        }
        return result
    }
    private var series: [String] {
        var names: [String] = []
        for name in points.map(\.series) where !names.contains(name) { names.append(name) }
        return names
    }
    private var scatterSeries: [String] {
        scatter.reduce(into: [String]()) { if !$0.contains($1.series) { $0.append($1.series) } }
    }
    private func palette(_ domain: [String]) -> [Color] { domain.indices.map(InteractiveChartPalette.color) }
    private var height: CGFloat { max(140, props["height"].doubleValue ?? (type == "HorizontalBarChart" ? Double(max(220, labels.count * 46)) : 240)) }
    private var interpolation: InterpolationMethod {
        switch props["variant"].stringValue { case "natural": return .catmullRom; case "step": return .stepCenter; default: return .linear }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            chart
            if ["PieChart", "RadialChart", "SingleStackedBarChart"].contains(type) { legend(slices.map(\.category)) }
            else if type == "ScatterChart" { legend(scatterSeries) }
            else { legend(series) }
            if let selectedCategory {
                ForEach(points.filter { $0.category == selectedCategory }) { point in
                    Text(point.category + " · " + point.series + ": " + point.value.formatted()).font(.caption).monospacedDigit()
                }
            }
            if type == "ScatterChart", !scatter.isEmpty { scatterDetails }
            else if !points.isEmpty || !slices.isEmpty { dataDetails }
        }.font(.caption).foregroundStyle(NanoTheme.ink)
    }
    private var chart: AnyView {
        switch type {
        case "PieChart":
            if slices.isEmpty || !slices.contains(where: { $0.value > 0 }) { return empty }
            if props["appearance"].stringValue == "semiCircular" {
                return AnyView(InteractivePolarChart(points: slices, mode: .semiPie, donut: props["variant"].stringValue == "donut").frame(height: 170))
            }
            return AnyView(Chart(slices.filter { $0.value > 0 }) { point in
                SectorMark(angle: .value(point.category, point.value), innerRadius: .ratio(props["variant"].stringValue == "donut" ? 0.58 : 0), angularInset: 1)
                    .foregroundStyle(by: .value(L("类别", "Category"), point.category))
                    .accessibilityLabel(point.category).accessibilityValue(point.value.formatted())
            }.chartForegroundStyleScale(domain: slices.map(\.category), range: palette(slices.map(\.category))).chartLegend(.hidden).frame(height: 230))
        case "RadialChart":
            guard !slices.isEmpty else { return empty }
            return AnyView(InteractivePolarChart(points: slices, mode: .radial, donut: false).frame(height: 250))
        case "SingleStackedBarChart":
            guard !slices.isEmpty else { return empty }
            return AnyView(Chart(slices) { point in
                BarMark(x: .value(L("数值", "Value"), point.value), y: .value("", ""))
                    .foregroundStyle(by: .value(L("类别", "Category"), point.category))
                    .accessibilityLabel(point.category).accessibilityValue(point.value.formatted())
            }.chartForegroundStyleScale(domain: slices.map(\.category), range: palette(slices.map(\.category))).chartLegend(.hidden).chartYAxis(.hidden).frame(height: 90))
        case "ScatterChart":
            guard !scatter.isEmpty else { return empty }
            return AnyView(Chart(scatter) { point in
                PointMark(x: .value(props["xLabel"].stringValue ?? "X", point.x), y: .value(props["yLabel"].stringValue ?? "Y", point.y))
                    .foregroundStyle(by: .value(L("数据集", "Dataset"), point.series))
                    .symbolSize(point.z.map { max(10, abs($0) * 8) } ?? 36)
                    .accessibilityLabel(point.series).accessibilityValue("X: \(point.x.formatted()), Y: \(point.y.formatted())")
            }.chartForegroundStyleScale(domain: scatterSeries, range: palette(scatterSeries)).chartLegend(.hidden)
                .chartXAxisLabel(InteractiveNode.text(props["xLabel"])).chartYAxisLabel(InteractiveNode.text(props["yLabel"]))
                .frame(height: height))
        case "RadarChart":
            guard !points.isEmpty, !labels.isEmpty else { return empty }
            return AnyView(InteractiveRadarChart(points: points, labels: labels, series: series).frame(height: 280))
        default:
            guard !points.isEmpty else { return empty }
            return cartesian
        }
    }
    private var cartesian: AnyView {
        if type == "HorizontalBarChart" {
            return AnyView(Chart(points) { point in
                if props["variant"].stringValue == "stacked" {
                    BarMark(x: .value(props["xLabel"].stringValue ?? L("数值", "Value"), point.value), y: .value(props["yLabel"].stringValue ?? L("类别", "Category"), point.category))
                        .foregroundStyle(by: .value(L("系列", "Series"), point.series))
                } else {
                    BarMark(x: .value(props["xLabel"].stringValue ?? L("数值", "Value"), point.value), y: .value(props["yLabel"].stringValue ?? L("类别", "Category"), point.category))
                        .foregroundStyle(by: .value(L("系列", "Series"), point.series)).position(by: .value(L("系列", "Series"), point.series))
                }
            }.chartForegroundStyleScale(domain: series, range: palette(series)).chartLegend(.hidden)
                .chartXAxisLabel(InteractiveNode.text(props["xLabel"])).chartYAxisLabel(InteractiveNode.text(props["yLabel"]))
                .chartYScale(domain: labels).chartYAxis { AxisMarks(position: .leading) { value in AxisValueLabel { if let name = value.as(String.self) { Text(name).lineLimit(nil).frame(maxWidth: 125, alignment: .trailing) } } } }
                .frame(height: height))
        }
        return AnyView(ScrollView(.horizontal) {
            Chart(points) { point in
                if type == "BarChart" {
                    if props["variant"].stringValue == "stacked" {
                        BarMark(x: .value(L("类别", "Category"), point.category), y: .value(L("数值", "Value"), point.value))
                            .foregroundStyle(by: .value(L("系列", "Series"), point.series))
                    } else {
                        BarMark(x: .value(L("类别", "Category"), point.category), y: .value(L("数值", "Value"), point.value))
                            .foregroundStyle(by: .value(L("系列", "Series"), point.series)).position(by: .value(L("系列", "Series"), point.series))
                    }
                } else if type == "AreaChart" {
                    AreaMark(x: .value(L("类别", "Category"), point.category), y: .value(L("数值", "Value"), point.value), stacking: .unstacked)
                        .foregroundStyle(by: .value(L("系列", "Series"), point.series)).opacity(0.25).interpolationMethod(interpolation)
                    LineMark(x: .value(L("类别", "Category"), point.category), y: .value(L("数值", "Value"), point.value))
                        .foregroundStyle(by: .value(L("系列", "Series"), point.series)).interpolationMethod(interpolation)
                } else {
                    LineMark(x: .value(L("类别", "Category"), point.category), y: .value(L("数值", "Value"), point.value))
                        .foregroundStyle(by: .value(L("系列", "Series"), point.series)).interpolationMethod(interpolation)
                    PointMark(x: .value(L("类别", "Category"), point.category), y: .value(L("数值", "Value"), point.value))
                        .foregroundStyle(by: .value(L("系列", "Series"), point.series)).symbolSize(20)
                }
            }.chartForegroundStyleScale(domain: series, range: palette(series)).chartLegend(.hidden)
                .chartXScale(domain: labels).chartXSelection(value: $selectedCategory)
                .chartXAxis { AxisMarks(values: labels) { value in AxisGridLine(); AxisTick(); AxisValueLabel { if let name = value.as(String.self) { Text(name).lineLimit(nil).frame(maxWidth: 84) } } } }
                .chartXAxisLabel(InteractiveNode.text(props["xLabel"])).chartYAxisLabel(InteractiveNode.text(props["yLabel"]))
                .frame(minWidth: CGFloat(max(260, labels.count * 56)), idealWidth: CGFloat(max(300, labels.count * 56)), maxWidth: .infinity)
                .frame(height: height).padding(.top, 4)
        })
    }
    private var empty: AnyView {
        AnyView(Label(L("暂无可显示的图表数据", "No chart data available"), systemImage: "chart.bar").font(.caption).foregroundStyle(NanoTheme.muted).frame(maxWidth: .infinity, minHeight: 100))
    }
    private func legend(_ values: [String]) -> some View {
        InteractiveFlowLayout(spacing: 10) {
            ForEach(Array(values.enumerated()), id: \.offset) { index, value in
                HStack(alignment: .firstTextBaseline, spacing: 5) { Circle().fill(InteractiveChartPalette.color(index)).frame(width: 8, height: 8); Text(value).font(.caption) }
            }
        }
    }
    private var dataDetails: some View {
        DisclosureGroup(L("查看数据", "View data")) {
            VStack(alignment: .leading, spacing: 7) {
                ForEach(points.isEmpty ? slices : points) { point in
                    Text(point.category + (points.isEmpty ? "" : " · " + point.series) + ": " + point.value.formatted()).monospacedDigit().textSelection(.enabled)
                }
            }.padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
    private var scatterDetails: some View {
        DisclosureGroup(L("查看数据", "View data")) {
            VStack(alignment: .leading, spacing: 7) {
                ForEach(scatter) { point in
                    Text(point.description).monospacedDigit().textSelection(.enabled)
                }
            }.padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct InteractiveChartPoint: Identifiable {
    let id: String
    let category: String
    let series: String
    let value: Double
    let index: Int
}
private struct InteractiveScatterPoint: Identifiable {
    let id: String
    let series: String
    let x: Double
    let y: Double
    let z: Double?
    var description: String {
        let coordinates = "X=\(x.formatted()), Y=\(y.formatted())"
        let depth = z.map { ", Z=\($0.formatted())" } ?? ""
        return series + ": " + coordinates + depth
    }
}
private enum InteractiveChartPalette {
    static let colors: [Color] = [NanoTheme.accent, .blue, .orange, .purple, .pink, .indigo, .brown, .cyan]
    static func color(_ index: Int) -> Color { colors[index % colors.count] }
}

/// Swift Charts has no radar mark; this native plot shares one scale across all series.
private struct InteractiveRadarChart: View {
    let points: [InteractiveChartPoint]
    let labels: [String]
    let series: [String]
    private var maximum: Double { max(1, points.map(\.value).max() ?? 1) }
    private var minimum: Double { min(0, points.map(\.value).min() ?? 0) }
    var body: some View {
        GeometryReader { geometry in
            let side = min(geometry.size.width, geometry.size.height)
            let center = CGPoint(x: geometry.size.width / 2, y: geometry.size.height / 2)
            let radius = side * 0.32
            ZStack {
                Canvas { context, _ in
                    for level in 1...5 {
                        let path = polygon(center: center, radius: radius * CGFloat(level) / 5)
                        context.stroke(path, with: .color(NanoTheme.border), lineWidth: 1)
                    }
                    for index in labels.indices {
                        var axis = Path(); axis.move(to: center); axis.addLine(to: position(index, fraction: 1, center: center, radius: radius))
                        context.stroke(axis, with: .color(NanoTheme.border), lineWidth: 1)
                    }
                    for (index, name) in series.enumerated() {
                        let data = points.filter { $0.series == name }.sorted { $0.index < $1.index }
                        var path = Path()
                        for (offset, point) in data.enumerated() {
                            let position = position(point.index, fraction: (point.value - minimum) / (maximum - minimum), center: center, radius: radius)
                            if offset == 0 { path.move(to: position) } else { path.addLine(to: position) }
                        }
                        path.closeSubpath()
                        context.fill(path, with: .color(InteractiveChartPalette.color(index).opacity(0.13)))
                        context.stroke(path, with: .color(InteractiveChartPalette.color(index)), lineWidth: 2)
                    }
                }.accessibilityHidden(true)
                ForEach(Array(labels.enumerated()), id: \.offset) { index, label in
                    Text(label).font(.caption2).multilineTextAlignment(.center).lineLimit(nil).frame(maxWidth: 90)
                        .position(position(index, fraction: 1.28, center: center, radius: radius))
                }
                Text(maximum.formatted()).font(.caption2).foregroundStyle(NanoTheme.muted).position(x: center.x + 18, y: center.y - radius + 10)
            }
        }
    }
    private func position(_ index: Int, fraction: Double, center: CGPoint, radius: CGFloat) -> CGPoint {
        let angle = Double(index) / Double(labels.count) * .pi * 2 - .pi / 2
        return CGPoint(x: center.x + cos(angle) * radius * fraction, y: center.y + sin(angle) * radius * fraction)
    }
    private func polygon(center: CGPoint, radius: CGFloat) -> Path {
        Path { path in
            for index in labels.indices {
                let point = position(index, fraction: 1, center: center, radius: radius)
                if index == 0 { path.move(to: point) } else { path.addLine(to: point) }
            }
            path.closeSubpath()
        }
    }
}

/// Half-pies and concentric radial bars retain their own geometry and readable legend.
private struct InteractivePolarChart: View {
    enum Mode { case semiPie, radial }
    let points: [InteractiveChartPoint]
    let mode: Mode
    let donut: Bool
    var body: some View {
        GeometryReader { geometry in
            Canvas { context, size in
                let radius = min(size.width / 2 - 10, mode == .semiPie ? size.height - 15 : size.height / 2 - 10)
                let center = CGPoint(x: size.width / 2, y: mode == .semiPie ? size.height - 6 : size.height / 2)
                let positive = points.filter { $0.value > 0 }
                let total = positive.reduce(0) { $0 + $1.value }, maximum = max(1, positive.map(\.value).max() ?? 1)
                var cursor = -Double.pi
                for (index, point) in points.enumerated() {
                    let start: Double, end: Double, inner: CGFloat, outer: CGFloat
                    if mode == .semiPie {
                        guard point.value > 0, total > 0 else { continue }
                        start = cursor; end = cursor + point.value / total * .pi; cursor = end
                        inner = donut ? radius * 0.58 : 0; outer = radius
                    } else {
                        start = -.pi / 2; end = start + max(0, point.value) / maximum * .pi * 2
                        let thickness = radius * 0.8 / CGFloat(max(1, points.count))
                        inner = radius * 0.2 + CGFloat(index) * thickness; outer = inner + thickness * 0.8
                        let track = arc(center: center, inner: inner, outer: outer, start: start, end: start + .pi * 2)
                        context.fill(track, with: .color(NanoTheme.canvas))
                    }
                    let path = arc(center: center, inner: inner, outer: outer, start: start, end: end)
                    context.fill(path, with: .color(InteractiveChartPalette.color(index)))
                }
            }.accessibilityHidden(true)
        }
    }
    private func arc(center: CGPoint, inner: CGFloat, outer: CGFloat, start: Double, end: Double) -> Path {
        Path { path in
            path.addArc(center: center, radius: outer, startAngle: .radians(start), endAngle: .radians(end), clockwise: false)
            if inner > 0 { path.addArc(center: center, radius: inner, startAngle: .radians(end), endAngle: .radians(start), clockwise: true) }
            else { path.addLine(to: center) }
            path.closeSubpath()
        }
    }
}
