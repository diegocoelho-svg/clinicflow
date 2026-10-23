import { ApiError } from './errors';

export interface RequestAuth {
  token: string;
  onUnauthorized: (token: string) => void;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  idempotencyKey?: string;
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
  onUnauthorized?: (token: string) => void;
}

// No persistence, credential logging, cookie authentication, or automatic retries.
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timeout = setTimeout(abort, 15000);
  try {
    const response = await fetch(`/api/v1/${path}`, {
      method: options.method || 'GET',
      headers: {
        Accept: 'application/json',
        ...(options.idempotencyKey ? { 'Idempotency-Key': options.idempotencyKey } : {}),
        ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: 'no-store',
      credentials: 'omit',
      signal: controller.signal,
    });
    if (response.status === 401 && options.token) options.onUnauthorized?.(options.token);
    if (response.status === 204) return undefined as T;
    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const messages: Record<number, string> = {
        400: 'Confira os campos e tente novamente.',
        401: 'Sua sessão foi encerrada. Entre novamente para continuar.',
        403: 'Você não tem permissão para realizar esta ação.',
        404: 'O recurso solicitado não está disponível. Tente novamente em instantes.',
        429: 'Muitas tentativas. Aguarde um minuto antes de tentar novamente.',
      };
      throw new ApiError(
        response.status,
        messages[response.status] || 'O serviço está indisponível. Tente novamente em instantes.',
        {},
        response.status === 400 && data && typeof data === 'object' && !Array.isArray(data)
          ? Object.keys(data)
          : [],
      );
    }
    if (data === null)
      throw new ApiError(0, 'A resposta do serviço não pôde ser lida. Tente novamente.');
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      'Não foi possível conectar ao serviço. Verifique sua conexão e tente novamente.',
    );
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', abort);
  }
}
