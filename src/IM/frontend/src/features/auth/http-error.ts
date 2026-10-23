import { i18n } from "../../i18n";

/** Read business errors without exposing an intermediary's HTML error page. */
export async function readHttpError(response: Response) {
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  const structured = detail && typeof detail === "object" ? detail : body;
  const text = typeof detail === "string" ? detail : structured?.message;
  return {
    detail: typeof text === "string" && text.trim() ? text : i18n.t("httpErrors.responseUnavailable", { status: response.status }),
    code: typeof structured?.code === "string" ? structured.code : null,
    agentId: typeof structured?.agent_id === "string" ? structured.agent_id : null,
    blocks: Array.isArray(structured?.blocks) ? structured.blocks : [],
  };
}
