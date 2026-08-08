# IM gateway-relay Specification (delta for bugfix-518)

## No new relay wire contract

本 unit 的 distill prompt 在用户发送普通消息前由 IM 向同节点 Gateway 请求；成功后消息继续走既有普通
relay。该次创建的 direct conversation 固定其 target node；对于这个 non-empty server pin，普通 direct relay
忽略请求携带的 legacy `target_node_id` hint，使消息回到生成 prompt 的 Gateway。不新增 relay metadata、投递
回执或幂等语义。
