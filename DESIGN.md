---
name: MCP Connector for Nextcloud
description: The connector's own OAuth and connection pages, deliberately visually distinct from Nextcloud, plus a signpost in Nextcloud's settings that Nextcloud renders itself.
colors:
  ink-navy: "#1F3A5F"
  page-mist: "#F5F6F7"
  card-white: "#FFFFFF"
  text-ink: "#1A1A1A"
  text-muted: "#5A6270"
  hairline: "#D5D8DD"
  error-red: "#B3261E"
  success-green: "#1E6B3A"
  warning-amber: "#8A5A00"
  warning-wash: "#FFF8E6"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.2
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, 'Cascadia Mono', Consolas, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  card: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
  page-wide: "64px"
  target: "44px"
  content-width: "560px"
components:
  button-primary:
    backgroundColor: "{colors.ink-navy}"
    textColor: "{colors.card-white}"
    rounded: "{rounded.card}"
    padding: "8px 24px"
    height: "{spacing.target}"
  button-secondary:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.ink-navy}"
    rounded: "{rounded.card}"
    padding: "8px 24px"
    height: "{spacing.target}"
  card:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.text-ink}"
    rounded: "{rounded.card}"
    padding: "24px"
  callout-warning:
    backgroundColor: "{colors.warning-wash}"
    textColor: "{colors.warning-amber}"
    rounded: "{rounded.card}"
    padding: "16px"
  callout-error:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.error-red}"
    rounded: "{rounded.card}"
    padding: "16px"
  callout-success:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.success-green}"
    rounded: "{rounded.card}"
    padding: "16px"
---

# Design System: MCP Connector for Nextcloud

## Overview

**Creative North Star: "The Sealed Envelope"** (proposal, to be confirmed by the owner)

The connector has two UI surfaces, and they follow opposite rules on purpose.

1. **Its own HTML pages** (`src/mcp_connector/exapp/ui/`): the OAuth sign-in handoff, waiting screen, consent screen, result and error pages, the token exchange pages and the per-user connections page. They are built by one function, `layout.page()`, with one inline stylesheet (`layout.STYLESHEET`) under a nonce CSP (`default-src 'none'`). Their palette is **deliberately not the Nextcloud palette** (threat T-03-23 in `layout.py`): a page that looks like Nextcloud would teach users that a Nextcloud-looking page can come from somewhere else. The password prompt is always Nextcloud's own page; the connector's pages must be visibly the connector's.
2. **The signpost in Nextcloud's admin settings** (`exapp/settings_form.py`): a Declarative Settings form with a title, a description and one link, rendered entirely by Nextcloud. It has no CSS of its own and automatically follows Nextcloud theming, dark mode and components.

This means the general Nextcloud-conformity rule (nextcloud-ui skill: Nc components, Nextcloud CSS variables, MDI icons) applies to surface 2 and to any future surface rendered inside Nextcloud, but **not** to surface 1. That exception is a security decision of the incumbent code; changing it is an owner decision, not a design refinement.

The pages themselves are a quiet single-column card: one navy accent, system font, generous spacing, 44 px targets, one primary action per page. They are written for a person making a security decision, so the tone is calm, explicit and unhurried.

**Key Characteristics:**
- One self-contained stylesheet, no external asset, no script, no web font, no icon package.
- A 560 px content column holding one white card on a pale grey page.
- One accent (ink navy) for the header rule, links, primary button and focus ring.
- Light only (`color-scheme: light`); no dark mode on the connector's own pages.
- Three inline stroke icons (warning, cross, check), 20 px, `currentColor`, always beside a word.
- English only in v1; all copy lives in `exapp/ui/strings.py`.

## Colors

A restrained cool-neutral palette with a single dark navy accent and three status inks.

### Primary
- **Ink Navy** (`ink-navy`): header underline, links, primary button fill, secondary button border and text, the 3 px focus ring. The only accent on any page.

### Neutral
- **Page Mist** (`page-mist`): page background behind the card.
- **Card White** (`card-white`): the card, secondary button fill, error and success callout fill.
- **Text Ink** (`text-ink`): all body text.
- **Text Muted** (`text-muted`): host name in the header, footer, muted lines and secondary row lines.
- **Hairline** (`hairline`): card border, row separators, default callout border.

### Status
- **Error Red** (`error-red`): error heading tone, error callout border and text.
- **Success Green** (`success-green`): success heading tone, success callout border and text.
- **Warning Amber** on **Warning Wash** (`warning-amber`, `warning-wash`): the warning callout (unverified client, anything that asks the user to slow down).

