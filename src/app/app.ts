import { Component, inject, signal, computed } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
import { filter, map } from 'rxjs';
import { toSignal } from '@angular/core/rxjs-interop';
import { TooltipComponent } from './shared/tooltip.component';
import { DataService } from './core/data.service';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, TooltipComponent],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  private readonly router = inject(Router);
  private readonly ds = inject(DataService);

  readonly menuOpen = signal(false);

  private readonly routeData = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map(() => {
        let route = this.router.routerState.root;
        while (route.firstChild) route = route.firstChild;
        return route.snapshot.data as { title?: string; desc?: string };
      }),
    ),
    { initialValue: { title: 'Resumen general', desc: '' } },
  );

  readonly viewTitle = computed(() => this.routeData().title ?? '');
  readonly viewDesc = computed(() => this.routeData().desc ?? '');
  readonly meses = this.ds.meses;
  readonly lastData2026 = this.ds.lastData2026;
  readonly hasPartial = this.ds.hasPartial;
  readonly footPeriod = computed(() => this.meses()[this.lastData2026()] + ' 2026');
  readonly badgeText = computed(() => {
    const m = this.meses()[this.lastData2026()];
    return this.hasPartial()
      ? `Datos hasta ${m} 2026 · mes parcial`
      : `Datos hasta ${m} 2026`;
  });

  toggleMenu(): void {
    this.menuOpen.update(v => !v);
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  readonly navItems = [
    { path: '/resumen', label: 'Resumen', color: 'var(--accent)' },
    { path: '/ambiente', label: 'Por ambiente', color: 'var(--dev)' },
    { path: '/comparativa', label: 'Comparativa entre meses', color: 'var(--qa)' },
    { path: '/modelos', label: 'Modelos desplegados', color: 'var(--mod)' },
  ];
}
