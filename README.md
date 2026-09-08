# Portfolio_param

A personal portfolio website for showcasing a professional resume, skills, projects, and contact information.

## Files

- `index.html` — Homepage with a brief introduction and navigation.
- `about.html` — About section with personal background.
- `projects.html` — Portfolio of completed projects.
- `hobbies.html` — Personal interests and hobbies.
- `style.css` — Site styling and layout rules.
- `theme.js` — Dark/light theme toggle behavior.

## Usage

1. Open `index.html` in a web browser.
2. Navigate between pages using the site menu.
3. Use the theme switcher to toggle light and dark modes.

## Notes

- This is a static website built with HTML, CSS, and JavaScript.
- Customize the content and styling to match your personal branding.

## Automatic GitHub project cards

`.github/workflows/sync-projects.yml` checks this account's public repositories
every third calendar day. Eligible repositories created after `activation_cutoff` are
added to the Projects page newest-first. Forks, archived/private repositories,
and repositories carrying the `portfolio-hidden` topic are excluded.

Copilot only produces small, validated metadata from a README; Python renders
the HTML, so the model cannot alter the site's layout. If Copilot is unavailable
or returns invalid JSON, the workflow produces a metadata-only fallback card.

### One-time setup

Create a fine-grained token owned by `routparam12` with **Account → Copilot
Requests** permission and public-repository access. Store it as the Actions
secret `COPILOT_GITHUB_TOKEN`, then manually run **Sync portfolio projects**.

### API-key provider later

Set `summary_provider` to `api` in `data/portfolio-sync.json`, add an Actions
secret named `PORTFOLIO_AI_API_KEY`. The existing `api_provider` block accepts
an OpenAI-compatible endpoint/model, so discovery, validation, caching, and
HTML rendering need no changes.

