import { useEffect, useRef, useState } from 'react';
import { ApiError, errorMessage, type FieldErrors } from '../api/errors';

// Scope each submission to its form's lifetime, even if a transport ignores abort.
export function useAsyncForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [fields, setFields] = useState<FieldErrors>({});
  const current = useRef<AbortController | null>(null);
  const generation = useRef(0);
  useEffect(
    () => () => {
      generation.current++;
      current.current?.abort();
    },
    [],
  );

  async function submit<T>(task: (signal: AbortSignal) => Promise<T>): Promise<{ data: T } | null> {
    if (current.current) return null;
    const controller = new AbortController();
    current.current = controller;
    const version = ++generation.current;
    setPending(true);
    setError('');
    setFields({});
    try {
      const data = await task(controller.signal);
      return version === generation.current && !controller.signal.aborted ? { data } : null;
    } catch (failure) {
      if (version === generation.current && !controller.signal.aborted) {
        setError(errorMessage(failure));
        setFields(failure instanceof ApiError ? failure.fields : {});
      }
      return null;
    } finally {
      if (version === generation.current) {
        current.current = null;
        setPending(false);
      }
    }
  }

  return { pending, error, fields, submit };
}
