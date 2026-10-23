import { beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter } from 'react-router';
import { App } from '../app/App';
import { routes } from '../app/router';

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const clinic = {
  id: 7,
  name: 'Review clinic',
  created_at: '2026-10-20T12:00:00Z',
  updated_at: '2026-10-20T12:00:00Z',
};
function backend(
  options: { losePatient?: boolean; loseProcedure?: boolean; rejectPatientOnce?: boolean } = {},
) {
  const patients = [
    {
      id: 2,
      clinic: 7,
      full_name: 'Review patient',
      birth_date: '1990-01-01',
      email: '',
      phone: '',
    },
  ];
  const procedures = [
    { id: 3, clinic: 7, name: 'Consulta', unit_price: '10.00', is_active: true },
    { id: 4, clinic: 7, name: 'Exame', unit_price: '20.00', is_active: true },
  ];
  const encounter = {
    id: 10,
    clinic: 7,
    patient: 2,
    description: 'Review encounter',
    performed_at: '2026-10-20T12:00:00Z',
  };
  const items = procedures.map((p, i) => ({
    id: 20 + i,
    encounter: 10,
    procedure: p.id,
    procedure_name: p.name,
    quantity: 1,
    unit_price: p.unit_price,
    total: p.unit_price,
  }));
  let patientResponseLost = false;
  let patientRejected = false;
  let procedureResponseLost = false;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method || 'GET';
      const body = init.body ? JSON.parse(String(init.body)) : {};
      if (url.endsWith('/auth/token/')) return json({ token: 'isolated-review-token' });
      if (url.endsWith('/auth/me/'))
        return json({
          id: 1,
          username: 'review',
          email: 'review@example.test',
          first_name: 'Review',
          last_name: 'Test',
        });
      if (url === '/api/v1/clinics/') return json([clinic]);
      if (url === '/api/v1/clinics/7/') return json(clinic);
      if (url.endsWith('/patients/')) {
        if (method === 'POST') {
          if (options.rejectPatientOnce && !patientRejected) {
            patientRejected = true;
            return json({ full_name: ['Synthetic validation rejection'] }, 400);
          }
          const patient = { ...body, clinic: 7, id: patients.length + 2 };
          patients.push(patient);
          if (options.losePatient && !patientResponseLost) {
            patientResponseLost = true;
            throw new TypeError('Response lost after committed patient');
          }
          return json(patient, 201);
        }
        return json(patients);
      }
      if (url.endsWith('/procedures/')) {
        if (method === 'POST') {
          const procedure = { ...body, clinic: 7, id: procedures.length + 3 };
          procedures.push(procedure);
          if (options.loseProcedure && !procedureResponseLost) {
            procedureResponseLost = true;
            throw new TypeError('Response lost after committed procedure');
          }
          return json(procedure, 201);
        }
        return json(procedures);
      }
      if (url.endsWith('/encounters/')) return json([encounter]);
      if (url.endsWith('/encounters/10/')) return json(encounter);
      if (url.endsWith('/encounters/10/items/')) return json(items);
      const detail = url.match(/\/items\/(\d+)\/$/);
      if (detail && method === 'PATCH') {
        const item = items.find((i) => i.id === Number(detail[1]))!;
        item.quantity = body.quantity;
        item.total = (Number(item.unit_price) * item.quantity).toFixed(2);
        return json(item);
      }
      if (url.endsWith('/charges/')) return json([]);
      throw new Error('Unexpected review route: ' + method + ' ' + url);
    }),
  );
  return { patients, procedures, items };
}

async function open(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: ['/entrar'] });
  render(<App router={router} />);
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Usuário'), 'review');
  await ui.type(screen.getByLabelText('Senha'), 'Fictional-review-password!2026');
  await ui.click(screen.getByRole('button', { name: 'Entrar' }));
  await screen.findByRole('link', { name: /Review clinic/ });
  await act(() => router.navigate(path));
  return ui;
}
beforeEach(() => vi.unstubAllGlobals());

it('keeps the unsaved quantity of a second item when the first one is saved', async () => {
  const api = backend();
  const ui = await open('/clinicas/7/atendimentos/10');
  await ui.click(await screen.findByRole('button', { name: 'Editar itens' }));
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantidade de Consulta' }), {
    target: { value: '3' },
  });
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantidade de Exame' }), {
    target: { value: '5' },
  });
  await ui.click(screen.getAllByRole('button', { name: 'Salvar quantidade' })[0]);
  await waitFor(() => expect(api.items[0].quantity).toBe(3));
  await waitFor(() =>
    expect(screen.getAllByRole('button', { name: 'Salvar quantidade' })[0]).toBeDisabled(),
  );
  const secondDraft = await screen.findByRole('spinbutton', { name: 'Quantidade de Exame' });
  expect(secondDraft).toHaveValue(5);
});

