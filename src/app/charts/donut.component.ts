import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { DonutItem } from '../core/costos.types';
import { sum } from '../core/chart.utils';
import { usd2, fmt2 } from '../core/format.utils';

interface DonutDatum {
  slices: { d: string; hex: string; tip: string }[];
  total: string;
  legendItems: { hex: string; label: string; pct: string }[];
}

@Component({
  selector: 'app-donut',
  standalone: true,
  imports: [TooltipDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host { display: block; }
    .donut-wrap { display: flex; align-items: flex-start; gap: 20px; }
    .donut-legend { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; }
    .donut-legend-item { display: flex; align-items: center; gap: 8px; }
    .donut-legend-item i { width: 11px; height: 11px; border-radius: 3px; flex: 0 0 11px; }
    .donut-legend-item .pct { color: var(--muted); margin-left: 4px; }
    .donut-center { font-family: var(--disp); font-size: 13px; font-weight: 600; fill: var(--text); }
  `],
  template: `
    @if (chartData(); as d) {
      <div class="donut-wrap">
        <svg viewBox="0 0 156 156" style="width:156px;height:156px;flex:0 0 156px">
          @for (s of d.slices; track $index) {
            <path [attr.d]="s.d" [attr.fill]="s.hex" [appTooltip]="s.tip"/>
          }
          <circle cx="78" cy="78" r="40" fill="var(--surface)"/>
          <text class="donut-center" x="78" y="82" text-anchor="middle">{{ d.total }}</text>
        </svg>
        <div class="donut-legend">
          @for (li of d.legendItems; track li.label) {
            <div class="donut-legend-item">
              <i [style.background]="li.hex"></i>
              <span>{{ li.label }}</span>
              <span class="pct">{{ li.pct }}</span>
            </div>
          }
        </div>
      </div>
    }
  `,
})
export class DonutComponent {
  readonly items = input.required<DonutItem[]>();

  readonly chartData = computed<DonutDatum | null>(() => {
    const list = this.items();
    if (!list.length) return null;

    const total = sum(list.map(d => d.value));
    const R = 62, r = 40, cx = 78, cy = 78;

    let angle = -Math.PI / 2;
    const slices: DonutDatum['slices'] = [];

    for (const item of list) {
      const frac = total > 0 ? item.value / total : 0;
      const sweep = frac * Math.PI * 2;
      const a1 = angle;
      const a2 = angle + sweep;

      const x1o = cx + R * Math.cos(a1);
      const y1o = cy + R * Math.sin(a1);
      const x2o = cx + R * Math.cos(a2);
      const y2o = cy + R * Math.sin(a2);
      const x1i = cx + r * Math.cos(a2);
      const y1i = cy + r * Math.sin(a2);
      const x2i = cx + r * Math.cos(a1);
      const y2i = cy + r * Math.sin(a1);

      const large = sweep > Math.PI ? 1 : 0;

      const d = [
        `M${x1o},${y1o}`,
        `A${R},${R} 0 ${large} 1 ${x2o},${y2o}`,
        `L${x1i},${y1i}`,
        `A${r},${r} 0 ${large} 0 ${x2i},${y2i}`,
        'Z',
      ].join(' ');

      const pct = total > 0 ? (item.value / total * 100) : 0;
      const tip = `<div class="tt-h">${item.label}</div><div class="tt-r"><span>Costo</span><span class="num">${usd2(item.value)}</span></div><div class="tt-r"><span>Participaci&oacute;n</span><span class="num">${fmt2(pct)}%</span></div>`;

      slices.push({ d, hex: item.hex, tip });
      angle = a2;
    }

    const legendItems = list.map(item => {
      const pct = total > 0 ? (item.value / total * 100) : 0;
      return { hex: item.hex, label: item.label, pct: `${fmt2(pct)}%` };
    });

    return {
      slices,
      total: '$' + fmt2(total),
      legendItems,
    };
  });
}
