import {
  Component, ChangeDetectionStrategy, inject, signal, computed,
} from '@angular/core';
import { DataService } from '../core/data.service';
import { TimelinePoint, BarItem } from '../core/costos.types';
import { AMB, sum } from '../core/chart.utils';
import { usd0 } from '../core/format.utils';
import { BarChartComponent } from '../charts/bar-chart.component';
import { HorizontalBarsComponent } from '../charts/horizontal-bars.component';
import { AiSummaryComponent } from '../shared/ai-summary.component';
@Component({
  selector: 'app-ambiente',
  standalone: true,
  imports: [BarChartComponent, HorizontalBarsComponent, AiSummaryComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; }
    .kpis-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
  `],
  template: `
    <div class="controls">
      <div class="seg">
        @for (a of ambientes; track a.label; let i = $index) {
          <button [class.active]="selectedEnv() === i" (click)="selectedEnv.set(i)">{{ a.label }}</button>
        }
      </div>
      <div class="seg">
        @for (y of years; track y) {
          <button [class.active]="selectedYear() === y" (click)="selectedYear.set(y)">{{ y }}</button>
        }
      </div>
    </div>

    <div class="kpis-3">
      <div class="kpi">
        <div class="strip" [style.background]="amb().hex"></div>
        <div class="lab">Costo total</div>
        <div class="val num">{{ totalFmt() }}</div>
        <div class="meta">{{ selectedYear() }} &middot; {{ amb().label }}</div>
      </div>
      <div class="kpi">
        <div class="strip" [style.background]="amb().hex"></div>
        <div class="lab">Mes pico</div>
        <div class="val num">{{ peakMonthLabel() }}</div>
        <div class="meta">{{ peakMonthValue() }}</div>
      </div>
      <div class="kpi">
        <div class="strip" [style.background]="amb().hex"></div>
        <div class="lab">Tipos de servicio</div>
        <div class="val num">{{ serviceCount() }}</div>
        <div class="meta">Servicios Azure distintos</div>
      </div>
    </div>

    <div class="card" [class.pad]="selectedYear() !== '2026'" [class.has-ai]="selectedYear() === '2026'" style="margin-bottom:20px">
      @if (selectedYear() === '2026') {
        <div class="chart-section">
          <div class="card-h">Costo mensual &middot; {{ amb().label }}</div>
          <div class="card-sub">{{ selectedYear() }} &middot; {{ nm() }} meses</div>
          <app-bar-chart [months]="barMonths()" [data]="barData()" [color]="amb().hex"/>
          <div class="note">Valores en USD por mes.</div>
        </div>
        <app-ai-summary
          chartTitle="Costo mensual"
          [cacheKey]="chart3CacheKey()"/>
      } @else {
        <div class="card-h">Costo mensual &middot; {{ amb().label }}</div>
        <div class="card-sub">{{ selectedYear() }} &middot; {{ nm() }} meses</div>
        <app-bar-chart [months]="barMonths()" [data]="barData()" [color]="amb().hex"/>
        <div class="note">Valores en USD por mes.</div>
      }
    </div>

    <div class="card pad" style="margin-bottom:20px">
      <div class="card-h">Servicios por costo</div>
      <div class="card-sub">{{ amb().label }} &middot; {{ selectedYear() }}</div>
      <app-horizontal-bars [items]="hBarItems()"/>
    </div>

    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Servicio</th>
            @for (m of monthHeaders(); track m) {
              <th>{{ m }}</th>
            }
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          @for (r of tableRows(); track r.name) {
            <tr>
              <td style="text-align:left">{{ r.name }}</td>
              @for (v of r.values; track $index) {
                <td class="num" [class.z]="v === 0">{{ v === 0 ? '-' : fmtUsd(v) }}</td>
              }
              <td class="num" style="font-weight:600">{{ fmtUsd(r.total) }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td style="text-align:left">Total</td>
            @for (v of footerValues(); track $index) {
              <td class="num">{{ fmtUsd(v) }}</td>
            }
            <td class="num">{{ totalFmt() }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  `,
})
export class AmbienteComponent {
  private readonly ds = inject(DataService);
  readonly ambientes = AMB;
  readonly years = ['2025', '2026'];

  readonly selectedEnv = signal(0);
  readonly selectedYear = signal('2026');

  readonly amb = computed(() => AMB[this.selectedEnv()]);

  readonly nm = computed(() =>
    this.selectedYear() === '2025' ? 12 : this.ds.n26());

  readonly monthly = computed(() => {
    const gen = this.ds.general();
    const year = this.selectedYear();
    const gk = this.amb().gk;
    return gen[year][gk].slice(0, this.nm());
  });

  readonly svcs = computed(() => {
    const services = this.ds.services();
    const sk = this.amb().sk;
    const year = this.selectedYear();
    const rows = services[sk]?.[year] ?? [];
    return [...rows].sort((a, b) => b.total - a.total);
  });

  readonly total = computed(() => sum(this.monthly()));
  readonly totalFmt = computed(() => usd0(this.total()));

  readonly peakIdx = computed(() => {
    const m = this.monthly();
    let idx = 0;
    for (let i = 1; i < m.length; i++) {
      if (m[i] > m[idx]) idx = i;
    }
    return idx;
  });

  readonly peakMonthLabel = computed(() => this.ds.meses()[this.peakIdx()]);
  readonly peakMonthValue = computed(() => usd0(this.monthly()[this.peakIdx()]));

  readonly serviceCount = computed(() => this.svcs().length);

  readonly barMonths = computed<TimelinePoint[]>(() => {
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

  readonly barData = computed(() => this.monthly());

  private static readonly AMB_KEYS = ['desarrollo', 'qa', 'produccion'];
  readonly chart3CacheKey = computed(() => `chart3_${AmbienteComponent.AMB_KEYS[this.selectedEnv()]}`);

  readonly hBarItems = computed<BarItem[]>(() =>
    this.svcs().map(s => ({
      label: s.name,
      value: s.total,
      color: this.amb().hex,
    })),
  );

  readonly monthHeaders = computed(() => {
    const meses = this.ds.meses();
    return meses.slice(0, this.nm());
  });

  readonly tableRows = computed(() => {
    const n = this.nm();
    return this.svcs().map(s => ({
      name: s.name,
      values: s.values.slice(0, n),
      total: s.total,
    }));
  });

  readonly footerValues = computed(() => {
    const n = this.nm();
    const rows = this.svcs();
    const vals: number[] = [];
    for (let i = 0; i < n; i++) {
      vals.push(rows.reduce((s, r) => s + (r.values[i] || 0), 0));
    }
    return vals;
  });

  fmtUsd(v: number): string {
    return usd0(v);
  }
}
