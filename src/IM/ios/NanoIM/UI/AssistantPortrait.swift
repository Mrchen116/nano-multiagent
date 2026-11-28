import SwiftUI

/// Uses the same silhouettes, palette and immutable identity seed as the Web portrait.
private struct AssistantPortrait: View {
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

    private struct Colors: Decodable { let body: String; let ink: String }
    private static let colors = try! JSONDecoder().decode([Colors].self, from: NSDataAsset(name: "portrait-palette")!.data)
    private func color(_ value: UInt32) -> Color {
        Color(red: Double(value >> 16) / 255, green: Double((value >> 8) & 255) / 255, blue: Double(value & 255) / 255)
    }
    var body: some View {
        let fallback = seed.isEmpty ? 0 : Self.variant(for: seed)
        let variant = selected.flatMap { (0..<24).contains($0) ? $0 : nil } ?? fallback
        let style = variant / 6
        let colors = Self.colors[variant % 6]
        let fill = UInt32(colors.body.dropFirst(), radix: 16)!
        let ink = UInt32(colors.ink.dropFirst(), radix: 16)!
        ZStack {
            Image("portrait-\(personal ? "personal" : "agent")-\(style)").resizable().foregroundStyle(color(fill))
            Canvas { ctx, bounds in
                ctx.scaleBy(x: bounds.width / 80, y: bounds.height / 80)
                for x in [31.0, 49.0] {
                    let rx = personal ? 7.0 : 6.5, ry = personal ? 9.0 : 8.0
                    ctx.fill(Path(ellipseIn: CGRect(x: x-rx, y: 37-ry, width: rx*2, height: ry*2)), with: .color(color(0xfffdf8)))
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

/// A preview describes an unassigned preset. Persisted identities use AvatarView.
struct PortraitPreview: View {
    var personal = true
    var variant = 0
    var size: CGFloat

    var body: some View { AssistantPortrait(personal: personal, seed: "", selected: variant, size: size) }
    static func defaultVariant(for id: String) -> Int { AssistantPortrait.variant(for: id) }
}

struct AvatarView: View {
    let id: AvatarIdentity
    var size: CGFloat = 44
    var online = false
    @Environment(\.avatarDirectory) private var directory
    @Environment(\.avatarImageStore) private var imageStore

    init(id: AvatarIdentity, size: CGFloat = 44, online: Bool = false) {
        self.id = id; self.size = size; self.online = online
    }

    struct Swatch: Decodable {
        let background: String
        let foreground: String
    }
    // The Web component imports the same JSON file packaged in this data asset.
    static let palette = try! JSONDecoder().decode([Swatch].self, from: NSDataAsset(name:"avatar-palette")!.data)
    static func paletteIndex(for seed: String) -> Int {
        var hash: Int64 = 0
        for unit in seed.utf16 { hash = Int64(Int32(truncatingIfNeeded:hash) &<< 5) - hash + Int64(unit) }
        return Int(abs(hash) % Int64(palette.count))
    }

    private static func initials(for name: String) -> String {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return "AG" }
        let initials = String(decoding: trimmed.utf16.prefix(2), as: UTF16.self).uppercased()
        return String(decoding: initials.utf16.prefix(2), as: UTF16.self)
    }

    private func color(_ hex: String) -> Color {
        let rgb = UInt32(hex.dropFirst(), radix:16)!
        return Color(red:Double(rgb >> 16) / 255, green:Double(rgb >> 8 & 255) / 255, blue:Double(rgb & 255) / 255)
    }
    var body: some View {
        let face = directory.resolve(id)
        let swatch = Self.palette[Self.paletteIndex(for:face.paletteSeed)]
        Group {
            switch face {
            case let .agent(seed, personal, variant):
                AssistantPortrait(personal:personal, seed:seed, selected:variant, size:size)
            case .group:
                Image("group-avatar").resizable().scaledToFit().frame(width:size * 0.525)
                    .frame(width:size, height:size).background(color(swatch.background), in: RoundedRectangle(cornerRadius:size * 0.275))
            case let .person(name, avatar):
                if let avatar, let uiImage = imageStore?.image(for: avatar) {
                    Image(uiImage: uiImage)
                        .resizable()
                        .scaledToFill()
                        .frame(width:size, height:size)
                        .clipShape(Circle())
                } else {
                    Text(Self.initials(for: name))
                        .font(.system(size:size * 0.35, weight:.semibold)).frame(width:size, height:size)
                        .background(color(swatch.background), in:Circle())
                        .task(id: avatar) {
                            if let avatar { imageStore?.loadIfNeeded(avatar) }
                        }
                }
            }
        }.foregroundStyle(color(swatch.foreground)).overlay(alignment:.bottomTrailing) {
            if online { Circle().fill(Color.green).frame(width:size * 0.23, height:size * 0.23)
                .overlay(Circle().stroke(NanoTheme.surface, lineWidth:2)) }
        }.accessibilityHidden(true)
    }
}
