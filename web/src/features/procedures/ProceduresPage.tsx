import { useCallback, useState } from 'react';
import { useResource } from '../../shared/hooks/useResource';
import { money } from '../../shared/format/money';
import { Dialog } from '../../shared/ui/Dialog';
import { Notice } from '../../shared/ui/Notice';
import { PageHeading } from '../../shared/ui/PageHeading';
import { ResourceMessage } from '../../shared/ui/ResourceMessage';
import { useActiveClinic } from '../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../clinics/hooks/useClinicAccess';
import type { Procedure } from '../encounters/types';
import { procedureApi } from './api';
import { ProcedureForm } from './ProcedureForm';

export function ProceduresPage() {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Procedure | 'new' | null>(null);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => procedureApi.list(clinic.id, auth, signal),
    [clinic.id, auth],
  );
  const { state, retry } = useResource(`${clinic.id}:procedures`, load);
  const procedures =
    state.status === 'success'
      ? state.data.filter((item) =>
          item.name.toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR')),
        )
      : [];
  return (
    <>
      <header className="operations-heading">
        <div>
          <PageHeading level={1} focusKey={`${clinic.id}:procedures`}>
            Procedimentos e preços
          </PageHeading>
          <p className="muted">Defina os serviços da clínica e o preço de cada unidade.</p>
        </div>
        <button className="button primary" onClick={() => setEditing('new')}>
          Novo procedimento
        </button>
      </header>
      {notice && <Notice kind="success">{notice}</Notice>}
      <div className="collection-toolbar">
        <div className="field">
          <label htmlFor="procedure-search">Buscar procedimento</label>
          <input
            id="procedure-search"
            type="search"
            placeholder="Nome do procedimento"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <button className="button subtle" onClick={retry} disabled={state.status === 'loading'}>
          Atualizar procedimentos
        </button>
      </div>
      <ResourceMessage state={state} label="procedimentos" retry={retry} />
      {state.status === 'success' && (
        <div className="table-scroll">
          <table className="data-table collection-table">
            <caption>{procedures.length} procedimento(s)</caption>
            <thead>
              <tr>
                <th>Procedimento</th>
                <th>Preço unitário</th>
                <th>Situação</th>
                <th>
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {procedures.map((procedure) => (
                <tr key={procedure.id}>
                  <th scope="row">{procedure.name}</th>
                  <td className="money">{money(procedure.unit_price)}</td>
                  <td>
                    <span
                      className={`charge-status ${procedure.is_active ? 'status-no_payment_required' : 'status-cancelled'}`}
                    >
                      {procedure.is_active ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                  <td>
                    <button
                      className="button subtle"
                      onClick={() => setEditing(procedure)}
                      aria-label={`Editar preço de ${procedure.name}`}
                    >
                      Editar preço e dados
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {procedures.length === 0 && (
            <p className="operations-empty">
              {search
                ? 'Nenhum procedimento encontrado.'
                : 'Cadastre o primeiro procedimento e seu preço para montar os atendimentos.'}
            </p>
          )}
        </div>
      )}
      <p className="muted form-hint">
        O cadastro e a alteração de preços são exclusivos de proprietários da clínica.
      </p>
      {editing && (
        <Dialog
          busy={saving}
          title={editing === 'new' ? 'Novo procedimento e preço' : 'Editar procedimento e preço'}
          close={() => setEditing(null)}
        >
          <ProcedureForm
            onBusyChange={setSaving}
            clinic={clinic.id}
            procedure={editing === 'new' ? undefined : editing}
            cancel={() => setEditing(null)}
            saved={(procedure) => {
              setEditing(null);
              setNotice(`${procedure.name}: preço e dados salvos.`);
              retry();
            }}
          />
        </Dialog>
      )}
    </>
  );
}
