import { Injectable, computed, signal } from '@angular/core';
import { CostosData } from './costos.types';
import costosData from '../../assets/data/costos.json';

@Injectable({ providedIn: 'root' })
export class DataService {
  readonly data = signal<CostosData>(costosData as CostosData);

  readonly meses = computed(() => this.data().meta.meses);
  readonly lastData2026 = computed(() => this.data().meta.lastData2026);
  readonly n26 = computed(() => this.lastData2026() + 1);
  readonly status2026 = computed(() => this.data().meta.status2026);
  readonly hasPartial = computed(() => this.status2026().includes('partial'));
  readonly general = computed(() => this.data().general);
  readonly services = computed(() => this.data().services);
  readonly models = computed(() => this.data().models);
}
