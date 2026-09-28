# LearnSync design system

The admin, faculty, and student pages load `static/css/design-system.css` and `static/js/design-system.js`. The shared shell places a fixed GMVCC header above a left navigation rail on wide screens. At 820 px and below, the rail becomes a drawer opened from the same header. Pages keep a common content inset and card width.

## Foundations

| Token | Use |
| --- | --- |
| `--ds-navy` | Navigation and primary headings |
| `--ds-blue` | Primary buttons and links |
| `--ds-canvas` | Page background |
| `--ds-surface` | Cards and tables |
| `--ds-ink`, `--ds-muted` | Primary and supporting text |
| `--ds-border` | Field, card, and table boundaries |
| `--ds-radius`, `--ds-shadow` | Shared card shape and elevation |

Use `ds-page` for the content width, `ds-stack` for vertical spacing, `ds-grid` for responsive cards, `ds-toolbar` for wrapping controls, and `ds-card` for a surface. Forms use `ds-field`; tables use `ds-table-wrap` and `ds-table`. Existing `lms-*` components receive shared token overrides until legacy markup is retired. All actionable controls have a visible keyboard focus ring. On phones, the gradebook switches from a wide score matrix to an assessment selector and vertical student list.

Role navigation is configured in `static/js/design-system.js`. Add new role pages there and include the shared stylesheet and script in the page head. Browser names are written into the header using `textContent`.

## Listing and feedback rules

Use semantic `ds-table` or `lms-table` tables for listings. The shared script adds a search field, a filter for Status/State/Role/Type columns, and 10/25/50 row pagination; it also handles rows inserted later by Alpine. Tables scroll horizontally on small screens. Keep forms outside the listing table and use a compact outline/detail layout for chapter content.

All `/api/` requests show a top loading bar. Mutating requests disable the active submit button while pending and show a success or error toast. Success toasts disappear after five seconds; errors remain until dismissed. Page-specific validation and field errors may still appear beside the form. Use `LearnSyncUI.toast(message, type)` for non-API actions that need explicit feedback.
