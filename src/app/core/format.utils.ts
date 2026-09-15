const nf0 = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf4 = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function usd0(n: number): string {
  return 'US$ ' + nf0.format(n || 0);
}

export function usd2(n: number): string {
  return 'US$ ' + nf2.format(n || 0);
}

export function pct(n: number): string {
  return (n >= 0 ? '+' : '') + nf2.format(n) + '%';
}

export function fmt0(n: number): string {
  return nf0.format(n);
}

export function fmt2(n: number): string {
  return nf2.format(n);
}

export function fmt4(n: number): string {
  return nf4.format(n);
}
