import { request, type RequestAuth } from '../../shared/api/http';
import { withApiErrors } from '../../shared/api/errors';

export interface Patient {
  id: number;
  clinic: number;
  full_name: string;
  birth_date: string;
  email: string;
  phone: string;
}
export type PatientInput = Pick<Patient, 'full_name' | 'birth_date' | 'email' | 'phone'>;
const errors = {
  messages: {
    403: 'Você não tem permissão para alterar pacientes nesta clínica.',
    404: 'Este paciente ou clínica não está disponível.',
  },
  fieldMessages: {
    full_name: 'Informe o nome completo, com até 255 caracteres.',
    birth_date: 'Informe uma data de nascimento válida, sem ser futura.',
    email: 'Informe um e-mail válido.',
    phone: 'Informe um telefone com até 30 caracteres.',
  },
};
export const patientApi = {
  list: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(request<Patient[]>(`clinics/${clinic}/patients/`, { ...auth, signal }), errors),
  save: (
    clinic: number,
    patient: number | undefined,
    data: PatientInput,
    auth: RequestAuth,
    signal: AbortSignal,
  ) =>
    withApiErrors(
      request<Patient>(`clinics/${clinic}/patients/${patient ? patient + '/' : ''}`, {
        ...auth,
        signal,
        method: patient ? 'PATCH' : 'POST',
        body: data,
      }),
      errors,
    ),
};
