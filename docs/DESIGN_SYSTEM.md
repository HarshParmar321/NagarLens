# NagarLens design system

Audit and reference for the web frontend (`frontend/`: Next.js 16, Tailwind 4, shadcn/ui, Recharts 3, react-leaflet 5).
Snapshot of the working tree on 2026-11-21, including the uncommitted polish edits (amber text fix, teal duplicate-bill colour, touch targets).
This file documents what exists, with file references. Anything marked **Proposal** has not been applied.

---

## 1. Design System Audit

### Summary

| Components reviewed | Issues found | Score |
|---|---|---|
| 34: 9 shared (`components/bits.tsx`), 2 shell (`Shell`, `Stat`), `WardMap`, 10 page-local (`FlowNode`, `Versus`, `Evidence`, `Cell`, `Bill`, `CaseView`, `SlaClock`, `Stamp`, `Group`, `IssueCard`), 12 shadcn primitives | 16 (8 naming, 4 token, 4 component/a11y) | **58/100**: one colour language is applied consistently (and AA-checked), and the shared blocks are reused well (`Kpi` 20 uses, `Section` 17). But nothing is tokenised: 289 hex literals (54 distinct), 121 arbitrary font sizes, and 0 of the 12 shadcn primitives are imported. |

### Naming Consistency

| Issue | Components | Recommendation |
|---|---|---|
| N1. The colour prop is named three ways | `Kpi`, `Stat`, `Bill`, `Stamp` take `tone` (raw hex). `Pill` takes `color` + `bg`. `PeerChip` is keyed by its display string. | Use one prop, `tone: "held" \| "failed" \| "review" \| "warranty" \| "primary" \| "neutral"`, resolved to tokens inside the component. |
| N2. Six key vocabularies for one palette | `KIND_COLOR` {source, work_type, held, failed, review} (`app/page.tsx:16`), `TONE` {ok, warn, flag, na} (`app/case/page.tsx:16`), `STATUS` {funded, deferred, warranty, excluded} (`app/next-rupee/page.tsx:24`), `CHIP_TONE` (`bits.tsx:27`) and `VERDICT_TONE` (`scorecards/page.tsx`) keyed by copy, `RULE_COLOR` by rule_id (`lib/api.ts:35`) | Put one `TONES` map in `lib/tones.ts` and map each domain key onto it. |
| N3. A hex carries two meanings | `#C2410C` means "needs review" but also draws the neutral "Billed, ₹" line in the rain chart (`app/page.tsx:97`). The `duplicate_bill`/primary-blue clash is already fixed: the rule now uses teal `#0F766E` (`lib/api.ts:37`). | Draw the billed line in ink `#16181D` or primary blue. |
| N4. "Label over value" exists five times | `Kpi` (bits:6), `Stat` (shell:116), `Cell` (audit:160), `Stamp` (case:245), `Versus` (scorecards) | Use `Kpi` with `size="sm" \| "md" \| "hero"` and `surface="card" \| "inset" \| "dark"`. |
| N5. The eyebrow label is copy-pasted | `text-[11px] font-bold uppercase tracking-wide text-[#454952]` ×6, plus an 11.5px table-head variant ×3 | Extract an `<Eyebrow>` component. |
| N6. Chips are built ad hoc | `Pill` exists, yet "under warranty" is an inline span (`app/page.tsx`), reason chips are copied twice (ask, next-rupee), and the toggle-chip classes are copied ×3 (scorecards, audit, case) | Add `<Pill tone>`, `<ReasonChip>` and `<ToggleChip pressed>`. |
| N7. Card containers have no shared name | `Section`, `Group` (`<details>` card, next-rupee:187), 6 raw `rounded-2xl border` divs, and 9 callouts in 4 tints (blue ×3, green ×1, yellow ×2, peach ×3, one of which is an inline `ErrorBox` copy in `ask/page.tsx`) | Add `<Section collapsible>` and `<Callout tone="info\|success\|note\|error">`. |
| N8. "Failed" copy drifts | "Failed within 30 days" ×2, "Failed in 30 days", "Re-opened", "Re-opened in 30 days", "re-opened within 30 days" ×2 | Use one label for the state ("Failed within 30 days") and one for the event ("re-opened within 30 days"). |

### Token Coverage

