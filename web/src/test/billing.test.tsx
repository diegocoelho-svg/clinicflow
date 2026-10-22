import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter } from 'react-router';
import { App } from '../app/App';
import { routes } from '../app/router';
import type { Charge } from '../features/charges/types';
import { itemSum, money } from '../shared/format/money';

const clinic = {
  id: 7,
  name: 'Clínica Demonstração',
  created_at: '2026-10-20T12:00:00Z',
  updated_at: '2026-10-20T12:00:00Z',
};
const encounter = {
  id: 10,
  clinic: 7,
  patient: 2,
  description: 'Consulta fictícia',
  performed_at: '2026-10-20T12:00:00Z',
};
const patient = { id: 2, full_name: 'Marina Exemplo' };
const initialItem = {
  id: 20,
  encounter: 10,
  procedure: 3,
  procedure_name: 'Consulta',
  quantity: 2,
  unit_price: '125.50',
  total: '251.00',
};
const account = {
  id: 4,
  username: 'demo',
  email: 'demo@example.test',
  first_name: 'Ana',
  last_name: 'Exemplo',
};
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

function backend(
  options: {
    amount?: string;
    empty?: boolean;
    denyCancel?: boolean;
    loseFirstResponse?: boolean;
    delayFirstResponse?: boolean;
    missingEncounter?: boolean;
  } = {},
) {
  let items = options.empty
    ? []
    : [
        {
          ...initialItem,
          unit_price: options.amount === '0.00' ? '0.00' : initialItem.unit_price,
          total: options.amount ?? initialItem.total,
        },
      ];
  const charges: Charge[] = [];
  const keys: string[] = [];
  let release: (() => void) | undefined;
  const fetchMock = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const url = String(input);
    const method = init.method ?? 'GET';
    if (url.endsWith('/auth/token/')) return json({ token: 'billing-test-token' });
    if (url.endsWith('/auth/me/')) return json(account);
    if (url.endsWith('/auth/logout/')) return new Response(null, { status: 204 });
    if (url === '/api/v1/clinics/') return json([clinic]);
    if (url === '/api/v1/clinics/7/') return json(clinic);
    if (url.endsWith('/patients/')) return json([patient]);
    if (url.endsWith('/procedures/'))
      return json([{ id: 3, name: 'Consulta', unit_price: '125.50', is_active: true }]);
    if (url === '/api/v1/clinics/7/encounters/') return json([encounter]);
    if (url.endsWith('/encounters/10/'))
      return options.missingEncounter ? json({}, 404) : json(encounter);
    if (url.endsWith('/encounters/10/items/')) return json(items);
    if (url.endsWith('/encounters/10/items/20/') && method === 'PATCH') {
      if (charges.some((charge) => charge.status !== 'CANCELLED')) return json({}, 409);
      const body = JSON.parse(String(init.body)) as { quantity: number };
      items = items.map((item) => ({
        ...item,
        quantity: body.quantity,
        total: itemSum([{ ...item, quantity: body.quantity }])!,
      }));
      return json(items[0]);
    }
    if (url.endsWith('/encounters/10/charges/') && method === 'POST') {
      const key = new Headers(init.headers).get('Idempotency-Key')!;
      keys.push(key);
      let charge = charges.find((entry) => entry.idempotency_key === key);
      if (!charge) {
        if (charges.some((entry) => entry.status !== 'CANCELLED')) return json({}, 409);
        charge = {
          id: 30 + charges.length,
          clinic: 7,
          encounter: 10,
          amount: options.amount ?? itemSum(items)!,
          currency: 'BRL',
          status: options.amount === '0.00' ? 'NO_PAYMENT_REQUIRED' : 'PENDING',
          idempotency_key: key,
          created_by: 4,
          created_at: '2026-10-20T12:00:00Z',
          updated_at: '2026-10-20T12:00:00Z',
          cancelled_at: null,
          cancelled_by: null,
          cancellation_reason: null,
          items: items.map((item) => ({ ...item })),
        };
        charges.push(charge);
      }
      if (keys.length === 1 && options.delayFirstResponse)
        await new Promise<void>((resolve) => {
          release = resolve;
        });
      if (keys.length === 1 && options.loseFirstResponse)
        throw new TypeError('Synthetic transport failure after commit');
      return json(charge, 201);
    }
    if (url === '/api/v1/clinics/7/charges/') return json(charges);
    const detail = url.match(/\/charges\/(\d+)\/(cancel\/)?$/);
    if (detail) {
      const charge = charges.find((entry) => entry.id === Number(detail[1]));
      if (!charge) return json({}, 404);
      if (detail[2]) {
        if (options.denyCancel) return json({}, 403);
        charge.status = 'CANCELLED';
        charge.cancellation_reason = (JSON.parse(String(init.body)) as { reason: string }).reason;
        charge.cancelled_by = 4;
        charge.cancelled_at = '2026-10-20T13:00:00Z';
      }
      return json(charge);
    }
    throw new Error('Unexpected billing test route: ' + method + ' ' + url);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, charges, keys, release: () => release?.() };
}

