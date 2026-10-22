import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { createMemoryRouter } from 'react-router';
import { App } from '../app/App';
import { routes } from '../app/router';
import { Dialog } from '../shared/ui/Dialog';
import { parseUnitPrice } from '../features/procedures/api';

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const clinic = {
  id: 7,
  name: 'Clínica de teste',
  created_at: '2026-10-20T12:00:00Z',
  updated_at: '2026-10-20T12:00:00Z',
};

function backend(options: { loseItemResponse?: boolean; denyPrice?: boolean } = {}) {
  const patients = [
    { id: 2, clinic: 7, full_name: 'Marina Teste', birth_date: '1990-01-01', email: '', phone: '' },
  ];
  const procedures = [
    { id: 3, name: 'Consulta', unit_price: '125.50', is_active: true },
    { id: 4, name: 'Complemento', unit_price: '25.00', is_active: true },
  ];
  const encounters = [
    {
      id: 10,
      clinic: 7,
      patient: 2,
      description: 'Atendimento existente',
      performed_at: '2026-10-20T12:00:00Z',
    },
  ];
  const items = [
    {
      id: 20,
      encounter: 10,
      procedure: 3,
      procedure_name: 'Consulta',
      quantity: 1,
      unit_price: '125.50',
      total: '125.50',
    },
  ];
  let lost = false;
  const fetchMock = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const url = String(input);
    const method = init.method ?? 'GET';
    const body = init.body ? JSON.parse(String(init.body)) : {};
    if (url.endsWith('/auth/token/')) return json({ token: 'operations-token' });
    if (url.endsWith('/auth/me/'))
      return json({
        id: 1,
        username: 'demo',
        email: 'demo@example.test',
        first_name: 'Ana',
        last_name: 'Teste',
      });
    if (url.endsWith('/auth/logout/')) return new Response(null, { status: 204 });
    if (url === '/api/v1/clinics/') return json([clinic]);
    if (url === '/api/v1/clinics/7/') return json(clinic);
    if (url.endsWith('/patients/')) {
      if (method === 'POST') {
        const patient = { ...body, id: patients.length + 2, clinic: 7 };
        patients.push(patient);
        return json(patient, 201);
      }
      return json(patients);
    }
    if (url.endsWith('/procedures/')) {
      if (method === 'POST') {
        if (options.denyPrice) return json({}, 403);
        const procedure = { ...body, id: procedures.length + 3 };
        procedures.push(procedure);
        return json(procedure, 201);
      }
      return json(procedures);
    }
    const procedureDetail = url.match(/\/procedures\/(\d+)\/$/);
    if (procedureDetail && method === 'PATCH') {
      const procedure = procedures.find((item) => item.id === Number(procedureDetail[1]))!;
      Object.assign(procedure, body);
      return json(procedure);
    }
    if (url.endsWith('/encounters/')) {
      if (method === 'POST') {
        if (!body.description?.trim()) return json({ description: ['Required.'] }, 400);
        const encounter = { ...body, id: encounters.length + 10, clinic: 7 };
        encounters.push(encounter);
        return json(encounter, 201);
      }
      return json(encounters);
    }
    const itemRoute = url.match(/\/encounters\/(\d+)\/items\/$/);
    if (itemRoute) {
      const encounter = Number(itemRoute[1]);
      if (method === 'POST') {
        const procedure = procedures.find((item) => item.id === body.procedure)!;
        const item = {
          id: items.length + 20,
          encounter,
          procedure: procedure.id,
          procedure_name: procedure.name,
          unit_price: procedure.unit_price,
          quantity: body.quantity,
          total: (Number(procedure.unit_price) * body.quantity).toFixed(2),
        };
        items.push(item);
        if (options.loseItemResponse && !lost) {
          lost = true;
          throw new TypeError('Synthetic response loss after item commit');
        }
        return json(item, 201);
      }
      return json(items.filter((item) => item.encounter === encounter));
    }
    const encounterDetail = url.match(/\/encounters\/(\d+)\/$/);
    if (encounterDetail)
      return json(encounters.find((item) => item.id === Number(encounterDetail[1])));
    if (/\/charges\/\d+\/$/.test(url)) return json({ detail: 'Not found.' }, 404);
    if (url.endsWith('/charges/')) return json([]);
    throw new Error('Unexpected operations test route: ' + method + ' ' + url);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { patients, procedures, encounters, items, fetchMock };
}

