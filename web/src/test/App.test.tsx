import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { createMemoryRouter } from 'react-router';
import { App as RoutedApp } from '../app/App';
import { routes } from '../app/router';

function App() {
  const [router] = useState(() => createMemoryRouter(routes, { initialEntries: ['/entrar'] }));
  return <RoutedApp router={router} />;
}

function renderRoute(path = '/entrar') {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RoutedApp router={router} />);
  return router;
}

const user = {
  id: 4,
  username: 'synthetic',
  first_name: 'Ana',
  last_name: 'Teste',
  email: 'ana@example.test',
};
const clinic = {
  id: 7,
  name: 'Clínica Sintética',
  created_at: '2026-10-17T12:00:00Z',
  updated_at: '2026-10-17T12:00:00Z',
};
const otherClinic = { ...clinic, id: 8, name: 'Segunda Clínica' };
const token = 'synthetic-test-token';
type Handler = (path: string, init: RequestInit) => Response | Promise<Response>;
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const empty = () => new Response(null, { status: 204 });

function mockApi(handler?: Handler) {
  const fetchMock = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const path = String(input);
    if (handler) return handler(path, init);
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

async function login() {
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Usuário'), user.username);
  await ui.type(screen.getByLabelText('Senha'), 'Fictitious-Password-936!');
  await ui.click(screen.getByRole('button', { name: 'Entrar' }));
  return ui;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
});

