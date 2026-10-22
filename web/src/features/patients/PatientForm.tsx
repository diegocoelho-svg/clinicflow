import { useEffect, useState, type FormEvent } from 'react';
import { Field } from '../../shared/ui/Field';
import { Notice } from '../../shared/ui/Notice';
import { useAsyncForm } from '../../shared/hooks/useAsyncForm';
import { useClinicAccess } from '../clinics/hooks/useClinicAccess';
import { patientApi, type Patient } from './api';

export function PatientForm({
  clinic,
  patient,
  saved,
  cancel,
  onBusyChange,
}: {
  clinic: number;
  patient?: Patient;
  saved: (patient: Patient) => void;
  cancel: () => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const auth = useClinicAccess();
  const form = useAsyncForm();
  useEffect(() => onBusyChange?.(form.pending), [form.pending, onBusyChange]);
  const [name, setName] = useState(patient?.full_name ?? '');
  const [birthDate, setBirthDate] = useState(patient?.birth_date ?? '');
  const [email, setEmail] = useState(patient?.email ?? '');
  const [phone, setPhone] = useState(patient?.phone ?? '');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = await form.submit((signal) =>
      patientApi.save(
        clinic,
        patient?.id,
        { full_name: name.trim(), birth_date: birthDate, email: email.trim(), phone: phone.trim() },
        auth,
        signal,
      ),
    );
    if (result) {
      onBusyChange?.(false);
      saved(result.data);
    }
  }
  return (
    <form onSubmit={submit} aria-label={patient ? 'Editar paciente' : 'Cadastrar paciente'}>
      {form.error && <Notice>{form.error}</Notice>}
      <fieldset disabled={form.pending}>
        <Field
          autoFocus
          label="Nome completo"
          name="patient-name"
          required
          maxLength={255}
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={form.fields.full_name}
        />
        <Field
          label="Data de nascimento"
          name="patient-birth-date"
          type="date"
          required
          value={birthDate}
          onChange={(event) => setBirthDate(event.target.value)}
          error={form.fields.birth_date}
        />
        <div className="field-row">
          <Field
            label="E-mail (opcional)"
            name="patient-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={form.fields.email}
          />
          <Field
            label="Telefone (opcional)"
            name="patient-phone"
            type="tel"
            maxLength={30}
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            error={form.fields.phone}
          />
        </div>
        <div className="form-actions">
          <button className="button primary" type="submit" disabled={!name.trim() || !birthDate}>
            {form.pending ? 'Salvando…' : 'Salvar paciente'}
          </button>
          <button className="text-button" type="button" onClick={cancel}>
            Cancelar
          </button>
        </div>
      </fieldset>
    </form>
  );
}
