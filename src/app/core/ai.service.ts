import { Injectable, inject } from '@angular/core';
import { DataService } from './data.service';

@Injectable({ providedIn: 'root' })
export class AiService {
  private readonly ds = inject(DataService);

  getCachedAnalysis(cacheKey: string): string {
    return this.ds.aiCache()[cacheKey] || 'Análisis no disponible para esta selección.';
  }
}
