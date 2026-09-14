import { EnvDef } from './costos.types';

export const ENVS: EnvDef[] = [
  { gk: 'Desarrollo', sk: 'Desarrollo', label: 'Desarrollo', color: 'var(--dev)', hex: '#3E7CB1' },
  { gk: 'Ambiente QA', sk: 'QA', label: 'QA', color: 'var(--qa)', hex: '#E0A13C' },
  { gk: 'Producción', sk: 'Producción', label: 'Producción', color: 'var(--prod)', hex: '#2E9E7B' },
  { gk: 'Modelos', sk: null, label: 'Modelos', color: 'var(--mod)', hex: '#8163AA' },
];

export const AMB = [
  { gk: 'Desarrollo', sk: 'Desarrollo', label: 'Desarrollo', hex: '#3E7CB1' },
  { gk: 'Ambiente QA', sk: 'QA', label: 'QA', hex: '#E0A13C' },
  { gk: 'Producción', sk: 'Producción', label: 'Producción', hex: '#2E9E7B' },
];

export const PAL = ['#3E7CB1', '#8163AA', '#2E9E7B', '#E0A13C', '#C2603A', '#4A9BD4', '#B0466B', '#6B8E23', '#5B7A8C', '#C9A227'];

export const TOOLS = ['Todas', 'ChatMigo', 'Ingenieria', 'Otras Unidades'];

export function sum(a: number[]): number {
  return a.reduce((x, y) => x + (y || 0), 0);
}

export function sumRange(arr: number[], n: number): number {
  return sum(arr.slice(0, n));
}

export function niceMax(v: number): number {
  if (v <= 0) return 10;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const s = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return s * p;
}

export function annual(general: Record<string, Record<string, number[]>>, year: string, gk: string): number {
  return sum(general[year][gk]);
}
