import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, type RouteObject } from 'react-router';
import { App } from '../app/App';
import { routes } from '../app/router';
import { ApiError } from '../shared/api/errors';
import { request } from '../shared/api/http';

const user = {
  id: 1,
  username: 'review_user',
  first_name: 'Lia',
  last_name: 'Teste',
  email: 'lia@example.test',
};
const clinic = {
  id: 7,
  name: 'Clínica de Revisão',
  created_at: '2026-10-17T12:00:00Z',
  updated_at: '2026-10-17T12:00:00Z',
};
const otherClinic = { ...clinic, id: 8, name: 'Clínica Disponível' };
const createdClinic = { ...clinic, id: 9, name: 'Clínica Nova' };
const token = 'review-fixture-token';
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const empty = () => new Response(null, { status: 204 });

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

type Handler = (path: string, init: RequestInit) => Response | Promise<Response> | undefined;
function mockApi(handler: Handler = () => undefined) {
  const fetchMock = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const path = String(input);
    const response = handler(path, init);
    if (response !== undefined) return response;
    if (path.endsWith('/token/')) return json({ token });
    if (path.endsWith('/me/')) return json(user);
    if (path.endsWith('/clinics/')) return json([clinic, otherClinic]);
    if (path.endsWith('/clinics/7/')) return json(clinic);
    if (path.endsWith('/clinics/8/')) return json(otherClinic);
    if (path.endsWith('/logout/')) return empty();
    throw new Error(`Unexpected test route: ${path}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function renderApp(path = '/entrar') {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<App router={router} />);
  return router;
}

async function login() {
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Usuário'), user.username);
  await ui.type(screen.getByLabelText('Senha'), 'Synthetic-review-password-846!');
  await ui.click(screen.getByRole('button', { name: 'Entrar' }));
  return ui;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('logout ordering with Django token reuse', () => {
  it('waits for a deferred logout before requesting another token and establishing a new session', async () => {
    const logout = deferred<Response>();
    let currentToken: string | null = token;
    let loginCount = 0;
    mockApi((path, init) => {
      if (path.endsWith('/token/')) {
        loginCount++;
        currentToken ||= 'replacement-review-token';
        return json({ token: currentToken });
      }
      if (path.endsWith('/me/'))
        return new Headers(init.headers).get('Authorization') === `Bearer ${currentToken}`
          ? json(user)
          : json({}, 401);
      if (path.endsWith('/logout/'))
        return logout.promise.then((response) => {
          currentToken = null;
          return response;
        });
    });
    renderApp();
    const ui = await login();
    await ui.click(await screen.findByRole('button', { name: 'Sair' }));
    await screen.findByRole('heading', { name: 'Entre no ClinicFlow' });
    await login();
    expect(loginCount).toBe(1);
    expect(screen.getByRole('button', { name: 'Entrando…' })).toBeDisabled();
    expect(screen.queryByRole('heading', { name: 'Minhas clínicas' })).not.toBeInTheDocument();
    await act(async () => {
      logout.resolve(empty());
    });
    expect(await screen.findByRole('heading', { name: 'Minhas clínicas' })).toBeInTheDocument();
    expect(loginCount).toBe(2);
    expect(currentToken).toBe('replacement-review-token');
  });

  it('does not submit a queued login after its form is left while logout is pending', async () => {
    const logout = deferred<Response>();
    const fetchMock = mockApi((path) => (path.endsWith('/logout/') ? logout.promise : undefined));
    renderApp();
    const ui = await login();
    await ui.click(await screen.findByRole('button', { name: 'Sair' }));
    await screen.findByRole('heading', { name: 'Entre no ClinicFlow' });
    await login();
    await ui.click(screen.getByRole('link', { name: 'Criar uma conta' }));
    await act(async () => {
      logout.resolve(empty());
    });
    expect(screen.getByRole('heading', { name: 'Crie sua conta' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([path]) => String(path).endsWith('/token/'))).toHaveLength(
      1,
    );
  });
});

describe('concurrent clinic snapshots', () => {
  it('keeps valid clinics when a detail 404 arrives before the initial list response', async () => {
    const list = deferred<Response>();
    mockApi((path) =>
      path.endsWith('/clinics/')
        ? list.promise
        : path.endsWith('/clinics/7/')
          ? json({}, 404)
          : undefined,
    );
    const router = renderApp();
    await login();
    await screen.findByRole('heading', { name: 'Minhas clínicas' });
    await act(async () => {
      await router.navigate('/clinicas/7');
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Esta clínica não está disponível');
    await act(async () => {
      list.resolve(json([clinic, otherClinic]));
    });
    expect(await screen.findByRole('link', { name: /Clínica Disponível/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Clínica de Revisão/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Nenhuma clínica por aqui' }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Esta clínica não está disponível');
  });

  it('shows a failed list request even when a concurrent detail removed an inaccessible clinic', async () => {
    const list = deferred<Response>();
    mockApi((path) =>
      path.endsWith('/clinics/')
        ? list.promise
        : path.endsWith('/clinics/7/')
          ? json({}, 404)
          : undefined,
    );
    const router = renderApp();
    await login();
    await screen.findByRole('heading', { name: 'Minhas clínicas' });
    await act(async () => {
      await router.navigate('/clinicas/7');
    });
    await screen.findByRole('alert');
    await act(async () => {
      list.resolve(json({}, 503));
    });
    expect(await screen.findByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
    expect(
      screen
        .getAllByRole('alert')
        .some((alert) => alert.textContent?.includes('O serviço está indisponível')),
    ).toBe(true);
    expect(
      screen.queryByRole('heading', { name: 'Nenhuma clínica por aqui' }),
    ).not.toBeInTheDocument();
  });

  it('merges a completed creation into a list refresh without losing existing clinics', async () => {
    const creation = deferred<Response>();
    const refresh = deferred<Response>();
    let listCount = 0;
    mockApi((path, init) => {
      if (!path.endsWith('/clinics/')) return;
      if (init.method === 'POST') return creation.promise;
      return ++listCount === 1 ? json([clinic]) : refresh.promise;
    });
    renderApp();
    const ui = await login();
    await screen.findByRole('link', { name: /Clínica de Revisão/ });
    await ui.type(screen.getByLabelText('Nome da clínica'), createdClinic.name);
    await ui.click(screen.getByRole('button', { name: /Criar clínica/ }));
    await ui.click(screen.getByRole('button', { name: 'Atualizar lista de clínicas' }));
    await act(async () => {
      creation.resolve(json(createdClinic, 201));
    });
    await screen.findByText('Clínica criada. Selecione-a na lista para abrir seu espaço.');
    await act(async () => {
      refresh.resolve(json([clinic]));
    });
    expect(await screen.findByRole('link', { name: /Clínica de Revisão/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Clínica Nova/ })).toBeInTheDocument();
  });
});

describe('feature-specific error wording', () => {
  it('describes a missing login endpoint as an access service error instead of a clinic error', async () => {
    mockApi((path) => (path.endsWith('/token/') ? json({}, 404) : undefined));
    renderApp();
    await login();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('O serviço de acesso não está disponível');
    expect(alert).not.toHaveTextContent(/clínica/i);
    expect(screen.getByLabelText('Senha')).toHaveValue('');
  });

  it('describes missing clinic detail in the clinic feature while retaining the signed-in identity', async () => {
    mockApi((path) => (path.endsWith('/clinics/7/') ? json({}, 404) : undefined));
    renderApp();
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica de Revisão/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Esta clínica não está disponível');
    expect(screen.getByText(user.email)).toBeInTheDocument();
  });

  it('keeps unclassified transport 404s generic', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({}, 404)),
    );
    const failure = await request('unavailable/').catch((error) => error);
    expect(failure).toBeInstanceOf(ApiError);
    if (!(failure instanceof ApiError)) throw failure;
    expect(failure.message).toBe(
      'O recurso solicitado não está disponível. Tente novamente em instantes.',
    );
  });

  it('maps registration validation keys within auth without rendering server values', async () => {
    mockApi((path) =>
      path.endsWith('/register/')
        ? json({ password: ['<script>unsafe details</script>'] }, 400)
        : undefined,
    );
    renderApp('/cadastro');
    const ui = userEvent.setup();
    for (const [label, value] of [
      ['Nome', 'Lia'],
      ['Sobrenome', 'Teste'],
      ['E-mail', user.email],
      ['Usuário', user.username],
      ['Senha', 'Synthetic-review-password-846!'],
    ]) {
      await ui.type(screen.getByLabelText(label), value);
    }
    await ui.click(screen.getByRole('button', { name: 'Criar conta' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Confira os campos');
    const password = screen.getByLabelText('Senha');
    expect(password).toHaveAttribute('aria-invalid', 'true');
    expect(password).toHaveAccessibleDescription(/Use uma senha forte/);
    expect(screen.queryByText(/unsafe details/)).not.toBeInTheDocument();
  });
});

describe('accessible route transitions', () => {
  it('uses the actual authentication page as the single level-one heading and focus target', async () => {
    mockApi();
    renderApp();
    const ui = userEvent.setup();
    const loginHeading = screen.getByRole('heading', { name: 'Entre no ClinicFlow', level: 1 });
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(loginHeading).toHaveFocus();
    await ui.click(screen.getByRole('link', { name: 'Criar uma conta' }));
    expect(await screen.findByRole('heading', { name: 'Crie sua conta', level: 1 })).toHaveFocus();
    expect(document.title).toBe('ClinicFlow · Criar conta');
  });

  it('focuses the workspace heading, selected clinic and collection heading on real navigation', async () => {
    mockApi();
    renderApp();
    const ui = await login();
    expect(await screen.findByRole('heading', { name: 'Minhas clínicas', level: 1 })).toHaveFocus();
    await ui.click(await screen.findByRole('link', { name: /Clínica de Revisão/ }));
    expect(await screen.findByRole('heading', { name: clinic.name, level: 2 })).toHaveFocus();
    await ui.click(
      within(screen.getByRole('navigation', { name: 'Navegação principal' })).getByRole('link', {
        name: /Minhas clínicas/,
      }),
    );
    expect(await screen.findByRole('heading', { name: 'Minhas clínicas', level: 1 })).toHaveFocus();
  });

  it('returns focus to the collection heading instead of a stale create error', async () => {
    mockApi((path, init) =>
      path.endsWith('/clinics/') && init.method === 'POST' ? json({}, 503) : undefined,
    );
    renderApp();
    const ui = await login();
    await screen.findByRole('link', { name: /Clínica de Revisão/ });
    await ui.type(screen.getByLabelText('Nome da clínica'), 'Clínica temporária');
    await ui.click(screen.getByRole('button', { name: /Criar clínica/ }));
    const createError = await screen.findByRole('alert');
    expect(createError).toHaveFocus();

    await ui.click(await screen.findByRole('link', { name: /Clínica de Revisão/ }));
    await screen.findByRole('heading', { name: clinic.name, level: 2 });
    await ui.click(
      within(screen.getByRole('navigation', { name: 'Navegação principal' })).getByRole('link', {
        name: /Minhas clínicas/,
      }),
    );

    expect(await screen.findByRole('heading', { name: 'Minhas clínicas', level: 1 })).toHaveFocus();
    expect(createError).toBeInTheDocument();
  });

  it('keeps focus on the session-expiry alert after redirecting from a protected route', async () => {
    let revoked = false;
    mockApi((path) => (revoked && path.endsWith('/clinics/') ? json({}, 401) : undefined));
    const router = renderApp();
    const ui = await login();
    await screen.findByRole('link', { name: /Clínica de Revisão/ });
    revoked = true;
    await ui.click(screen.getByRole('button', { name: 'Atualizar lista de clínicas' }));
    const alert = await screen.findByRole('alert');
    await waitFor(() => expect(router.state.location.pathname).toBe('/entrar'));
    expect(alert).toHaveTextContent('Sua sessão foi encerrada');
    expect(alert).toHaveFocus();
    expect(
      screen.getByRole('heading', { name: 'Entre no ClinicFlow', level: 1 }),
    ).not.toHaveFocus();
  });

  it('announces unknown URLs with the matching document title and focused page heading', async () => {
    mockApi();
    renderApp('/pagina-inexistente');
    const heading = screen.getByRole('heading', { name: 'Página não encontrada', level: 1 });
    expect(document.title).toBe('ClinicFlow · Página não encontrada');
    expect(heading).toHaveFocus();
  });

  it('sets an error-page title and focuses its heading after a route render exception', async () => {
    function BrokenRoute(): never {
      throw new Error('Synthetic route render failure');
    }
    const [root] = routes;
    const children: RouteObject[] = [
      ...(root.children ?? []),
      { path: 'erro-de-teste', Component: BrokenRoute },
    ];
    const router = createMemoryRouter([{ ...root, children } as RouteObject], {
      initialEntries: ['/erro-de-teste'],
    });
    render(<App router={router} />);

    const heading = await screen.findByRole('heading', {
      name: 'Não foi possível abrir esta página',
      level: 1,
    });
    await waitFor(() => expect(document.title).toBe('ClinicFlow · Erro ao abrir a página'));
    expect(heading).toHaveFocus();
  });
});
