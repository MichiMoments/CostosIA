import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { TimelinePoint, ChartSeries } from '../core/costos.types';
import { niceMax, sum } from '../core/chart.utils';
import { usd0 } from '../core/format.utils';

interface AreaDatum {
  paths: { d: string; hex: string }[];
  gridLines: { y: number; label: string }[];
  xLabels: { x: number; text: string }[];
  columns: {
    x: number; w: number; tip: string;
    partialLine: number | null;
  }[];
}

@Component({
  selector: 'app-stacked-area',
  standalone: true,
  imports: [TooltipDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (chartData(); as d) {
      <div class="chart">
        <svg [attr.viewBox]="'0 0 920 360'" preserveAspectRatio="xMidYMid meet">
          <!-- gridlines -->
          @for (g of d.gridLines; track g.label) {
            <line class="gridline"
              [attr.x1]="64" [attr.y1]="g.y"
              [attr.x2]="902" [attr.y2]="g.y"/>
            <text class="axis" text-anchor="end"
              [attr.x]="58" [attr.y]="g.y + 4">{{ g.label }}</text>
          }
          <!-- stacked area paths -->
          @for (p of d.paths; track p.hex) {
            <path [attr.d]="p.d" [attr.fill]="p.hex" opacity="0.82"/>
          }
          <!-- x-axis labels -->
          @for (xl of d.xLabels; track xl.x) {
            <text class="axis" text-anchor="middle"
              [attr.x]="xl.x" [attr.y]="336">{{ xl.text }}</text>
          }
          <!-- partial dashed lines + hover rects -->
          @for (c of d.columns; track c.x) {
            @if (c.partialLine !== null) {
              <line [attr.x1]="c.x + c.w / 2" [attr.y1]="18"
                    [attr.x2]="c.x + c.w / 2" [attr.y2]="318"
                    stroke="var(--faint)" stroke-width="1"
                    stroke-dasharray="4 3" opacity="0.55"/>
            }
            <rect [attr.x]="c.x" [attr.y]="18"
                  [attr.width]="c.w" [attr.height]="300"
                  fill="transparent" [appTooltip]="c.tip"/>
          }
        </svg>
      </div>
    }
  `,
})
export class StackedAreaComponent {
  readonly timeline = input.required<TimelinePoint[]>();
  readonly series   = input.required<ChartSeries[]>();

  readonly chartData = computed<AreaDatum | null>(() => {
    const tl = this.timeline();
    const sr = this.series();
    if (!tl.length || !sr.length) return null;

    const W = 920, H = 360;
    const pl = 64, pr = 18, pt = 18, pb = 42;
    const iw = W - pl - pr;
    const ih = H - pt - pb;
    const n = tl.length;

    // compute stacked totals per column
    const stacked: number[][] = [];
    for (let i = 0; i < n; i++) {
      let acc = 0;
      const col: number[] = [0];
      for (const s of sr) {
        acc += (s.data[i] || 0);
        col.push(acc);
      }
      stacked.push(col);
    }

    const maxVal = niceMax(Math.max(...stacked.map(c => c[c.length - 1]), 0));
    const scaleY = (v: number) => pt + ih - (v / maxVal) * ih;
    const colW = iw / n;
    const cx = (i: number) => pl + colW * i + colW / 2;

    // gridlines (0, 25, 50, 75, 100%)
    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
      const val = maxVal * f;
      return { y: scaleY(val), label: usd0(val) };
    });

    // area paths (bottom to top, render bottom-most last so it's on top)
    const paths: { d: string; hex: string }[] = [];
    for (let si = sr.length - 1; si >= 0; si--) {
      let d = '';
      // top edge (layer si+1 cumulative)
      for (let i = 0; i < n; i++) {
        const x = cx(i);
        const y = scaleY(stacked[i][si + 1]);
        d += (i === 0 ? 'M' : 'L') + `${x},${y}`;
      }
      // bottom edge (layer si cumulative), reversed
      for (let i = n - 1; i >= 0; i--) {
        const x = cx(i);
        const y = scaleY(stacked[i][si]);
        d += `L${x},${y}`;
      }
      d += 'Z';
      paths.push({ d, hex: sr[si].hex });
    }

    // x-axis labels
    const step = n > 12 ? Math.ceil(n / 12) : 1;
    const xLabels: { x: number; text: string }[] = [];
    for (let i = 0; i < n; i += step) {
      xLabels.push({ x: cx(i), text: tl[i].lab });
    }

    // columns with tooltips
    const columns = tl.map((tp, i) => {
      const x = pl + colW * i;
      const total = stacked[i][sr.length];
      const rows = sr.map((s, si) => {
        const v = s.data[i] || 0;
        return `<div class="tt-r"><span><i style="background:${s.hex}"></i>${s.name}</span><span class="num">${usd0(v)}</span></div>`;
      }).join('');
      const tip =
        `<div class="tt-h">${tp.full}${tp.partial ? ' &middot; parcial' : ''}</div>` +
        rows +
        `<div class="tt-r" style="border-top:1px solid rgba(255,255,255,.15);margin-top:4px;padding-top:4px"><span>Total</span><span class="num">${usd0(total)}</span></div>`;

      return {
        x,
        w: colW,
        tip,
        partialLine: tp.partial ? cx(i) : null,
      };
    });

    return { paths, gridLines, xLabels, columns };
  });
}
