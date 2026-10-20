import { useState, type FormEvent } from 'react';
import { useAsyncForm } from '../../../shared/hooks/useAsyncForm';
import { Field } from '../../../shared/ui/Field';
import { Notice } from '../../../shared/ui/Notice';
import { clinicApi } from '../api';
import { useClinicDirectory } from '../context';
import { useClinicAccess } from '../hooks/useClinicAccess';

export function CreateClinicForm() {
  const access = useClinicAccess();
  const directory = useClinicDirectory();
  const form = useAsyncForm();
  const [name, setName] = useState('');
  const [nameError, setNameError] = useState('');
  const [created, setCreated] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreated(false);
    setNameError('');
    if (!name.trim()) {
      setNameError('Informe o nome da clínica.');
      return;
    }
    const result = await form.submit((signal) => clinicApi.create(name, access, signal));
    if (result) {
      directory.addClinic(result.data);
      setName('');
      setCreated(true);
    }
  }

  return (
    <div className="create-clinic">
      <h3>Adicionar uma clínica</h3>
      <p className="muted">Ao criar, você será responsável por esta clínica.</p>
      {form.error && <Notice>{form.error}</Notice>}
      {created && (
        <Notice kind="success">Clínica criada. Selecione-a na lista para abrir seu espaço.</Notice>
      )}
      <form onSubmit={submit} aria-busy={form.pending}>
        <fieldset disabled={form.pending || directory.loading || Boolean(directory.error)}>
          <Field
            label="Nome da clínica"
            name="name"
            placeholder="Ex.: Clínica Horizonte"
            required
            maxLength={255}
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={nameError || form.fields.name}
          />
          <button className="button secondary full" type="submit">
            {form.pending ? 'Criando clínica…' : 'Criar clínica'}
            <span aria-hidden="true">+</span>
          </button>
        </fieldset>
      </form>
    </div>
  );
}
