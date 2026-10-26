import { withApiErrors } from '../../shared/api/errors';
import { request, type RequestAuth } from '../../shared/api/http';
import type { Payment, PaymentEvent } from './types';

const messages = {
  403: 'Você não tem acesso aos pagamentos desta clínica.',
  404: 'Esta clínica ou recebimento não está disponível. Confira a clínica selecionada.',
};

export const paymentApi = {
  list: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Payment[]>(`clinics/${clinic}/payments/`, { ...auth, signal }), {
      messages,
    }),
  events: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(
      request<PaymentEvent[]>(`clinics/${clinic}/payment-events/`, { ...auth, signal }),
      { messages },
    ),
};
