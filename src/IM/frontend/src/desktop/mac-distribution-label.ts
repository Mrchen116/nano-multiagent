import type { DesktopInstall } from '../features/onboarding/onboarding-api';

export function macDistributionLabel(materials: DesktopInstall) {
  switch (materials.macos_distribution) {
    case 'developer-id-notarized': return 'crewdenDownload.macNotarized';
    case 'unsigned-test': return 'crewdenDownload.macTestPackage';
    default: return 'crewdenDownload.macUnnotarized';
  }
}
