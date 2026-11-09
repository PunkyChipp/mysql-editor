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

Published and verified on GitHub Pages at the repository's current custom-domain
path. The Actions workflow deploys the built interface, rather than the README.

Automatic boot handoff checks (`python3 tests/test_boot_browser.py -v`):

- Preparing and checking states stay on the progress screen.
- Readiness automatically replaces setup with the editor, without a button click.
- Setup errors stay visible and retry resumes the automatic handoff.
- Readiness navigation also works inside an embedded preview frame.
- The optional `?stay=1` diagnostic view remains open after readiness.
- Blocked local/session storage receives an in-memory preference store; available
  browser storage and its saved preferences are left intact.

The devcontainer now starts the launcher in the foreground after browser attach,
prints a localhost URL for port detection, and uses the documented `openPreview`
port action rather than opening a new tab before the client connects.

The actual code-server handoff was also checked at desktop size and inside a
cross-site tablet preview with third-party storage blocked. Its own CSP nonce
allows the small storage fallback without relaxing the editor's CSP.
The fresh full-stack trial on this executor ran out of local disk while MySQL
initialized; the test containers/volumes were removed. MySQL integration remains
covered by the earlier runtime checks, not by a fresh end-to-end Codespaces run.

Actual first-time Codespaces provisioning, iPad Safari, and the school network
still require a pilot. Existing Codespaces retain their old checkout and
container configuration; use a fresh Codespace to test this revised boot flow.