async function openBilling() {
  const router = createMemoryRouter(routes, { initialEntries: ['/entrar'] });
  render(<App router={router} />);
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Usuário'), 'demo');
  await ui.type(screen.getByLabelText('Senha'), 'Synthetic-Password-936!');
  await ui.click(screen.getByRole('button', { name: 'Entrar' }));
  await screen.findByRole('link', { name: /Clínica Demonstração/ });
  await act(() => router.navigate('/clinicas/7/atendimentos/10'));
  return { router, ui };
}

beforeEach(() => vi.unstubAllGlobals());

describe('billing through the application routes', () => {
  it('issues an exact BRL total, locks items and preserves the recorded snapshot', async () => {
    const api = backend();
    const { ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    expect(
      await screen.findByText(
        'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Editar itens' })).toBeDisabled();
    expect(api.keys[0]).toMatch(/^[0-9a-f-]{36}$/i);
    expect(api.charges[0]).toMatchObject({
      amount: '251.00',
      status: 'PENDING',
      items: [{ quantity: 2, unit_price: '125.50' }],
    });
    await ui.click(screen.getByRole('link', { name: 'Ver cobrança #30' }));
    expect(await screen.findByRole('heading', { name: 'Cobrança #30' })).toBeInTheDocument();
    expect(
      await screen.findByRole('table', { name: 'Itens preservados na cobrança' }),
    ).toHaveTextContent('Consulta');
  });

  it('keeps paid items locked without offering cancellation or suggesting it as a correction', async () => {
    const api = backend();
    const { ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    await screen.findByText(
      'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
    );
    api.charges[0].status = 'PAID';
    await ui.click(screen.getByRole('button', { name: 'Atualizar atendimento' }));
    await screen.findByText(
      'Esta cobrança está paga. Os itens e valores do atendimento estão preservados.',
    );
    const panel = within(screen.getByRole('dialog'));
    expect(panel.getByRole('button', { name: 'Editar itens' })).toBeDisabled();
    expect(panel.queryByRole('button', { name: 'Cancelar cobrança' })).not.toBeInTheDocument();
    expect(panel.queryByRole('button', { name: 'Emitir cobrança' })).not.toBeInTheDocument();
    expect(panel.queryByText(/precisa cancelar a cobrança primeiro/)).not.toBeInTheDocument();
  });

  it('reuses an uncertain issuance key after navigating to the charge list and back', async () => {
    const api = backend({ loseFirstResponse: true });
    const { router, ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    await screen.findByRole('button', { name: 'Verificar emissão' });
    await act(() => router.navigate('/clinicas/7/cobrancas'));
    expect(await screen.findByRole('link', { name: 'Cobrança #30' })).toBeInTheDocument();
    await act(() => router.navigate('/clinicas/7/atendimentos/10'));
    await ui.click(await screen.findByRole('button', { name: 'Verificar emissão' }));
    await screen.findByText(
      'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
    );
    expect(api.keys).toHaveLength(2);
    expect(api.keys[1]).toBe(api.keys[0]);
    expect(api.charges).toHaveLength(1);
  });

  it('keeps a submission alive across navigation and prevents another click while it is pending', async () => {
    const api = backend({ delayFirstResponse: true });
    const { router, ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    expect(await screen.findByRole('button', { name: 'Confirmando emissão…' })).toBeDisabled();
    await act(() => router.navigate('/clinicas/7/cobrancas'));
    await screen.findByRole('heading', { name: 'Cobranças' });
    await act(() => router.navigate('/clinicas/7/atendimentos/10'));
    expect(await screen.findByRole('button', { name: 'Confirmando emissão…' })).toBeDisabled();
    await act(async () => api.release());
    await screen.findByText(
      'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
    );
    expect(api.keys).toHaveLength(1);
  });

  it('requires a cancellation reason, preserves its audit, unlocks items and uses a new issuance key', async () => {
    const api = backend();
    const { router, ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    await screen.findByText(
      'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
    );
    await act(() => router.navigate('/clinicas/7/cobrancas/30'));
    await ui.click(await screen.findByRole('button', { name: 'Cancelar cobrança' }));
    expect(screen.getByRole('button', { name: 'Confirmar cancelamento' })).toBeDisabled();
    await ui.type(screen.getByLabelText('Motivo do cancelamento'), 'Corrigir quantidade');
    await ui.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }));
    expect(await screen.findByText('Corrigir quantidade')).toBeInTheDocument();
    await ui.click(screen.getByRole('link', { name: 'Corrigir atendimento e emitir novamente' }));
    await ui.click(await screen.findByRole('button', { name: 'Editar itens' }));
    const quantityForm = screen.getByRole('form', { name: 'Quantidade de Consulta' });
    const quantityInput = within(quantityForm).getByLabelText('Quantidade de Consulta');
    await ui.clear(quantityInput);
    await ui.type(quantityInput, '3');
    await ui.click(within(quantityForm).getByRole('button', { name: 'Salvar quantidade' }));
    await ui.click(await screen.findByRole('button', { name: 'Concluir edição' }));
    await ui.click(await screen.findByRole('button', { name: 'Emitir nova cobrança' }));
    await screen.findByText(
      'Emissão da cobrança #31 confirmada. Veja a situação atual no histórico.',
    );
    expect(api.keys[1]).not.toBe(api.keys[0]);
    expect(api.charges[0]).toMatchObject({
      status: 'CANCELLED',
      amount: '251.00',
      cancellation_reason: 'Corrigir quantidade',
    });
    expect(api.charges[1]).toMatchObject({ status: 'PENDING', amount: '376.50' });
  });

  it('explains owner-only cancellation when the API denies the operation', async () => {
    const api = backend({ denyCancel: true });
    const { router, ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    await screen.findByText(
      'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
    );
    await act(() => router.navigate('/clinicas/7/cobrancas/30'));
    await ui.click(await screen.findByRole('button', { name: 'Cancelar cobrança' }));
    await ui.type(screen.getByLabelText('Motivo do cancelamento'), 'Correção');
    await ui.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Somente proprietários desta clínica podem cancelar cobranças.',
    );
    expect(api.charges[0].status).toBe('PENDING');
  });

  it('shows a zero amount as no payment required, never as paid', async () => {
    const api = backend({ amount: '0.00' });
    const { ui } = await openBilling();
    await ui.click(await screen.findByRole('button', { name: 'Emitir cobrança' }));
    await screen.findByText(
      'Emissão da cobrança #30 confirmada. Veja a situação atual no histórico.',
    );
    expect(
      within(screen.getByRole('dialog')).getByText('Sem pagamento necessário'),
    ).toBeInTheDocument();
    expect(api.charges[0]).toMatchObject({ amount: '0.00', status: 'NO_PAYMENT_REQUIRED' });
    expect(screen.queryByText('Paga')).not.toBeInTheDocument();
  });

  it('prevents billing an encounter without any items', async () => {
    const api = backend({ empty: true });
    await openBilling();
    expect(await screen.findByRole('button', { name: 'Emitir cobrança' })).toBeDisabled();
    expect(
      screen.getByText('Adicione pelo menos um procedimento para emitir uma cobrança.'),
    ).toBeInTheDocument();
    expect(api.keys).toHaveLength(0);
  });

  it('does not expose billing controls when an encounter is unavailable in the selected clinic', async () => {
    backend({ missingEncounter: true });
    await openBilling();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Este atendimento ou clínica não está disponível.',
    );
    expect(screen.queryByRole('button', { name: 'Emitir cobrança' })).not.toBeInTheDocument();
  });
});

describe('financial display boundaries', () => {
  it('formats and sums amounts above floating point precision using integer cents', () => {
    expect(itemSum([{ unit_price: '999999999999999999.99', quantity: 2 }])).toBe(
      '1999999999999999999.98',
    );
    expect(money('1999999999999999999.98').replace(/\s/g, ' ')).toBe(
      'R$ 1.999.999.999.999.999.999,98',
    );
  });

  it('rejects fractional quantities, invalid monetary strings and total overflow', () => {
    expect(itemSum([{ unit_price: '0.10', quantity: 1.5 }])).toBeNull();
    expect(itemSum([{ unit_price: 'NaN', quantity: 1 }])).toBeNull();
    expect(itemSum([{ unit_price: '99999999999999999999.99', quantity: 2 }])).toBeNull();
  });
});
