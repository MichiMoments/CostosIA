import { Directive, HostListener, inject, input } from '@angular/core';
import { TooltipService } from './tooltip.service';

@Directive({
  selector: '[appTooltip]',
  standalone: true,
})
export class TooltipDirective {
  readonly appTooltip = input.required<string>();
  private readonly tt = inject(TooltipService);

  @HostListener('mouseenter', ['$event'])
  onEnter(e: MouseEvent): void {
    this.tt.show(this.appTooltip(), e);
  }

  @HostListener('mousemove', ['$event'])
  onMove(e: MouseEvent): void {
    this.tt.move(e);
  }

  @HostListener('mouseleave')
  onLeave(): void {
    this.tt.hide();
  }
}
