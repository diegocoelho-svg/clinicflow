import { statusLabel } from '../types';

export function ChargeStatusBadge({ status }: { status: string }) {
  const known = ['PENDING', 'NO_PAYMENT_REQUIRED', 'CANCELLED', 'PAID'].includes(status);
  return (
    <span className={`charge-status status-${known ? status.toLowerCase() : 'unknown'}`}>
      {statusLabel(status)}
    </span>
  );
}
