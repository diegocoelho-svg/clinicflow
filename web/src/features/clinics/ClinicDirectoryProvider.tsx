import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { errorMessage } from '../../shared/api/errors';
import { clinicApi } from './api';
import { ClinicDirectoryContext } from './context';
import { useClinicAccess } from './hooks/useClinicAccess';
import type { Clinic } from './types';

export function ClinicDirectoryProvider({ children }: { children: ReactNode }) {
  const access = useClinicAccess();
  const [clinics, setClinics] = useState<Clinic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const pendingChanges = useRef<{
    added: Map<number, Clinic>;
    removed: Set<number>;
  } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const changes = { added: new Map<number, Clinic>(), removed: new Set<number>() };
    pendingChanges.current = changes;
    setLoading(true);
    setError('');
    void clinicApi
      .list(access, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        // Reconcile changes made while this snapshot was in flight. A rejected
        // detail must not discard every other clinic in a valid list response.
        const next = new Map(
          data
            .filter((clinic) => !changes.removed.has(clinic.id))
            .map((clinic) => [clinic.id, clinic]),
        );
        for (const clinic of changes.added.values()) next.set(clinic.id, clinic);
        setClinics([...next.values()]);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          pendingChanges.current = null;
          setLoading(false);
        }
      });
    return () => {
      controller.abort();
      if (pendingChanges.current === changes) pendingChanges.current = null;
    };
  }, [access, revision]);

  const reload = useCallback(() => setRevision((current) => current + 1), []);
  const addClinic = useCallback((clinic: Clinic) => {
    pendingChanges.current?.removed.delete(clinic.id);
    pendingChanges.current?.added.set(clinic.id, clinic);
    setClinics((current) => [...current.filter((item) => item.id !== clinic.id), clinic]);
  }, []);
  const removeClinic = useCallback((id: number) => {
    pendingChanges.current?.added.delete(id);
    pendingChanges.current?.removed.add(id);
    setClinics((current) => current.filter((item) => item.id !== id));
  }, []);
  const value = useMemo(
    () => ({ clinics, loading, error, reload, addClinic, removeClinic }),
    [clinics, loading, error, reload, addClinic, removeClinic],
  );
  return <ClinicDirectoryContext value={value}>{children}</ClinicDirectoryContext>;
}
