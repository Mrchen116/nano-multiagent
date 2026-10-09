import SwiftUI

func settingsError(_ error: Error) -> String {
    guard let api = error as? APIError else {
        return L("暂时无法连接服务，请检查网络后重试。", "Unable to reach the service. Check your connection and retry.")
    }
    switch api.detail {
    case "cannot suspend the last active administrator":
        return L("不能停用最后一位有效管理员。请先保留另一位有效管理员。", "The last active administrator cannot be suspended. Another active administrator is required.")
    case "binding operation invalid or expired":
        return L("绑定链接无效、已取消或已过期，请在设备上重新发起绑定。", "This binding link is invalid, cancelled or expired. Start binding again on the device.")
    case "receiving account already fixed":
        return L("此绑定已由其他账号接受，请使用对应账号或重新发起绑定。", "Another account has accepted this binding. Use that account or start a new binding.")
    case "binding cannot be cancelled":
        return L("无法取消此绑定，请刷新检查是否已经完成或过期。", "This binding cannot be cancelled. Refresh to check whether it has completed or expired.")
    case "default_entry_node_id not owned by user":
        return L("默认入口设备必须属于当前账号。请重新选择。", "The default device must belong to your account. Select it again.")
    default: break
    }
    switch api.status {
    case 401: return L("登录已失效，请重新登录。", "Your session has expired. Sign in again.")
    case 403: return L("当前账号无权执行此操作，或公司资格已改变。请刷新账号状态。", "Your account cannot perform this action, or membership has changed. Refresh your account status.")
    case 404: return L("此内容不存在或已无权访问，请刷新。", "This item no longer exists or is no longer accessible. Refresh and try again.")
    case 429: return L("请求过于频繁，请稍后重试。", "Too many requests. Wait before retrying.")
    case 400, 409, 422:
        return L("未能保存，请检查输入并重试：", "Unable to save. Check your input and retry: ") + api.detail
    default: return L("服务暂时不可用，请稍后重试。", "The service is temporarily unavailable. Please retry.")
    }
}

func settingsStatus(_ status: String) -> String {
    switch status {
    case "online": return L("在线", "Online")
    case "offline": return L("离线", "Offline")
    case "degraded": return L("受限", "Degraded")
    case "pending": return L("待批准", "Pending")
    case "active": return L("有效成员", "Active")
    case "suspended": return L("已停用", "Suspended")
    default: return status
    }
}

struct SettingsFeedback: View {
    var error: String?
    var success: String? = nil
    var body: some View {
        if let error { Section { ErrorNotice(message: error) } }
        if let success { Section { Label(success, systemImage: "checkmark.circle").foregroundStyle(.green) } }
    }
}

struct SettingsLoading: View {
    var retry: () -> Void
    var error: String?
    var body: some View {
        Section {
            if let error {
                ErrorNotice(message: error)
                Button(L("重试", "Retry"), action: retry)
            } else { ProgressView(L("正在加载", "Loading")) }
        }
    }
}
