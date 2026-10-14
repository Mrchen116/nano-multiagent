import { useQuery } from "@tanstack/react-query";

import { getCurrentLanguage, useTranslation } from "../../../i18n";
import { authFetchJson } from "../../auth/auth-fetch";

type Usage = {
  used_bytes: number;
  reserved_bytes: number;
  limit_bytes: number;
  full: boolean;
};
type Capacity = {
  service: Usage;
  owners: Array<
    Usage & {
      owner_id: string;
      username: string | null;
      display_name: string | null;
    }
  >;
};

function formatBytes(bytes: number, locale: string) {
  const unit =
    bytes >= 1024 ** 3 ? 3 : bytes >= 1024 ** 2 ? 2 : bytes >= 1024 ? 1 : 0;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(bytes / 1024 ** unit)} ${["B", "KiB", "MiB", "GiB"][unit]}`;
}

/** Show actual storage independently of editable presets, for an authenticated administrator. */
export function AttachmentCapacityPanel() {
  const { t } = useTranslation();
  const locale = getCurrentLanguage();
  const query = useQuery({
    queryKey: ["settings", "attachment-capacity"],
    retry: false,
    queryFn: () => authFetchJson<Capacity>("/im/v1/attachments/capacity"),
  });
  const usage = query.data?.service;
  const occupied = usage ? usage.used_bytes + usage.reserved_bytes : 0;
  const remaining = usage ? Math.max(0, usage.limit_bytes - occupied) : 0;
  const full = usage ? usage.full || occupied >= usage.limit_bytes : false;
  const percent = usage
    ? Math.min(100, (occupied / usage.limit_bytes) * 100)
    : 0;
  const size = (bytes: number) => formatBytes(bytes, locale);

  return (
    <section
      className="settings-card settings-capacity"
      aria-labelledby="capacity-title"
      aria-busy={query.isFetching}
    >
      <header className="settings-capacity-heading">
        <div>
          <h2 id="capacity-title">{t("company.capacity")}</h2>
          <p>{t("settings.capacity.subtitle")}</p>
        </div>
        <button
          type="button"
          className="im-btn im-btn-muted"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          {t("settings.capacity.refresh")}
        </button>
      </header>
      {query.isError ? (
        <div className="settings-state">
          <p role="alert">{t("settings.capacity.failed")}</p>
          <button
            type="button"
            className="im-btn im-btn-muted"
            onClick={() => void query.refetch()}
          >
            {t("common.retry")}
          </button>
        </div>
      ) : !usage ? (
        <p role="status" className="settings-muted">
          {t("common.loading")}
        </p>
      ) : (
        <>
          <div className="settings-capacity-total">
            <strong>{size(occupied)}</strong>
            <span>
              / {size(usage.limit_bytes)} {t("settings.capacity.occupied")}
            </span>
            <span className={`settings-badge ${full ? "warning" : ""}`}>
              {t(
                full ? "company.full" : "settings.capacity.available",
              )}
            </span>
          </div>
          <div
            className={`settings-capacity-meter ${full ? "full" : ""}`}
            role="meter"
            aria-label={t("settings.capacity.occupied")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-valuetext={`${size(occupied)} / ${size(usage.limit_bytes)}`}
          >
            <span style={{ width: `${percent}%` }} />
          </div>
          <dl className="settings-capacity-stats">
            <div>
              <dt>{t("company.used")}</dt>
              <dd>{size(usage.used_bytes)}</dd>
            </div>
            <div>
              <dt>{t("company.reserved")}</dt>
              <dd>{size(usage.reserved_bytes)}</dd>
            </div>
            <div>
              <dt>{t("settings.capacity.remaining")}</dt>
              <dd>{size(remaining)}</dd>
            </div>
          </dl>
          {full && (
            <p className="settings-notice warning" role="status">
              {t("settings.capacity.fullHint")}
            </p>
          )}
          <details className="settings-details">
            <summary>
              {t("settings.capacity.members", {
                count: query.data!.owners.length,
              })}
            </summary>
            <p className="settings-field-hint">
              {t("settings.capacity.visibility")}
            </p>
            {query.data!.owners.length === 0 ? (
              <p className="settings-muted">{t("settings.capacity.empty")}</p>
            ) : (
              query.data!.owners.map((owner) => (
                <div
                  className="settings-row settings-owner"
                  key={owner.owner_id}
                >
                  <div>
                    <h3>
                      {owner.display_name || owner.username || owner.owner_id}
                    </h3>
                    {owner.username && <p>@{owner.username}</p>}
                    <p>
                      {t("company.used")} {size(owner.used_bytes)} ·{" "}
                      {t("company.reserved")}{" "}
                      {size(owner.reserved_bytes)} ·{" "}
                      {t("company.limit")} {size(owner.limit_bytes)}
                    </p>
                  </div>
                  <span
                    className={`settings-badge ${owner.full ? "warning" : ""}`}
                  >
                    {t(
                      owner.full
                        ? "company.full"
                        : "settings.capacity.available",
                    )}
                  </span>
                </div>
              ))
            )}
          </details>
        </>
      )}
    </section>
  );
}
