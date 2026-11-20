// The system browser may finish binding in a second tab. Keep its account-scoped
// result separate from the editable draft so a typing tab cannot overwrite it.
export const bindingTargetKey = (userId: string) => `nano-onboarding-binding:${userId}`;
