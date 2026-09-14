import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'resumen', pathMatch: 'full' },
  {
    path: 'resumen',
    loadComponent: () => import('./views/resumen.component').then(m => m.ResumenComponent),
    data: { title: 'Resumen general', desc: 'Panorama del consumo en Azure y consolidado anual por ambiente.' },
  },
  {
    path: 'ambiente',
    loadComponent: () => import('./views/ambiente.component').then(m => m.AmbienteComponent),
    data: { title: 'Consumo por ambiente', desc: 'Gasto por ambiente con el detalle de tipos de recurso de Azure.' },
  },
  {
    path: 'comparativa',
    loadComponent: () => import('./views/comparativa.component').then(m => m.ComparativaComponent),
    data: { title: 'Comparativa entre meses', desc: 'Año contra año y mes contra mes anterior (últimos 3 meses).' },
  },
  {
    path: 'modelos',
    loadComponent: () => import('./views/modelos.component').then(m => m.ModelosComponent),
    data: { title: 'Modelos desplegados', desc: 'Consumo de los modelos desplegados al máximo detalle: meter y part number.' },
  },
];
