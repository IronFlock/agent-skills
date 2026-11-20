# Changelog

What changed for the people who use the plugins. Write each change under
`## Unreleased` as you make it; the release turns that heading into the
version and its date. Versions follow semantic versioning: a major version
when people have to change their setup, a minor one for new skills or
abilities, a patch for fixes.

## Unreleased

- The `ironflock` plugin connects Claude Code to IronFlock: it declares
  IronFlock's MCP server and asks, when you install it, for the API address
  (`https://api.ironflock.com` by default, `https://api.<domain>` for an
  appliance) and your API key, which Claude Code keeps in the system's secure
  credential store. Change them with `/plugin configure ironflock@ironflock`.
- New skill `ironflock-connect`: how to connect Claude to IronFlock in Claude
  Code, in the Claude app (chat on the web, on the desktop and on a phone) and
  in Cowork, where you add IronFlock as a custom connector with your key as a
  request header; how to create the key in Studio, check the connection, and
  what to do when it fails; and what a key lets Claude do.
- The README has a section "Connect to IronFlock" with the same steps in
  short.

## 1.0.0 - 2026-11-20

- Two plugins in the `ironflock` marketplace instead of one. `ironflock` is
  for operating IronFlock. For now it holds only `ironflock-dev-moved`, a
  short skill that tells people who build apps to install `ironflock-dev`;
  the release that brings the connection and the first operator skills
  replaces it. `ironflock-dev` holds the
  skills `ironflock-templates` and `ironflock-widgets`, unchanged, and needs
  `ironflock`, which Claude Code installs with it.
- If you had `ironflock@ironflock` enabled, install `ironflock-dev@ironflock`
  to keep the two skills. They are now invoked as
  `/ironflock-dev:ironflock-templates` and `/ironflock-dev:ironflock-widgets`.
- The plugins have versions now. An installed plugin updates when a new
  version is released. A new install gets the content of the main branch,
  which may hold changes that are not released yet.
