import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, errorMessage } from '../../shared/api/errors';
import type { NoticeData } from '../../shared/ui/Notice';
import { authApi } from './api';
import { AuthContext } from './context';
import type { Credentials, Session } from './types';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState<NoticeData | null>(null);
  const [suggestedUsername, setSuggestedUsername] = useState('');
  const current = useRef<Session | null>(null);
  const generation = useRef(0);
  const pendingLogout = useRef<Promise<void> | null>(null);

  const clearNotice = useCallback(() => setNotice(null), []);
  const expire = useCallback((token: string) => {
    if (current.current?.token !== token) return;
    generation.current++;
    current.current = null;
    setSession(null);
    setSuggestedUsername('');
    setNotice({
      kind: 'error',
      message: 'Sua sessão foi encerrada. Entre novamente para continuar.',
      routeAlert: true,
    });
  }, []);

  const login = useCallback(async (credentials: Credentials, signal: AbortSignal) => {
    const version = ++generation.current;
    setNotice(null);
    // Django reuses a user's token: a still-pending logout must settle before
    // requesting another token. A network timeout cannot confirm remote ordering.
    if (pendingLogout.current) await pendingLogout.current;
    if (signal.aborted || version !== generation.current) return false;
    const { token } = await authApi.login(credentials, signal);
    if (signal.aborted || version !== generation.current) return false;
    const user = await authApi.me(token, signal);
    if (signal.aborted || version !== generation.current) return false;
    const next = { token, user };
    current.current = next;
    setSession(next);
    setSuggestedUsername('');
    return true;
  }, []);

  const logout = useCallback(() => {
    const previous = current.current;
    if (!previous) return;
    const version = ++generation.current;
    current.current = null;
    setSession(null);
    setSuggestedUsername('');
    setNotice({ kind: 'success', message: 'Você saiu da sua conta.' });
    const operation = authApi.logout(previous.token).catch((failure: unknown) => {
      if (
        version === generation.current &&
        !(failure instanceof ApiError && failure.status === 401)
      ) {
        setNotice({
          kind: 'error',
          message: `A sessão local foi encerrada, mas não foi possível confirmar a saída no servidor. ${errorMessage(failure)}`,
        });
      }
    });
    pendingLogout.current = operation;
    void operation.then(() => {
      if (pendingLogout.current === operation) pendingLogout.current = null;
    });
  }, []);

  const registrationSucceeded = useCallback((username: string) => {
    setSuggestedUsername(username);
    setNotice({
      kind: 'success',
      message: 'Conta criada. Entre com seu usuário e senha para continuar.',
    });
  }, []);

  const value = useMemo(
    () => ({
      session,
      notice,
      suggestedUsername,
      login,
      logout,
      expire,
      clearNotice,
      registrationSucceeded,
    }),
    [session, notice, suggestedUsername, login, logout, expire, clearNotice, registrationSucceeded],
  );
  return <AuthContext value={value}>{children}</AuthContext>;
}
