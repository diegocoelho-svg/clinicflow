import { money } from '../../../shared/format/money';
import type { ChargeItem } from '../types';

export function ChargeItems({ items, caption }: { items: readonly ChargeItem[]; caption: string }) {
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="data-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Procedimento</th>
            <th scope="col">Quantidade</th>
            <th scope="col">Valor unitário</th>
            <th scope="col">Total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <th scope="row">{item.procedure_name}</th>
              <td>{item.quantity}</td>
              <td className="money">{money(item.unit_price)}</td>
              <td className="money">{money(item.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
