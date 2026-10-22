import { useCallback, useState } from 'react';
import { useResource } from '../../shared/hooks/useResource';
import { Dialog } from '../../shared/ui/Dialog';
import { PageHeading } from '../../shared/ui/PageHeading';
import { ResourceMessage } from '../../shared/ui/ResourceMessage';
import { Notice } from '../../shared/ui/Notice';
import { useActiveClinic } from '../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../clinics/hooks/useClinicAccess';
import { patientApi, type Patient } from './api';
import { PatientForm } from './PatientForm';

export function PatientsPage() {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Patient | 'new' | null>(null);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => patientApi.list(clinic.id, auth, signal),
    [clinic.id, auth],
  );
  const { state, retry } = useResource(`${clinic.id}:patients`, load);
  const patients =
    state.status === 'success'
      ? state.data.filter((patient) =>
          `${patient.full_name} ${patient.email}`
            .toLocaleLowerCase('pt-BR')
            .includes(search.toLocaleLowerCase('pt-BR')),
        )
      : [];
  return (
    <>
      <header className="operations-heading">
        <div>
          <PageHeading level={1} focusKey={`${clinic.id}:patients`}>
            Pacientes
          </PageHeading>
          <p className="muted">Cadastre os pacientes e mantenha os dados de contato à mão.</p>
        </div>
        <button className="button primary" onClick={() => setEditing('new')}>
          Novo paciente
        </button>
      </header>
      {notice && <Notice kind="success">{notice}</Notice>}
      <div className="collection-toolbar">
        <div className="field">
          <label htmlFor="patient-search">Buscar paciente</label>
          <input
            id="patient-search"
            type="search"
            placeholder="Nome ou e-mail"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <button className="button subtle" onClick={retry} disabled={state.status === 'loading'}>
          Atualizar pacientes
        </button>
      </div>
      <ResourceMessage state={state} label="pacientes" retry={retry} />
      {state.status === 'success' && (
        <div className="table-scroll">
          <table className="data-table collection-table">
            <caption>{patients.length} paciente(s)</caption>
            <thead>
              <tr>
                <th>Paciente</th>
                <th>Nascimento</th>
                <th>Contato</th>
                <th>
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {patients.map((patient) => (
                <tr key={patient.id}>
                  <th scope="row">{patient.full_name}</th>
                  <td>{patient.birth_date.split('-').reverse().join('/')}</td>
                  <td>{patient.email || patient.phone || 'Não informado'}</td>
                  <td>
                    <button
                      className="button subtle"
                      onClick={() => setEditing(patient)}
                      aria-label={`Editar paciente ${patient.full_name}`}
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {patients.length === 0 && (
            <p className="operations-empty">
              {search
                ? 'Nenhum paciente encontrado.'
                : 'Cadastre o primeiro paciente para registrar um atendimento.'}
            </p>
          )}
        </div>
      )}
      {editing && (
        <Dialog
          busy={saving}
          title={editing === 'new' ? 'Novo paciente' : 'Editar paciente'}
          close={() => setEditing(null)}
        >
          <PatientForm
            onBusyChange={setSaving}
            clinic={clinic.id}
            patient={editing === 'new' ? undefined : editing}
            cancel={() => setEditing(null)}
            saved={(patient) => {
              setEditing(null);
              setNotice(`${patient.full_name}: dados salvos.`);
              retry();
            }}
          />
        </Dialog>
      )}
    </>
  );
}