it('blocks a duplicate patient after a lost response and reloads the saved record', async () => {
  const api = backend({ losePatient: true });
  const ui = await open('/clinicas/7/pacientes');
  await ui.click(await screen.findByRole('button', { name: 'Novo paciente' }));
  await ui.type(screen.getByLabelText('Nome completo'), 'New review patient');
  fireEvent.change(screen.getByLabelText('Data de nascimento'), {
    target: { value: '1990-02-03' },
  });
  await ui.click(screen.getByRole('button', { name: 'Salvar paciente' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Salvar paciente' })).toBeDisabled();
  await act(async () => {
    fireEvent.submit(screen.getByRole('form', { name: 'Cadastrar paciente' }));
  });
  expect(api.patients.filter((p) => p.full_name === 'New review patient')).toHaveLength(1);
  await ui.click(screen.getByRole('button', { name: 'Conferir pacientes' }));
  await screen.findByRole('button', { name: 'Editar paciente New review patient' });
  expect(api.patients.filter((p) => p.full_name === 'New review patient')).toHaveLength(1);
});

it('blocks a duplicate catalog entry after a lost response and reloads its price', async () => {
  const api = backend({ loseProcedure: true });
  const ui = await open('/clinicas/7/procedimentos');
  await ui.click(await screen.findByRole('button', { name: 'Novo procedimento' }));
  await ui.type(screen.getByLabelText('Nome do procedimento'), 'New review procedure');
  await ui.type(screen.getByLabelText('Preço unitário (R$)'), '50,00');
  await ui.click(screen.getByRole('button', { name: 'Salvar procedimento' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Salvar procedimento' })).toBeDisabled();
  await act(async () => {
    fireEvent.submit(screen.getByRole('form', { name: 'Cadastrar procedimento e preço' }));
  });
  expect(api.procedures.filter((p) => p.name === 'New review procedure')).toHaveLength(1);
  await ui.click(screen.getByRole('button', { name: 'Conferir procedimentos' }));
  await screen.findByRole('button', { name: 'Editar preço de New review procedure' });
  expect(api.procedures.filter((p) => p.name === 'New review procedure')).toHaveLength(1);
});

it('recovers an inline patient after response loss without clearing encounter drafts', async () => {
  const api = backend({ losePatient: true });
  const ui = await open('/clinicas/7/atendimentos');
  await ui.click(await screen.findByRole('button', { name: 'Novo atendimento' }));
  await ui.type(
    await screen.findByLabelText('Descrição do atendimento'),
    'Keep this encounter draft',
  );
  await ui.click(screen.getByRole('button', { name: /Cadastrar paciente aqui/ }));
  await ui.type(screen.getByLabelText('Nome completo'), 'Recovered inline patient');
  fireEvent.change(screen.getByLabelText('Data de nascimento'), {
    target: { value: '1990-02-03' },
  });
  await ui.click(screen.getByRole('button', { name: 'Salvar paciente' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Salvar paciente' })).toBeDisabled();
  await ui.click(screen.getByRole('button', { name: 'Conferir pacientes' }));
  await screen.findByRole('option', { name: 'Recovered inline patient' });
  expect(screen.getByLabelText('Descrição do atendimento')).toHaveValue(
    'Keep this encounter draft',
  );
  await ui.selectOptions(screen.getByLabelText('Paciente'), '3');
  expect(api.patients.filter((p) => p.full_name === 'Recovered inline patient')).toHaveLength(1);
});

it('recovers an inline price after response loss without clearing selected items', async () => {
  const api = backend({ loseProcedure: true });
  const ui = await open('/clinicas/7/atendimentos');
  await ui.click(await screen.findByRole('button', { name: 'Novo atendimento' }));
  await ui.selectOptions(await screen.findByLabelText('Procedimento 1'), '3');
  fireEvent.change(screen.getByLabelText('Quantidade 1'), { target: { value: '2' } });
  await ui.type(screen.getByLabelText('Descrição do atendimento'), 'Keep these items');
  await ui.click(screen.getByRole('button', { name: /Cadastrar procedimento e preço/ }));
  await ui.type(screen.getByLabelText('Nome do procedimento'), 'Recovered inline procedure');
  await ui.type(screen.getByLabelText('Preço unitário (R$)'), '50,00');
  await ui.click(screen.getByRole('button', { name: 'Salvar procedimento' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Salvar procedimento' })).toBeDisabled();
  await ui.click(screen.getByRole('button', { name: 'Conferir procedimentos' }));
  await screen.findByRole('option', { name: /Recovered inline procedure/ });
  expect(screen.getByLabelText('Descrição do atendimento')).toHaveValue('Keep these items');
  expect(screen.getByLabelText('Procedimento 1')).toHaveValue('3');
  expect(screen.getByLabelText('Quantidade 1')).toHaveValue(2);
  expect(api.procedures.filter((p) => p.name === 'Recovered inline procedure')).toHaveLength(1);
});

it('permits a corrected retry after an explicit validation rejection', async () => {
  const api = backend({ rejectPatientOnce: true });
  const ui = await open('/clinicas/7/pacientes');
  await ui.click(await screen.findByRole('button', { name: 'Novo paciente' }));
  await ui.type(screen.getByLabelText('Nome completo'), 'Validated retry patient');
  fireEvent.change(screen.getByLabelText('Data de nascimento'), {
    target: { value: '1990-02-03' },
  });
  await ui.click(screen.getByRole('button', { name: 'Salvar paciente' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Salvar paciente' })).toBeEnabled();
  await ui.click(screen.getByRole('button', { name: 'Salvar paciente' }));
  await screen.findByRole('button', { name: 'Editar paciente Validated retry patient' });
  expect(api.patients.filter((p) => p.full_name === 'Validated retry patient')).toHaveLength(1);
});
