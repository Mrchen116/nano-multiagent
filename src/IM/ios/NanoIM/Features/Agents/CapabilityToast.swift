import SwiftUI
import Accessibility
import UIKit

struct CapabilityToastMessage: Equatable {
    var text: String
    var anchor: String
    var id = UUID()
}
private struct CapabilityAnchors: PreferenceKey {
    static let defaultValue: [String: Anchor<CGRect>] = [:]
    static func reduce(value: inout [String: Anchor<CGRect>], nextValue: () -> [String: Anchor<CGRect>]) { value.merge(nextValue(), uniquingKeysWith: { _, next in next }) }
}
extension View {
    func capabilityAnchor(_ id: String) -> some View { anchorPreference(key: CapabilityAnchors.self, value: .bounds) { [id: $0] } }
    func capabilityToast(_ message: Binding<CapabilityToastMessage?>) -> some View { modifier(CapabilityToastModifier(message: message)) }
}
private struct CapabilityToastModifier: ViewModifier {
    @Binding var message: CapabilityToastMessage?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var height: CGFloat = 48
    func body(content: Content) -> some View {
        content.overlayPreferenceValue(CapabilityAnchors.self) { anchors in
            GeometryReader { geometry in
                if let message {
                    let rect = anchors[message.anchor].map { geometry[$0] } ?? CGRect(x: 16, y: geometry.safeAreaInsets.top + 64, width: geometry.size.width - 32, height: 0)
                    let maxWidth = min(320, geometry.size.width - 32)
                    let textWidth = (message.text as NSString).boundingRect(with: CGSize(width: maxWidth - 24, height: .greatestFiniteMagnitude), options: [.usesLineFragmentOrigin, .usesFontLeading], attributes: [.font: UIFont.systemFont(ofSize: 13)], context: nil).width
                    let width = min(maxWidth, ceil(textWidth) + 24)
                    let top = rect.minY - height - 8 >= geometry.safeAreaInsets.top + 16 ? rect.minY - height - 8 : rect.maxY + 8
                    if rect.maxY >= 0 && top + height <= geometry.size.height - geometry.safeAreaInsets.bottom - 16 {
                        Text(message.text)
                            .font(.system(size: 13)).foregroundStyle(.white).fixedSize(horizontal: false, vertical: true)
                            .padding(.vertical, 8).padding(.horizontal, 12).frame(width: width, alignment: .leading)
                            .background(Color(red: 0.188, green: 0.212, blue: 0.220), in: RoundedRectangle(cornerRadius: 7))
                            .background(GeometryReader { proxy in Color.clear.onAppear { height = proxy.size.height }.onChange(of: proxy.size.height) { _, value in height = value } })
                            .offset(x: max(16, min(rect.minX, geometry.size.width - width - 16)), y: top)
                            .allowsHitTesting(false).transition(.opacity)
                            .accessibilityLabel(message.text)
                    }
                }
            }.allowsHitTesting(false)
        }
        .onScrollGeometryChange(for: CGFloat.self) { $0.contentOffset.y } action: { old, next in if old != next { message = nil } }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.15), value: message)
        .task(id: message?.id) {
            guard let current = message else { return }
            var announcement = AttributedString(current.text)
            announcement.accessibilitySpeechAnnouncementPriority = .low
            AccessibilityNotification.Announcement(announcement).post()
            do { try await Task.sleep(for: .seconds(2)); withAnimation { message = nil } } catch { }
        }
    }
}