| Category | Defined (CSS variables / theme tokens) | Hardcoded values found |
|---|---|---|
| Colour | Greyscale shadcn tokens in oklch (`--background`, `--primary`, `--muted*`, `--border`, `--chart-1..5`, sidebar) in `app/globals.css:51-118`. None carries a NagarLens meaning, and app code references none of them. | **289 hex literals, 54 distinct.** 201 sit in Tailwind arbitrary classes (`text-[#..]` 110, `border-[#..]` 55, `bg-[#..]` 35, `accent-[#..]` 1). 83 are quoted strings in inline `style`, tone props, colour maps, Recharts props and Leaflet styles. There are also 4 `rgba()` (hero gradient, SLA heatmap) and 3 hexes in `globals.css:132-133`. |
| Typography | `--font-sans`, `--font-mono`, `--font-heading` (`globals.css:10-12`). The same stack is declared again, unlayered, on `html, body` (`globals.css:132`). | **121 `text-[Npx]`** across 17 sizes, against 4 `text-sm`. Recharts `fontSize` 11 ×4 and 12.5 ×1. Leaflet tooltip 12px. |
| Spacing | Tailwind default scale only | Padding and gaps stay on the scale (`gap-2` 19, `px-3` 15, `gap-3` 14, `space-y-5` 7). There are 18 arbitrary layout values: `max-w-[1280px]` ×3, `grid-cols-[..]` templates, `max-h-[620px]`/`[420px]`, `left-[170px]`, and the `min-w-[480/520/640/760px]` scroll guards. |
| Radius | `--radius: 0.625rem`, giving `sm` 6px, `md` 8px, `lg` 10px, `xl` 14px, `2xl` 18px | `rounded-lg` 14, `rounded-xl` 11, `rounded-full` 11, `rounded` (4px) 10, `rounded-2xl` 7, `rounded-sm` 4. Inline `borderRadius: 12` on the map, 8px on the Leaflet tooltip. |
| Shadow | none | 0 `shadow-*`. Elevation is a 1px border on a tinted page, by design. |
| Borders | `--border` (unused) | Card `#D5D6D0` (19), divider `#EDEDE8` (11). Inline `borderTop: 5px/6px solid <tone>` (`Bill`, case steps). Nav `border-b-[3px]`. |

**Most-used hardcoded hexes.** The top 12 account for 198 of the 289 literals.

| Hex | Count | Meaning |
|---|---|---|
| `#454952` | 60 | Secondary text: labels, hints, units (9.0:1 on white) |
| `#16181D` | 28 | Ink: headings, values, hero band, selected ward/decision |
| `#D5D6D0` | 19 | Card and input border |
| `#1E4FD8` | 16 | Primary / neutral accent: active tab, selection, Ask button, slider, risk bar, Sankey links, heatmap |
| `#C2410C` | 15 | Needs review / flagged / over rate card / SLA deadline |
| `#EDEDE8` | 11 | Row divider, chart grid, template-badge bg |
| `#2A2D33` | 11 | Body-secondary text: legends, lists, badge text, "in line with peers" |
| `#1E7B34` | 11 | Held / better than peers / SLA met / planned within budget |
| `#8A8F98` | 8 | Neutral **fill**: work-type node, rate-card bar, `TONE.na` |
| `#8A5A00` | 7 | Failed / below peers / SLA missed, **as text** |
| `#F6F6F3` | 6 | Page background, inset panels (`Versus`, `Stamp`, officer decision) |
| `#17306E` | 6 | Text on blue tints (selected chip, reason chips, AI badge) |

### Component Completeness

Scores are out of 10: states 3, variants 3, docs 2, a11y 2.

| Component | States | Variants | Docs | Score |
|---|---|---|---|---|
| `Kpi` (bits:6) | Value only. Callers pass "…" or "–". | `tone` = any hex | File comment | 5 |
| `Section` (bits:59) | n/a | `right` slot; no collapsible variant (`Group` copies it) | none | 6 |
| `PageTitle` (bits:88) | n/a | `sub` | none | 7 |
| `Pill` (bits:42) | n/a | Free `color`/`bg` | none | 4 |
| `PeerChip` (bits:33) | Unknown value falls back to "in line" | 3, keyed by copy | none | 6 |
| `DataBadge` (bits:19) | Fixed label | `className` | Intent comment | 6 |
| `SourceBadge` (bits:50) | claude / cache / template | 2 | none | 6 |
| `Loading` (bits:74) | Pulse. Also used as an empty prompt ("Pick a lead"). | `label` | none | 4 |
| `ErrorBox` (bits:78) | One message for every error | none | none | 3 |
| shadcn `ui/*` (badge, button, card, input, select, separator, skeleton, slider, table, tabs, textarea, tooltip) | Full (focus-visible, disabled, aria) | cva | upstream | **0/12 imported.** Buttons, inputs, selects, sliders and tables are hand-built. |

