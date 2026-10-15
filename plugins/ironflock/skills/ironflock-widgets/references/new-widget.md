# Creating a new widget

A new widget is a new npm package, a new repository and a new entry in several
places of the platform. Most of it happens outside the widget's own repo, so plan
it with the user before writing code.

## Contents

1. [First, check that it needs to be a new widget](#first-check-that-it-needs-to-be-a-new-widget)
2. [Name it](#name-it)
3. [Scaffold it](#scaffold-it)
4. [Make it yours](#make-it-yours)
5. [Publish the first version](#publish-the-first-version)
6. [Register it on the platform](#register-it-on-the-platform)

## First, check that it needs to be a new widget

Every widget adds to what users scan in the palette and to the AI's prompt, whose
widget list is close to its size limit
([config-schema.md](config-schema.md#aiselection)). Prefer a new setting on an
existing widget when the new behaviour is a variant of what one already shows: a
horizontal bar is `widget-linechart` with a setting, not a bar-chart widget.
Read [widget-index.md](widget-index.md) and the existing widgets' `notFor` lists
before deciding, and ask the user if it is not clear.

## Name it

`widget-<name>`, with `<name>` a short lower-case noun in kebab case
(`widget-progress`, `widget-state-timeline`). The same string is the repo name
(`IronFlock/widget-<name>`), the npm package (`@ironflock/widget-<name>`), the local
folder, Studio's `package_name`, and the custom element prefix. It can never be
changed once boards use it. Studio's palette shows it capitalized without the
`widget-` prefix, so the name is also the label users see.

## Scaffold it

```bash
python3 <skill>/scripts/new_widget.py <name> --dest <ironflock-widgets>/widget-<name>
```

This copies the starter template (`assets/widget-template/`) and renames
everything: the package, the files, the element tag, the class, the schema title
and the generated root type. `--title "Progress Bar"` sets the display name used
in the schema title (the default is derived from the name). It refuses to write
into a folder that is not empty.

Then, in the new folder:

```bash
git init -b main
npm install
npm run build
npm start          # the demo, on http://localhost:8000/demo/
```

The starter shows the latest value of each data series. It is there to be
replaced, but it already follows every rule in this skill; change it rather than
starting from an empty file, and keep its infrastructure files (`scripts/`,
`.github/`, `.npmrc`, configs) as they are.

## Make it yours

1. **Schema** (`src/definition-schema.json`): the settings, following
   [config-schema.md](config-schema.md). Rewrite the root `title` and
   `description`, then `npm run types`.
2. **Component** (`src/widget-<name>.ts`), following [component.md](component.md).
   [widget-index.md](widget-index.md) lists which existing widget solves which
   sub-problem; read its code before writing your own.
3. **`src/default-data.json`**: a small, neutral, valid example of the new config.
4. **`aiSelection`**: where the AI should use the widget and where a neighbour fits
   better. Then add the converse to those neighbours' `notFor` lists (in their
   repos, in later releases).
5. **README.md and CLAUDE.md**: replace every `TODO:` and describe the widget's own
   data flow and decisions.
6. **Thumbnails** (`thumbnail.png`, `thumbnail.webp`), see
   [repo-and-release.md](repo-and-release.md#documentation-and-thumbnails).
7. **Check**: `npm run build`, then `check_widget.py` until it reports no errors.
   It reports leftover `TODO:` text and missing thumbnails as errors.

## Publish the first version

The user does this; it needs their GitHub and npm accounts. They create the GitHub
repository `IronFlock/widget-<name>` and push `main`. npm only lets CI publish
(trusted publishing) to a package that already exists, so an owner of the
`@ironflock` npm scope publishes the very first version once by hand; every later
version goes through `npm run release`. Keep exactly one workflow file in
`.github/workflows/`: the trusted publisher is bound to its file name.

## Register it on the platform

A published package is not yet a widget anyone can use. Studio, the IronFlock AI
and the platform database each have to learn the new package, in a fixed order and
only once its first version is on npm; the board-template schema and this plugin's
widget catalog come last, so no agent writes boards the platform cannot install
yet. These changes are in IronFlock's internal repositories, and the platform team
deploys them.

IronFlock developers find the steps, with every file, in the internal runbook
`docs/INTERNAL-widget-platform.md` of the deployments repository (checked out next
to `ironflock-widgets/`, as `REDeployments/` or `deployments/`). Prepare those
changes only when the user asks, and never deploy. Without access to the runbook,
tell the user that the widget still needs to be registered on the platform by
IronFlock.
