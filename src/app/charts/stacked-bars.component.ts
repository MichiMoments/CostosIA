import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { TimelinePoint, ChartSeries } from '../core/costos.types';
import { usd0, usd2, fmt0, fmt2 } from '../core/format.utils';

// Finer than niceMax (1, 2, 2.5, 5, 10) so the axis hugs the tallest bar.
const STEPS = [1, 1.25, 2, 2.5, 3, 3.75, 5, 7.5, 10];

function axisMax(v: number): number {
  if (v <= 0) return 10;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  return STEPS.find(s => s * p >= v)! * p;
}

interface SBDatum {
  gridLines: { y: number; label: string }[];
  xLabels: { x: number; text: string }[];
  segments: {
    x: number; y: number; w: number; h: number;
    hex: string; opacity: number;
    label: string; labelY: number;
  }[];
  totals: { x: number; y: number; text: string }[];
  columns: { x: number; w: number; tip: string }[];
}

@Component({
  selector: 'app-stacked-bars',
  standalone: true,
  imports: [TooltipDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (chartData(); as d) {
      <div class="chart">
        <svg [attr.viewBox]="'0 0 760 300'" preserveAspectRatio="xMidYMid meet">
          <!-- gridlines -->
          @for (g of d.gridLines; track g.label) {
            <line class="gridline"
              [attr.x1]="76" [attr.y1]="g.y"
              [attr.x2]="744" [attr.y2]="g.y"/>
            <text class="axis" text-anchor="end"
              [attr.x]="70" [attr.y]="g.y + 4">{{ g.label }}</text>
          }
          <!-- stacked segments -->
          @for (s of d.segments; track $index) {
            <rect [attr.x]="s.x" [attr.y]="s.y"
                  [attr.width]="s.w" [attr.height]="s.h"
                  [attr.fill]="s.hex" [attr.fill-opacity]="s.opacity"/>
            @if (s.label) {
              <text text-anchor="middle" fill="#fff" font-size="10" font-weight="600"
                    font-family="var(--sans)" pointer-events="none"
                    [attr.x]="s.x + s.w / 2" [attr.y]="s.labelY">{{ s.label }}</text>
            }
          }
          <!-- totals on top -->
          @for (t of d.totals; track t.x) {
            <text text-anchor="middle" font-size="10.5" font-weight="600"
                  font-family="var(--sans)" fill="var(--text)"
                  [attr.x]="t.x" [attr.y]="t.y">{{ t.text }}</text>
          }
          <!-- hover columns -->
          @for (c of d.columns; track c.x) {
            <rect [attr.x]="c.x" [attr.y]="16"
                  [attr.width]="c.w" [attr.height]="242"
                  fill="transparent" [appTooltip]="c.tip"/>
          }
          <!-- x-axis labels -->
          @for (xl of d.xLabels; track xl.x) {
            <text class="axis" text-anchor="middle"
              [attr.x]="xl.x" [attr.y]="276">{{ xl.text }}</text>
          }
        </svg>
      </div>
    }
  `,
})
export class StackedBarsComponent {
  readonly months = input.required<TimelinePoint[]>();
  readonly series = input.required<ChartSeries[]>();

  readonly chartData = computed<SBDatum | null>(() => {
    const tl = this.months();
    const visible = this.series().filter(s => !s.hidden);
    if (!tl.length || !visible.length) return null;

    const W = 760, H = 300;
    const pl = 76, pr = 16, pt = 16, pb = 42;
    const iw = W - pl - pr;
    const ih = H - pt - pb;
    const n = tl.length;

    const totalsByMonth = tl.map((_, i) =>
      visible.reduce((acc, s) => acc + (s.data[i] || 0), 0));
    // Headroom for the total label above the tallest bar
    const maxVal = axisMax(Math.max(...totalsByMonth, 0) * 1.08);
    const scaleY = (v: number) => pt + ih - (v / maxVal) * ih;
    const colW = iw / n;
    const barW = Math.min(40, colW * 0.62);
    const cx = (i: number) => pl + colW * i + colW / 2;

    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
      const val = maxVal * f;
      return { y: scaleY(val), label: usd0(val) };
    });

    // First series (largest) sits at the bottom of each bar
    const segments: SBDatum['segments'] = [];
    const totals: SBDatum['totals'] = [];
    const columns: SBDatum['columns'] = [];
    tl.forEach((tp, i) => {
      const bx = cx(i) - barW / 2;
      let acc = 0;
      for (const s of visible) {
        const v = s.data[i] || 0;
        if (v <= 0) continue;
        const yTop = scaleY(acc + v);
        const h = scaleY(acc) - yTop;
        acc += v;
        segments.push({
          x: bx, y: yTop, w: barW, h,
          hex: s.hex,
          opacity: tp.partial ? 0.55 : 1,
          label: h >= 16 && barW >= 24 ? fmt0(v) : '',
          labelY: yTop + h / 2 + 3.5,
        });
      }
      if (acc > 0) {
        totals.push({ x: cx(i), y: scaleY(acc) - 6, text: fmt2(acc) });
      }

      const rows = visible.map(s =>
        `<div class="tt-r"><span><i style="background:${s.hex}"></i>${s.name}</span><span class="num">${usd2(s.data[i] || 0)}</span></div>`,
      ).join('');
      const tip =
        `<div class="tt-h">${tp.full}${tp.partial ? ' &middot; parcial' : ''}</div>` + rows +
        `<div class="tt-r"><span><b>Total</b></span><span class="num"><b>${usd2(acc)}</b></span></div>`;
      columns.push({ x: pl + colW * i, w: colW, tip });
    });

    const step = n > 12 ? Math.ceil(n / 12) : 1;
    const xLabels: SBDatum['xLabels'] = [];
    for (let i = 0; i < n; i += step) {
      xLabels.push({ x: cx(i), text: tl[i].lab });
    }

    return { gridLines, xLabels, segments, totals, columns };
  });
}
