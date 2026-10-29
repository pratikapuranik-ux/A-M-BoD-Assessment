# Sharing the prototype

The prototype is static (HTML, CSS, JavaScript). Nothing runs on a server and nothing leaves the viewer's browser.
It contains an A&M draft report on a listed company and simulated board material, so share it **inside A&M** and keep the
DRAFT notice and run-mode labelling intact.

| Option | Best for | How |
|---|---|---|
| **Zip** | Colleagues | Send `AM_Board_Assessment_Prototype.zip` (email, Teams, SharePoint library). They unzip and double-click `index.html`. Works offline in Chrome, Edge or Safari. |
| **Single file** | Quick circulation | Run `npm run build:single`, then send `dist/AM_Board_Assessment_Prototype.html` (about 3 MB, everything inlined). Download it first: SharePoint or OneDrive previews do not run scripts. |
| **Internal hosting** | A live link for a wider group | Upload the folder to any internal static host: Azure Static Web Apps or Azure Storage static website behind firewall / SSO, or an internal web server. In VS Code use the "Azure Static Web Apps" extension: sign in, "Create Static Web App", app location `/`, no build. |
| **Private repository** | Developers | Put the folder in an internal Git repository (Azure DevOps or internal GitHub). `.gitignore` is set. |

Avoid public hosting (public GitHub Pages, public Netlify or similar): the content is proprietary draft material.

Before sharing outside the core team: replace the logo with the approved master artwork, confirm the run-mode label and
circulation line, and have a qualified A&M professional review the content.
