import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { TimelinePoint } from '../core/costos.types';
import { niceMax } from '../core/chart.utils';
import { usd0 } from '../core/format.utils';

interface BarDatum {
  gridLines: { y: number; label: string }[];
  xLabels: { x: number; text: string }[];
  bars: {
    x: number; y: number; w: number; h: number;
    color: string; opacity: number; dash: string;
    labelY: number; labelText: string;
    tip: string;
  }[];
}

@Component({
  selector: 'app-bar-chart',
  standalone: true,
  imports: [TooltipDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (chartData(); as d) {
      <div class="chart">
        <svg [attr.viewBox]="'0 0 760 280'" preserveAspectRatio="xMidYMid meet">
          <!-- gridlines -->
          @for (g of d.gridLines; track g.label) {
            <line class="gridline"
              [attr.x1]="60" [attr.y1]="g.y"
              [attr.x2]="744" [attr.y2]="g.y"/>
            <text class="axis" text-anchor="end"
              [attr.x]="54" [attr.y]="g.y + 4">{{ g.label }}</text>
          }
          <!-- bars -->
          @for (b of d.bars; track b.x) {
            <rect [attr.x]="b.x" [attr.y]="b.y"
                  [attr.width]="b.w" [attr.height]="b.h"
                  [attr.fill]="b.color" [attr.fill-opacity]="b.opacity"
                  [attr.stroke]="b.color" stroke-width="1.5"
                  [attr.stroke-dasharray]="b.dash"
                  rx="3" [appTooltip]="b.tip"/>
            <text class="axis" text-anchor="middle"
              [attr.x]="b.x + b.w / 2" [attr.y]="b.labelY">{{ b.labelText }}</text>
          }
          <!-- x-axis labels -->
          @for (xl of d.xLabels; track xl.x) {
            <text class="axis" text-anchor="middle"
              [attr.x]="xl.x" [attr.y]="258">{{ xl.text }}</text>
          }
        </svg>
      </div>
    }
  `,
})
export class BarChartComponent {
  readonly months = input.required<TimelinePoint[]>();
  readonly data   = input.required<number[]>();
  readonly color  = input.required<string>();

  readonly chartData = computed<BarDatum | null>(() => {
    const tl = this.months();
    const vals = this.data();
    const clr = this.color();
    if (!tl.length) return null;

    const W = 760, H = 280;
    const pl = 60, pr = 16, pt = 16, pb = 38;
    const iw = W - pl - pr;
    const ih = H - pt - pb;
    const n = tl.length;

    const maxVal = niceMax(Math.max(...vals, 0));
    const scaleY = (v: number) => pt + ih - (v / maxVal) * ih;
    const barW = Math.min(38, (iw / n) * 0.62);
    const colW = iw / n;

    // gridlines (0, 25, 50, 75, 100%)
    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
      const val = maxVal * f;
      return { y: scaleY(val), label: usd0(val) };
    });

    // bars
    const bars = tl.map((tp, i) => {
      const v = vals[i] || 0;
      const cx = pl + colW * i + colW / 2;
      const bx = cx - barW / 2;
      const by = scaleY(v);
      const bh = Math.max(0, scaleY(0) - by);
      const partial = tp.partial;
      return {
        x: bx,
        y: by,
        w: barW,
        h: bh,
        color: clr,
        opacity: partial ? 0.45 : 1,
        dash: partial ? '4 3' : '',
        labelY: by - 6,
        labelText: usd0(v),
        tip: `<div class="tt-h">${tp.full}${partial ? ' &middot; parcial' : ''}</div><div class="tt-r"><span>Costo</span><span class="num">${usd0(v)}</span></div>`,
      };
    });

    // x-axis labels
    const step = n > 14 ? Math.ceil(n / 14) : 1;
    const xLabels: { x: number; text: string }[] = [];
    for (let i = 0; i < n; i += step) {
      xLabels.push({
        x: pl + colW * i + colW / 2,
        text: tl[i].lab,
      });
    }

    return { gridLines, bars, xLabels };
  });
}
