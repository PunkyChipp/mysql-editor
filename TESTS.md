# GitHub Pages migration checks

Passed locally:

- Static build uses the supplied OWNER/REPOSITORY identity and rejects malformed values.
- Only index.html and .nojekyll are emitted into the Pages artifact.
- Desktop and tablet Chromium layouts render without horizontal page overflow.
- Create my workspace points to codespaces.new for the actual build identity.
- No ChatGPT-hosted URLs or local-download links are present on the public front page.
- Private workspace addresses save, survive reload, and can be forgotten.
- Invalid/non-HTTPS addresses are rejected.
- Python/JSON sources, inline JavaScript, and workflow syntax validate.
- The workflow grants the Pages/OIDC permissions and uploads dist/ only.

The browser editor/runtime is carried over from the tested Study Desk launcher:
SQL/MySQL integration, Python debugging, save/reload, automatic editor sign-in,
and extension/network restrictions were validated in the previous runtime tests.

Not yet verified: publication to an actual GitHub account, the Actions deployment,
and first-time Codespaces provisioning. Account authentication is required to
complete those. Initial Pages enablement needs repository administration access.
A real iPad and the school network also require a pilot.