**Component/a11y issues**
- C1: Custom buttons and chips have no `focus-visible` style (`outline-ring/50` in `globals.css:122` only tints the browser default). The 3 toggle-chip groups have no `aria-pressed`. Touch targets are good: `min-h-10`/`min-h-11` were added across nav, chips and buttons.
- C2: Text alternatives cover 2 of 6 visuals. `role="img"` plus a data summary exists on the Sankey and rain chart (`app/page.tsx:56,87`). The SLA heatmap, rate-card bars, SLA clock and ward map have none.
- C3: `Loading` has no `role="status"` and `ErrorBox` has no `role="alert"`, so neither is announced.
- C4: `Loading` doubles as an empty state, and `ErrorBox` always says "Could not reach the API", even for 4xx. `ask/page.tsx` copies its markup inline to show a different message.

### Priority Actions

1. **Add the `--nl-*` tokens (section 5) and migrate the top 12 hexes (198 literals).** Classes become `text-nl-muted` and `border-nl-border`; JS maps use `var(--nl-…)`. The amber split (`#B07A00` fill, `#8A5A00` text) is correct today only by hand-typing, and tokens lock it in.
2. **Make tone semantic.** Add a single `TONES` map plus a `tone` union prop on `Kpi`/`Pill`/`Stat`/`Stamp`, absorbing `KIND_COLOR`, `TONE`, `STATUS`, `CHIP_TONE`, `VERDICT_TONE` and `RULE_COLOR`. Recolour the rain chart's billed line (N3).
3. **Fix announcements and focus.** `Loading` gets `role="status"`, `ErrorBox` gets `role="alert"` and a `title` prop (then delete the inline copy in `/ask`). Add `focus-visible:ring-2 ring-[--nl-primary]` and `aria-pressed` on toggle chips.
4. **Extract `Eyebrow` (6), `ToggleChip` (3), `ReasonChip` (2) and `Callout` (9) into `bits.tsx`.** Give the heatmap, rate-card bars, SLA clock and ward map a `role="img"` summary.
5. **Collapse the type scale from 17 sizes to 8** (11/12/13/14/16/18/24/30) as `--text-nl-*`: 11.5→12, 12.5→13, 13.5/14.5→14, 15→16, 17→18, 20/22/26→24. Then adopt shadcn `Button`/`Table`/`Skeleton` or delete `components/ui/`.

---

## 2. Tokens

### Colour palette (names proposed; hexes and usage exist today)

Rule (`components/bits.tsx:3-4`): **green = held / better than peers, amber = failed / below peers, orange = needs review, purple = warranty, blue = neutral / primary.**

