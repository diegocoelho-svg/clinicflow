export interface Payment {
  id: number;
  clinic: number;
  charge: number;
  payment_reference: string;
  source_event: number;
  amount: string;
  currency: string;
  paid_at: string;
  reconciled_at: string;
}

export type EventStatus = 'RECEIVED' | 'RECONCILED' | 'DISCREPANCY';

export interface PaymentEvent {
  id: number;
  event_id: string;
  clinic: number;
  charge_reference: number;
  payment_reference: string;
  amount: string;
  currency: string;
  paid_at: string;
  status: EventStatus;
  discrepancy_code: string;
  payment: number | null;
  received_at: string;
  processed_at: string | null;
}

export interface PaymentWorkspaceData {
  payments: Payment[];
  events: PaymentEvent[];
}

export const eventStatusLabels: Record<EventStatus, string> = {
  RECEIVED: 'Aguardando conciliação',
  RECONCILED: 'Conciliado',
  DISCREPANCY: 'Divergência',
};

const discrepancyLabels: Record<string, string> = {
  CHARGE_NOT_FOUND: 'A cobrança informada não foi encontrada nesta clínica.',
  CHARGE_NOT_PENDING: 'A cobrança não estava aguardando pagamento.',
  CURRENCY_MISMATCH: 'A moeda recebida é diferente da moeda da cobrança.',
  AMOUNT_MISMATCH: 'O valor recebido é diferente do valor da cobrança.',
  PAYMENT_REFERENCE_CONFLICT: 'A referência de pagamento já foi usada em outra cobrança.',
};

export function discrepancyLabel(code: string): string {
  return Object.hasOwn(discrepancyLabels, code)
    ? discrepancyLabels[code]
    : 'O recebimento precisa ser conferido.';
}
