import {
  Component, ChangeDetectionStrategy, inject, signal, computed,
} from '@angular/core';
import { DataService } from '../core/data.service';
import { TimelinePoint, GroupedBarItem } from '../core/costos.types';
import { ENVS, sumRange } from '../core/chart.utils';
import { usd0, fmt2 } from '../core/format.utils';
import { GroupedBarsComponent } from '../charts/grouped-bars.component';
import { BarChartComponent } from '../charts/bar-chart.component';
import { AiSummaryComponent } from '../shared/ai-summary.component';
@Component({
  selector: 'app-comparativa',
  standalone: true,
  imports: [GroupedBarsComponent, BarChartComponent, AiSummaryComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; }
    .kpis-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
  `],
  template: `
    <div class="controls">
      <div class="seg">
        @for (opt of segOptions; track opt.idx) {
          <button [class.active]="selectedEnv() === opt.idx" (click)="selectedEnv.set(opt.idx)">{{ opt.label }}</button>
        }
      </div>
    </div>

    <!-- YoY section -->
    <h3 class="sec-title"><span class="sq" style="background:var(--dev)"></span>Año contra año</h3>
    <p class="sec-desc">Comparativa mensual de los primeros {{ n26() }} meses entre 2025 y 2026 &middot; {{ envLabel() }}</p>

    <div class="card has-ai" style="margin-bottom:20px">
      <div class="chart-section">
        <app-grouped-bars
          [groups]="yoyGroups()"
          [seriesA]="yoyA()"
          [seriesB]="yoyB()"
          [legendNames]="['2025','2026']"/>
      </div>
      <app-ai-summary
        chartTitle="Año contra año"
        [cacheKey]="chart4CacheKey()"/>
    </div>

    <div class="tbl-wrap" style="margin-bottom:30px">
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Mes</th>
            <th>2025</th>
            <th>2026</th>
            <th>Δ USD</th>
            <th>Δ %</th>
          </tr>
        </thead>
        <tbody>
          @for (r of yoyRows(); track r.mes) {
            <tr>
              <td style="text-align:left">{{ r.mes }}</td>
              <td class="num">{{ r.v25 }}</td>
              <td class="num">{{ r.v26 }}</td>
              <td class="num">
                <span class="delta" [class.up]="r.dUsd >= 0" [class.down]="r.dUsd < 0">
                  {{ r.dUsd >= 0 ? '▲' : '▼' }} {{ r.dUsdFmt }}
                </span>
              </td>
              <td class="num">
                <span class="delta" [class.up]="r.dPct >= 0" [class.down]="r.dPct < 0">
                  {{ r.dPct >= 0 ? '▲' : '▼' }} {{ r.dPctFmt }}
                </span>
              </td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td style="text-align:left">Periodo (Ene-{{ mesLabel() }})</td>
            <td class="num">{{ yoyFooter().v25 }}</td>
            <td class="num">{{ yoyFooter().v26 }}</td>
            <td class="num">
              <span class="delta" [class.up]="yoyFooter().dUsd >= 0" [class.down]="yoyFooter().dUsd < 0">
                {{ yoyFooter().dUsd >= 0 ? '▲' : '▼' }} {{ yoyFooter().dUsdFmt }}
              </span>
            </td>
            <td class="num">
              <span class="delta" [class.up]="yoyFooter().dPct >= 0" [class.down]="yoyFooter().dPct < 0">
                {{ yoyFooter().dPct >= 0 ? '▲' : '▼' }} {{ yoyFooter().dPctFmt }}
              </span>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- MoM section -->
    <h3 class="sec-title"><span class="sq" style="background:var(--qa)"></span>Mes contra mes anterior</h3>
    <p class="sec-desc">Últimos 3 meses de 2026 comparados con su mes inmediatamente anterior &middot; {{ envLabel() }}</p>

    <div class="kpis-3">
      @for (k of momKpis(); track k.mes) {
        <div class="kpi">
          <div class="strip" [style.background]="k.color"></div>
          <div class="lab">{{ k.mes }}</div>
          <div class="val num">{{ k.valFmt }}</div>
          <div class="meta">
            <span class="delta" [class.up]="k.dPct >= 0" [class.down]="k.dPct < 0">
              {{ k.dPct >= 0 ? '▲' : '▼' }} {{ k.dPctFmt }}
            </span>
            vs {{ k.prevMes }}
          </div>
        </div>
      }
    </div>

    <div class="card has-ai" style="margin-bottom:20px">
      <div class="chart-section">
        <div class="card-h">Evolución mensual 2026</div>
        <div class="card-sub">Últimos 3 meses &middot; {{ envLabel() }}</div>
        <app-bar-chart [months]="momBarMonths()" [data]="momBarData()" [color]="momBarColor()"/>
      </div>
      <app-ai-summary
        chartTitle="Evolución mensual 2026"
        [cacheKey]="chart5CacheKey()"/>
    </div>

    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Mes</th>
            <th>Valor</th>
            <th>Mes anterior</th>
            <th>Δ USD</th>
            <th>Δ % MoM</th>
          </tr>
        </thead>
        <tbody>
          @for (r of momRows(); track r.mes) {
            <tr>
              <td style="text-align:left">{{ r.mes }}</td>
              <td class="num">{{ r.valFmt }}</td>
              <td class="num dim">{{ r.prevFmt }}</td>
              <td class="num">
                <span class="delta" [class.up]="r.dUsd >= 0" [class.down]="r.dUsd < 0">
                  {{ r.dUsd >= 0 ? '▲' : '▼' }} {{ r.dUsdFmt }}
                </span>
              </td>
              <td class="num">
                <span class="delta" [class.up]="r.dPct >= 0" [class.down]="r.dPct < 0">
                  {{ r.dPct >= 0 ? '▲' : '▼' }} {{ r.dPctFmt }}
                </span>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class ComparativaComponent {
  private readonly ds = inject(DataService);

  readonly segOptions = [
    { idx: -1, label: 'Total' },
    ...ENVS.map((e, i) => ({ idx: i, label: e.label })),
  ];

  readonly selectedEnv = signal(-1);

  readonly n26 = this.ds.n26;
  readonly meses = this.ds.meses;

  readonly mesLabel = computed(() => this.meses()[this.ds.lastData2026()]);

  readonly envLabel = computed(() => {
    const idx = this.selectedEnv();
    return idx < 0 ? 'Total' : ENVS[idx].label;
  });

  private cmpSeries(year: string): number[] {
    const gen = this.ds.general();
    const idx = this.selectedEnv();
    if (idx < 0) {
      const arr: number[] = new Array(12).fill(0);
      for (const e of ENVS) {
        const vals = gen[year][e.gk];
        for (let i = 0; i < 12; i++) arr[i] += (vals[i] || 0);
      }
      return arr;
    }
    return [...gen[year][ENVS[idx].gk]];
  }

  readonly d25 = computed(() => this.cmpSeries('2025'));
  readonly d26 = computed(() => this.cmpSeries('2026'));

  /* --- YoY --- */
  readonly yoyGroups = computed(() => {
    const m = this.meses();
    const n = this.n26();
    return m.slice(0, n);
  });

  readonly yoyA = computed<GroupedBarItem[]>(() => {
    const d = this.d25();
    const n = this.n26();
    return d.slice(0, n).map(v => ({ value: v, hex: '#8CA3B4' }));
  });

  readonly yoyB = computed<GroupedBarItem[]>(() => {
    const d = this.d26();
    const n = this.n26();
    const st = this.ds.status2026();
    const idx = this.selectedEnv();
    const hex = idx < 0 ? 'var(--accent)' : ENVS[idx].hex;
    return d.slice(0, n).map((v, i) => ({
      value: v,
      hex,
      partial: st[i] === 'partial',
    }));
  });

  readonly yoyRows = computed(() => {
    const m = this.meses();
    const a = this.d25();
    const b = this.d26();
    const n = this.n26();
    const rows = [];
    for (let i = 0; i < n; i++) {
      const dUsd = b[i] - a[i];
      const dPct = a[i] !== 0 ? dUsd / a[i] * 100 : 0;
      rows.push({
        mes: m[i],
        v25: usd0(a[i]),
        v26: usd0(b[i]),
        dUsd,
        dUsdFmt: usd0(Math.abs(dUsd)),
        dPct,
        dPctFmt: fmt2(Math.abs(dPct)) + '%',
      });
    }
    return rows;
  });

  readonly yoyFooter = computed(() => {
    const n = this.n26();
    const s25 = sumRange(this.d25(), n);
    const s26 = sumRange(this.d26(), n);
    const dUsd = s26 - s25;
    const dPct = s25 !== 0 ? dUsd / s25 * 100 : 0;
    return {
      v25: usd0(s25),
      v26: usd0(s26),
      dUsd,
      dUsdFmt: usd0(Math.abs(dUsd)),
      dPct,
      dPctFmt: fmt2(Math.abs(dPct)) + '%',
    };
  });

  private static readonly ENV_KEYS = ['total', 'desarrollo', 'qa', 'produccion', 'modelos'];
  readonly chart4CacheKey = computed(() => `chart4_${ComparativaComponent.ENV_KEYS[this.selectedEnv() + 1]}`);

  /* --- MoM --- */
  readonly momKpis = computed(() => {
    const m = this.meses();
    const d = this.d26();
    const n = this.n26();
    const idx = this.selectedEnv();
    const color = idx < 0 ? 'var(--accent)' : ENVS[idx].hex;
    const kpis = [];
    const start = Math.max(1, n - 3);
    for (let i = start; i < n; i++) {
      const val = d[i];
      const prev = d[i - 1];
      const dPct = prev !== 0 ? (val - prev) / prev * 100 : 0;
      kpis.push({
        mes: m[i] + ' 2026',
        valFmt: usd0(val),
        prevMes: m[i - 1],
        dPct,
        dPctFmt: fmt2(Math.abs(dPct)) + '%',
        color,
      });
    }
    return kpis;
  });

  readonly momBarMonths = computed<TimelinePoint[]>(() => {
    const m = this.meses();
    const st = this.ds.status2026();
    const n = this.n26();
    const pts: TimelinePoint[] = [];
    for (let i = 0; i < n; i++) {
      pts.push({ lab: m[i], full: m[i] + ' 2026', partial: st[i] === 'partial' });
    }
    return pts.slice(-3);
  });

  readonly momBarData = computed(() => this.d26().slice(0, this.n26()).slice(-3));

  readonly momBarColor = computed(() => {
    const idx = this.selectedEnv();
    return idx < 0 ? '#5FBFA0' : ENVS[idx].hex;
  });

  readonly chart5CacheKey = computed(() => `chart5_${ComparativaComponent.ENV_KEYS[this.selectedEnv() + 1]}`);

  readonly momRows = computed(() => {
    const m = this.meses();
    const d = this.d26();
    const n = this.n26();
    const rows = [];
    const start = Math.max(1, n - 3);
    for (let i = start; i < n; i++) {
      const val = d[i];
      const prev = d[i - 1];
      const dUsd = val - prev;
      const dPct = prev !== 0 ? dUsd / prev * 100 : 0;
      rows.push({
        mes: m[i] + ' 2026',
        valFmt: usd0(val),
        prevFmt: usd0(prev),
        dUsd,
        dUsdFmt: usd0(Math.abs(dUsd)),
        dPct,
        dPctFmt: fmt2(Math.abs(dPct)) + '%',
      });
    }
    return rows;
  });
}
