const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export function minorUnits(value: string): bigint | null {
  if (typeof value !== 'string' || !/^\d{1,20}\.\d{2}$/.test(value)) return null;
  const [whole, fraction] = value.split('.');
  return BigInt(whole) * 100n + BigInt(fraction);
}

export function decimalAmount(value: bigint): string {
  return `${value / 100n}.${String(value % 100n).padStart(2, '0')}`;
}

export function money(value: string): string {
  const minor = minorUnits(value);
  if (minor === null) return 'Valor indisponível';
  return currency
    .formatToParts(minor / 100n)
    .map((part) => (part.type === 'fraction' ? String(minor % 100n).padStart(2, '0') : part.value))
    .join('');
}

export function itemSum(items: readonly { unit_price: string; quantity: number }[]): string | null {
  let total = 0n;
  for (const item of items) {
    const unit = minorUnits(item.unit_price);
    if (
      unit === null ||
      !Number.isInteger(item.quantity) ||
      item.quantity < 1 ||
      item.quantity > 2147483647
    )
      return null;
    total += unit * BigInt(item.quantity);
  }
  return total <= 9999999999999999999999n ? decimalAmount(total) : null;
}
