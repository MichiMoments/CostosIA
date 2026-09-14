import {
  Component, ChangeDetectionStrategy, input, computed,
} from '@angular/core';
import { TooltipDirective } from '../shared/tooltip.directive';
import { GroupedBarItem } from '../core/costos.types';
import { niceMax } from '../core/chart.utils';
import { usd0 } from '../core/format.utils';

interface GBarDatum {
  gridLines: { y: number; label: string }[];
  xLabels: { x: number; text: string }[];
  bars: {
    x: number; y: number; w: number; h: number;
    hex: string; opacity: number; dash: string;
    labelY: number; labelText: string;
    tip: string;
  }[];
  legend: { hex: string; name: string }[];
}

@Component({
  selector: 'app-grouped-bars',
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
              [attr.x1]="60" [attr.y1]="g.y"
              [attr.x2]="744" [attr.y2]="g.y"/>
            <text class="axis" text-anchor="end"
              [attr.x]="54" [attr.y]="g.y + 4">{{ g.label }}</text>
          }
          <!-- bars -->
          @for (b of d.bars; track $index) {
            <rect [attr.x]="b.x" [attr.y]="b.y"
                  [attr.width]="b.w" [attr.height]="b.h"
                  [attr.fill]="b.hex" [attr.fill-opacity]="b.opacity"
                  [attr.stroke]="b.hex" stroke-width="1.5"
                  [attr.stroke-dasharray]="b.dash"
                  rx="3" [appTooltip]="b.tip"/>
            <text class="axis" text-anchor="middle"
              [attr.x]="b.x + b.w / 2" [attr.y]="b.labelY">{{ b.labelText }}</text>
          }
          <!-- x-axis labels -->
          @for (xl of d.xLabels; track xl.x) {
            <text class="axis" text-anchor="middle"
              [attr.x]="xl.x" [attr.y]="276">{{ xl.text }}</text>
          }
        </svg>
        <div class="legend">
          @for (l of d.legend; track l.name) {
            <span style="display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:500">
              <i [style.background]="l.hex" style="width:11px;height:11px;border-radius:3px;display:inline-block"></i>
              {{ l.name }}
            </span>
          }
        </div>
      </div>
    }
  `,
})
export class GroupedBarsComponent {
  readonly groups      = input.required<string[]>();
  readonly seriesA     = input.required<GroupedBarItem[]>();
  readonly seriesB     = input.required<GroupedBarItem[]>();
  readonly legendNames = input.required<[string, string]>();

  readonly chartData = computed<GBarDatum | null>(() => {
    const grps = this.groups();
    const sa = this.seriesA();
    const sb = this.seriesB();
    const names = this.legendNames();
    if (!grps.length) return null;

    const W = 760, H = 300;
    const pl = 60, pr = 16, pt = 16, pb = 42;
    const iw = W - pl - pr;
    const ih = H - pt - pb;
    const n = grps.length;

    const allVals = [...sa.map(d => d.value), ...sb.map(d => d.value)];
    const maxVal = niceMax(Math.max(...allVals, 0));
    const scaleY = (v: number) => pt + ih - (v / maxVal) * ih;
    const groupW = iw / n;
    const barW = Math.min(30, groupW * 0.32);
    const gap = 3;

    // gridlines
    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
      const val = maxVal * f;
      return { y: scaleY(val), label: usd0(val) };
    });

    // bars
    const bars: GBarDatum['bars'] = [];
    for (let i = 0; i < n; i++) {
      const cx = pl + groupW * i + groupW / 2;
      const a = sa[i];
      const b = sb[i];

      // bar A (left)
      const axL = cx - barW - gap / 2;
      const ay = scaleY(a.value);
      const ah = Math.max(0, scaleY(0) - ay);
      bars.push({
        x: axL, y: ay, w: barW, h: ah,
        hex: a.hex, opacity: 1, dash: '',
        labelY: ay - 5, labelText: usd0(a.value),
        tip: `<div class="tt-h">${grps[i]}</div><div class="tt-r"><span>${names[0]}</span><span class="num">${usd0(a.value)}</span></div>`,
      });

      // bar B (right)
      const bxL = cx + gap / 2;
      const by = scaleY(b.value);
      const bh = Math.max(0, scaleY(0) - by);
      const partial = !!b.partial;
      bars.push({
        x: bxL, y: by, w: barW, h: bh,
        hex: b.hex, opacity: partial ? 0.45 : 1, dash: partial ? '4 3' : '',
        labelY: by - 5, labelText: usd0(b.value),
        tip: `<div class="tt-h">${grps[i]}${partial ? ' &middot; parcial' : ''}</div><div class="tt-r"><span>${names[1]}</span><span class="num">${usd0(b.value)}</span></div>`,
      });
    }

    // x-axis labels
    const xLabels = grps.map((g, i) => ({
      x: pl + groupW * i + groupW / 2,
      text: g,
    }));

    // legend
    const legend = [
      { hex: sa[0]?.hex || '#999', name: names[0] },
      { hex: sb[0]?.hex || '#999', name: names[1] },
    ];

    return { gridLines, bars, xLabels, legend };
  });
}
