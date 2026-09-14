import { Component, inject } from '@angular/core';
import { TooltipService } from './tooltip.service';

@Component({
  selector: 'app-tooltip',
  standalone: true,
  template: `
    <div class="tt"
         [class.visible]="tt.visible()"
         [style.left.px]="tt.x()"
         [style.top.px]="tt.y()"
         [innerHTML]="tt.html()">
    </div>
  `,
})
export class TooltipComponent {
  readonly tt = inject(TooltipService);
}