describe('route boundaries and navigation', () => {
  it('redirects a protected direct URL or fresh page to login without sending authenticated requests', async () => {
    const fetchMock = mockApi();
    const router = renderRoute('/clinicas/7');
    expect(await screen.findByRole('heading', { name: 'Entre no ClinicFlow' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/entrar');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders a recoverable not-found page for unknown URLs', async () => {
    mockApi();
    renderRoute('/pagina-inexistente');
    expect(
      await screen.findByRole('heading', { name: 'Página não encontrada' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ir para minhas clínicas' })).toHaveAttribute(
      'href',
      '/clinicas',
    );
  });

  it('uses nested clinic URLs and reloads authorized detail when navigating back and forward', async () => {
    const fetchMock = mockApi();
    const router = renderRoute();
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    await screen.findByRole('heading', { name: clinic.name });
    expect(router.state.location.pathname).toBe('/clinicas/7');
    await ui.click(screen.getByRole('link', { name: /Segunda Clínica/ }));
    await screen.findByRole('heading', { name: otherClinic.name });
    expect(router.state.location.pathname).toBe('/clinicas/8');
    await act(async () => {
      await router.navigate(-1);
    });
    expect(await screen.findByRole('heading', { name: clinic.name })).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(([path]) => String(path).endsWith('/clinics/7/')),
    ).toHaveLength(2);
    await act(async () => {
      await router.navigate(1);
    });
    expect(await screen.findByRole('heading', { name: otherClinic.name })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Segunda Clínica/ })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('prevents browser back from restoring a protected clinic after logout', async () => {
    mockApi();
    const router = renderRoute();
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    await screen.findByRole('heading', { name: clinic.name });
    await ui.click(screen.getByRole('button', { name: 'Sair' }));
    await screen.findByRole('heading', { name: 'Entre no ClinicFlow' });
    await act(async () => {
      await router.navigate(-1);
    });
    expect(await screen.findByRole('heading', { name: 'Entre no ClinicFlow' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/entrar');
    expect(screen.queryByText(user.email)).not.toBeInTheDocument();
    expect(screen.queryByText(clinic.name)).not.toBeInTheDocument();
  });

  it('ignores an older detail response after navigating to another clinic', async () => {
    const fetchMock = mockApi();
    const delegate = fetchMock.getMockImplementation()!;
    let resolve!: (response: Response) => void;
    fetchMock.mockImplementation(async (path, init) =>
      String(path).endsWith('/clinics/7/')
        ? new Promise<Response>((done) => {
            resolve = done;
          })
        : delegate(path, init),
    );
    const router = renderRoute();
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    await ui.click(screen.getByRole('link', { name: /Segunda Clínica/ }));
    await screen.findByRole('heading', { name: otherClinic.name });
    await act(async () => {
      resolve(json(clinic));
    });
    expect(router.state.location.pathname).toBe('/clinicas/8');
    expect(screen.getByRole('heading', { name: otherClinic.name })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
  });
});

describe('authentication and session boundaries', () => {
  it('logs in through token then me and sends opaque Bearer authentication only to protected endpoints', async () => {
    const fetchMock = mockApi();
    render(<App />);
    await login();
    expect(await screen.findByRole('heading', { name: 'Minhas clínicas' })).toBeInTheDocument();
    expect(screen.getByText(user.email)).toBeInTheDocument();
    const tokenRequest = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/token/'));
    expect(JSON.parse(String(tokenRequest?.[1]?.body))).toEqual({
      username: user.username,
      password: 'Fictitious-Password-936!',
    });
    expect(tokenRequest?.[1]?.headers).not.toHaveProperty('Authorization');
    const me = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/me/'));
    expect(me?.[1]?.headers).toHaveProperty('Authorization', `Bearer ${token}`);
    expect(me?.[1]?.credentials).toBe('omit');
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('keeps invalid login generic, translates the error and clears the password', async () => {
    const fetchMock = mockApi(() =>
      json({ non_field_errors: ['Unable to log in with provided credentials.'] }, 400),
    );
    render(<App />);
    await login();
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuário ou senha inválidos');
    expect(screen.getByLabelText('Senha')).toHaveValue('');
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('registers all five fields, preserves password whitespace and requires a separate login', async () => {
    const fetchMock = mockApi(() => json(user, 201));
    const ui = userEvent.setup();
    render(<App />);
    await ui.click(screen.getByRole('link', { name: 'Criar uma conta' }));
    await ui.type(screen.getByLabelText('Nome'), 'Ana');
    await ui.type(screen.getByLabelText('Sobrenome'), 'Teste');
    await ui.type(screen.getByLabelText('E-mail'), user.email);
    await ui.type(screen.getByLabelText('Usuário'), user.username);
    await ui.type(screen.getByLabelText('Senha'), ' Fictitious-Password-936! ');
    await ui.click(screen.getByRole('button', { name: 'Criar conta' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Conta criada');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      username: user.username,
      password: ' Fictitious-Password-936! ',
      first_name: 'Ana',
      last_name: 'Teste',
      email: user.email,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('Senha')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('logs out, revokes the token, and removes selected clinic and identity', async () => {
    const fetchMock = mockApi();
    render(<App />);
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    expect(await screen.findByRole('heading', { name: clinic.name })).toBeInTheDocument();
    await ui.click(screen.getByRole('button', { name: 'Sair' }));
    expect(await screen.findByRole('heading', { name: 'Entre no ClinicFlow' })).toBeInTheDocument();
    expect(screen.queryByText(user.email)).not.toBeInTheDocument();
    expect(screen.queryByText(clinic.name)).not.toBeInTheDocument();
    const logout = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/logout/'));
    expect(logout?.[1]?.method).toBe('POST');
    expect(logout?.[1]?.headers).toHaveProperty('Authorization', `Bearer ${token}`);
  });

  it('clears local session even if server logout fails and explains the revocation uncertainty', async () => {
    const defaultFetch = mockApi();
    const delegate = defaultFetch.getMockImplementation()!;
    defaultFetch.mockImplementation(async (path, init) => {
      if (String(path).endsWith('/logout/')) throw new TypeError('Synthetic offline');
      return delegate(path, init);
    });
    render(<App />);
    const ui = await login();
    await ui.click(await screen.findByRole('button', { name: 'Sair' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'não foi possível confirmar a saída no servidor',
    );
    expect(screen.queryByText(user.email)).not.toBeInTheDocument();
  });

  it('clears session and clinic selection after an authenticated 401', async () => {
    const fetchMock = mockApi();
    const delegate = fetchMock.getMockImplementation()!;
    let revoked = false;
    fetchMock.mockImplementation(async (path, init) =>
      revoked ? json({ detail: 'Invalid token.' }, 401) : delegate(path, init),
    );
    render(<App />);
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    expect(await screen.findByRole('heading', { name: clinic.name })).toBeInTheDocument();
    revoked = true;
    await ui.click(screen.getByRole('button', { name: 'Atualizar lista de clínicas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sua sessão foi encerrada');
    expect(screen.queryByText(clinic.name)).not.toBeInTheDocument();
    expect(screen.queryByText(user.email)).not.toBeInTheDocument();
  });

  it('ignores a login response arriving after switching authentication forms', async () => {
    let resolve!: (response: Response) => void;
    const fetchMock = mockApi(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    );
    render(<App />);
    const ui = await login();
    await ui.click(screen.getByRole('link', { name: 'Criar uma conta' }));
    resolve(json({ token }));
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Crie sua conta' })).toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument();
  });
});

describe('clinic interactions', () => {
  it('loads detail on selection and shows only the selected clinic workspace', async () => {
    const fetchMock = mockApi();
    render(<App />);
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    expect(await screen.findByRole('heading', { name: clinic.name })).toHaveFocus();
    await ui.click(screen.getByRole('link', { name: /Segunda Clínica/ }));
    expect(await screen.findByRole('heading', { name: otherClinic.name })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([path]) => String(path).endsWith('/clinics/8/'))).toBe(true);
  });

  it('removes a clinic that returns 404, clears the old workspace, and keeps the user signed in', async () => {
    const fetchMock = mockApi();
    const delegate = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (path, init) =>
      String(path).endsWith('/clinics/8/')
        ? json({ detail: 'Not found.' }, 404)
        : delegate(path, init),
    );
    render(<App />);
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    await screen.findByRole('heading', { name: clinic.name });
    await ui.click(screen.getByRole('link', { name: /Segunda Clínica/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Esta clínica não está disponível');
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Segunda Clínica/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sair' })).toBeInTheDocument();
  });

  it('supports retrying a failed list request, then creating and selecting a clinic', async () => {
    const fetchMock = mockApi();
    const delegate = fetchMock.getMockImplementation()!;
    let listCalls = 0;
    fetchMock.mockImplementation(async (path, init = {}) => {
      if (String(path).endsWith('/clinics/')) {
        if (init.method === 'POST') return json(clinic, 201);
        return ++listCalls === 1 ? json({}, 503) : json([]);
      }
      return delegate(path, init);
    });
    render(<App />);
    const ui = await login();
    expect(await screen.findByRole('alert')).toHaveTextContent('O serviço está indisponível');
    await ui.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(
      await screen.findByRole('heading', { name: 'Nenhuma clínica por aqui' }),
    ).toBeInTheDocument();
    await ui.type(screen.getByLabelText('Nome da clínica'), '  Clínica Sintética  ');
    await ui.click(screen.getByRole('button', { name: /Criar clínica/ }));
    expect(await screen.findByRole('status')).toHaveTextContent('Clínica criada');
    const creation = fetchMock.mock.calls.find(
      ([, init]) => init?.method === 'POST' && String(init.body).includes('Clínica Sintética'),
    );
    expect(JSON.parse(String(creation?.[1]?.body))).toEqual({ name: 'Clínica Sintética' });
    await ui.click(screen.getByRole('link', { name: /Clínica Sintética/ }));
    expect(await screen.findByRole('heading', { name: clinic.name })).toBeInTheDocument();
  });

  it('shows safe Portuguese field errors for clinic validation without rendering server HTML', async () => {
    const fetchMock = mockApi();
    const delegate = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (path, init = {}) =>
      init.method === 'POST' && String(path).endsWith('/clinics/')
        ? json({ name: ['<script>secret details</script>'] }, 400)
        : delegate(path, init),
    );
    render(<App />);
    const ui = await login();
    const input = await screen.findByLabelText('Nome da clínica');
    await ui.type(input, 'Synthetic');
    await ui.click(screen.getByRole('button', { name: /Criar clínica/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Confira os campos');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('Informe um nome de clínica com até 255 caracteres.');
    expect(screen.queryByText(/secret details/)).not.toBeInTheDocument();
  });

  it('ignores delayed clinic responses after logout, even when transport ignores abort', async () => {
    const fetchMock = mockApi();
    const delegate = fetchMock.getMockImplementation()!;
    let resolve!: (response: Response) => void;
    fetchMock.mockImplementation(async (path, init) =>
      String(path).endsWith('/clinics/7/')
        ? new Promise<Response>((done) => {
            resolve = done;
          })
        : delegate(path, init),
    );
    render(<App />);
    const ui = await login();
    await ui.click(await screen.findByRole('link', { name: /Clínica Sintética/ }));
    await ui.click(screen.getByRole('button', { name: 'Sair' }));
    resolve(json(clinic));
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Entre no ClinicFlow' })).toBeInTheDocument(),
    );
    expect(screen.queryByText(clinic.name)).not.toBeInTheDocument();
    expect(within(screen.getByRole('main')).queryByText(user.email)).not.toBeInTheDocument();
  });
});
