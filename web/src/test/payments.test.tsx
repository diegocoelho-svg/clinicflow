import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter } from 'react-router';
import { App } from '../app/App';
import { routes } from '../app/router';
import type { Payment, PaymentEvent } from '../features/payments/types';
import { money } from '../shared/format/money';

const clinic = {
  id: 7,
  name: 'Clínica Pagamentos',
  created_at: '2026-10-26T12:00:00Z',
  updated_at: '2026-10-26T12:00:00Z',
};
const otherClinic = { ...clinic, id: 8, name: 'Outra clínica' };
const timestamp = '2026-10-26T12:00:00Z';
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

function backend(options: { status?: number; failOnce?: boolean; foreignPayload?: boolean } = {}) {
  const payments: Payment[] = [30, 31].map((charge, index) => ({
    id: 50 + index,
    clinic: 7,
    charge,
    payment_reference: `qa-pago-${index}`,
    source_event: 70 + index,
    amount: '125.50',
    currency: 'BRL',
    paid_at: timestamp,
    reconciled_at: timestamp,
  }));
  const events: PaymentEvent[] = [
    {
      id: 70,
      event_id: 'origem',
      clinic: 7,
      charge_reference: 30,
      payment_reference: 'qa-pago-0',
      amount: '125.50',
      currency: 'BRL',
      paid_at: timestamp,
      status: 'RECONCILED',
      discrepancy_code: '',
      payment: 50,
      received_at: timestamp,
      processed_at: timestamp,
    },
    {
      id: 71,
      event_id: 'divergencia',
      clinic: 7,
      charge_reference: 32,
      payment_reference: 'qa-valor',
      amount: '120.00',
      currency: 'BRL',
      paid_at: timestamp,
      status: 'DISCREPANCY',
      discrepancy_code: 'AMOUNT_MISMATCH',
      payment: null,
      received_at: timestamp,
      processed_at: timestamp,
    },
    {
      id: 72,
      event_id: 'pendente',
      clinic: 7,
      charge_reference: 33,
      payment_reference: 'qa-pendente',
      amount: '125.50',
      currency: 'BRL',
      paid_at: timestamp,
      status: 'RECEIVED',
      discrepancy_code: '',
      payment: null,
      received_at: timestamp,
      processed_at: null,
    },
    {
      id: 73,
      event_id: 'moeda',
      clinic: 7,
      charge_reference: 32,
      payment_reference: 'qa-moeda',
      amount: '125.50',
      currency: 'USD',
      paid_at: timestamp,
      status: 'DISCREPANCY',
      discrepancy_code: 'CURRENCY_MISMATCH',
      payment: null,
      received_at: timestamp,
      processed_at: timestamp,
    },
  ];
  let failed = false;
  const fetchMock = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const url = String(input);
    if (url.endsWith('/auth/token/')) return json({ token: 'payments-test-token' });
    if (url.endsWith('/auth/me/'))
      return json({
        id: 1,
        username: 'demo',
        email: 'demo@example.test',
        first_name: 'Ana',
        last_name: 'Teste',
      });
    if (url === '/api/v1/clinics/') return json([clinic, otherClinic]);
    if (url === '/api/v1/clinics/7/') return json(clinic);
    if (url === '/api/v1/clinics/8/') return json(otherClinic);
    if (url === '/api/v1/clinics/8/payments/' || url === '/api/v1/clinics/8/payment-events/')
      return json([], 403);
    if (url === '/api/v1/clinics/7/payments/') {
      if (options.status) return json({}, options.status);
      if (options.failOnce && !failed) {
        failed = true;
        return json({}, 503);
      }
      return json(
        options.foreignPayload
          ? [{ ...payments[0], clinic: 8, payment_reference: 'NAO-EXIBIR-OUTRA-CLINICA' }]
          : payments,
      );
    }
    if (url === '/api/v1/clinics/7/payment-events/') return json(events);
    if (url === '/api/v1/clinics/7/charges/30/')
      return json({
        id: 30,
        clinic: 7,
        encounter: 10,
        amount: '125.50',
        currency: 'BRL',
        status: 'PAID',
        items: [],
        created_by: 1,
        created_at: timestamp,
        cancelled_at: null,
        cancelled_by: null,
        cancellation_reason: null,
      });
    throw new Error('Unexpected payments test route: ' + (init.method ?? 'GET') + ' ' + url);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { payments, events, fetchMock };
}

async function open(path = '/clinicas/7/pagamentos') {
  const router = createMemoryRouter(routes, { initialEntries: ['/entrar'] });
  render(<App router={router} />);
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Usuário'), 'demo');
  await ui.type(screen.getByLabelText('Senha'), 'Synthetic-Password-936!');
  await ui.click(screen.getByRole('button', { name: 'Entrar' }));
  await screen.findByRole('heading', { name: 'Minhas clínicas' });
  await act(() => router.navigate(path));
  return { router, ui };
}

