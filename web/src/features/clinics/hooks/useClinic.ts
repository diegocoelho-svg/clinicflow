import { useEffect, useState } from 'react';
import { ApiError, errorMessage } from '../../../shared/api/errors';
import { clinicApi } from '../api';
import { useClinicDirectory } from '../context';
import type { Clinic } from '../types';
import { useClinicAccess } from './useClinicAccess';

type ClinicState =
  | { id: string; status: 'loading' }
  | { id: string; status: 'success'; clinic: Clinic }
  | { id: string; status: 'error'; message: string };

export function useClinic(id: string) {
  const access = useClinicAccess();
  const { removeClinic } = useClinicDirectory();
  const [state, setState] = useState<ClinicState>({ id, status: 'loading' });
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const number = Number(id);
    if (!/^\d+$/.test(id) || !Number.isSafeInteger(number) || number <= 0) {
      setState({
        id,
        status: 'error',
        message: 'Esta clínica não está disponível. Selecione uma clínica da lista.',
      });
      return () => controller.abort();
    }
    setState({ id, status: 'loading' });
    void clinicApi
      .get(number, access, controller.signal)
      .then((clinic) => {
        if (!controller.signal.aborted) setState({ id, status: 'success', clinic });
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        setState({ id, status: 'error', message: errorMessage(failure) });
        if (failure instanceof ApiError && [403, 404].includes(failure.status))
          removeClinic(number);
      });
    return () => controller.abort();
  }, [id, access, removeClinic, revision]);

  return {
    state: state.id === id ? state : ({ id, status: 'loading' } as const),
    retry: () => setRevision((current) => current + 1),
  };
}
