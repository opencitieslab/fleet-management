# Theming to Open Cities Lab

The whole branding surface in this repo is one 13-line JSON file, three template images, and an empty Keycloak themes folder.

## Current state

`deployment/manager/app/manager_config.json`:

```json
{
  "loadLocales": true,
  "realms": {
    "default": {
      "appTitle": "Custom Project",
      "styles": ":host > * {--or-app-color2: #F9F9F9; --or-app-color3: #22211f; --or-app-color4: #0c4da2; --or-app-color5: #CCCCCC;}",
      "logo": "/images/logo.png",
      "logoMobile": "/images/logo-mobile.png",
      "favicon": "/images/favicon.ico",
      "language": "en"
    }
  }
}
```

- `logo.png`, `logo-mobile.png` and `favicon.ico` under `deployment/manager/app/images/` are the unmodified OpenRemote template assets.
- `deployment/keycloak/themes/` holds only a README. Login pages are stock OpenRemote.
- `ui/app/custom/src/index.ts` declares a second, conflicting palette (accent `#e3000a`). It is not deployed, but delete or align it so nobody ships it by accident.
- `deployment/map/mapsettings.json` centres on Brussels at zoom 7.

## The colour variables

Defaults from `ui/component/core/src/defaults.ts` upstream. The Appearance UI exposes 1 to 6 and 8.

| Variable | Default | Role |
|---|---|---|
| `--or-app-color1` | `#FFFFFF` | Surface: dialogs, panels, headers |
| `--or-app-color2` | `#F9F9F9` | Background behind panels |
| `--or-app-color3` | `#4c4c4c` | Text, titles, icon fill |
| `--or-app-color4` | `#4d9d2a` | **Primary**: buttons, actions, list headers. Mapped to `--or-color-primary` and consumed by every `or-*` component including rules, insights and map controls |
| `--or-app-color5` | `#CCCCCC` | Borders and dividers |
| `--or-app-color6` | `#be0000` | Error state |
| `--or-app-color7` | `#FFFFFF` | Secondary (not exposed in the UI) |
| `--or-app-color8` | `#FFFFFF` | Text on primary |

## Open Cities Lab palette

opencitieslab.org runs WordPress with Elementor (Hello theme). The global palette is in the kit CSS at `/wp-content/uploads/elementor/css/post-6.css`, so these are the brand's own tokens.

| Elementor token | Hex | Use on the site |
|---|---|---|
| primary | `#FAAD00` amber | Declared primary; weak contrast under white text |
| secondary / text | `#2F3542` slate | Body text and headings |
| accent | `#D66139` terracotta | Links, icons, borders, buttons. Most-used accent on the homepage |
| custom | `#6EDABB` mint, `#0984E3` blue, `#4D9E4D` green, `#837DD1` lavender | Category accents on cards |
| custom | `#F8F8F8` | Light background |

Fonts are Montserrat (headings) and Poppins. The Manager UI does not expose a font setting without a custom app build, so leave type alone.

Logos: `https://www.opencitieslab.org/wp-content/uploads/OCLLogomark-Color.png` and `OCLLogomark-White.png`, about 3:1, which suits the header slot.

## Proposed `manager_config.json`

```json
{
  "loadLocales": true,
  "manager": { "applyConfigToAdmin": true },
  "realms": {
    "default": {
      "appTitle": "Open Cities Lab Fleet",
      "language": "en",
      "logo": "/images/logo.png",
      "logoMobile": "/images/logo-mobile.png",
      "favicon": "/images/favicon.ico",
      "styles": ":host > * {--or-app-color1:#FFFFFF; --or-app-color2:#F8F8F8; --or-app-color3:#2F3542; --or-app-color4:#D66139; --or-app-color5:#CCCCCC; --or-app-color8:#FFFFFF;}"
    }
  }
}
```

Terracotta `#D66139` as primary rather than amber: it is what the site actually uses for actions, and white text on it passes contrast. Use amber as a highlight in map markers or dashboards if wanted. `applyConfigToAdmin: true` so superusers see the branding too; with it false, styling is hidden for the admin account and the theme appears broken when you test as `admin`.

Per-realm overrides go under `realms.<name>` and are merged over `default`, so a client realm can carry its own logo and title later. A `pages` key exists for map markers, rules and insights config; an invalid `pages` array breaks saving from the UI, so validate any hand-written one.

## Steps

1. Replace the three images. Export the colour logomark as `logo.png` (roughly 3:1), a square mark as `logo-mobile.png`, and a 32 px favicon.
2. Replace `manager_config.json` with the block above.
3. Set the map centre in `deployment/map/mapsettings.json` to `[31.0218, -29.8587]` at zoom 11, and colour markers by fleet group under `pages.map.markers` using the four category colours.
4. Keycloak login theme: copy the upstream `openremote` theme (from the `openremote/keycloak` repo, `theme/src/main/resources/theme/openremote`) into `deployment/keycloak/themes/opencitieslab/`, recolour the login and email templates, and set it as the realm default. The 1.30.0 release notes flag that custom themes need updates for Keycloak 26, so budget time for template drift. For live editing use `profile/dev-testing.yml`, which disables theme caching.
5. Remove or align the palette in `ui/app/custom/src/index.ts`.
6. Rebuild the deployment image (`./gradlew clean installDist`, then the buildx step in `build_and_publish_to_docker.sh`) and redeploy; the `deployment-data` volume must be recreated for the new config to land.

## Or iterate in the UI first

Settings, then Appearance (superuser) has colour pickers, logo upload, a header picker and a JSON editor per realm. It writes to `/storage/manager/manager_config.json` and `/storage/manager/.../images`, which survive restarts on a persistent volume and take precedence over the docroot copy. Iterate there, then copy the resulting JSON back into `deployment/manager/app/manager_config.json` so a clean install reproduces it. The same page accepts an `.mbtiles` upload for map tiles.
