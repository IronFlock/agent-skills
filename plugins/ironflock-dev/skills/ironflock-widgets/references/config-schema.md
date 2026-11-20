# The config schema and the default config

`src/definition-schema.json` defines what a widget's config (`inputData`) may
contain. It looks like JSON Schema, but its readers are not a JSON Schema
validator, and each of them reads only part of it. This file says what each
keyword does, as the platform implements it.

## Contents

1. [Who reads the schema](#who-reads-the-schema)
2. [The root](#the-root)
3. [Properties](#properties)
4. [Types](#types)
5. [Binding data: arrays and scalars](#binding-data-arrays-and-scalars)
6. [Conditions](#conditions)
7. [Other keywords, and dead ones](#other-keywords-and-dead-ones)
8. [Changing a schema without breaking boards](#changing-a-schema-without-breaking-boards)
9. [default-data.json](#default-datajson)
10. [aiSelection](#aiselection)
11. [layout](#layout)
12. [Generated types](#generated-types)
13. [Size limits](#size-limits)

## Who reads the schema

| Reader | What it uses |
|---|---|
| Studio's config editor | Builds the settings form: labels from `title`, help tips from `description`, order from `order`, the input from `type`, the data-binding switch from `dataDrivenDisabled`, visibility from `condition`, a text dialog's highlighting from `contentMediaType`. |
| Studio's board editor | Gives a dropped widget the fixed height or width of the root `layout`. |
| Studio's renderer | Removes undeclared keys and `null` values inside declared object settings (by the board's pinned version) before the widget gets them. Top-level keys and keys directly in list items pass through. |
| The IronFlock AI | Picks widgets by the root `description` and `aiSelection`, configures them from the property descriptions, validates its configs against the schema, and gives a placed widget the fixed size of `layout`. |
| json2ts (`npm run types`) | Generates `src/definition-schema.d.ts`; every `title` becomes a type name. |
| The ironflock-templates skill | `widget.py` prints the schema for agents writing board templates; the validator checks board configs and positions against it; the widget catalog is built from `description`, `aiSelection` and `layout`. |

Descriptions are therefore user and AI documentation at the same time. They are
the only documentation of a setting most people and agents will ever read.

## The root

```json
{
    "title": "Gauge Chart Configuration",
    "description": "…",
    "aiSelection": { "dataShape": "…", "useWhen": ["…"], "notFor": ["…"] },
    "layout": { "fixedHeight": true, "height": 48 },
    "type": "object",
    "properties": { … }
}
```

Exactly these keys; `layout` only when the widget has a fixed size.

- **`title`** names the root interface json2ts generates
  (`GaugeChartConfiguration`), which the component imports. Renaming it renames
  the type.
- **`description`** is the widget's entry in the AI's list of widgets, and its
  first two sentences are the widget's summary in the ironflock-templates catalog.
  Say what the widget shows and what it is for, in two or three sentences. Write
  "such as" rather than "e.g. ": the catalog cuts sentences at ". ". State what the
  widget does **not** do when people would expect it (widget-value: "performs NO
  aggregation").
- **`aiSelection`**: see [below](#aiselection).
- **`layout`**: see [below](#layout).

## Properties

Every property node has `title`, `description`, `type` and `order`:

```json
"precision": {
    "title": "Decimals",
    "description": "Number of decimal places shown. Leave it empty for whole numbers.",
    "type": "number",
    "minimum": 0,
    "maximum": 6,
    "dataDrivenDisabled": true,
    "order": 3
}
```

- **`title`**: the label in the editor. Arrays and checkboxes have no fallback
  label, so a missing title shows nothing. It also names the generated type
  (`Decimals`); titles that repeat get numbered (`Value1`).
- **`description`**: the help tip in the editor, and what the AI and agents read.
  Put the point in the first sentence (tools excerpt it). Say what the setting
  does, its unit, its range, its default when unset, and how it interacts with
  other settings.
- **`order`**: the position among siblings. Give every property one, unique among
  its siblings, except siblings that a condition makes mutually exclusive. Studio
  puts properties without an order first and keeps ties in file order, while
  `widget.py` puts them last and sorts ties alphabetically, so a missing or
  duplicate order shows differently in each.
- Avoid property names that shadow schema keywords (`type`, `title`, `condition`,
  `required`) when you can. They are legal, but trip up naive schema walkers.

## Types

Use one string, from this list:

| `type` | Editor input | Value the widget gets |
|---|---|---|
| `string` | text input; a select if it has an `enum` | string |
| `number` | number input with `step` 0.0001 (more decimals are silently dropped) | number |
| `boolean` | checkbox | boolean |
| `object` | a collapsible group | object |
| `array` | a list of tabs, one per item; or a table binding | array |
| `color` | colour picker | CSS colour string; `''` when unset |
| `textarea` | a button opening a 24-line text dialog; a Markdown editor with `contentMediaType` (below) | string |
| `image` | an upload field | the upload's URL |
| `targetColumn` | the picker of a table column to write to (widget-form) | `{ swarm_app_databackend_key, tablename, column, … }` |
| `actionApp` / `actionDevice` | app and device selects for device actions | numeric keys |

Don't use:

- **`integer`**: the editor cannot store it. Use `number` and round in code.
- **type arrays** (`["string", "number"]`): Studio compares `type` with `===`.
- **`font`**: the editor cannot edit it and the AI rejects its object shape
  (widget-scada only, generated).
- **`targetTable`**: the editor supports it, but it crashes the AI's validator.
- `$ref`, `allOf`/`anyOf`/`oneOf`/`not`/`if`: the editor cannot render them.

## Binding data: arrays and scalars

A board can bind a setting to data instead of a constant, and Studio replaces the
binding with data before the widget sees it:

- **An `array` property can be bound to a table** (`tableRef`). Each row of the
  table becomes one item, shaped like the array's `items`, oldest row first. So
  `items` is the shape of one row as the widget wants it: an object whose leaves
  are the values the user maps columns to (`x`, `y`, `value`, `pivot`, `tsp`).
  Keep row items flat, with scalar leaves; nested arrays inside items work
  (widget-doughnut's `sections` is a list of lists) but are hard to configure.
- **A scalar** (string, number, boolean, color, textarea) **can be bound to a
  single value** (`valueRef`): the newest value of one column.
- **An `object` cannot be bound**; its fields can.
- **`dataDrivenDisabled: true`** turns binding off: the editor shows only the
  literal input, and the AI and the board validator reject a binding there. Set it
  on everything that is configuration rather than data:
  - structural lists, such as a `dataseries` list whose items each have a
    bindable `data` array (the pattern of value, gauge and linechart);
  - modes, enums and booleans that change what is drawn;
  - most colours, sizes and layout settings;
  - every property that a `condition` points at (see below);
  - `actionApp` and `targetColumn`, which otherwise open the binding picker
    instead of their own.
- Leave it off on values that come from data: the numbers, labels, units and
  timestamps a widget displays.
- `dataDrivenDisabled: false` is the same as leaving the key out. Leave it out.
- Inside a bound array's row format, a property with `dataDrivenDisabled: true`
  is a constant that applies to every row (an icon name for every menu item).

## Conditions

A condition shows a property only while another property has one of the listed
values:

```json
"value": {
    "title": "Value",
    "type": "number",
    "condition": { "relativePath": "../multiChart", "showIfValueIn": [false] },
    "order": 5
}
```

- **`relativePath` starts at the property itself**: each `..` steps up one level.
  `../multiChart` is the sibling `multiChart`. An array item counts as a level, so
  from `dataseries[].data[].r`, `../../../type` is `dataseries[].type`. Paths are
  always relative; a leading `/` is ignored.
- **The target must be literal-only** (`dataDrivenDisabled: true`) and a
  `boolean` or a string with an `enum`. A bound target holds an object, and the
  editor fails on it.
- **`showIfValueIn` is compared with `===`** after the editor decodes the stored
  value: `[false]` matches `false` and unset (unset reads as `false`), `"true"`
  never matches `true`. Values must not contain `:`, which the editor's decoding
  cuts off.
- **`false` in the list of an enum target matches a target left unset.** List it
  to keep a property visible before anything is chosen: widget-form shows Target
  Column for every input type plus `false`, so a new field tab has it before a
  type is picked, and only a `section` hides it. The editor, the AI's validator,
  the board validator and `check_widget.py` all read it that way.
- **Never point at a sibling inside a bindable array**: once the array is bound,
  the sibling reads as unset and the field is always hidden.
- The editor hides the field and deletes its value when the condition is not met.
  **The renderer does not evaluate conditions**, so the widget can still receive a
  stale value for a hidden field. Check the condition in code.

## Other keywords, and dead ones

| Keyword | What it does |
|---|---|
| `enum` | On `type: "string"` only: the editor shows a select, the AI validates. Never remove a value from it. |
| `enumLabels` | Display names for the `enum` values: an **array in the same order** as `enum`. The editor looks labels up by position. |
| `default` | Only a hint for the editor form: it fills an unset field when the editor opens (not for colours). The widget never receives it, so apply the same default in code. `default-data.json` wins over it in the editor. |
| `minimum` / `maximum` | The editor's number input enforces them (an out-of-range value is not saved), the AI validates. |
| `pattern` | Only the AI's validator checks it. |
| `contentMediaType` | On `textarea` only: what the text is written in. `"text/markdown"` turns the text dialog into a Markdown editor with syntax highlighting. Leave it out where the widget shows the text as it is (widget-label): the dialog is then a plain text field, and so it is for any other value. Validators ignore it, and the widget gets the same string either way. |

These appear in some schemas but nothing reads them. Don't add them, and drop them
when you touch the property:

- `color: true` next to `type: "color"`;
- `min` / `max` (use `minimum` / `maximum`);
- `required: true` on a property: the editor, the AI and json2ts ignore it, and it
  crashed `widget.py` on an object node. Say "required" in the description and
  handle the missing value in code;
- `enumLabels` as an object map;
- `dataDrivenDisabled: false`.

## Changing a schema without breaking boards

Boards keep their configs and their pinned versions for years, and the Widget
Editor lets users move a tile to a new version with its old config. A new version
must accept every config an older version accepted.

- **Adding a property** is safe. Its default (in code) must keep the old look, so
  existing tiles don't change when they move to the new version.
- **Never rename a property.** Boards keep the old key. The editor no longer shows
  it, the AI rejects it, and inside a settings object Studio strips it before the
  widget sees it, so the old values vanish. If a name must change, add the new key
  and keep declaring and reading the old one.
- **Never change a property's type or meaning.** Add a new property instead.
- **Never remove an `enum` value** or a property; mark it as deprecated in its
  description, keep it working, and drop it from `default-data.json`.
- Changing `title`, `description` or `order` is safe for boards (they only affect
  labels and generated type names).
- After any schema edit: `npm run types`, update the code, `default-data.json`,
  the README, and `aiSelection` if the widget can now do something new.

## default-data.json

`src/default-data.json` is the config a new tile starts with: Studio copies it
into the board when someone drops the widget (adding the `$str:`/`$num:`/`$bool:`
prefixes itself), fills unset fields from it when the editor opens, and renders it
as-is in the style dialog's demo tiles and in the widget's own demo. The AI sees
it as the widget's example, and `widget.py --example` prints it.

- **Valid against the schema**: only declared keys, the right types, allowed
  `enum` values, within `minimum`/`maximum`.
- **Plain values only**: no `$str:`/`$num:`/`$bool:` prefixes, no `tableRef` or
  `valueRef`.
- **No values for fields whose condition is not met.**
- **Neutral**: generic labels ("Metric A"), no units, brands, or machine names.
  Whatever is here ends up on every new tile and in AI-built configs (`°C` once
  spread from a demo file into unrelated boards).
- **Leave out what only a running project knows**: `actionApp`, `actionDevice`,
  `targetColumn`.
- **Small, and showing the main feature**: one or two series with a few rows is
  enough. It counts against the AI's size budget too.

## aiSelection

The AI's widget builder reads the root `description` plus this block to choose a
widget for a request. It is not JSON Schema; every other reader ignores it.

```json
"aiSelection": {
    "dataShape": "…what columns this widget consumes and what each one means…",
    "useWhen": ["…a situation, naming the properties that express it…"],
    "notFor": ["…a situation this widget is wrong for, naming the widget to use instead…"]
}
```

- `dataShape` is a string; `useWhen` and `notFor` are lists of strings (the
  catalog generator depends on these types).
- `notFor` is the most valuable part. Every entry names the widget that should be
  used instead ("… — use widget-linechart").
- Write for a model with no other documentation: describe the visible result and
  the user's intent, not the implementation.
- Prefer entries that tell the widget apart from its neighbours. The `notFor` lists
  of all widgets form one routing table and should be reciprocal: when this widget
  routes a case to another, check that the other routes the converse back.
- Update it whenever a change alters what the widget can do, not only how it
  looks.
- **Keep it short.** The descriptions and `aiSelection` blocks of all widgets go
  into the AI's prompt together, and they already use about 44,000 of the 50,000
  characters available for them. Aim for under 2,000 characters for `description`
  and `aiSelection` combined.

## layout

Most widgets fill whatever tile they get. A widget whose content has a natural
size along one axis declares it here, and the platform keeps that axis fixed:

```json
"layout": { "fixedHeight": true, "height": 48 }
"layout": { "fixedWidth": true, "width": 184 }
```

- `fixedHeight` / `fixedWidth` are the flags a board position carries; `height` /
  `width` are the tile's natural size in pixels. Each flag needs its size, and a
  size its flag.
- Studio sets the flag and the matching number of grid cells when the widget is
  dropped onto a board, the IronFlock AI does the same when it places the widget,
  the widget catalog and `widget.py` show it, and the ironflock-templates
  validator warns about a position without it. Nothing else has to list which
  widget wants which size.
- Declare it only for content that does not scale: a form field, a button, a menu
  bar, a sidebar of labels (widget-filter-dropdown, widget-sidenav). A chart, a
  gauge or a value scales with its tile and has none.
- A size that depends on the config, such as widget-scada's symbol shape, cannot be
  declared here; the platform handles that one separately.
- Like `aiSelection` it is not JSON Schema: json2ts and the config editor ignore it.

## Generated types

`npm run types` pipes the schema through json2ts into `src/definition-schema.d.ts`.
Never edit that file; the CI gate (`just lint`) regenerates it and fails when it
differs.

- Every field is optional (`?:`), and every object allows extra keys
  (`[k: string]: unknown`). The types describe what may arrive, not what will.
- Custom types (`color`, `textarea`, `image`, …) become empty interfaces, unless the
  property has a string `default`. Check with `typeof value === 'string'` before
  using such a value as a string.
- Type names come from titles, so renaming a title can rename a type the code
  imports. The build's type check catches that.

## Size limits

- The AI loads a widget's schema and default config together; when the JSON is
  longer than 50,000 characters (non-ASCII characters count six), it gets only an
  overview of the top-level properties. Today only widget-scada is over the limit,
  with a generated schema of 230 KB; widget-form, the largest of the others, is
  about 40,000. The JSON is indented, so depth costs: a `condition` listing ten
  values inside a list item takes about 430 characters there.
- 50,000 is also the most any AI tool result can hold. When the AI fetches several
  widgets' schemas in one call, a schema that would push the result past it is
  left out with a note to fetch it alone.
- Keep descriptions informative but not repetitive. Don't paste the same paragraph
  into every item of a list.
