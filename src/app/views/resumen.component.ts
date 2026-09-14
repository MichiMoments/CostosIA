import {
  Component, ChangeDetectionStrategy, inject, computed,
} from '@angular/core';
import { DataService } from '../core/data.service';
import {
  TimelinePoint, ChartSeries, GroupedBarItem, DonutItem,
} from '../core/costos.types';
import { ENVS, annual, sumRange } from '../core/chart.utils';
import { usd0, pct, fmt2 } from '../core/format.utils';
import { StackedAreaComponent } from '../charts/stacked-area.component';
import { GroupedBarsComponent } from '../charts/grouped-bars.component';
import { DonutComponent } from '../charts/donut.component';
import { SafeHtmlPipe } from '../shared/safe-html.pipe';
@Component({
  selector: 'app-resumen',
  standalone: true,
  imports: [StackedAreaComponent, GroupedBarsComponent, DonutComponent, SafeHtmlPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; }
    .legend-inline { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px; }
    .legend-inline span { display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 500; }
    .legend-inline i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
    .donut-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
  `],
  template: `
    <div class="callout" [innerHTML]="execReading() | safeHtml"></div>

    <div class="kpis">
      <div class="kpi">
        <div class="strip" style="background:var(--accent)"></div>
        <div class="lab">Total 2025</div>
        <div class="val num">{{ t25Fmt() }}</div>
        <div class="meta">Enero - Diciembre &middot; 12 meses completos</div>
      </div>
      <div class="kpi">
        <div class="strip" style="background:var(--dev)"></div>
        <div class="lab">Total 2026 (a {{ mesLabel() }})</div>
        <div class="val num">{{ t26Fmt() }}</div>
        <div class="meta">
          Ene - {{ mesLabel() }} &middot; {{ n26() }} meses
          <span class="delta" [class.up]="yoy() >= 0" [class.down]="yoy() < 0"
                style="margin-left:8px">
            {{ yoy() >= 0 ? '▲' : '▼' }} {{ yoyFmt() }}
          </span>
          <span style="font-size:11px;color:var(--faint);margin-left:4px">vs mismo periodo 2025</span>
        </div>
      </div>
    </div>

    <div class="chips">
      @for (c of chips(); track c.label) {
        <div class="chip">
          <div class="cl"><i [style.background]="c.hex"></i>{{ c.label }}</div>
          <div class="cv num">{{ c.val }}</div>
        </div>
      }
    </div>

    <div class="card pad" style="margin-bottom:20px">
      <div class="card-h">Consumo mensual por ambiente</div>
      <div class="card-sub">Últimos 3 meses &middot; todas las unidades</div>
      <app-stacked-area [timeline]="timeline()" [series]="areaSeries()"/>
      <div class="legend-inline">
        @for (e of envDefs; track e.label) {
          <span><i [style.background]="e.hex"></i>{{ e.label }}</span>
        }
      </div>
      <div class="note">Los valores representan costos mensuales en USD. Las barras con borde punteado indican meses con datos parciales.</div>
    </div>

    <div class="two" style="margin-bottom:20px">
      <div class="card pad">
        <div class="donut-title">Distribución 2025</div>
        <app-donut [items]="donut25()"/>
      </div>
      <div class="card pad">
        <div class="donut-title">Distribución 2026 (a {{ mesLabel() }})</div>
        <app-donut [items]="donut26()"/>
      </div>
    </div>

    <div class="callout" style="margin-bottom:20px">
      <b>Consolidado anual:</b> comparativa del gasto total por ambiente entre 2025 completo y 2026 acumulado a {{ mesLabel() }}.
    </div>

    <div class="card pad" style="margin-bottom:20px">
      <div class="card-h">Comparativa anual por ambiente</div>
      <div class="card-sub">2025 completo vs 2026 a {{ mesLabel() }}</div>
      <app-grouped-bars
        [groups]="annualGroups()"
        [seriesA]="annualA()"
        [seriesB]="annualB()"
        [legendNames]="['2025','2026']"/>
    </div>

    <div class="tbl-wrap" style="margin-bottom:20px">
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Ambiente</th>
            <th>2025 completo</th>
            <th>% 2025</th>
            <th>2026 a {{ mesLabel() }}</th>
            <th>% 2026</th>
          </tr>
        </thead>
        <tbody>
          @for (r of annualRows(); track r.label) {
            <tr>
              <td style="text-align:left">
                <span style="display:inline-flex;align-items:center;gap:8px">
                  <i [style.background]="r.hex" style="width:9px;height:9px;border-radius:2px;display:inline-block"></i>
                  {{ r.label }}
                </span>
              </td>
              <td class="num">{{ r.v25 }}</td>
              <td class="num dim">{{ r.p25 }}</td>
              <td class="num">{{ r.v26 }}</td>
              <td class="num dim">{{ r.p26 }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td style="text-align:left">Total</td>
            <td class="num">{{ t25Fmt() }}</td>
            <td class="num">100,00%</td>
            <td class="num">{{ t26Fmt() }}</td>
            <td class="num">100,00%</td>
          </tr>
        </tfoot>
      </table>
    </div>
  `,
})
export class ResumenComponent {
  private readonly ds = inject(DataService);
  readonly envDefs = ENVS;

  readonly n26 = this.ds.n26;
  readonly meses = this.ds.meses;
  readonly general = this.ds.general;
  readonly status2026 = this.ds.status2026;

  readonly mesLabel = computed(() => this.meses()[this.ds.lastData2026()]);

  readonly t25 = computed(() =>
    ENVS.reduce((s, e) => s + annual(this.general(), '2025', e.gk), 0));
  readonly t26 = computed(() =>
    ENVS.reduce((s, e) => s + annual(this.general(), '2026', e.gk), 0));

  readonly p25 = computed(() =>
    ENVS.reduce((s, e) => s + sumRange(this.general()['2025'][e.gk], this.n26()), 0));
  readonly p26 = computed(() =>
    ENVS.reduce((s, e) => s + sumRange(this.general()['2026'][e.gk], this.n26()), 0));

  readonly yoy = computed(() => {
    const p25 = this.p25();
    return p25 !== 0 ? (this.p26() - p25) / p25 * 100 : 0;
  });

  readonly t25Fmt = computed(() => usd0(this.t25()));
  readonly t26Fmt = computed(() => usd0(this.t26()));
  readonly yoyFmt = computed(() => pct(this.yoy()));

  readonly chips = computed(() =>
    ENVS.map(e => ({
      label: e.label,
      hex: e.hex,
      val: usd0(annual(this.general(), '2026', e.gk)),
    })),
  );

  readonly execReading = computed(() => {
    const gen = this.general();
    const n = this.n26();
    const envTotals = ENVS.map(e => ({
      label: e.label,
      total: sumRange(gen['2026'][e.gk], n),
    }));
    const top = envTotals.reduce((a, b) => b.total > a.total ? b : a);
    const qa25 = sumRange(gen['2025']['Ambiente QA'], n);
    const qa26 = sumRange(gen['2026']['Ambiente QA'], n);
    const qaGrowth = qa25 > 0 ? ((qa26 - qa25) / qa25 * 100) : 0;

    const models = this.ds.models();
    const mRows = models['2026'] || [];
    const topMeter = mRows.length
      ? mRows.reduce((a, b) => b.total > a.total ? b : a)
      : null;

    let text = `<b>Lectura ejecutiva:</b> El mayor consumo 2026 es <b>${top.label}</b> con <b>${usd0(top.total)}</b>.`;
    if (qa25 > 0) {
      text += ` QA ${qaGrowth >= 0 ? 'crece' : 'decrece'} <b>${fmt2(Math.abs(qaGrowth))}%</b> vs 2025.`;
    }
    if (topMeter) {
      text += ` El meter de mayor consumo en modelos es <b>${topMeter.meter}</b> (${usd0(topMeter.total)}).`;
    }
    return text;
  });

  readonly timeline = computed<TimelinePoint[]>(() => {
    const m = this.meses();
    const st = this.status2026();
    const n = this.n26();
    const pts: TimelinePoint[] = [];
    for (let i = 0; i < 12; i++) {
      pts.push({ lab: m[i], full: m[i] + ' 2025', partial: false });
    }
    for (let i = 0; i < n; i++) {
      pts.push({ lab: m[i], full: m[i] + ' 2026', partial: st[i] === 'partial' });
    }
    return pts.slice(-3);
  });

  readonly areaSeries = computed<ChartSeries[]>(() => {
    const gen = this.general();
    const n = this.n26();
    return ENVS.map(e => ({
      name: e.label,
      hex: e.hex,
      data: [...gen['2025'][e.gk], ...gen['2026'][e.gk].slice(0, n)].slice(-3),
    }));
  });

  readonly donut25 = computed<DonutItem[]>(() =>
    ENVS.map(e => ({ label: e.label, hex: e.hex, value: annual(this.general(), '2025', e.gk) })),
  );

  readonly donut26 = computed<DonutItem[]>(() =>
    ENVS.map(e => ({ label: e.label, hex: e.hex, value: annual(this.general(), '2026', e.gk) })),
  );

  readonly annualGroups = computed(() => ENVS.map(e => e.label));

  readonly annualA = computed<GroupedBarItem[]>(() =>
    ENVS.map(e => ({ value: annual(this.general(), '2025', e.gk), hex: '#8CA3B4' })),
  );

  readonly annualB = computed<GroupedBarItem[]>(() =>
    ENVS.map(e => ({
      value: annual(this.general(), '2026', e.gk),
      hex: e.hex,
      partial: this.ds.hasPartial(),
    })),
  );

  readonly annualRows = computed(() => {
    const gen = this.general();
    const t25 = this.t25();
    const t26 = this.t26();
    return ENVS.map(e => {
      const v25 = annual(gen, '2025', e.gk);
      const v26 = annual(gen, '2026', e.gk);
      return {
        label: e.label,
        hex: e.hex,
        v25: usd0(v25),
        p25: fmt2(t25 > 0 ? v25 / t25 * 100 : 0) + '%',
        v26: usd0(v26),
        p26: fmt2(t26 > 0 ? v26 / t26 * 100 : 0) + '%',
      };
    });
  });
}
