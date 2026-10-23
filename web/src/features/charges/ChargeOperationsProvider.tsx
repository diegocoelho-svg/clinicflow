import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, errorMessage } from '../../shared/api/errors';
import { useAuth } from '../auth/useAuth';
import { chargeApi } from './api';
import { ChargeOperationsContext, issuanceScope, type Issuance } from './context';

// Lives for one authenticated session. Navigation does not discard an uncertain
// operation or abort its request; unmounting on logout aborts every owned request.
export function ChargeOperationsProvider({ children }: { children: ReactNode }) {
  const { session, expire } = useAuth();
  const token = session?.token;
  const auth = useMemo(() => (token ? { token, onUnauthorized: expire } : null), [token, expire]);
  const records = useRef(new Map<string, Issuance>());
  const controllers = useRef(new Map<string, AbortController>());
  const live = useRef(true);
  const [intents, setIntents] = useState<ReadonlyMap<string, Issuance>>(new Map());
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((current) => current + 1), []);
  useEffect(() => {
    live.current = true;
    const pending = controllers.current;
    return () => {
      live.current = false;
      for (const controller of pending.values()) controller.abort();
    };
  }, []);

  const issue = useCallback(
    async (clinic: number, encounter: number) => {
      const scope = issuanceScope(clinic, encounter);
      if (!auth || controllers.current.has(scope) || !live.current) return;
      const previous = records.current.get(scope);
      let key: string;
      try {
        key =
          previous && previous.status !== 'confirmed' && previous.key
            ? previous.key
            : crypto.randomUUID();
      } catch {
        records.current.set(scope, {
          key: '',
          status: 'rejected',
          message: 'Não foi possível preparar a emissão. Atualize a página e tente novamente.',
        });
        setIntents(new Map(records.current));
        return;
      }
      const controller = new AbortController();
      controllers.current.set(scope, controller);
      const update = (record: Issuance) => {
        if (!live.current || controller.signal.aborted) return;
        records.current.set(scope, record);
        setIntents(new Map(records.current));
      };
      update({ key, status: 'pending' });
      try {
        const charge = await chargeApi.issue(clinic, encounter, key, auth, controller.signal);
        if (
          charge.clinic !== clinic ||
          charge.encounter !== encounter ||
          charge.idempotency_key.toLowerCase() !== key.toLowerCase()
        ) {
          throw new ApiError(
            0,
            'A emissão não pôde ser confirmada. Verifique novamente antes de iniciar outra.',
          );
        }
        update({ key, status: 'confirmed', charge });
      } catch (failure) {
        const uncertain =
          !(failure instanceof ApiError) || failure.status === 0 || failure.status >= 500;
        update({
          key,
          status: uncertain ? 'uncertain' : 'rejected',
          message: uncertain
            ? 'Não foi possível confirmar a emissão. Verifique novamente para localizar a mesma cobrança antes de continuar.'
            : errorMessage(failure),
        });
      } finally {
        controllers.current.delete(scope);
        if (live.current && !controller.signal.aborted) refresh();
      }
    },
    [auth, refresh],
  );
  const value = useMemo(
    () => ({ intents, revision, issue, refresh }),
    [intents, revision, issue, refresh],
  );
  return <ChargeOperationsContext value={value}>{children}</ChargeOperationsContext>;
}
