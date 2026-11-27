# IronFlock Appliance

Connect Claude Code directly to an IronFlock appliance, alongside the IronFlock cloud connection. The computer running Claude Code needs to reach the appliance and trust its HTTPS certificate.

1. Add the IronFlock marketplace with `/plugin marketplace add IronFlock/ai-plugins`.
2. Install `/plugin install ironflock-appliance@ironflock`. The plugin also installs the IronFlock skills.
3. Enter the **Appliance MCP address**, including `/mcp`, for example `https://api.plant.example/mcp`. To change it later, use `/plugin configure ironflock-appliance@ironflock`.
4. Reload the plugins or restart Claude Code. In `/mcp`, select the appliance connection, authenticate in the browser and review the permissions on the appliance. Ask Claude which projects are on that appliance.

The appliance issues its own sign-in and handles requests for its local account. Claude receives the tool results you request. End the grant in that appliance’s Studio under **Account Settings → Developer → App sign-ins**.

In Claude chat or Cowork, add a custom connector with the appliance’s full MCP address if Anthropic’s connector service can reach it. The optional address setting above is for Claude Code.

[Privacy](https://ironflock.com/en/company-legal/terms-privacy/): IronFlock's terms and privacy notice.
