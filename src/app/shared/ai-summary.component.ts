import {
  Component, ChangeDetectionStrategy, inject, input, computed,
} from '@angular/core';
import { AiService } from '../core/ai.service';

@Component({
  selector: 'app-ai-summary',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      padding: 16px 14px;
      background: #FAFBFC;
    }
    .ai-h {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 600;
      color: var(--muted, #64757F);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 10px;
    }
    .ai-h .dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--accent, #5FBFA0);
      flex: 0 0 6px;
    }
    .ai-body {
      font-size: 12px;
      line-height: 1.55;
      color: var(--text, #17242F);
      flex: 1;
      overflow-y: auto;
    }
    .ai-body p {
      margin: 0 0 12px;
    }
    .ai-body p:last-child {
      margin-bottom: 0;
    }
  `],
  template: `
    <div class="ai-h"><span class="dot"></span>Análisis IA</div>
    <div class="ai-body">
      @for (paragraph of paragraphs(); track $index) {
        <p>{{ paragraph }}</p>
      }
    </div>
  `,
})
export class AiSummaryComponent {
  private readonly ai = inject(AiService);

  readonly cacheKey = input.required<string>();
  readonly chartTitle = input.required<string>();

  readonly result = computed(() => this.ai.getCachedAnalysis(this.cacheKey()));

  readonly paragraphs = computed(() =>
    this.result()
      .split('\n')
      .map((p) => p.trim())
      .filter((p) => p.length > 0)
  );
}
