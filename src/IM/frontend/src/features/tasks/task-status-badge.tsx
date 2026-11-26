import * as Dialog from "@radix-ui/react-dialog";
import { useTranslation } from "../../i18n";
import { isKnownTaskStatus, type TaskStatus } from "./task-graphs-api";

export function useTaskStatusLabel() {
  const { t } = useTranslation();
  return (status: string): string =>
    isKnownTaskStatus(status) ? t(`tasks.status.${status}`) : t("tasks.status.unknown");
}

/** Canonical nine-word status pill. Never mixes wait reasons, timers, or assignees inside. */
export function TaskStatusBadge({ status }: { status: TaskStatus | string }) {
  const labelFor = useTaskStatusLabel();
  const known = isKnownTaskStatus(status);
  const modifier = known ? status : "unknown";
  return (
    <span className={`tasks-badge tasks-badge--${modifier}`} data-status={modifier}>
      {labelFor(status)}
    </span>
  );
}

export function TaskStatusHelpDialog({ open, onClose }: { open: boolean; onClose(): void }) {
  const { t } = useTranslation();
  return (
    <Dialog.Root open={open} onOpenChange={next => { if (!next) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="tasks-dialog-overlay tasks-help-overlay" />
        <Dialog.Content
          className="tasks-help-dialog"
          aria-describedby={undefined}
        >
          <div className="tasks-help-head">
            <div>
              <Dialog.Title className="tasks-help-title">{t("tasks.help.title")}</Dialog.Title>
              <p className="tasks-help-subtitle">{t("tasks.help.subtitle")}</p>
            </div>
            <Dialog.Close className="tasks-pill-btn">{t("tasks.help.close")}</Dialog.Close>
          </div>

          <div className="tasks-flow-board">
            <div className="tasks-flow-section-title">{t("tasks.help.trackTitle")}</div>
            <div className="tasks-flow-main-track">
              <div className="tasks-flow-node">
                <div><TaskStatusBadge status="proposed" /></div>
                <span className="tasks-flow-node-sub">{t("tasks.help.subProposed")}</span>
              </div>
              <span className="tasks-flow-edge">{t("tasks.help.edgeApprove")}</span>
              <div className="tasks-flow-node">
                <div><TaskStatusBadge status="todo" /></div>
                <span className="tasks-flow-node-sub">{t("tasks.help.subTodo")}</span>
              </div>
              <span className="tasks-flow-edge">{t("tasks.help.edgeStart")}</span>
              <div className="tasks-flow-node">
                <div><TaskStatusBadge status="doing" /></div>
                <span className="tasks-flow-node-sub">{t("tasks.help.subDoing")}</span>
              </div>
              <span className="tasks-flow-edge">{t("tasks.help.edgeSubmit")}</span>
              <div className="tasks-flow-node">
                <div><TaskStatusBadge status="in_review" /></div>
                <span className="tasks-flow-node-sub">{t("tasks.help.subReview")}</span>
              </div>
              <span className="tasks-flow-edge">{t("tasks.help.edgeConfirm")}</span>
              <div className="tasks-flow-node">
                <div><TaskStatusBadge status="done" /></div>
                <span className="tasks-flow-node-sub">{t("tasks.help.subDone")}</span>
              </div>
            </div>

            <div className="tasks-flow-branches">
              <div className="tasks-flow-branch-box">
                <div className="tasks-flow-section-title">{t("tasks.help.branchProposedTitle")}</div>
                <div className="tasks-flow-branch-row">
                  <TaskStatusBadge status="backlog" />
                  <span>{t("tasks.help.branchBacklogDesc")}</span>
                </div>
                <div className="tasks-flow-branch-row">
                  <TaskStatusBadge status="closed" />
                  <span>{t("tasks.help.branchClosedDesc")}</span>
                </div>
              </div>

              <div className="tasks-flow-branch-box">
                <div className="tasks-flow-section-title">{t("tasks.help.branchProgressTitle")}</div>
                <div className="tasks-flow-branch-row">
                  <TaskStatusBadge status="waiting" />
                  <span>{t("tasks.help.branchWaitingDesc")}</span>
                </div>
                <div className="tasks-flow-branch-row">
                  <TaskStatusBadge status="paused" />
                  <span>{t("tasks.help.branchPausedDesc")}</span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <div className="tasks-flow-section-title" style={{ marginBottom: 8 }}>{t("tasks.help.zonesTitle")}</div>
            <div className="tasks-zone-guide-grid">
              <div className="tasks-zone-guide-card">
                <div className="tasks-flow-section-title">{t("tasks.help.zone1Title")}</div>
                <div className="tasks-zone-badges">
                  <TaskStatusBadge status="proposed" />
                  <TaskStatusBadge status="in_review" />
                  <TaskStatusBadge status="backlog" />
                  <TaskStatusBadge status="paused" />
                </div>
                <p>{t("tasks.help.zone1Desc")}</p>
              </div>
              <div className="tasks-zone-guide-card">
                <div className="tasks-flow-section-title">{t("tasks.help.zone2Title")}</div>
                <div className="tasks-zone-badges">
                  <TaskStatusBadge status="doing" />
                  <TaskStatusBadge status="todo" />
                  <TaskStatusBadge status="waiting" />
                </div>
                <p>{t("tasks.help.zone2Desc")}</p>
              </div>
              <div className="tasks-zone-guide-card">
                <div className="tasks-flow-section-title">{t("tasks.help.zone3Title")}</div>
                <div className="tasks-zone-badges">
                  <TaskStatusBadge status="done" />
                  <TaskStatusBadge status="closed" />
                </div>
                <p>{t("tasks.help.zone3Desc")}</p>
              </div>
            </div>
            <p className="tasks-help-tip">{t("tasks.help.lensTip")}</p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
