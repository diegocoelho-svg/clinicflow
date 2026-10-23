import { withApiErrors } from '../../shared/api/errors';
import { request, type RequestAuth } from '../../shared/api/http';
import type { Encounter, EncounterItem, PatientSummary, Procedure } from './types';

const readMessages = {
  403: 'Você não tem acesso aos atendimentos desta clínica.',
  404: 'Este atendimento ou clínica não está disponível. Confira a clínica selecionada.',
};
const itemErrors = {
  messages: {
    ...readMessages,
    409: 'Os itens estão bloqueados por uma cobrança. Atualize o atendimento para conferir a situação.',
  },
  fieldMessages: {
    quantity: 'Use uma quantidade inteira entre 1 e 2.147.483.647.',
    procedure: 'Escolha um procedimento ativo desta clínica que ainda não esteja no atendimento.',
  },
};

export const encounterApi = {
  create: (
    clinic: number,
    data: Pick<Encounter, 'patient' | 'performed_at' | 'description'>,
    auth: RequestAuth,
    signal: AbortSignal,
  ) =>
    withApiErrors(
      request<Encounter>(`clinics/${clinic}/encounters/`, {
        ...auth,
        signal,
        method: 'POST',
        body: data,
      }),
      {
        messages: readMessages,
        fieldMessages: {
          patient: 'Escolha um paciente desta clínica.',
          performed_at: 'Informe quando o atendimento foi realizado, sem usar uma data futura.',
          description: 'Descreva o atendimento realizado.',
        },
      },
    ),
  list: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Encounter[]>(`clinics/${clinic}/encounters/`, { ...auth, signal }), {
      messages: readMessages,
    }),
  get: (clinic: number, id: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Encounter>(`clinics/${clinic}/encounters/${id}/`, { ...auth, signal }), {
      messages: readMessages,
    }),
  patients: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<PatientSummary[]>(`clinics/${clinic}/patients/`, { ...auth, signal }), {
      messages: readMessages,
    }),
  items: (clinic: number, encounter: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(
      request<EncounterItem[]>(`clinics/${clinic}/encounters/${encounter}/items/`, {
        ...auth,
        signal,
      }),
      { messages: readMessages },
    ),
  procedures: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Procedure[]>(`clinics/${clinic}/procedures/`, { ...auth, signal }), {
      messages: readMessages,
    }),
  addItem: (
    clinic: number,
    encounter: number,
    procedure: number,
    quantity: number,
    auth: RequestAuth,
    signal: AbortSignal,
  ) =>
    withApiErrors(
      request<EncounterItem>(`clinics/${clinic}/encounters/${encounter}/items/`, {
        ...auth,
        signal,
        method: 'POST',
        body: { procedure, quantity },
      }),
      itemErrors,
    ),
  updateItem: (
    clinic: number,
    encounter: number,
    item: number,
    quantity: number,
    auth: RequestAuth,
    signal: AbortSignal,
  ) =>
    withApiErrors(
      request<EncounterItem>(`clinics/${clinic}/encounters/${encounter}/items/${item}/`, {
        ...auth,
        signal,
        method: 'PATCH',
        body: { quantity },
      }),
      itemErrors,
    ),
  removeItem: (
    clinic: number,
    encounter: number,
    item: number,
    auth: RequestAuth,
    signal: AbortSignal,
  ) =>
    withApiErrors(
      request<void>(`clinics/${clinic}/encounters/${encounter}/items/${item}/`, {
        ...auth,
        signal,
        method: 'DELETE',
      }),
      itemErrors,
    ),
};