| Proposed token | Hex | Meaning | Where used |
|---|---|---|---|
| `--nl-ink` | `#16181D` | Primary text, hero | Headings, values, hero band, Sankey source node, selected ward outline, selected decision, heatmap cell text |
| `--nl-ink-2` | `#2A2D33` | Secondary body text | Legends, method lists, `DataBadge`/`Pill` default text |
| `--nl-muted` | `#454952` | Labels, hints, units | `Section` hint, `Kpi` label/sub, table heads, footer |
| `--nl-subtle` | `#8A8F98` | Neutral fill (3.25:1, not for text) | Work-type node, rate-card bar, hero arrows (5.5:1 on ink) |
| `--nl-subtle-text` | `#6A6F78` | Neutral as text (5.05:1) | `RULE_COLOR.sla_missed`, rank numbers (`next-rupee`) |
| `--nl-faint` | `#B9BDC6` | Faint fill, hover border | "Upper end of normal" bar, in-line chip border, list hover |
| `--nl-border` | `#D5D6D0` | Card and input border | `Kpi`, `Section`, `Loading`, inputs, buttons, nav rule |
| `--nl-divider` | `#EDEDE8` | Row divider, grid | Table rows, `CartesianGrid`, template badge bg |
| `--nl-track` | `#EFEFEA` / `#F1F1EC` | Bar track, neutral chip | Rate-card and risk bars, SLA clock, "in line" chip (merge the two) |
| `--nl-chip` | `#E4E4DE` | Default pill bg | `Pill`, `DataBadge` |
| `--nl-page` / `--nl-card` | `#F6F6F3` / `#FFFFFF` | Page bg / card surface | `globals.css:132`, `Shell`, inset panels / every card |
| `--nl-on-dark-muted` | `#C9CBD1` | Secondary text on hero | Tagline, stat labels, disclaimer |
| `--nl-primary` | `#1E4FD8` | Neutral accent, selection, action | Active tab, selected chip/row, Ask button, slider `accent`, risk bar, Sankey links, heatmap `rgba(30,79,216,α)` |
| `--nl-primary-ink` / `-tint` / `-wash` | `#17306E` / `#E3EBFD` / `#EEF3FD` | Text, selected bg, info callout | Toggle chips, `SourceBadge` (claude), reason chips, verdict/answer cards |
| `--nl-primary-line` / `-select` | `#A9BEF0`, `#C9D7F5` / `#F3F6FE` | Callout and chip border / selected row | Audit lead list, "this case" row |
| `--nl-chart-blue-1..2` | `#9DB4EE`, `#5C82E6` | Chart ramp | Rainfall bars, SLA clock segments |
| `--nl-held` | `#1E7B34` | Held, better than peers, met | `Versus`, case step `ok`, Sankey held, Ask outcome, plan KPI, matching bill |
| `--nl-held-ink` / `-tint` | `#1E5B1F` / `#E5F4E4` | Chip text / bg | "better than peers", `STATUS.funded` |
| `--nl-success-wash` / `-line` | `#EAF6EA` / `#9CCFA0` | Success callout | "Recover first, then reinvest" |
| `--nl-failed` | `#B07A00` | Failed / below peers, **fills only** | Sankey failed node (`app/page.tsx:16`), "below peers" border (`bits.tsx:30`) |
| `--nl-failed-text` | `#8A5A00` | Same meaning, **as text** | `Kpi` failed spend, `Versus`, case history and `Stamp`, `TONE.warn`, `RULE_COLOR.reopened_fix` |
| `--nl-failed-ink` / `-tint` | `#7A4B00` / `#F9EEDA` | Chip text / bg, reasons | "below peers", `STATUS.deferred`, exclusion reasons, drainage pill |
| `--nl-note-wash` / `-line` | `#FFF8E6` / `#E8CF8A` | Caution note | "Borderline" (audit), "assigned before complaint" (case) |
| `--nl-review` | `#C2410C` | Needs review, flagged | `Kpi` "To review", overbilled rule, flagged bill, SLA deadline, `=` marks |
| `--nl-review-strong` | `#9A3208` | Over budget (text, 7.4:1) | Billed KPI sub-line (`app/page.tsx:47`) |
| `--nl-review-ink` / `-tint` / `-line` | `#7A2A08` / `#FFF3EC` / `#E9A988` | Lead and error callout | `ErrorBox`, case lead cards, Ask error |
| `--nl-review-on-dark` | `#FF9B6A` | Brand / review on hero | "Lens" wordmark, hero review stat |
| `--nl-map-1..5` | `#FDF3EC #F9D2B8 #F0A070 #D9662B #A8340A` | ₹ to review, low to high | `ward-map.tsx:12` choropleth and legend |
| `--nl-warranty` | `#5B4BC4` | Warranty (DLP) | "Sent to warranty" KPI, `RULE_COLOR.dlp_paid_by_bmc` (6.5:1) |
| `--nl-warranty-ink` / `-tint` | `#3A2E8C` / `#EFEDFF` | Warranty pill | "under warranty", `STATUS.warranty`, DLP surface pill |
| `--nl-duplicate` | `#0F766E` | Duplicate-bill rule (teal, 5.5:1) | `RULE_COLOR.duplicate_bill` |
| `--nl-cta-on-dark` | `#7FD99A` (hover `#9BE5B0`, text `#0F2A17`) | Hero call to action | "See the next-rupee plan →" (`shell.tsx:78`) |

