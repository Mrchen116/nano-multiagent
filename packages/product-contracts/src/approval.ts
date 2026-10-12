/** Node-resolved automatic approval configuration; never model-supplied. */
export interface ApprovalConfiguration {
  enabled: boolean;
  rules: 'nano' | 'dsh';
  dangerouslySkipPermissions: boolean;
  alwaysAllowTools: string[];
  denyLimit: number;
  totalDenyLimit: number;
  askTimeoutSec: number;
  unattendedFallback: 'allow' | 'deny';
  allow: string[];
  softDeny: string[];
  hardDeny: string[];
  environment: string[];
  globalRoot: string;
  reviewer?: { provider: string; model: string };
}

export const approvalDefaults: Omit<ApprovalConfiguration, 'globalRoot'> = {
  enabled: true, rules: 'nano', dangerouslySkipPermissions: false, alwaysAllowTools: [],
  denyLimit: 3, totalDenyLimit: 20, askTimeoutSec: 600, unattendedFallback: 'deny',
  allow: [], softDeny: [], hardDeny: [], environment: [],
};
