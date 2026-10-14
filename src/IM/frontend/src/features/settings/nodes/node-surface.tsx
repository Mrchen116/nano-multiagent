import * as Dialog from '@radix-ui/react-dialog';
import type { ReactNode, RefObject } from 'react';
import { useTranslation } from '../../../i18n';

const paths = {
  computer: <><rect x="4" y="4" width="16" height="12" rx="1.5"/><path d="M2 19h20M9 16v3m6-3v3"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  back: <path d="m14 6-6 6 6 6"/>,
  next: <path d="m9 6 6 6-6 6"/>,
  update: <path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5m-4 6a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  leaf: <path d="M5 17C1 9 9 4 20 4c0 11-5 17-12 14M4 21 15 10"/>,
  copy: <><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/></>
};

/** Render the computer feature's consistent, decorative line icons. */
export function NodeIcon({ name, spin = false }: { name: keyof typeof paths; spin?: boolean }) {
  return <svg className={spin ? 'node-icon node-spin' : 'node-icon'} viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

/** Keep details modal and keyboard focus consistent on desktop and mobile. */
export function NodeDrawer({ title, children, onClose, returnFocus }: {
  title: string; children: ReactNode; onClose(): void; returnFocus: RefObject<HTMLElement | null>;
}) {
  const { t } = useTranslation();
  return <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}>
    <Dialog.Portal><Dialog.Overlay className="node-drawer-overlay"/>
      <Dialog.Content className="node-drawer" aria-describedby={undefined} onCloseAutoFocus={event => {
        event.preventDefault(); returnFocus.current?.focus();
      }}>
        <header className="node-drawer-head"><Dialog.Title>{title}</Dialog.Title>
          <Dialog.Close className="node-icon-button" aria-label={t('computers.backToList')}>
            <span className="node-mobile-back"><NodeIcon name="back"/></span><span className="node-desktop-close"><NodeIcon name="close"/></span>
          </Dialog.Close>
        </header><div className="node-drawer-body">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