**Accessibility rule.** Amber `#B07A00` fails WCAG AA as small text: 3.73:1 on white, 3.45:1 on `#F6F6F3`. **Text uses `#8A5A00` (5.93:1); fills, borders and chart marks keep `#B07A00`.** The working tree now follows this everywhere. Other measured ratios on white:
- held `#1E7B34`: 5.33
- review `#C2410C`: 5.18 (4.76 on `#FFF3EC`)
- primary `#1E4FD8`: 6.63
- muted `#454952`: 9.02
- all ink-on-tint chip pairs: above 6:1

### Typography

- **Family:** `Inter, "Segoe UI", system-ui, …, "Noto Sans Devanagari", sans-serif` (`globals.css:10,132`). Inter is not loaded, so Windows renders Segoe UI. Devanagari covers Marathi and Hindi, and `/ask` sets `lang` on the answer.
- **Sizes** (`text-[Npx]`, count): 13 (28), 12.5 (18), 11 (16), 12 (12), 11.5 (10), 16 (8), 13.5 (8), 18 (4), 26 (3), 24, 22, 17, 15, 14, 14.5 (2 each), 30 (1), 20 (1).
- **Roles:** page title 24 extrabold tight (`PageTitle`) · section title 16 bold (`Section`, `Group`) · KPI value 26 extrabold (`Kpi`) · hero stat 30 extrabold (`Stat`) · body 13/13.5 · hint 12.5 · eyebrow 11 bold uppercase wide · badge 11–11.5 bold · citizen answer 18 relaxed (`/ask`).

- **Weights:** semibold 30, bold 26, extrabold 17, normal 7 (no `font-medium`). `tabular-nums` appears only on the home roads table.

### Spacing, radius, borders, shadows

- **Layout:** `max-w-[1280px] px-5` column (`shell.tsx`). Pages stack with `space-y-5`. KPI rows use `gap-3`, section grids `gap-5`. Padding is `p-5` for `Section` and `px-4 py-3` for `Kpi`. Wide tables and the Sankey sit in `overflow-x-auto` with a `min-w-[…]` guard.
- **Radius:** `rounded-2xl` 18px (Section, hero, large cards) · `rounded-xl` 14px (Kpi, callouts, Loading, ErrorBox) · `rounded-lg` 10px (inputs, buttons, list rows, PeerChip) · `rounded-full` (pills, chips) · `rounded` 4px (bars).
- **Borders:** 1px hairlines everywhere, plus semantic top bars (`borderTop: 6px solid <tone>` on case steps, 5px on `Bill`) and the 3px active-tab underline.
- **Shadows:** none.

---

## 3. Components (`frontend/components/bits.tsx`)

### Kpi
Label, big value, and optional context line in a white bordered tile. It is the unit of every KPI row.

| Property | Type | Default | Description |
|---|---|---|---|
| `label` | `string` | (required) | 12px semibold muted label |
| `value` | `ReactNode` | (required) | 26px extrabold value |
| `sub` | `ReactNode` | none | 12px context: period, peers, counts |
| `tone` | `string` (hex) | `#16181D` | Value colour |

- **Tones:** review `#C2410C`, held `#1E7B34`, failed `#8A5A00`, warranty `#5B4BC4`, primary `#1E4FD8`, `RULE_COLOR[id]`.
- **States:** none built in. Callers render "…" or "–".
- **A11y:** the label is not tied to the value; a `<dl>` would fix that. The tone must be backed by words.
- **Do:** put the comparison in `sub` ("similar wards manage 62%"). **Don't:** colour a value without saying why in `label` or `sub`.

```tsx
<Kpi label="To review" value={inr(d.review.total_at_risk_inr)} sub={`${d.review.jobs} jobs, counted once`} tone="#C2410C" />
```

### Section
A white `<section>` card with an `h2`, an optional hint, and a right slot.

| Property | Type | Default | Description |
|---|---|---|---|
| `title` | `string` | (required) | 16px bold `h2` |
| `hint` | `string` | none | 12.5px muted: method, units, how to read it |
| `right` | `ReactNode` | none | `DataBadge`, pill, amount or action |
| `children` | `ReactNode` | (required) | Body |

