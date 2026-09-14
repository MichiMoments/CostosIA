import { Injectable, inject, signal } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

@Injectable({ providedIn: 'root' })
export class TooltipService {
  private readonly sanitizer = inject(DomSanitizer);
  readonly visible = signal(false);
  readonly html = signal<SafeHtml>('');
  readonly x = signal(0);
  readonly y = signal(0);

  show(htmlContent: string, event: MouseEvent): void {
    this.html.set(this.sanitizer.bypassSecurityTrustHtml(htmlContent));
    this.visible.set(true);
    this.move(event);
  }

  move(event: MouseEvent): void {
    const pad = 12;
    let x = event.clientX + pad;
    let y = event.clientY + pad;
    const maxW = 260;
    if (x + maxW > window.innerWidth - 8) {
      x = event.clientX - maxW - pad;
    }
    if (y + 100 > window.innerHeight - 8) {
      y = event.clientY - 100 - pad;
    }
    this.x.set(x);
    this.y.set(y);
  }

  hide(): void {
    this.visible.set(false);
  }
}
