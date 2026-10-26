# @ironflock/widget-starter

TODO: one paragraph for people: what this widget shows on an IronFlock board, and
what its configuration lets them change.

A [Lit](https://lit.dev) web component for [IronFlock](https://ironflock.com) boards.

## Installation

```bash
npm i @ironflock/widget-starter
```

`lit` is imported from the page: IronFlock Studio provides it through its import map.

## Usage

The package version is part of the tag name (`widget-starter-<version>`), so several
versions can be registered on one page. Build the tag from the version of the package
you installed, as `demo/index.html` does from `package.json`, and set the data and the
theme as properties:

```js
import '@ironflock/widget-starter'
import pkg from '@ironflock/widget-starter/package.json' with { type: 'json' }

const widget = document.createElement(`widget-starter-${pkg.version}`)
widget.inputData = { title: 'Metrics', dataseries: [ ... ] }
widget.theme = { theme_name: 'light', theme_object: lightTheme }
document.body.append(widget)
```

## inputData

`src/definition-schema.json` describes every field. The `StarterConfiguration` type in
`src/definition-schema.d.ts` is generated from it with `npm run types`.
`src/default-data.json` is a working example, and it is also the config a new board
tile starts with.

## Theming

- `theme`: `{ theme_name, theme_object }`, an ECharts theme. `theme_object` can be
  missing.
- `--re-text-color`: when this CSS custom property is set on the widget or an
  ancestor, it colours the text instead of the theme's title colour.

The widget paints no background of its own, so the board's tile shows through.

## Development

| Command | What it does |
| --- | --- |
| `npm start` | Dev server on port 8000 with the demo in `demo/index.html`, plus a watch build |
| `npm run build` | Type check, then the library build to `dist/widget-starter.js` |
| `npm run types` | Regenerate `src/definition-schema.d.ts` after editing `src/definition-schema.json` |
| `just release-patch` | A release pull request; its merge publishes to npm in CI and tags the version (`just merge`: a pull request that releases nothing) |
