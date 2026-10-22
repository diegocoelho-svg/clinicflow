import { Link } from 'react-router';
import { dateTime } from '../../../shared/format/date';
import { money } from '../../../shared/format/money';
import type { Charge } from '../types';
import { ChargeStatusBadge } from './ChargeStatusBadge';

export function ChargeHistory({ clinic, charges }: { clinic: number; charges: readonly Charge[] }) {
  if (charges.length === 0)
    return <p className="muted">Nenhuma cobrança emitida para este atendimento.</p>;
  return (
    <ul className="charge-history">
      {[...charges].reverse().map((charge) => (
        <li key={charge.id}>
          <div>
            <Link to={`/clinicas/${clinic}/cobrancas/${charge.id}`}>Cobrança #{charge.id}</Link>
            <small>{dateTime(charge.created_at)}</small>
          </div>
          <strong className="money">{money(charge.amount)}</strong>
          <ChargeStatusBadge status={charge.status} />
        </li>
      ))}
    </ul>
  );
}
