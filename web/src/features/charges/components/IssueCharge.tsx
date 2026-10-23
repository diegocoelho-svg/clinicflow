import { Link } from 'react-router';
import { Notice } from '../../../shared/ui/Notice';
import { money } from '../../../shared/format/money';
import { issuanceScope, useChargeOperations } from '../context';
import type { Charge } from '../types';
import { statusLabel } from '../types';

export function IssueCharge({
  clinic,
  encounter,
  active,
  total,
  itemCount,
  editing,
}: {
  clinic: number;
  encounter: number;
  active: Charge | undefined;
  total: string | null;
  itemCount: number;
  editing: boolean;
}) {
  const operations = useChargeOperations();
  const intent = operations.intents.get(issuanceScope(clinic, encounter));
  const retryUncertain = intent?.status === 'uncertain';
  const pending = intent?.status === 'pending';
  return (
    <section className="billing-section" aria-labelledby="issuance-heading">
      <h3 id="issuance-heading">Emissão da cobrança</h3>
      {intent?.status === 'confirmed' && (
        <Notice kind="success">
          Emissão da cobrança #{intent.charge.id} confirmada. Veja a situação atual no histórico.
        </Notice>
      )}
      {(intent?.status === 'uncertain' || intent?.status === 'rejected') && (
        <Notice>{intent.message}</Notice>
      )}
      {active ? (
        <p>
          Este atendimento possui uma cobrança {statusLabel(active.status).toLowerCase()}.{' '}
          <Link to={`/clinicas/${clinic}/cobrancas/${active.id}`}>Ver cobrança #{active.id}</Link>.
        </p>
      ) : (
        <>
          <div className="amount-summary">
            <span>Total dos itens</span>
            <strong className="money">
              {total === null ? 'Valor indisponível' : money(total)}
            </strong>
          </div>
          <p className="muted">
            Confira os itens antes de emitir. A cobrança registra os valores salvos e bloqueia
            alterações até ser cancelada.
          </p>
        </>
      )}
      {editing && <p className="muted">Conclua a edição dos itens antes de emitir.</p>}
      {!active && itemCount === 0 && (
        <p className="muted">Adicione pelo menos um procedimento para emitir uma cobrança.</p>
      )}
      {(!active || retryUncertain || pending) && (
        <button
          className="button primary"
          disabled={
            pending ||
            editing ||
            (!retryUncertain && (Boolean(active) || itemCount === 0 || total === null))
          }
          onClick={() => void operations.issue(clinic, encounter)}
        >
          {pending
            ? 'Confirmando emissão…'
            : retryUncertain
              ? 'Verificar emissão'
              : intent?.status === 'rejected'
                ? 'Tentar emissão novamente'
                : intent?.status === 'confirmed'
                  ? 'Emitir nova cobrança'
                  : 'Emitir cobrança'}
        </button>
      )}
    </section>
  );
}
