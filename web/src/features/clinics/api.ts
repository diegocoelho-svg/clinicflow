import { request, type RequestAuth } from '../../shared/api/http';
import { withApiErrors } from '../../shared/api/errors';
import { clinicDetailMessages, clinicFieldMessages, clinicServiceMessages } from './errors';
import type { Clinic } from './types';

export const clinicApi = {
  list: (auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Clinic[]>('clinics/', { ...auth, signal }), {
      messages: clinicServiceMessages,
    }),
  get: (id: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Clinic>(`clinics/${id}/`, { ...auth, signal }), {
      messages: clinicDetailMessages,
    }),
  create: (name: string, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(
      request<Clinic>('clinics/', { ...auth, method: 'POST', body: { name: name.trim() }, signal }),
      {
        messages: clinicServiceMessages,
        fieldMessages: clinicFieldMessages,
      },
    ),
};
