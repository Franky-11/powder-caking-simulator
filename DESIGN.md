# Powder Caking App Design System

## 1. Visual Theme & Atmosphere

Build a scientific transport simulation interface for evaluating caking risk in skim milk powder sacks.
The interface must feel precise, industrial, calm, and data-oriented. Use a light-first,
Carbon-inspired design language: white and gray surfaces, strict alignment, restrained color, and clear
status signaling.

The first screen is the simulator. Do not build a landing page, marketing hero, or explanatory splash screen.
The user should immediately see inputs, climate profile context, simulation status, and the main result.

Design keywords:

- scientific
- traceable
- operational
- engineering-grade
- data-dense but readable
- controlled and audit-friendly

Avoid:

- decorative gradients
- purple or purple-blue dominant palettes
- dark-dashboard default layouts
- card stacks nested inside cards
- playful illustration-driven UI
- marketing copy

## 2. Color Palette & Roles

Use a neutral gray foundation with blue interaction accents and separate semantic status colors.

| Token | Hex | Role |
| --- | --- | --- |
| `background` | `#f4f4f4` | Page background |
| `surface` | `#ffffff` | Primary panels and content surfaces |
| `surface-muted` | `#f8f8f8` | Secondary panels, table headers |
| `border-subtle` | `#e0e0e0` | Dividers, panel borders |
| `border-strong` | `#8d8d8d` | Focus outlines, selected states |
| `text-primary` | `#161616` | Main text |
| `text-secondary` | `#525252` | Supporting labels and descriptions |
| `text-muted` | `#6f6f6f` | Metadata and units |
| `interactive` | `#0f62fe` | Primary buttons, links, selected controls |
| `interactive-hover` | `#0043ce` | Hover and pressed interaction |
| `focus` | `#0f62fe` | Keyboard focus ring |
| `success` | `#24a148` | Not caked, valid, OK |
| `warning` | `#f1c21b` | Data warnings, nearing threshold |
| `danger` | `#da1e28` | Caked, critical threshold exceeded |
| `info` | `#4589ff` | Informational banners |
| `chart-temp` | `#0f62fe` | Temperature series |
| `chart-rh` | `#009d9a` | Relative humidity series |
| `chart-moisture` | `#8a3ffc` | Moisture and water activity series, minor accent only |
| `chart-strength` | `#da1e28` | Cake strength and critical line |
| `chart-grid` | `#e0e0e0` | Chart grid lines |

Purple may appear only as a minor chart color for moisture-related series. It must not dominate the page.

## 3. Typography Rules

Use a modern sans-serif with engineering clarity. Prefer this stack:

```css
font-family: "IBM Plex Sans", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

Use monospace only for units, parameter keys, fit names, endpoint paths, and CSV-like values:

```css
font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
```

Typography scale:

| Use | Size | Weight | Line height |
| --- | --- | --- | --- |
| Page title | `28px` | `400` | `36px` |
| Section heading | `20px` | `500` | `28px` |
| Panel heading | `16px` | `600` | `24px` |
| Body | `14px` | `400` | `20px` |
| Label | `12px` | `600` | `16px` |
| Metadata | `12px` | `400` | `16px` |
| KPI value | `28px` | `400` | `36px` |
| KPI unit | `13px` | `400` | `18px` |

Rules:

- Letter spacing is `0`.
- Do not scale font size with viewport width.
- Keep labels short and unit-aware.
- Use German product copy in the UI.
- Do not write self-referential copy such as "this card shows".

## 4. Layout Principles

Use an 8px spacing grid.

| Token | Value |
| --- | --- |
| `space-1` | `4px` |
| `space-2` | `8px` |
| `space-3` | `12px` |
| `space-4` | `16px` |
| `space-5` | `24px` |
| `space-6` | `32px` |
| `space-7` | `48px` |

Recommended simulator layout:

- Top application bar with product name, API status, and compact run status.
- Main content in a responsive two-column grid.
- Left column: simulation inputs and profile selection.
- Right column: KPI result band and warnings.
- Below: climate preview and charts.
- Tables and downloads appear after the main result, not before.

Desktop:

- Max content width: `1440px`.
- Page padding: `24px`.
- Input column width: `360px` to `420px`.
- Result/chart column fills remaining width.

Mobile:

- Single-column stack.
- Page padding: `16px`.
- Inputs first, KPIs second, charts third.
- Touch targets at least `40px` high.

## 5. Component Styling

### Panels

Use flat white surfaces with a subtle border. Panels are functional containers, not decorative cards.

```css
background: #ffffff;
border: 1px solid #e0e0e0;
border-radius: 0;
```

Do not nest panels inside panels. Repeated KPI tiles may sit within a result band, but avoid visual card stacks.

### Buttons

Primary button:

- background `#0f62fe`
- text `#ffffff`
- hover `#0043ce`
- border radius `0`
- height `40px`
- horizontal padding `16px`

