import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { TimelinePoint, ChartSeries } from '../core/costos.types';
import { niceMax } from '../core/chart.utils';
import { usd0 } from '../core/format.utils';

interface MLDatum {
  gridLines: { y: number; label: string }[];
  xLabels: { x: number; text: string }[];
  lines: { d: string; hex: string }[];
  dots: { cx: number; cy: number; hex: string; filled: boolean }[];
  columns: { x: number; w: number; tip: string; partialLine: boolean; cx: number }[];
}

@Component({
  selector: 'app-multi-line',
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
              [attr.x1]="64" [attr.y1]="g.y"
              [attr.x2]="744" [attr.y2]="g.y"/>
            <text class="axis" text-anchor="end"
              [attr.x]="58" [attr.y]="g.y + 4">{{ g.label }}</text>
          }
          <!-- line paths -->
          @for (l of d.lines; track l.hex) {
            <path [attr.d]="l.d" [attr.stroke]="l.hex"
                  fill="none" stroke-width="2" stroke-linejoin="round"/>
          }
          <!-- dots -->
          @for (dot of d.dots; track $index) {
            <circle [attr.cx]="dot.cx" [attr.cy]="dot.cy" r="3.5"
                    [attr.fill]="dot.filled ? dot.hex : 'var(--surface)'"
                    [attr.stroke]="dot.hex" stroke-width="2"/>
          }
          <!-- partial dashed lines + hover rects -->
          @for (c of d.columns; track c.x) {
            @if (c.partialLine) {
              <line [attr.x1]="c.cx" [attr.y1]="16"
                    [attr.x2]="c.cx" [attr.y2]="258"
                    stroke="var(--faint)" stroke-width="1"
                    stroke-dasharray="4 3" opacity="0.55"/>
            }
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
export class MultiLineComponent {
  readonly months = input.required<TimelinePoint[]>();
  readonly series = input.required<ChartSeries[]>();

  readonly chartData = computed<MLDatum | null>(() => {
    const tl = this.months();
    const allSeries = this.series();
    if (!tl.length || !allSeries.length) return null;

    const visible = allSeries.filter(s => !s.hidden);
    if (!visible.length) return null;

    const W = 760, H = 300;
    const pl = 64, pr = 16, pt = 16, pb = 42;
    const iw = W - pl - pr;
    const ih = H - pt - pb;
    const n = tl.length;

    const allVals = visible.flatMap(s => s.data.slice(0, n));
    const maxVal = niceMax(Math.max(...allVals, 0));
    const scaleY = (v: number) => pt + ih - (v / maxVal) * ih;
    const colW = iw / n;
    const cx = (i: number) => pl + colW * i + colW / 2;

    // gridlines
    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
      const val = maxVal * f;
      return { y: scaleY(val), label: usd0(val) };
    });

    // line paths
    const lines: MLDatum['lines'] = visible.map(s => {
      let d = '';
      for (let i = 0; i < n; i++) {
        const x = cx(i);
        const y = scaleY(s.data[i] || 0);
        d += (i === 0 ? 'M' : 'L') + `${x},${y}`;
      }
      return { d, hex: s.hex };
    });

    // dots
    const dots: MLDatum['dots'] = [];
    for (const s of visible) {
      for (let i = 0; i < n; i++) {
        dots.push({
          cx: cx(i),
          cy: scaleY(s.data[i] || 0),
          hex: s.hex,
          filled: !tl[i].partial,
        });
      }
    }

    // x-axis labels
    const step = n > 12 ? Math.ceil(n / 12) : 1;
    const xLabels: { x: number; text: string }[] = [];
    for (let i = 0; i < n; i += step) {
      xLabels.push({ x: cx(i), text: tl[i].lab });
    }

    // columns with tooltips
    const columns = tl.map((tp, i) => {
      const rows = visible.map(s => {
        const v = s.data[i] || 0;
        return `<div class="tt-r"><span><i style="background:${s.hex}"></i>${s.name}</span><span class="num">${usd0(v)}</span></div>`;
      }).join('');
      const tip =
        `<div class="tt-h">${tp.full}${tp.partial ? ' &middot; parcial' : ''}</div>` + rows;

      return {
        x: pl + colW * i,
        w: colW,
        tip,
        partialLine: tp.partial,
        cx: cx(i),
      };
    });

    return { gridLines, xLabels, lines, dots, columns };
  });
}
