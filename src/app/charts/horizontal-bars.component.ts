import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { BarItem } from '../core/costos.types';
import { niceMax } from '../core/chart.utils';
import { usd2 } from '../core/format.utils';

interface HBarDatum {
  svgH: number;
  rows: {
    y: number;
    label: string;
    barX: number; barW: number; barH: number;
    color: string;
    valueLabel: string; valueLabelX: number;
    tip: string;
  }[];
}

@Component({
  selector: 'app-horizontal-bars',
  standalone: true,
  imports: [TooltipDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (chartData(); as d) {
      <div class="chart">
        <svg [attr.viewBox]="'0 0 760 ' + d.svgH" preserveAspectRatio="xMidYMid meet">
          @for (r of d.rows; track r.label) {
            <!-- label -->
            <text class="axis" text-anchor="end"
              [attr.x]="306" [attr.y]="r.y + r.barH / 2 + 4"
              style="font-size:12px">{{ r.label }}</text>
            <!-- bar -->
            <rect [attr.x]="r.barX" [attr.y]="r.y"
                  [attr.width]="r.barW" [attr.height]="r.barH"
                  [attr.fill]="r.color" rx="3"
                  [appTooltip]="r.tip"/>
            <!-- value -->
            <text class="axis" [attr.x]="r.valueLabelX" [attr.y]="r.y + r.barH / 2 + 4"
                  style="font-size:11px;fill:var(--muted)">{{ r.valueLabel }}</text>
          }
        </svg>
      </div>
    }
  `,
})
export class HorizontalBarsComponent {
  readonly items = input.required<BarItem[]>();

  readonly chartData = computed<HBarDatum | null>(() => {
    const list = this.items();
    if (!list.length) return null;

    const W = 760;
    const rowH = 30;
    const svgH = list.length * rowH + 8;
    const barLeft = 0.42 * W;   // 319.2
    const barArea = W - barLeft - 16;

    const maxVal = niceMax(Math.max(...list.map(d => d.value), 0));

    const rows = list.map((item, i) => {
      const y = i * rowH + 4;
      const bh = rowH - 8;
      const bw = Math.max(2, (item.value / maxVal) * barArea);
      const subText = item.sub ? `<div class="tt-r" style="color:#8CA3B4;margin-top:2px"><span>${item.sub}</span></div>` : '';
      return {
        y,
        label: item.label,
        barX: barLeft,
        barW: bw,
        barH: bh,
        color: item.color,
        valueLabel: usd2(item.value),
        valueLabelX: barLeft + bw + 8,
        tip: `<div class="tt-h">${item.label}</div><div class="tt-r"><span>Costo</span><span class="num">${usd2(item.value)}</span></div>${subText}`,
      };
    });

    return { svgH, rows };
  });
}
