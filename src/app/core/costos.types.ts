export interface CostosData {
  meta: {
    currency: string;
    meses: string[];
    status2026: string[];
    lastData2026: number;
    august_source: string;
  };
  general: Record<string, Record<string, number[]>>;
  services: Record<string, Record<string, ServiceRow[]>>;
  models: Record<string, ModelRow[]>;
}

export interface ServiceRow {
  name: string;
  values: number[];
  total: number;
}

export interface ModelRow {
  tool: string;
  serviceName: string;
  family: string;
  serviceTier: string;
  meter: string;
  partNumber: string;
  values: number[];
  total: number;
  model: string;
  fam: string;
  tt: string;
}

export interface EnvDef {
  gk: string;
  sk: string | null;
  label: string;
  color: string;
  hex: string;
}

export interface TimelinePoint {
  lab: string;
  full: string;
  partial: boolean;
}

export interface ChartSeries {
  name: string;
  hex: string;
  color?: string;
  data: number[];
  hidden?: boolean;
}

export interface BarItem {
  label: string;
  value: number;
  color: string;
  sub?: string;
}

export interface GroupedBarItem {
  value: number;
  hex: string;
  partial?: boolean;
}

export interface DonutItem {
  label: string;
  hex: string;
  value: number;
}
