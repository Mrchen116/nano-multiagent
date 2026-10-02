import { Link } from "react-router-dom";
import { useTranslation } from "../../i18n";
import { taskGraphUrl, useTaskActivity } from "./task-graphs-api";
import "./task-graphs.css";

export function GroupTaskPanel({ conversationId, onClose }: { conversationId: string; onClose(): void }) {
  const { t } = useTranslation();
  const query = useTaskActivity(conversationId);
  return <aside className="group-task-panel" aria-label={t("shell.tabs.tasks")}>
    <header><h2>{t("shell.tabs.tasks")}</h2><button aria-label={t("tasks.close")} onClick={onClose}>×</button></header>
    {query.isPending ? <p role="status">{t("tasks.loading")}</p>
      : query.isError ? <div role="alert">{t("tasks.readFailed")}<button onClick={() => void query.refetch()}>{t("tasks.refresh")}</button></div>
        : !query.data ? <p>{t("tasks.unavailable")}</p>
          : query.data.items.length === 0 ? <p>{t("tasks.noGraphsHint")}</p>
            : <ul>{query.data.items.map(item => <li key={`${item.graph_id}:${item.node_id}`}>
              <Link to={`${taskGraphUrl(item.graph_id, item.scope_id ?? item.node_id, item.node_id)}&return_chat=${encodeURIComponent(conversationId)}`}>
                <strong>{item.title}</strong><span>{item.root_title}</span>
                <small>{t(`tasks.status.${item.status}`)} · {new Date(item.updated_at).toLocaleString()}</small>
              </Link>
            </li>)}</ul>}
  </aside>;
}