- **Variants:** none. The collapsible copy is `Group` (`next-rupee/page.tsx:187`).
- **A11y:** semantic landmark plus `h2`; `PageTitle` owns the `h1`.
- **Do:** explain the encoding in `hint` ("Darker = more to review"). **Don't:** nest a Section in a Section.

```tsx
<Section title="Rupees to review, by ward" hint="Darker = more to review." right={<DataBadge />}>
  <WardMap … />
</Section>
```

### PageTitle

| Property | Type | Default | Description |
|---|---|---|---|
| `title` | `string` | (required) | 24px extrabold `h1`: the brief's question, made concrete with data |
| `sub` | `string` | none | 13.5px scope and caveat |

- **Do:** state the caveat ("billed amounts from work orders, not payments"). **Don't:** use more than one per page.

```tsx
<PageTitle title={`Where should ward ${ward}'s next rupee go?`} sub="Costs are estimates from the rate card." />
```

### Pill

| Property | Type | Default | Description |
|---|---|---|---|
| `children` | `ReactNode` | (required) | Label (11.5px bold, `nowrap`) |
| `color` | `string` (hex) | `#2A2D33` | Text |
| `bg` | `string` (hex) | `#E4E4DE` | Background |

- **Variants in use:** neutral "Needs review"; warranty `#3A2E8C`/`#EFEDFF`; drainage `#7A4B00`/`#F9EEDA`; plan `STATUS`. **A11y:** every pair in use is above 6:1; static text.
- **Do:** use the ink/tint pairs. **Don't:** pass a fill hue (`#B07A00`, `#8A8F98`) as `color`.

```tsx
<Pill color="#3A2E8C" bg="#EFEDFF">Under warranty</Pill>
```

### PeerChip

| Property | Type | Default | Description |
|---|---|---|---|
| `label` | `string` | (required) | Dimension (Speed / Durability / Cost), as an eyebrow |
| `value` | `string` | (required) | `"better than peers"` \| `"in line with peers"` \| `"below peers"`; unknown values fall back to in-line |

- **Tones:** better = green border with `#1E5B1F` on `#E5F4E4`; in line = grey; below = `#B07A00` border with `#7A4B00` on `#F9EEDA`. The verdict is spelled out, so colour is not the only cue.
- **Do:** compare against peers on the same job mix. **Don't:** invent new verdict phrases; keep the three neutral ones.

```tsx
<PeerChip label="Durability" value={r.durability_chip} />
```

### DataBadge

Takes only `className?: string`. Renders "Synthetic (organizer)". Every number carries its data layer (`bits.tsx:18`).
- **Do:** put it in the `right` slot of every data `Section`. **Don't:** crop it out of demo screenshots.

```tsx
<Section title="Leads" right={<DataBadge />}>…</Section>
```

### SourceBadge

| Property | Type | Default | Description |
|---|---|---|---|
| `source` | `string` | none | `"claude"` or `"cache"` gives "Written by Claude" (blue). Anything else gives "Template (Claude offline)" (grey). |

- **Do:** show it beside every generated answer or verdict. **Don't:** label template fallbacks as Claude.

```tsx
{verdict ? <SourceBadge source={verdict.source} /> : null}
```

### Loading

| Property | Type | Default | Description |
|---|---|---|---|
| `label` | `string` | `"Loading…"` | Placeholder text in a dashed, pulsing box |

- **A11y:** needs `role="status"` and a `motion-reduce:animate-none` variant.
- **Do:** name what is loading ("Loading the case…"). **Don't:** use it for empty results. Write a sentence instead ("No leads for this filter.").

```tsx
if (!q.data) return <Loading label="Loading map…" />;
```

### ErrorBox

| Property | Type | Default | Description |
|---|---|---|---|
| `error` | `unknown` | (required) | Raw message shown under "Could not reach the API" plus the uvicorn start command |

- **A11y:** needs `role="alert"`. `#7A2A08` on `#FFF3EC` is 8.9:1.
- **Do:** return it early when a page's primary query fails. **Don't:** copy its markup for other messages (as `/ask` does). Add a `title` prop.

```tsx
if (q.error) return <ErrorBox error={q.error} />;
```

---

## 4. Patterns