Secondary button:

- white or transparent background
- border `1px solid #8d8d8d`
- text `#161616`

Disabled:

- background `#c6c6c6`
- text `#8d8d8d`
- no hover effect

### Inputs

Use compact, clearly labeled controls.

- height `40px`
- background `#f4f4f4`
- border bottom `1px solid #8d8d8d`
- no full outline unless focused
- focus border and outline use `#0f62fe`
- helper text uses `#6f6f6f`
- error text uses `#da1e28`

### KPI Tiles

KPI tiles should be stable in size and aligned in a grid.

- fixed min-height: `96px`
- label top
- value middle
- unit/status bottom
- status color appears as a left border or compact badge, not a full colored background

### Warning Banners

Warnings should be direct and visible without being visually loud.

- warning border-left `4px solid #f1c21b`
- danger border-left `4px solid #da1e28`
- background `#ffffff`
- text `#161616`

### Tables

Use dense but readable tables.

- header background `#f4f4f4`
- row border `1px solid #e0e0e0`
- numeric columns right-aligned
- units in header labels

## 6. Charts

Use ECharts with a restrained technical style.

Chart rules:

- white plot background
- subtle gray grid lines
- no decorative gradients
- line width `2px`
- dots disabled by default for long time series
- tooltips enabled
- axis labels use `12px`
- legends are compact and top-aligned
- critical `20 kPa` line is red and labeled `kritische Festigkeit 20 kPa`

Recommended series colors:

- temperature: `#0f62fe`
- relative humidity: `#009d9a`
- moisture / water activity: `#8a3ffc`
- Tg: `#6f6f6f`
- caking rate: `#fa4d56`
- cake strength: `#da1e28`

## 7. Status Semantics

Use consistent status language:

- `Nicht verklumpt`: success, green
- `Warnung`: warning, yellow
- `Verklumpt`: danger, red
- `Datenhinweis`: info, blue

Do not use vague risk wording unless a risk-class model is implemented. Until then, the primary decision is based on:

```text
sigma_c_kPa >= 20
```

## 8. Responsive Behavior

- Collapse to one column below `900px`.
- Preserve input order and result order.
- Keep chart containers at stable heights:
  - desktop: `320px` to `420px`
  - mobile: `260px` to `320px`
- Long labels wrap instead of shrinking font size.
- Do not let KPI values resize their tiles.

## 9. Do's and Don'ts

Do:

- start with the simulator, not a marketing screen
- show units everywhere
- keep forms compact and grouped by decision
- make warnings visible before simulation is run
- show API or simulation errors plainly
- make the `20 kPa` threshold visually explicit
- use whitespace to separate functional regions

Don't:

- hide scientific parameters behind decorative UI
- use dominant purple, beige, orange, brown, or dark-blue palettes
- create floating ornamental shapes
- put the main experience inside a decorative preview frame
- use rounded pill-heavy consumer styling
- invent risk classes without model support
- make charts visually heavier than the result decision

## 10. Implementation Notes

The frontend should define CSS custom properties matching these tokens.

Prefer semantic class names:

- `.app-shell`
- `.top-bar`
- `.input-panel`
- `.result-band`
- `.kpi-grid`
- `.warning-list`
- `.chart-panel`
- `.data-table`

The preview file `preview.html` in this repo is the local visual catalog for this design system. Use it as the
reference when implementing the React UI.
