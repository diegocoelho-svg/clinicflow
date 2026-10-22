import { request, type RequestAuth } from '../../shared/api/http';
import { withApiErrors } from '../../shared/api/errors';
import type { Charge } from './types';

const readMessages = {
  403: 'Você não tem acesso às cobranças desta clínica.',
  404: 'Esta cobrança ou clínica não está disponível. Confira a clínica selecionada.',
};

export const chargeApi = {
  list: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Charge[]>(`clinics/${clinic}/charges/`, { ...auth, signal }), {
      messages: readMessages,
    }),
  get: (clinic: number, id: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Charge>(`clinics/${clinic}/charges/${id}/`, { ...auth, signal }), {
      messages: readMessages,
    }),
  issue: (clinic: number, encounter: number, key: string, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(
      request<Charge>(`clinics/${clinic}/encounters/${encounter}/charges/`, {
        ...auth,
        signal,
        method: 'POST',
        body: {},
        idempotencyKey: key,
      }),
      {
        messages: {
          ...readMessages,
          400: 'Não foi possível emitir. Confira se o atendimento tem itens e um total válido.',
          409: 'O atendimento já possui uma cobrança ou a operação está em conflito. Confira o histórico atualizado.',
        },
      },
    ),
  cancel: (clinic: number, id: number, reason: string, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(
      request<Charge>(`clinics/${clinic}/charges/${id}/cancel/`, {
        ...auth,
        signal,
        method: 'POST',
        body: { reason: reason.trim() },
      }),
      {
        messages: {
          0: 'Não foi possível confirmar o cancelamento. Atualize a cobrança ou tente confirmar novamente.',
          403: 'Somente proprietários desta clínica podem cancelar cobranças.',
          404: readMessages[404],
          409: 'Esta cobrança não pode ser cancelada no estado atual. Atualize para conferir a situação.',
        },
        fieldMessages: {
          reason: 'Informe um motivo com até 1.000 caracteres, sem deixar em branco.',
        },
      },
    ),
};
