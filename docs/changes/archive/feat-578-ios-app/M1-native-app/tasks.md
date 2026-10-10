# M1 implementation

先实现并构建原生 App，完成模拟器真实入口验证，有可安装版本后再安排真机与 Mini。Gate 2 R2 已通过。最终 S1-S30 不减。

## Ownership

- Root: Xcode project/build, shared client/session/stream, authentication, Chat/Tasks, integration and tests.
- First implementation feature slices: Agents management/Work; My account/nodes/binding/company/policies. Shared worktree, disjoint feature directories, no independent commits.
- Root owns all follow-up fixes and integration. Independent product and static gates follow the completed implementation.

## Shared Swift interface (root-owned)

- Swift 5 language mode, iOS 26+, SwiftUI. Main App target includes every file in `NanoIM` using a synchronized group. DTOs use snake_case wire names and conform to Codable/Sendable.
- `actor IMClient`: `get<T: Decodable & Sendable>(_ path: String, query: [URLQueryItem] = []) async throws -> T`; `send<T: Decodable & Sendable, B: Encodable & Sendable>(_ path: String, method: String = "POST", body: B) async throws -> T`; `delete<T: Decodable & Sendable>(_ path: String, query: [URLQueryItem] = []) async throws -> T`. Paths include `/im/v1`. All share Session auth and bounded refresh; no feature handles tokens.
- `APIError: Error, LocalizedError, Sendable { status: Int; detail: String; retryAfter: TimeInterval }`.
- `EmptyResponse: Codable, Sendable` accepts empty/204 responses. `JSONValue: Codable, Sendable, Equatable` for truly arbitrary tool/detail values, with `.object`, `.array`, `.string`, `.number`, `.bool`, `.null`, `prettyPrinted` and read accessors. Core domain DTOs remain explicit.
- `AuthUser: Codable, Sendable, Equatable`: `id`, `username`, `display_name`, `owner_id`, `locale`, `membership_status` (String), `is_company_admin` (Bool), `default_entry_node_id: String?`, `owned_node_ids: [String]`, `created_at: String`.
- `Contact: Codable, Identifiable, Sendable, Hashable`: `user_id`, `kind`, `display_name` required strings; `agent_id`, `owner_id`, `owner_display_name`, `node_name`, `status`, `work_mode` optional strings. `id` is user_id. `ActorRef: Codable, Sendable, Hashable`: `type`, `id`, optional display_name/user_id/is_stale.
- `L(_ zh: String, _ en: String) -> String` returns current `UserDefaults` `nano.locale` language (default zh). Use both languages for all user-facing labels. App model updates locale from login/profile.
- `ErrorNotice(message: String)` and `JSONDetailView(value: JSONValue)` native reusable UI; arbitrary JSON only in diagnostics/process detail, not a replacement for native management forms.
- Root route callbacks are @MainActor closures. `AgentsView(client: IMClient, user: AuthUser, onOpenChat: @escaping (String) -> Void)` entry. `AgentCreateView(client: IMClient, nodeID: String? = nil)` usable from Nodes. `MeView(client: IMClient, user: AuthUser, onAccountUpdated: @escaping () -> Void, onSignOut: @escaping () -> Void)` entry. Each feature supplies content; root owns TabView/NavigationStack, destination pages hide tab bar.

## Test strategy

No preexisting iOS suite (`src/IM/ios` absent). Keep existing Python/Web contracts unchanged. Add lowest-layer Swift tests for token refresh/session replacement, request ownership, protected-resource origin, idempotent timeline recovery and task layout. Run real native UI against own isolated IM/Gateway; do not count mock/static checks as product acceptance. Document screenshots/runtime evidence without committing caches or secrets.