async function openPage(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: ['/entrar'] });
  const rendered = render(<App router={router} />);
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Usuário'), 'demo');
  await ui.type(screen.getByLabelText('Senha'), 'Synthetic-password-936!');
  await ui.click(screen.getByRole('button', { name: 'Entrar' }));
  await screen.findByRole('link', { name: /Clínica de teste/ });
  await act(() => router.navigate(path));
  return { router, ui, ...rendered };
}

beforeEach(() => vi.unstubAllGlobals());

describe('daily clinic workflow', () => {
  it('creates and edits an exact catalog price directly from its menu', async () => {
    const api = backend();
    const { ui } = await openPage('/clinicas/7/procedimentos');
    await ui.click(await screen.findByRole('button', { name: 'Novo procedimento' }));
    await ui.type(screen.getByLabelText('Nome do procedimento'), 'Avaliação');
    await ui.type(screen.getByLabelText('Preço unitário (R$)'), '180,35');
    await ui.click(screen.getByRole('button', { name: 'Salvar procedimento' }));
    await screen.findByRole('button', { name: 'Editar preço de Avaliação' });
    expect(api.procedures.at(-1)?.unit_price).toBe('180.35');
    await ui.click(screen.getByRole('button', { name: 'Editar preço de Avaliação' }));
    await ui.clear(screen.getByLabelText('Preço unitário (R$)'));
    await ui.type(screen.getByLabelText('Preço unitário (R$)'), '200,50');
    await ui.click(screen.getByRole('button', { name: 'Salvar procedimento' }));
    await screen.findByRole('button', { name: 'Editar preço de Avaliação' });
    expect(api.procedures.at(-1)?.unit_price).toBe('200.50');
    expect(api.items[0].unit_price).toBe('125.50');
  });

  it('creates a patient and price inside a new encounter, then opens its panel with the right total', async () => {
    const api = backend();
    const { router, ui } = await openPage('/clinicas/7/atendimentos');
    await ui.click(await screen.findByRole('button', { name: 'Novo atendimento' }));
    await ui.click(await screen.findByRole('button', { name: /Cadastrar paciente aqui/ }));
    await ui.type(screen.getByLabelText('Nome completo'), 'Paciente Novo');
    fireEvent.change(screen.getByLabelText('Data de nascimento'), {
      target: { value: '1992-06-15' },
    });
    await ui.click(screen.getByRole('button', { name: 'Salvar paciente' }));
    await screen.findByRole('dialog', { name: 'Novo atendimento' });
    expect(screen.getByLabelText('Paciente')).toHaveValue('3');
    await ui.click(screen.getByRole('button', { name: /Cadastrar procedimento e preço/ }));
    await ui.type(screen.getByLabelText('Nome do procedimento'), 'Avaliação Nova');
    await ui.type(screen.getByLabelText('Preço unitário (R$)'), '125,50');
    await ui.click(screen.getByRole('button', { name: 'Salvar procedimento' }));
    await screen.findByRole('dialog', { name: 'Novo atendimento' });
    fireEvent.change(screen.getByLabelText('Quantidade 1'), { target: { value: '2' } });
    expect(screen.getByText(/251,00/)).toBeInTheDocument();
    await ui.type(
      screen.getByLabelText('Descrição do atendimento'),
      'Consulta de avaliação fictícia',
    );
    await ui.click(screen.getByRole('button', { name: 'Salvar atendimento' }));
    expect(await screen.findByRole('dialog', { name: 'Atendimento #11' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/clinicas/7/atendimentos/11');
    expect(api.encounters.at(-1)?.patient).toBe(3);
    expect(api.items.at(-1)).toMatchObject({
      encounter: 11,
      quantity: 2,
      unit_price: '125.50',
      total: '251.00',
    });
  });

  it('closes encounter details back to the same searched list', async () => {
    backend();
    const { router, ui } = await openPage('/clinicas/7/atendimentos');
    const search = await screen.findByLabelText('Buscar atendimento');
    await ui.type(search, 'Marina');
    await ui.click(screen.getByRole('link', { name: 'Ver atendimento #10' }));
    await screen.findByRole('dialog', { name: 'Atendimento #10' });
    await ui.click(screen.getByRole('button', { name: 'Fechar atendimento #10' }));
    expect(router.state.location.pathname).toBe('/clinicas/7/atendimentos');
    expect(screen.getByLabelText('Buscar atendimento')).toHaveValue('Marina');
    expect(screen.getByRole('link', { name: 'Ver atendimento #10' })).toBeInTheDocument();
  });

  it('resumes partially saved items without creating a second encounter or duplicate item', async () => {
    const api = backend({ loseItemResponse: true });
    const { ui } = await openPage('/clinicas/7/atendimentos');
    await ui.click(await screen.findByRole('button', { name: 'Novo atendimento' }));
    await ui.selectOptions(await screen.findByLabelText('Paciente'), '2');
    await ui.selectOptions(screen.getByLabelText('Procedimento 1'), '3');
    await ui.click(screen.getByRole('button', { name: 'Adicionar procedimento' }));
    await ui.selectOptions(screen.getByLabelText('Procedimento 2'), '4');
    await ui.type(
      screen.getByLabelText('Descrição do atendimento'),
      'Consulta de avaliação fictícia',
    );
    await ui.click(screen.getByRole('button', { name: 'Salvar atendimento' }));
    await screen.findByRole('alert');
    await ui.click(screen.getByRole('button', { name: 'Concluir itens do atendimento' }));
    await screen.findByRole('dialog', { name: 'Atendimento #11' });
    expect(api.encounters).toHaveLength(2);
    expect(api.items.filter((item) => item.encounter === 11)).toHaveLength(2);
    expect(
      api.fetchMock.mock.calls.filter(
        ([url, init]) => String(url).endsWith('/encounters/') && init?.method === 'POST',
      ),
    ).toHaveLength(1);
  });

  it('keeps the procedure form open with a clear owner-permission error', async () => {
    backend({ denyPrice: true });
    const { ui } = await openPage('/clinicas/7/procedimentos');
    await ui.click(await screen.findByRole('button', { name: 'Novo procedimento' }));
    await ui.type(screen.getByLabelText('Nome do procedimento'), 'Consulta');
    await ui.type(screen.getByLabelText('Preço unitário (R$)'), '0,00');
    await ui.click(screen.getByRole('button', { name: 'Salvar procedimento' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Somente proprietários da clínica');
    expect(screen.getByRole('dialog', { name: 'Novo procedimento e preço' })).toBeInTheDocument();
  });
});

describe('price input and modal boundaries', () => {
  it('normalizes decimal input without floating point and rejects ambiguous or oversized values', () => {
    expect(parseUnitPrice('180,35')).toBe('180.35');
    expect(parseUnitPrice('0')).toBe('0.00');
    expect(parseUnitPrice('9999999999,99')).toBe('9999999999.99');
    expect(parseUnitPrice('1.234,56')).toBeNull();
    expect(parseUnitPrice('10000000000')).toBeNull();
    expect(parseUnitPrice('-1')).toBeNull();
  });

  it('restores the application accessibility and body scrolling when nested panels unmount together', async () => {
    function Nested() {
      const [child, setChild] = useState(false);
      return (
        <>
          <Dialog title="Parent" close={() => {}}>
            <button onClick={() => setChild(true)}>Open child</button>
          </Dialog>
          {child && (
            <Dialog title="Child" close={() => setChild(false)}>
              Child content
            </Dialog>
          )}
        </>
      );
    }
    const previousOverflow = document.body.style.overflow;
    const rendered = render(<Nested />);
    await userEvent.click(screen.getByRole('button', { name: 'Open child' }));
    expect(screen.getByRole('dialog', { name: 'Child' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Parent' })).not.toBeInTheDocument();
    rendered.unmount();
    expect(rendered.container).not.toHaveAttribute('aria-hidden');
    expect(document.body.style.overflow).toBe(previousOverflow);
  });
});

describe('persistent workspace navigation', () => {
  it.each([
    ['atendimentos', 'Atendimentos'],
    ['pacientes', 'Pacientes'],
    ['procedimentos', 'Procedimentos e preços'],
    ['cobrancas', 'Cobranças'],
  ])('opens %s through clinic selection without changing the menu', async (path, label) => {
    backend();
    const { router, ui } = await openPage('/clinicas');
    const navigation = screen.getByRole('navigation', { name: 'Navegação principal' });
    const labelsBefore = within(navigation)
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(labelsBefore).toHaveLength(5);
    await ui.click(within(navigation).getByRole('link', { name: label }));
    expect(router.state.location.search).toBe(`?area=${path}`);
    expect(screen.getByRole('heading', { level: 1, name: label })).toBeInTheDocument();
    expect(within(navigation).getByRole('link', { name: label })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(navigation).getByRole('link', { name: /Minhas clínicas/ })).not.toHaveAttribute(
      'aria-current',
    );

    await ui.click(screen.getByRole('button', { name: 'Atualizar lista de clínicas' }));
    expect(router.state.location.search).toBe(`?area=${path}`);
    await ui.click(await screen.findByRole('link', { name: /Clínica de teste/ }));
    await screen.findByRole('heading', { level: 1, name: label });
    expect(router.state.location.pathname).toBe(`/clinicas/7/${path}`);
    expect(
      within(navigation)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(labelsBefore);
    expect(within(navigation).getByRole('link', { name: label })).toHaveAttribute(
      'href',
      `/clinicas/7/${path}`,
    );
  });

  it('returns to the clinic and then its directory using the breadcrumb links', async () => {
    backend();
    const { router, ui } = await openPage('/clinicas/7/procedimentos');
    await screen.findByRole('heading', { level: 1, name: 'Procedimentos e preços' });
    const breadcrumb = () => screen.getByRole('navigation', { name: 'Caminho de navegação' });
    expect(within(breadcrumb()).getByText('Procedimentos e preços')).toHaveAttribute(
      'aria-current',
      'page',
    );
    await ui.click(within(breadcrumb()).getByRole('link', { name: clinic.name }));
    await screen.findByRole('heading', { name: clinic.name });
    expect(router.state.location.pathname).toBe('/clinicas/7');
    expect(within(breadcrumb()).getByText(clinic.name)).toHaveAttribute('aria-current', 'page');
    await ui.click(within(breadcrumb()).getByRole('link', { name: 'Minhas clínicas' }));
    expect(router.state.location.pathname).toBe('/clinicas');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Minhas clínicas' }),
    ).toBeInTheDocument();
    expect(within(breadcrumb()).getByText('Minhas clínicas')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(breadcrumb()).queryByRole('link')).not.toBeInTheDocument();
  });

  it('offers the charge collection as a parent even when charge detail is unavailable', async () => {
    backend();
    const { router, ui } = await openPage('/clinicas/7/cobrancas/31');
    await screen.findByRole('alert');
    const breadcrumb = screen.getByRole('navigation', { name: 'Caminho de navegação' });
    expect(within(breadcrumb).getByText('Cobrança #31')).toHaveAttribute('aria-current', 'page');
    await ui.click(within(breadcrumb).getByRole('link', { name: 'Cobranças' }));
    expect(router.state.location.pathname).toBe('/clinicas/7/cobrancas');
    expect(await screen.findByRole('heading', { level: 1, name: 'Cobranças' })).toBeInTheDocument();
  });
});
