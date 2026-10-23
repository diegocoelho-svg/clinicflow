import { useEffect, useState, type FormEvent } from 'react';
import { Field } from '../../shared/ui/Field';
import { Notice } from '../../shared/ui/Notice';
import { useAsyncForm } from '../../shared/hooks/useAsyncForm';
import { useClinicAccess } from '../clinics/hooks/useClinicAccess';
import type { Procedure } from '../encounters/types';
import { procedureApi, parseUnitPrice } from './api';

export function ProcedureForm({
  clinic,
  procedure,
  saved,
  cancel,
  onBusyChange,
}: {
  clinic: number;
  procedure?: Procedure;
  saved: (procedure: Procedure) => void;
  cancel: () => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const auth = useClinicAccess();
  const form = useAsyncForm({ guardCreation: !procedure });
  useEffect(() => onBusyChange?.(form.pending), [form.pending, onBusyChange]);
  const [name, setName] = useState(procedure?.name ?? '');
  const [price, setPrice] = useState(procedure?.unit_price.replace('.', ',') ?? '');
  const [active, setActive] = useState(procedure?.is_active ?? true);
  const [priceError, setPriceError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = parseUnitPrice(price);
    if (amount === null) {
      setPriceError('Informe um preço válido. Exemplo: 180,00.');
      return;
    }
    setPriceError('');
    const result = await form.submit((signal) =>
      procedureApi.save(
        clinic,
        procedure?.id,
        { name: name.trim(), unit_price: amount, is_active: active },
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
    <form
      onSubmit={submit}
      aria-label={procedure ? 'Editar procedimento e preço' : 'Cadastrar procedimento e preço'}
    >
      {form.error && <Notice>{form.error}</Notice>}
      <fieldset disabled={form.pending || form.uncertain}>
        <Field
          autoFocus
          label="Nome do procedimento"
          name="procedure-name"
          placeholder="Ex.: Consulta, avaliação, retorno"
          required
          maxLength={255}
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={form.fields.name}
        />
        <Field
          label="Preço unitário (R$)"
          name="procedure-price"
          inputMode="decimal"
          placeholder="180,00"
          required
          maxLength={13}
          value={price}
          onChange={(event) => setPrice(event.target.value)}
          error={priceError || form.fields.unit_price}
          hint="Use vírgula para os centavos, sem separador de milhar. Zero é permitido."
        />
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={active}
            onChange={(event) => setActive(event.target.checked)}
          />
          Disponível para novos atendimentos
        </label>
        <p className="muted form-hint">
          O preço é copiado ao adicionar o procedimento a um atendimento. Alterar o catálogo
          preserva os valores dos itens já registrados.
        </p>
        <div className="form-actions">
          <button className="button primary" type="submit" disabled={!name.trim() || !price.trim()}>
            {form.pending ? 'Salvando…' : 'Salvar procedimento'}
          </button>
          <button className="text-button" type="button" onClick={cancel}>
            Cancelar
          </button>
        </div>
      </fieldset>
      {form.uncertain && (
        <>
          <Notice kind="info">
            O cadastro pode ter sido salvo. Confira a lista antes de cadastrar novamente.
          </Notice>
          <button className="button secondary" type="button" onClick={cancel}>
            Conferir procedimentos
          </button>
        </>
      )}
    </form>
  );
}
