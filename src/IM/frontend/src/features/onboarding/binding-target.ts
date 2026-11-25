import { desktopScopedKey } from '../../desktop/desktop-context';

// The system browser may finish binding in a second tab. Keep its account-scoped
// result separate from the editable draft so a typing tab cannot overwrite it.
export const bindingTargetKey = (userId: string) => desktopScopedKey(`nano-onboarding-binding:${userId}`);
