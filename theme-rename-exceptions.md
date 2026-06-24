# Theme Rename Exceptions — ai-resume

Scope: `refactor: rename CSS tokens to semantic roles (theme-arch step 1)`

## Semantic mismatches

| Location | Old token | Usage | Issue | Recommended future token |
|---|---|---|---|---|
| `src/components/Footer.tsx:13` | `--color-text-primary` (was `--site-ink`) | `background-color` on `<footer>` | Correct value (`#1a2332`) but semantically wrong name for a background | `--color-bg-footer` |

## Tailwind key names preserved

No Tailwind config in this repo (uses plain Tailwind classes via CDN/index.css). N/A.

## Notes

All `--site-*` references in source replaced. Primitive block in `src/index.css` renamed to `--primitive-*`. Semantic `--color-*` tokens imported from `src/styles/themes/default.css`.

`src/components/AIChat.tsx` user message bubble text color was a hardcoded `#ffffff` — converted to `var(--color-interactive-text)` for semantic consistency.
