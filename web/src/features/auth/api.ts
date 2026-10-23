import { request } from '../../shared/api/http';
import { withApiErrors } from '../../shared/api/errors';
import { authServiceMessages, registrationFieldMessages } from './errors';
import type { Credentials, Registration, User } from './types';

export const authApi = {
  register: (body: Registration, signal: AbortSignal) =>
    withApiErrors(request<User>('auth/register/', { method: 'POST', body, signal }), {
      messages: authServiceMessages,
      fieldMessages: registrationFieldMessages,
    }),
  login: (body: Credentials, signal: AbortSignal) =>
    withApiErrors(request<{ token: string }>('auth/token/', { method: 'POST', body, signal }), {
      messages: { ...authServiceMessages, 400: 'Usuário ou senha inválidos. Confira seus dados.' },
    }),
  me: (token: string, signal: AbortSignal) =>
    withApiErrors(request<User>('auth/me/', { token, signal }), { messages: authServiceMessages }),
  logout: (token: string) =>
    withApiErrors(request<void>('auth/logout/', { method: 'POST', token }), {
      messages: authServiceMessages,
    }),
};
