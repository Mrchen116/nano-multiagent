import SwiftUI

/// Uses the same silhouettes, palette and immutable identity seed as the Web portrait.
struct AssistantPortrait: View {
    let personal: Bool
    let seed: String
    let selected: Int?
    var size: CGFloat = 44

    static func variant(for id: String) -> Int {
        var hash: UInt32 = 2166136261
        for scalar in id.unicodeScalars {
            let unit = scalar.value <= 0xffff ? scalar.value : 0xd800 + ((scalar.value - 0x10000) >> 10)
            hash = (hash ^ unit) &* 16777619
        }
        return Int(hash % 24)
    }

    private let colors: [(UInt32, UInt32)] = [
        (0xb19aef, 0x43335e), (0x8bcbb0, 0x285345), (0x8cbce9, 0x2c4b6c),
        (0xf0ab89, 0x704735), (0xeaa5c2, 0x693c56), (0xeac76a, 0x655126)
    ]
    private func color(_ value: UInt32) -> Color {
        Color(red: Double(value >> 16) / 255, green: Double((value >> 8) & 255) / 255, blue: Double(value & 255) / 255)
    }
    var body: some View {
        let fallback = seed.isEmpty ? 0 : Self.variant(for: seed)
        let variant = selected.flatMap { (0..<24).contains($0) ? $0 : nil } ?? fallback
        let style = variant / 6
        let (fill, ink) = colors[variant % 6]
        ZStack {
            Image("portrait-\(personal ? "personal" : "agent")-\(style)").resizable().foregroundStyle(color(fill))
            Canvas { ctx, bounds in
                ctx.scaleBy(x: bounds.width / 80, y: bounds.height / 80)
                for x in [31.0, 49.0] {
                    let rx = personal ? 7.0 : 6.5, ry = personal ? 9.0 : 8.0
                    ctx.fill(Path(ellipseIn: CGRect(x: x-rx, y: 37-ry, width: rx*2, height: ry*2)), with: .color(.white))
                    let pupil = x + (style.isMultiple(of: 2) ? -1 : 2)
                    ctx.fill(Path(ellipseIn: CGRect(x: pupil-2.8, y: 33.8, width: 5.6, height: 8.4)), with: .color(color(ink)))
                }
                if personal {
                    var mouth = Path()
                    mouth.move(to: CGPoint(x: 36, y: 52))
                    mouth.addQuadCurve(to: CGPoint(x: 46, y: 51), control: CGPoint(x: 41, y: 56))
                    ctx.stroke(mouth, with: .color(color(ink)), style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                }
            }.rotationEffect(.degrees([-7, 8, -4, 5][style]))
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}

struct PortraitPicker: View {
    let personal: Bool
    @Binding var variant: Int

    var body: some View {
        let colors = [L("紫色", "Purple"), L("绿色", "Green"), L("蓝色", "Blue"), L("橙色", "Orange"), L("粉色", "Pink"), L("黄色", "Yellow")]
        let shapes = personal
            ? [L("圆形", "Circle"), L("椭圆形", "Oval"), L("花朵", "Flower"), L("水滴", "Droplet")]
            : [L("拱形", "Arch"), L("菱形", "Diamond"), L("方形", "Square"), L("四角星", "Four-point star")]
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 2), count: 6), spacing: 2) {
            ForEach(0..<24) { index in
                Button { variant = index } label: {
                    AssistantPortrait(personal: personal, seed: "", selected: index, size: 38)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(index == variant ? NanoTheme.softAccent : Color.clear, in: RoundedRectangle(cornerRadius: 12))
                        .overlay(alignment: .bottomTrailing) {
                            if index == variant {
                                Image(systemName: "checkmark.circle.fill").font(.caption.bold())
                                    .foregroundStyle(.white, NanoTheme.accent).padding(2)
                            }
                        }
                        .contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityLabel(L("形象 \(index + 1)", "Appearance \(index + 1)"))
                    .accessibilityValue("\(colors[index % 6]) \(shapes[index / 6])")
                    .accessibilityAddTraits(index == variant ? .isSelected : [])
            }
        }
    }
}