### Named Rules
**The Visibly-Ours Rule.** The connector's own pages never borrow Nextcloud's palette, logo or variables (T-03-23). A user must be able to tell the connector's page from Nextcloud's password prompt at a glance.

**The One Accent Rule.** Ink Navy is the only accent. Status colours appear only together with an icon and a word.

## Typography

**Body Font:** system-ui stack (no web font; the CSP forbids external fonts anyway).
**Mono Font:** ui-monospace stack, for client ids, redirect URIs and other literal values.

**Character:** Plain system type, two weights (400 and 600), four sizes.

### Hierarchy
- **Headline** (600, 28 px, 1.2): the one h1 of every page, optionally with a status icon and tone colour.
- **Title** (600, 20 px, 1.2): section headings (h2).
- **Body** (400, 16 px, 1.5): sentences, lists, buttons (buttons use 600).
- **Label** (600, 14 px): wordmark, definition terms, callout titles. The same size at 400 is the muted line.
- **Mono** (400, 14 px): literal values, wrapping anywhere so long URIs never overflow.

### Named Rules
**The Four Sizes Rule.** 28, 20, 16 and 14 px, nothing else. Rank beyond that is carried by weight 600.

## Layout

A single centred column, `max-width: 560px`, for header, main and footer. Page padding 24 px by 16 px on narrow screens and 64 px by 24 px from 600 px up (the only breakpoint). The card sits 48 px below the header and the footer 32 px below the card. Vertical rhythm is in multiples of four: 4, 8, 16, 24, 32, 48. Action rows wrap with a 16 px gap; row lists are flex rows that wrap on narrow screens.

## Elevation & Depth

Flat. There is no shadow anywhere. Depth is a single tonal step: white card with a hairline border on a pale grey page.

**The Flat Card Rule.** One card per page, bordered, never shadowed, never nested.

## Shapes

One radius, 8 px, for the card, callouts, buttons and the button-styled link. Borders are 1 px hairline, except the 2 px navy rule under the header and 1 px status borders on callouts.

## Components

### Buttons
- **Shape:** 8 px radius, at least 44 by 44 px, 8 px by 24 px padding, 16 px weight 600.
- **Primary:** Ink Navy fill, white text. One per page; on the consent page it is the grant.
- **Secondary:** white fill, Ink Navy border and text. On the consent page "Deny" comes before "Allow" in the tab order.
- **Button-styled link:** outbound sign-in and return links look like the primary button.
- **Focus:** 3 px Ink Navy outline, 2 px offset, on every focusable element; never removed.

### Callouts
- **Style:** icon plus title plus sentence, 16 px padding, 8 px radius, 32 px vertical margin.
- **Variants:** warning (amber on wash), error and success (status ink on white).

### Cards / Containers
- **Corner Style:** 8 px.
- **Background:** Card White on Page Mist.
- **Shadow Strategy:** none.
- **Border:** 1 px Hairline.
- **Internal Padding:** 24 px.

### Navigation
- **Header bar:** wordmark (14 px, 600) and the public host (14 px, muted, taken from configuration and never from the request), above a 2 px navy rule.
- **Row list (connections page):** title in 600, a muted line and a mono line, separated by hairlines.

### Consent screen (signature)
The only page with a granting button. The heading takes initial focus (`tabindex="-1"`), so a stray Enter cannot grant. Client names are attacker input: control characters stripped and cut at 80 characters before rendering.

## Do's and Don'ts

### Do:
- **Do** build every new page through `layout.page()` and its component functions, so the four security headers and the escaping always apply.
- **Do** keep all copy in `strings.py`: every error says what happened and what to do next, no error codes, no exclamation marks, no emoji, never "click here".
- **Do** keep 44 px targets, the 3 px focus ring and one primary action per page.
- **Do** follow the nextcloud-ui skill (Nextcloud components, CSS variables, MDI icons, theming) for anything rendered inside Nextcloud, such as the Declarative Settings form.

### Don't:
- **Don't** use Nextcloud colours, CSS variables, logos or fonts on the connector's own pages (T-03-23).
- **Don't** add external stylesheets, scripts, fonts or icon packages; the CSP is `default-src 'none'` with a style nonce only.
- **Don't** add shadows, gradients, a second accent or a nested card.
- **Don't** add a dark mode by inventing a second palette without an owner decision; the pages are light only today.
