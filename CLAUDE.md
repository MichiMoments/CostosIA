# ChatMigo Azure Cost Dashboard — Angular 22

## Source of Truth
- The original dashboard is `tablero-costos-chatmigo.html` at the project root (`CostosIA/`)
- Data extracted to `src/assets/data/costos.json` — this is STATIC and stable
- All CSS custom properties, colors, spacing, and fonts must match the original exactly

## Architecture Decisions
- **Angular 22** with standalone components (no NgModules)
- **Angular Router** for 4 views: `/resumen`, `/ambiente`, `/comparativa`, `/modelos`
- **Hand-rolled SVG** charts in Angular templates (no chart library) — matching the original approach
- **Signals** for all component state; `computed()` for derived data
- **Static JSON import** via `resolveJsonModule` — data bundled at build time, no HTTP calls
- **Global CSS** in `src/styles.css` — preserves all original CSS variables and classes
- **Tooltip system**: directive (`appTooltip`) + service (signals) + component (floating div)

## Project Structure
```
src/app/
  core/         — types, data service, format & chart utilities
  shared/       — tooltip directive/component/service
  charts/       — 6 SVG chart components (stacked-area, bar, grouped-bars, horizontal-bars, donut, multi-line)
  views/        — 4 view components (resumen, ambiente, comparativa, modelos)
```

## Fonts
- IBM Plex Sans (400, 500, 600) — body text
- Space Grotesk (500, 600) — display headings, KPI values

## Key Conventions
- Chart components receive data via signal inputs; compute SVG elements in `computed()` signals
- SVG rendered with `@for` loops and `[attr.*]` bindings (never innerHTML for SVG)
- All number formatting uses `es-CO` locale (Colombian Spanish number format)
- Spanish language throughout the UI
- Responsive at 880px breakpoint (sidebar collapses to top bar)

## Commands
- `ng serve` — dev server at localhost:4200
- `ng build` — production build
- `ng test` — run tests with Vitest
