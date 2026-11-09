# Study Desk — GitHub Pages + a private browser workspace

The public start page lives on GitHub Pages. Create my workspace opens this
repository in the student's own Codespace. The devcontainer installs the host
prerequisites, starts the guided launcher, and opens private port 8787. Students
use a normal browser; no local installs, uploads, or setup commands are needed.

The editor, real MySQL server, and Python run in that GitHub-hosted computer.
Pages serves the front page. No ChatGPT-hosted website is needed.

## Publication

Enable repository Pages with Source: GitHub Actions. The included workflow builds
the page using the actual repository name and publishes only dist/. Runtime
source, credentials, and coursework are not published as Pages assets. Every push
to main updates the front page. Initial Pages enablement needs repository admin
access; the workflow does not ask for a personal access token.

## Student flow

1. Open the Pages URL, choose Create my workspace, sign into GitHub, and approve creation.
2. Wait for the private Study Desk tab. If needed: Ports > 8787 > Open in Browser.
3. Keep that port PRIVATE. Choose Start coding when setup finishes.
4. Bookmark the workspace or save its address on the start page.
5. Resume existing workspaces in GitHub. Stop them when finished to conserve allowance.

First launch takes several minutes. GitHub account, compute, storage, and usage
restrictions apply. Creating another Codespace creates another environment.

## Persistence and isolation

Saved files and MySQL data use Docker volumes. Export backups outside Codespaces
before deleting it or rebuilding its host container. Source commits do not
include inner coursework/database contents automatically. Each student has a
separate environment; this is not a shared multi-user server.

The coding runtime has no external network and a read-only extension installation.
No AI extensions are installed. Ordinary completion, diagnostics, debugging,
SQLTools, and Python's MySQL connector are included. The outer Codespace remains
the owner's administration interface.

The launcher automatically signs into the inner editor, relying on localhost or
PRIVATE Codespaces forwarding. Do not expose the launcher as a public service.
The public Pages site contains no runtime passwords.

## Development

    python3 scripts/build_pages.py --repository OWNER/REPOSITORY
    python3 -m http.server 8808 --bind 127.0.0.1 --directory dist

The static build uses Python's standard library. On a Docker host, python3
launch.py opens the guided setup. Actual GitHub provisioning still needs a
one-account pilot before classroom use; this session lacks valid GitHub access.
