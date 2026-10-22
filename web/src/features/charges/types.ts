export type ChargeStatus = 'PENDING' | 'NO_PAYMENT_REQUIRED' | 'CANCELLED' | 'PAID';

export interface ChargeItem {
  id: number;
  procedure: number;
  procedure_name: string;
  quantity: number;
  unit_price: string;
  total: string;
}

export interface Charge {
  id: number;
  clinic: number;
  encounter: number;
  amount: string;
  currency: 'BRL';
  status: ChargeStatus;
  idempotency_key: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  cancelled_at: string | null;
  cancelled_by: number | null;
  cancellation_reason: string | null;
  items: ChargeItem[];
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    PENDING: 'Aguardando pagamento',
    NO_PAYMENT_REQUIRED: 'Sem pagamento necessário',
    CANCELLED: 'Cancelada',
    PAID: 'Paga',
  };
  return Object.hasOwn(labels, status) ? labels[status] : 'Situação indisponível';
}