- **Page shell and nav tabs** (`components/shell.tsx`): a 1280px column with the hero band, a tab nav (`NAV`, one label per question in the brief), `<main>` and a footer disclaimer. The active tab gets a `#1E4FD8` 3px underline, blue text and `aria-current="page"`. Tabs scroll horizontally on mobile with `min-h-11` targets. The ward selector lives in the hero and feeds every page through `useWard()`.
- **Hero band:** ink `#16181D` with a gradient over `public/hero.png`. Wordmark "Nagar" in white, "Lens" in `#FF9B6A`. Story steps: billed, then needs a second look (orange), then the green next-rupee CTA, joined by `aria-hidden` arrows. Closes with "leads for review, not accusations".
- **KPI row:** `grid grid-cols-2 gap-3 md:grid-cols-5` of `Kpi`. Colour only the values that carry meaning, and give every value a comparison or count in `sub`.
- **Section card:** `Section` inside `lg:grid-cols-5` (3+2) or `lg:grid-cols-2` splits.
- **Ranked cards (next-rupee):** `Group` (`<details>`, "Funded" open) holds `IssueCard`s. Each card shows rank; road, category and status `Pill`; blue reason chips; method and match quality; a risk bar (0–100, `#1E4FD8`, labelled "Risk n / 100"); and the estimated cost. Nothing is dropped silently. Excluded issues and complaints are listed with a reason in `#7A4B00`.
- **Evidence card (audit):** `Evidence` (`audit/page.tsx:79`) is a `Section` whose `right` slot holds the amount to review in the rule colour. Order: "Needs review" `Pill` + `DataBadge`; one exhibit per rule (duplicate bill = twin `Bill` cards with green/orange top bars and `=` on matching fields; over rate card = three bars; warranty = a fact grid); "Why it was flagged / Fair context / Next action"; officer-decision buttons ("a human decides").
- **Chips and pills:** `Pill` = status; `PeerChip` = peer verdict; reason chip = `#EEF3FD`/`#C9D7F5`/`#17306E` at 11.5px; toggle chip = selected `#1E4FD8` border on `#E3EBFD` with `#17306E` text, otherwise `#D5D6D0` on white.
- **Charts**
  - **Colours:** semantic (`KIND_COLOR` Sankey nodes; links `#1E4FD8` at 0.16; rainfall `#9DB4EE`).
  - **Legends name units:** "Rainfall, mm (left axis)", "Billed, ₹ (right axis)", "Band width = rupees billed", "₹ to review:" (map).
  - **Axes:** `en-IN` "d MMM" dates, `inr()` ticks, 11px, horizontal grid `#EDEDE8` only.
  - **Text alternatives:** wrap the chart in `role="img"` with a data-bearing `aria-label` (`app/page.tsx:56,87`). Extend this to the remaining 4 visuals.
  - **SLA heatmap:** `rgba(30,79,216, 0.04 + 0.56·v)` with ink text in every cell (6.2:1 at the darkest), a 5-step legend, and the "All contractors" row set off by a 2px ink rule.
  - **`Versus`:** colours follow the chip verdict and add `▲`/`▼` marks, so colour is never the only cue.
- **Data-layer and AI source badges:** `DataBadge` on data sections, `SourceBadge` on generated text. The hero badge reads "AI: <engine>" or "AI offline: cached answers + templates".
- **Rupee formatting** (`lib/format.ts`). Every function formats only and never computes. Missing values render "–". `inr(x)`: `₹1.23 Cr` (≥1e7), `₹4.5 L` (≥1e5), else `₹12,345` (en-IN grouping) · `inrFull(x)`: full en-IN number for bills and evidence · `pct(x, digits=0)` · `when(iso, withTime)`: en-IN date, 24h · `cleanName()` strips " (synthetic)".
- **Neutral wording:** "needs review", "needs a second look", "lead", "to review", "fair context". **Never "fraud".** A grep for fraud, scam, corrupt or theft in `app/` and `components/` finds 0 hits. Audit copy says "leads for review, not findings of wrongdoing"; plan copy says "a recommendation … not a funding approval".

---

## 5. Proposed token block for `app/globals.css` (Proposal, not applied)

Paste it after the existing `@theme inline` block. Tailwind 4 then generates `text-nl-muted`, `bg-nl-page`, `border-nl-border` and so on. JS colour maps should use `"var(--nl-held)"`.