beforeEach(() => vi.unstubAllGlobals());

describe('payments workspace', () => {
  it('offers the payment area before clinic selection', async () => {
    backend();
    const { ui, router } = await open('/clinicas');
    await ui.click(
      within(screen.getByRole('navigation', { name: 'Navegação principal' })).getByRole('link', {
        name: 'Pagamentos',
      }),
    );
    await ui.click(await screen.findByRole('link', { name: /Clínica Pagamentos/ }));
    await screen.findByRole('link', { name: 'Pagamento #50' });
    expect(router.state.location.pathname).toBe('/clinicas/7/pagamentos');
  });

  it('shows exact payment amounts and opens linked read-only details', async () => {
    const { fetchMock } = backend();
    const { ui } = await open();
    await ui.click(await screen.findByRole('link', { name: 'Pagamento #50' }));
    const dialog = screen.getByRole('dialog', { name: 'Pagamento #50' });
    expect(within(dialog).getByText('qa-pago-0')).toBeVisible();
    expect(within(dialog).getByText(/125,50/)).toBeVisible();
    expect(within(dialog).getByRole('link', { name: 'Cobrança #30' })).toHaveAttribute(
      'href',
      '/clinicas/7/cobrancas/30',
    );
    expect(within(dialog).getByRole('link', { name: 'Ver recebimento de origem' })).toHaveAttribute(
      'href',
      '/clinicas/7/pagamentos/eventos/70',
    );
    const calls = fetchMock.mock.calls.filter(([url]) =>
      /payments\/|payment-events\//.test(String(url)),
    );
    expect(calls.length).toBeGreaterThan(0);
    for (const [, init = {}] of calls) {
      expect(init.method).toBe('GET');
      expect(new Headers(init.headers).get('Authorization')).toBe('Bearer payments-test-token');
      expect(init.cache).toBe('no-store');
    }
  });

  it('keeps search and status when closing, navigating records and refreshing', async () => {
    backend();
    const { ui, router } = await open(
      '/clinicas/7/pagamentos/eventos?situacao=DISCREPANCY&busca=qa',
    );
    await ui.click(await screen.findByRole('link', { name: 'Evento #73' }));
    await ui.click(
      within(screen.getByRole('dialog')).getByRole('link', { name: 'Próximo registro' }),
    );
    expect(router.state.location.pathname).toBe('/clinicas/7/pagamentos/eventos/71');
    expect(router.state.location.search).toContain('situacao=DISCREPANCY');
    await ui.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Fechar evento #71' }),
    );
    expect(screen.getByLabelText('Buscar por cobrança ou referência')).toHaveValue('qa');
    expect(screen.getByLabelText('Situação do recebimento')).toHaveValue('DISCREPANCY');
    await ui.click(screen.getByRole('button', { name: 'Atualizar pagamentos' }));
    await screen.findByRole('link', { name: 'Evento #73' });
    expect(screen.queryByRole('link', { name: 'Evento #72' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Buscar por cobrança ou referência')).toHaveValue('qa');
  });

  it('refreshes an open pending receipt after reconciliation', async () => {
    const data = backend();
    const { ui } = await open('/clinicas/7/pagamentos/eventos/72');
    const dialog = await screen.findByRole('dialog', { name: 'Evento #72' });
    expect(within(dialog).getByText(/Recebimento registrado e aguardando/)).toBeVisible();
    data.events[2] = {
      ...data.events[2],
      status: 'RECONCILED',
      payment: 50,
      processed_at: timestamp,
    };
    await ui.click(within(dialog).getByRole('button', { name: 'Atualizar registro' }));
    expect(
      await within(dialog).findByRole('link', { name: 'Ver pagamento conciliado' }),
    ).toHaveAttribute('href', '/clinicas/7/pagamentos/50');
    expect(
      within(dialog).queryByText(/Recebimento registrado e aguardando/),
    ).not.toBeInTheDocument();
  });

  it.each([
    ['AMOUNT_MISMATCH', 'O valor recebido é diferente do valor da cobrança.'],
    ['CURRENCY_MISMATCH', 'A moeda recebida é diferente da moeda da cobrança.'],
    ['CHARGE_NOT_PENDING', 'A cobrança não estava aguardando pagamento.'],
    ['CHARGE_NOT_FOUND', 'A cobrança informada não foi encontrada nesta clínica.'],
    ['PAYMENT_REFERENCE_CONFLICT', 'A referência de pagamento já foi usada em outra cobrança.'],
    ['FUTURE_REASON', 'O recebimento precisa ser conferido.'],
    ['constructor', 'O recebimento precisa ser conferido.'],
  ])('explains discrepancy %s without offering financial mutations', async (code, message) => {
    const data = backend();
    data.events[1].discrepancy_code = code;
    await open('/clinicas/7/pagamentos/eventos/71');
    const dialog = await screen.findByRole('dialog', { name: 'Evento #71' });
    expect(within(dialog).getByRole('alert')).toHaveTextContent(message);
    expect(
      within(dialog).queryByRole('button', { name: /pagar|resolver|reprocessar|cancelar/i }),
    ).not.toBeInTheDocument();
    if (code === 'CHARGE_NOT_FOUND')
      expect(within(dialog).queryByRole('link', { name: 'Cobrança #32' })).not.toBeInTheDocument();
  });

  it('displays the received currency on mismatching receipts', async () => {
    backend();
    await open('/clinicas/7/pagamentos/eventos/73');
    const dialog = await screen.findByRole('dialog', { name: 'Evento #73' });
    expect(within(dialog).getByText(/US\$.*125,50/)).toBeVisible();
    expect(within(dialog).queryByText(/^R\$/)).not.toBeInTheDocument();
  });

  it('follows the source receipt and returns to the reconciled payment', async () => {
    backend();
    const { ui, router } = await open('/clinicas/7/pagamentos/50');
    await ui.click(await screen.findByRole('link', { name: 'Ver recebimento de origem' }));
    const dialog = screen.getByRole('dialog', { name: 'Evento #70' });
    await ui.click(within(dialog).getByRole('link', { name: 'Ver pagamento conciliado' }));
    expect(router.state.location.pathname).toBe('/clinicas/7/pagamentos/50');
    expect(screen.getByRole('dialog', { name: 'Pagamento #50' })).toBeVisible();
  });

  it('links paid charges to their matching payment', async () => {
    backend();
    const { ui } = await open('/clinicas/7/cobrancas/30');
    await ui.click(await screen.findByRole('link', { name: 'Ver pagamento conciliado' }));
    await screen.findByRole('link', { name: 'Pagamento #50' });
    expect(screen.queryByRole('link', { name: 'Pagamento #51' })).not.toBeInTheDocument();
  });

  it('supports status filters and useful empty search results', async () => {
    backend();
    const { ui } = await open('/clinicas/7/pagamentos/eventos');
    await screen.findByRole('link', { name: 'Evento #72' });
    await ui.selectOptions(screen.getByLabelText('Situação do recebimento'), 'RECEIVED');
    expect(screen.getByRole('link', { name: 'Evento #72' })).toBeVisible();
    expect(screen.queryByRole('link', { name: 'Evento #71' })).not.toBeInTheDocument();
    await ui.type(screen.getByLabelText('Buscar por cobrança ou referência'), 'inexistente');
    expect(screen.getByRole('heading', { name: 'Nenhum registro encontrado' })).toBeVisible();
  });

  it('recovers from a transient read error', async () => {
    backend({ failOnce: true });
    const { ui } = await open();
    await ui.click(await screen.findByRole('button', { name: /Tentar carregar novamente/i }));
    expect(await screen.findByRole('link', { name: 'Pagamento #50' })).toBeVisible();
  });

  it('does not display another clinic payload', async () => {
    backend({ foreignPayload: true });
    await open();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível conferir os recebimentos desta clínica.',
    );
    expect(screen.queryByText('NAO-EXIBIR-OUTRA-CLINICA')).not.toBeInTheDocument();
  });

  it('clears previous clinic data when the next clinic denies access', async () => {
    backend();
    const { router } = await open();
    await screen.findByRole('link', { name: 'Pagamento #50' });
    await act(() => router.navigate('/clinicas/8/pagamentos'));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Você não tem acesso aos pagamentos desta clínica.',
    );
    expect(screen.queryByText('qa-pago-0')).not.toBeInTheDocument();
  });

  it.each([
    '/clinicas/7/pagamentos/999',
    '/clinicas/7/pagamentos/invalid',
    '/clinicas/7/pagamentos/eventos/999',
  ])('handles unavailable detail %s', async (path) => {
    backend();
    await open(path);
    expect(await screen.findByRole('alert')).toHaveTextContent(/indisponível nesta clínica/);
  });

  it('shows empty payment and receipt states', async () => {
    const data = backend();
    data.payments.length = 0;
    data.events.length = 0;
    const { ui } = await open();
    expect(
      await screen.findByRole('heading', { name: 'Nenhum pagamento conciliado' }),
    ).toBeVisible();
    await ui.click(screen.getByRole('link', { name: 'Eventos e divergências' }));
    expect(screen.getByRole('heading', { name: 'Nenhum recebimento registrado' })).toBeVisible();
  });
});

it('formats foreign currency without floating-point rounding', () => {
  expect(money('99999999999999999999.99', 'USD')).toContain('99.999.999.999.999.999.999,99');
  expect(money('10.00', 'USD')).toMatch(/US\$.*10,00/);
  expect(money('invalid', 'USD')).toBe('Valor indisponível');
  expect(money('10.00', 'invalid')).toBe('Valor indisponível');
});
