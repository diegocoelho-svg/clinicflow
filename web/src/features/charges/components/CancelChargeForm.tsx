import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAsyncForm } from '../../../shared/hooks/useAsyncForm';
import { Notice } from '../../../shared/ui/Notice';
import { useClinicAccess } from '../../clinics/hooks/useClinicAccess';
import { chargeApi } from '../api';
import { useChargeOperations } from '../context';
import type { Charge } from '../types';

export function CancelChargeForm({ charge }: { charge: Charge }) {
  const auth = useClinicAccess();
  const operations = useChargeOperations();
  const form = useAsyncForm();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const textarea = useRef<HTMLTextAreaElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) textarea.current?.focus();
  }, [open]);
  if (!['PENDING', 'NO_PAYMENT_REQUIRED'].includes(charge.status)) return null;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return;
    const result = await form.submit((signal) =>
      chargeApi.cancel(charge.clinic, charge.id, reason, auth, signal),
    );
    if (result) operations.refresh();
  }
  const id = `cancel-charge-${charge.id}`;
  return (
    <section className="billing-section cancellation-section" aria-labelledby={`${id}-heading`}>
      <h3 id={`${id}-heading`}>Corrigir esta cobrança</h3>
      <p className="muted">
        Somente proprietários da clínica podem cancelar. O histórico será preservado e os itens do
        atendimento poderão ser corrigidos.
      </p>
      {!open ? (
        <button
          ref={trigger}
          className="button secondary danger"
          aria-expanded={false}
          aria-controls={id}
          onClick={() => setOpen(true)}
        >
          Cancelar cobrança
        </button>
      ) : (
        <form id={id} aria-label="Confirmar cancelamento da cobrança" onSubmit={submit}>
          {form.error && <Notice>{form.error}</Notice>}
          <fieldset disabled={form.pending}>
            <div className="field">
              <label htmlFor={`${id}-reason`}>Motivo do cancelamento</label>
              <textarea
                ref={textarea}
                id={`${id}-reason`}
                name="reason"
                required
                maxLength={1000}
                rows={3}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                aria-invalid={Boolean(form.fields.reason)}
                aria-describedby={`${id}-hint${form.fields.reason ? ` ${id}-error` : ''}`}
              />
              <small id={`${id}-hint`}>
                Explique a correção necessária em até 1.000 caracteres.
              </small>
              {form.fields.reason && (
                <small className="field-error" id={`${id}-error`}>
                  {form.fields.reason}
                </small>
              )}
            </div>
            <div className="action-row">
              <button className="button secondary danger" type="submit" disabled={!reason.trim()}>
                {form.pending ? 'Cancelando…' : 'Confirmar cancelamento'}
              </button>
              <button
                className="text-button"
                type="button"
                onClick={() => {
                  setOpen(false);
                  queueMicrotask(() => trigger.current?.focus());
                }}
              >
                Voltar sem cancelar
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}
