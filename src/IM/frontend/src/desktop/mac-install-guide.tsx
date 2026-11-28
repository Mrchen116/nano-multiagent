import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { DesktopInstall } from '../features/onboarding/onboarding-api';
import { useTranslation } from '../i18n';

function macDistributionLabel(materials: DesktopInstall) {
  switch (materials.macos_distribution) {
    case 'developer-id-notarized': return 'crewdenDownload.macNotarized';
    case 'unsigned-test': return 'crewdenDownload.macTestPackage';
    default: return 'crewdenDownload.macUnnotarized';
  }
}

export function MacInstallGuide({ materials }: { materials: DesktopInstall }) {
  const { t } = useTranslation();
  return (
    <Dialog.Root>
      <Dialog.Trigger type="button" className="mac-install-guide-link">
        {t('crewdenDownload.installGuide')}
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="crew-dialog-overlay" />
        <Dialog.Content className="crew-dialog mac-install-guide">
          <Dialog.Title>{t('crewdenDownload.macInstallTitle')}</Dialog.Title>
          <Dialog.Description>{t('crewdenDownload.macInstallSteps')}</Dialog.Description>
          <h3>{t(macDistributionLabel(materials))}</h3>
          {materials.macos_distribution !== 'developer-id-notarized' && (
            <p>{t('crewdenDownload.macFirstOpen')}</p>
          )}
          <Dialog.Close className="crew-dialog-close" aria-label={t('crewdenHome.close')}><X /></Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
