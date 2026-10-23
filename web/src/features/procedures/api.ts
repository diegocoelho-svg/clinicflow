import { request, type RequestAuth } from '../../shared/api/http';
import { withApiErrors } from '../../shared/api/errors';
import type { Procedure } from '../encounters/types';

export type ProcedureInput = Pick<Procedure, 'name' | 'unit_price' | 'is_active'>;
const errors = {
  messages: {
    403: 'Somente proprietários da clínica podem cadastrar ou alterar procedimentos e preços.',
    404: 'Este procedimento ou clínica não está disponível.',
  },
  fieldMessages: {
    name: 'Informe um nome com até 255 caracteres.',
    unit_price: 'Use um valor em reais entre 0,00 e 9.999.999.999,99.',
    is_active: 'Informe se o procedimento está ativo.',
  },
};
export const procedureApi = {
  list: (clinic: number, auth: RequestAuth, signal: AbortSignal) =>
    withApiErrors(
      request<Procedure[]>(`clinics/${clinic}/procedures/`, { ...auth, signal }),
      errors,
    ),
  save: (
    clinic: number,
    procedure: number | undefined,
    data: ProcedureInput,
    auth: RequestAuth,
    signal: AbortSignal,
  ) =>
    withApiErrors(
      request<Procedure>(`clinics/${clinic}/procedures/${procedure ? procedure + '/' : ''}`, {
        ...auth,
        signal,
        method: procedure ? 'PATCH' : 'POST',
        body: data,
      }),
      errors,
    ),
};

export function parseUnitPrice(value: string): string | null {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(normalized)) return null;
  const [whole, fraction = ''] = normalized.split('.');
  return `${BigInt(whole)}.${fraction.padEnd(2, '0')}`;
}
