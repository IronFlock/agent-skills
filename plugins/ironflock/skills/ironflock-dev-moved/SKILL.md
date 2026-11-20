---
name: ironflock-dev-moved
description: The skills to build IronFlock apps and widgets moved to the ironflock-dev plugin. Use this whenever the user builds, designs, refactors or changes an IronFlock app or its edge code, its .ironflock templates (board-template.yml, data-template.yml, env-template.yml, port-template.yml, ai-template.yml), a board, dashboard or widget, or an @ironflock/widget-* package, and the ironflock-templates and ironflock-widgets skills are not available.
metadata:
  mcp-tools: none
---

# The IronFlock build skills moved

Tell the user this, then help as well as you can without those skills: the
skills to build IronFlock apps, templates, boards and widgets moved from the
`ironflock` plugin to the `ironflock-dev` plugin, so they need to install it
once with `claude plugin install ironflock-dev@ironflock` (or add
`"ironflock-dev@ironflock": true` to `enabledPlugins` in their settings). After
that, run `/reload-plugins` or start a new session, and the skills
`ironflock-templates` and `ironflock-widgets` are back.