```css
/* NagarLens semantic tokens (proposal). Fills keep the base hue; text uses -text / -ink variants (WCAG AA). */
:root {
  --nl-ink: #16181D;  --nl-ink-2: #2A2D33;  --nl-muted: #454952;
  --nl-subtle: #8A8F98;        /* fills only: 3.25:1 */
  --nl-subtle-text: #6A6F78;   /* neutral as text: 5.05:1 */
  --nl-faint: #B9BDC6;  --nl-border: #D5D6D0;  --nl-divider: #EDEDE8;  --nl-track: #EFEFEA;  --nl-chip: #E4E4DE;
  --nl-page: #F6F6F3;  --nl-card: #FFFFFF;  --nl-on-dark-muted: #C9CBD1;

  --nl-primary: #1E4FD8;  --nl-primary-ink: #17306E;  --nl-primary-tint: #E3EBFD;  --nl-primary-wash: #EEF3FD;
  --nl-primary-line: #A9BEF0;  --nl-primary-select: #F3F6FE;

  --nl-held: #1E7B34;  --nl-held-ink: #1E5B1F;  --nl-held-tint: #E5F4E4;
  --nl-failed: #B07A00;        /* fills, borders, chart marks only: 3.7:1 on white */
  --nl-failed-text: #8A5A00;   /* amber as text: 5.9:1 on white */
  --nl-failed-ink: #7A4B00;  --nl-failed-tint: #F9EEDA;
  --nl-review: #C2410C;  --nl-review-strong: #9A3208;  --nl-review-ink: #7A2A08;
  --nl-review-tint: #FFF3EC;  --nl-review-line: #E9A988;  --nl-review-on-dark: #FF9B6A;
  --nl-warranty: #5B4BC4;  --nl-warranty-ink: #3A2E8C;  --nl-warranty-tint: #EFEDFF;
  --nl-duplicate: #0F766E;
  --nl-note-wash: #FFF8E6;  --nl-note-line: #E8CF8A;
}

@theme inline {
  --color-nl-ink: var(--nl-ink);  --color-nl-ink-2: var(--nl-ink-2);  --color-nl-muted: var(--nl-muted);
  --color-nl-subtle: var(--nl-subtle);  --color-nl-subtle-text: var(--nl-subtle-text);  --color-nl-faint: var(--nl-faint);
  --color-nl-border: var(--nl-border);  --color-nl-divider: var(--nl-divider);  --color-nl-track: var(--nl-track);
  --color-nl-chip: var(--nl-chip);  --color-nl-page: var(--nl-page);  --color-nl-card: var(--nl-card);
  --color-nl-primary: var(--nl-primary);  --color-nl-primary-ink: var(--nl-primary-ink);
  --color-nl-primary-tint: var(--nl-primary-tint);  --color-nl-primary-wash: var(--nl-primary-wash);
  --color-nl-held: var(--nl-held);  --color-nl-held-ink: var(--nl-held-ink);  --color-nl-held-tint: var(--nl-held-tint);
  --color-nl-failed: var(--nl-failed);  --color-nl-failed-text: var(--nl-failed-text);
  --color-nl-failed-ink: var(--nl-failed-ink);  --color-nl-failed-tint: var(--nl-failed-tint);
  --color-nl-review: var(--nl-review);  --color-nl-review-ink: var(--nl-review-ink);  --color-nl-review-tint: var(--nl-review-tint);
  --color-nl-warranty: var(--nl-warranty);  --color-nl-warranty-ink: var(--nl-warranty-ink);
  --color-nl-warranty-tint: var(--nl-warranty-tint);  --color-nl-duplicate: var(--nl-duplicate);

  /* Collapsed type scale (proposal): replaces 17 arbitrary sizes */
  --text-nl-2xs: 11px;  --text-nl-xs: 12px;  --text-nl-sm: 13px;  --text-nl-base: 14px;
  --text-nl-lg: 16px;   --text-nl-xl: 18px;  --text-nl-2xl: 24px; --text-nl-3xl: 30px;
}
```

Migration examples:
- `text-[#454952]` becomes `text-nl-muted` (60 instances).
- `border-[#D5D6D0]` becomes `border-nl-border` (19).
- `style={{ color: tone }}` with `VERDICT_TONE` becomes `className="text-nl-held"` or `"text-nl-failed-text"`.
