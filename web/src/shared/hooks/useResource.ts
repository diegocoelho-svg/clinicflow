import { useEffect, useState } from 'react';
import { errorMessage } from '../api/errors';

export type Resource<T> =
  { status: 'loading' } | { status: 'error'; message: string } | { status: 'success'; data: T };

export function useResource<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{ key: string; value: Resource<T> }>({
    key,
    value: { status: 'loading' },
  });
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${key}:${attempt}`;
  useEffect(() => {
    const controller = new AbortController();
    setState({ key: requestKey, value: { status: 'loading' } });
    void load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ key: requestKey, value: { status: 'success', data } });
      })
      .catch((failure) => {
        if (!controller.signal.aborted)
          setState({ key: requestKey, value: { status: 'error', message: errorMessage(failure) } });
      });
    return () => controller.abort();
  }, [requestKey, load]);
  return {
    state: state.key === requestKey ? state.value : ({ status: 'loading' } as Resource<T>),
    retry: () => setAttempt((current) => current + 1),
  };
}
