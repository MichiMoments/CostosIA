import {
  Component, ChangeDetectionStrategy, inject, signal, computed,
} from '@angular/core';
import { DataService } from '../core/data.service';
import {
  TimelinePoint, ChartSeries, BarItem,
} from '../core/costos.types';
import { TOOLS, PAL, sum } from '../core/chart.utils';
import { usd2 } from '../core/format.utils';
import { MultiLineComponent } from '../charts/multi-line.component';
import { HorizontalBarsComponent } from '../charts/horizontal-bars.component';
@Component({
  selector: 'app-modelos',
  standalone: true,
  imports: [MultiLineComponent, HorizontalBarsComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; }
    .kpis-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
    .legend button { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--text); font-weight: 500; }
    .legend button.off { color: var(--faint); }
    .legend button.off i { opacity: .3; }
    .legend i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
    .io-stats { display: flex; gap: 20px; margin-top: 8px; font-size: 12.5px; color: var(--muted); }
    .io-stats b { font-weight: 600; color: var(--text); }
    .detail-table { max-height: 520px; overflow-y: auto; }
  `],
  template: `
    <div class="controls">
      <div class="seg">
        @for (y of years; track y) {
          <button [class.active]="selectedYear() === y" (click)="selectedYear.set(y)">{{ y }}</button>
        }
      </div>
      <div class="seg">
        @for (t of tools; track t) {
          <button [class.active]="selectedTool() === t" (click)="selectedTool.set(t)">{{ t }}</button>
        }
      </div>
      <div class="search">
        <input type="text" placeholder="Buscar meter, familia o part number..."
               [value]="searchQuery()"
               (input)="searchQuery.set($any($event.target).value)"/>
      </div>
    </div>

    <div class="kpis-3">
      <div class="kpi">
        <div class="strip" style="background:var(--mod)"></div>
        <div class="lab">Gasto total modelos</div>
        <div class="val num">{{ totalFmt() }}</div>
        <div class="meta">{{ selectedYear() }} &middot; {{ selectedTool() }}</div>
      </div>
      <div class="kpi">
        <div class="strip" style="background:var(--mod)"></div>
        <div class="lab">Familia principal</div>
        <div class="val">{{ topFamily() }}</div>
        <div class="meta num">{{ topFamilyVal() }}</div>
      </div>
      <div class="kpi">
        <div class="strip" style="background:var(--mod)"></div>
        <div class="lab">ChatMigo</div>
        <div class="val num">{{ chatMigoFmt() }}</div>
        <div class="meta">Consumo acumulado</div>
      </div>
    </div>

    <!-- Time series card -->
    <div class="card pad" style="margin-bottom:20px">
      <div class="card-h">Comportamiento en el tiempo</div>
      <div class="card-sub">{{ selectedYear() }} &middot; {{ selectedTool() }}</div>
      <div class="controls" style="margin-bottom:10px">
        <div class="seg">
          <button [class.active]="tsMode() === 'familia'" (click)="tsMode.set('familia')">Por familia</button>
          <button [class.active]="tsMode() === 'io'" (click)="tsMode.set('io')">Entrada / Salida</button>
        </div>
        @if (tsMode() === 'io') {
          <select style="padding:7px 12px;border:1px solid var(--line);border-radius:8px;font-size:13px;font-family:var(--sans);background:var(--surface)"
                  (change)="selectedModel.set($any($event.target).value || null)">
            <option value="">Todos los modelos</option>
            @for (m of modelNames(); track m) {
              <option [value]="m">{{ m }}</option>
            }
          </select>
        }
      </div>

      @if (tsMode() === 'familia') {
        <app-multi-line [months]="tsMonths()" [series]="famSeries()"/>
        <div class="legend">
          @for (s of famSeriesRaw(); track s.name) {
            <button [class.off]="s.hidden" (click)="toggleFamily(s.name)">
              <i [style.background]="s.hex"></i>{{ s.name }}
            </button>
          }
        </div>
      }
      @if (tsMode() === 'io') {
        <app-multi-line [months]="tsMonths()" [series]="ioSeries()"/>
        <div class="legend">
          @for (s of ioSeries(); track s.name) {
            <span style="display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:500">
              <i [style.background]="s.hex"></i>{{ s.name }}
            </span>
          }
        </div>
        <div class="io-stats">
          <span>Entrada: <b>{{ ioEntradaFmt() }}</b></span>
          <span>Salida: <b>{{ ioSalidaFmt() }}</b></span>
          <span>Ratio S/E: <b>{{ ioRatio() }}</b></span>
        </div>
      }
    </div>

    <!-- Top meters -->
    <div class="card pad" style="margin-bottom:20px">
      <div class="card-h">Top consumos por meter</div>
      <div class="card-sub">Primeros 12 meters por costo &middot; {{ selectedYear() }}</div>
      <app-horizontal-bars [items]="topMeters()"/>
    </div>

    <!-- Detail table -->
    <div class="card-h">Detalle máximo</div>
    <div class="card-sub">{{ filteredRows().length }} registros &middot; clic en encabezado para ordenar</div>
    <div class="tbl-wrap detail-table">
      <table>
        <thead>
          <tr>
            <th style="text-align:left" class="sortable" (click)="setSort('tool')">
              Unidad @if (sortKey() === 'tool') { <span class="ar">{{ sortDir() === 1 ? '▲' : '▼' }}</span> }
            </th>
            <th style="text-align:left" class="sortable" (click)="setSort('fam')">
              Familia @if (sortKey() === 'fam') { <span class="ar">{{ sortDir() === 1 ? '▲' : '▼' }}</span> }
            </th>
            <th style="text-align:left" class="sortable" (click)="setSort('meter')">
              Meter @if (sortKey() === 'meter') { <span class="ar">{{ sortDir() === 1 ? '▲' : '▼' }}</span> }
            </th>
            <th style="text-align:left">Part No</th>
            @for (m of detailMonthHeaders(); track m) {
              <th>{{ m }}</th>
            }
            <th class="sortable" (click)="setSort('total')">
              Total @if (sortKey() === 'total') { <span class="ar">{{ sortDir() === 1 ? '▲' : '▼' }}</span> }
            </th>
          </tr>
        </thead>
        <tbody>
          @for (r of sortedRows(); track r.partNumber) {
            <tr>
              <td style="text-align:left"><span class="tag">{{ r.tool }}</span></td>
              <td style="text-align:left">{{ r.fam }}</td>
              <td style="text-align:left">{{ r.meter }}</td>
              <td style="text-align:left;font-size:11px" class="dim">{{ r.partNumber }}</td>
              @for (v of r.vals; track $index) {
                <td class="num" [class.z]="v === 0">{{ v === 0 ? '-' : fmtVal(v) }}</td>
              }
              <td class="num" style="font-weight:600">{{ fmtVal(r.total) }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td style="text-align:left" colspan="4">Total</td>
            @for (v of detailFooter(); track $index) {
              <td class="num">{{ fmtVal(v) }}</td>
            }
            <td class="num">{{ totalFmt() }}</td>
          </tr>
        </tfoot>
      </table>
    </div>

    <div class="note" style="margin-top:12px">
      Los datos de modelos provienen del cruce entre el reporte de consumo Azure y la metadata de despliegues.
      Las familias agrupan modelos con arquitectura común (GPT-4o, GPT-4o mini, etc.).
    </div>
  `,
})
export class ModelosComponent {
  private readonly ds = inject(DataService);
  readonly tools = TOOLS;
  readonly years = ['2025', '2026'];

  readonly selectedYear = signal('2026');
  readonly selectedTool = signal('Todas');
  readonly searchQuery = signal('');
  readonly sortKey = signal('total');
  readonly sortDir = signal(-1);
  readonly tsMode = signal<'familia' | 'io'>('familia');
  readonly selectedModel = signal<string | null>(null);
  readonly hiddenFamilies = signal(new Set<string>());

  readonly nm = computed(() =>
    this.selectedYear() === '2025' ? 12 : this.ds.n26());

  readonly filteredRows = computed(() => {
    const models = this.ds.models();
    const year = this.selectedYear();
    const tool = this.selectedTool();
    const q = this.searchQuery().toLowerCase().trim();
    let rows = models[year] ?? [];
    if (tool !== 'Todas') {
      rows = rows.filter(r => r.tool === tool);
    }
    if (q) {
      rows = rows.filter(r =>
        r.meter.toLowerCase().includes(q) ||
        r.fam.toLowerCase().includes(q) ||
        r.partNumber.toLowerCase().includes(q) ||
        r.family.toLowerCase().includes(q),
      );
    }
    return rows;
  });

  readonly total = computed(() =>
    this.filteredRows().reduce((s, r) => s + r.total, 0));
  readonly totalFmt = computed(() => usd2(this.total()));

  readonly topFamily = computed(() => {
    const rows = this.filteredRows();
    if (!rows.length) return '-';
    const map = new Map<string, number>();
    for (const r of rows) {
      map.set(r.fam, (map.get(r.fam) || 0) + r.total);
    }
    let best = '';
    let bestVal = 0;
    for (const [k, v] of map) {
      if (v > bestVal) { best = k; bestVal = v; }
    }
    return best;
  });

  readonly topFamilyVal = computed(() => {
    const rows = this.filteredRows();
    const fam = this.topFamily();
    const val = rows.filter(r => r.fam === fam).reduce((s, r) => s + r.total, 0);
    return usd2(val);
  });

  readonly chatMigoFmt = computed(() => {
    const models = this.ds.models();
    const year = this.selectedYear();
    const rows = (models[year] ?? []).filter(r => r.tool === 'ChatMigo');
    return usd2(rows.reduce((s, r) => s + r.total, 0));
  });

  /* --- Time series shared --- */
  readonly tsMonths = computed<TimelinePoint[]>(() => {
    const meses = this.ds.meses();
    const year = this.selectedYear();
    const st = this.ds.status2026();
    const n = this.nm();
    const pts: TimelinePoint[] = [];
    for (let i = 0; i < n; i++) {
      pts.push({
        lab: meses[i],
        full: meses[i] + ' ' + year,
        partial: year === '2026' && st[i] === 'partial',
      });
    }
    return pts;
  });

  /* --- Familia mode --- */
  readonly famSeriesRaw = computed<ChartSeries[]>(() => {
    const rows = this.filteredRows();
    const n = this.nm();
    const map = new Map<string, number[]>();
    const totals = new Map<string, number>();
    for (const r of rows) {
      if (!map.has(r.fam)) {
        map.set(r.fam, new Array(n).fill(0));
        totals.set(r.fam, 0);
      }
      const arr = map.get(r.fam)!;
      for (let i = 0; i < n; i++) arr[i] += (r.values[i] || 0);
      totals.set(r.fam, totals.get(r.fam)! + r.total);
    }
    const sorted = [...map.entries()].sort((a, b) =>
      (totals.get(b[0]) || 0) - (totals.get(a[0]) || 0));
    const hidden = this.hiddenFamilies();
    return sorted.map(([name, data], i) => ({
      name,
      hex: PAL[i % PAL.length],
      data,
      hidden: hidden.has(name),
    }));
  });

  readonly famSeries = computed<ChartSeries[]>(() => this.famSeriesRaw());

  toggleFamily(name: string): void {
    this.hiddenFamilies.update(set => {
      const next = new Set(set);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  /* --- IO mode --- */
  readonly modelNames = computed(() => {
    const rows = this.filteredRows();
    const names = new Set<string>();
    for (const r of rows) {
      if (r.model) names.add(r.model);
    }
    return [...names].sort();
  });

  readonly ioSeries = computed<ChartSeries[]>(() => {
    const rows = this.filteredRows();
    const n = this.nm();
    const sel = this.selectedModel();
    let filtered = rows.filter(r => r.tt === 'Entrada' || r.tt === 'Salida');
    if (sel) {
      filtered = filtered.filter(r => r.model === sel);
    }
    const entrada = new Array(n).fill(0);
    const salida = new Array(n).fill(0);
    for (const r of filtered) {
      const target = r.tt === 'Entrada' ? entrada : salida;
      for (let i = 0; i < n; i++) target[i] += (r.values[i] || 0);
    }
    return [
      { name: 'Entrada (Input)', hex: '#3E7CB1', data: entrada },
      { name: 'Salida (Output)', hex: '#E0A13C', data: salida },
    ];
  });

  readonly ioEntradaFmt = computed(() => {
    const s = this.ioSeries();
    return usd2(sum(s[0].data));
  });
  readonly ioSalidaFmt = computed(() => {
    const s = this.ioSeries();
    return usd2(sum(s[1].data));
  });
  readonly ioRatio = computed(() => {
    const s = this.ioSeries();
    const e = sum(s[0].data);
    const sal = sum(s[1].data);
    return e > 0 ? (sal / e).toFixed(2) + 'x' : '-';
  });

  /* --- Top meters --- */
  readonly topMeters = computed<BarItem[]>(() => {
    const rows = this.filteredRows();
    const map = new Map<string, number>();
    for (const r of rows) {
      map.set(r.meter, (map.get(r.meter) || 0) + r.total);
    }
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([label, value]) => ({ label, value, color: '#8163AA' }));
  });

  /* --- Detail table --- */
  readonly detailMonthHeaders = computed(() =>
    this.ds.meses().slice(0, this.nm()));

  setSort(key: string): void {
    if (this.sortKey() === key) {
      this.sortDir.update(d => d * -1);
    } else {
      this.sortKey.set(key);
      this.sortDir.set(key === 'total' ? -1 : 1);
    }
  }

  readonly sortedRows = computed(() => {
    const rows = this.filteredRows();
    const key = this.sortKey();
    const dir = this.sortDir();
    const n = this.nm();
    const mapped = rows.map(r => ({
      tool: r.tool,
      fam: r.fam,
      meter: r.meter,
      partNumber: r.partNumber,
      vals: r.values.slice(0, n),
      total: r.total,
    }));
    return mapped.sort((a, b) => {
      let va: string | number;
      let vb: string | number;
      switch (key) {
        case 'tool':  va = a.tool;  vb = b.tool;  break;
        case 'fam':   va = a.fam;   vb = b.fam;   break;
        case 'meter': va = a.meter; vb = b.meter;  break;
        default:      va = a.total; vb = b.total;  break;
      }
      if (typeof va === 'string') {
        return va.localeCompare(vb as string) * dir;
      }
      return ((va as number) - (vb as number)) * dir;
    });
  });

  readonly detailFooter = computed(() => {
    const rows = this.filteredRows();
    const n = this.nm();
    const vals: number[] = new Array(n).fill(0);
    for (const r of rows) {
      for (let i = 0; i < n; i++) vals[i] += (r.values[i] || 0);
    }
    return vals;
  });

  fmtVal(v: number): string {
    return usd2(v);
  }
}
