# Running CI on your own Forgejo

GitHub Actions can't run for this repository while the account is locked (ADR-0017). The same CI runs on a self-hosted
Forgejo instead:

```
GitHub repo  --(sync script, every few minutes)-->  Forgejo repo  -->  Forgejo Actions
 (you, Claude sessions push here)                    (a copy for CI)     Linux runner (Docker)
                                                                         Windows runner (optional)
```

- `.forgejo/workflows/effect-tests.yml` is the Forgejo workflow. GitHub ignores that folder, and Forgejo uses it
  instead of `.github/workflows/`. Both workflows build MAME with the same script, `tools/ci/build-mame.sh`.
- `tools/forgejo/sync-github-to-forgejo.sh` copies every branch and tag from GitHub to Forgejo. Each new commit arrives
  as an ordinary push, which starts the workflow. A Forgejo *pull mirror* won't do: Forgejo keeps Actions off for
  mirrors.
- No game ROM is involved unless you choose to point the runner at a ROM folder on the homelab (step 5). ROMs still
  never go into git.

What you need: the Forgejo instance (Actions enabled, which is the default in current versions), a Linux machine with
Docker for the runner (it can be the Forgejo host), and optionally a Windows 10 or 11 machine.

## 1. Create the Forgejo repository

1. In Forgejo, create a new, empty repository, for example `arcade-cabinet-simulator`. Don't make it a mirror, and
   don't let Forgejo add a README.
2. In the repository's **Settings → Units** (called **Repository → Features** in some versions), make sure **Actions** is
   on.
3. For the sync, add a **deploy key with write access** (**Settings → Deploy keys**). Generate the key on the machine
   that will run the sync:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/acs_forgejo_deploy -N "" -C "acs sync"
   cat ~/.ssh/acs_forgejo_deploy.pub    # paste this into Forgejo, tick "write access"
   ```

## 2. Register a Linux runner

The workflow's Linux job asks for a runner labelled `docker` and runs in a `node:22-bookworm` container (Debian 12 with
Node, git and gcc).

1. Install `forgejo-runner` on a Linux machine with Docker (a binary release, a distribution package, or its container
   image): [runner installation guide](https://forgejo.org/docs/latest/admin/actions/runner-installation/).
2. Get a registration token: the repository's **Settings → Actions → Runners → Create new runner** (or the same page
   under **Site administration** for an instance-wide runner).
3. Register and start it. With a recent runner that looks like this; check `forgejo-runner register --help` for yours:

   ```bash
   forgejo-runner generate-config > config.yml      # the cache server is on by default; leave it on
   forgejo-runner register --no-interactive --instance https://<your forgejo> --token <token> \
       --name homelab-linux --labels docker:docker://node:22-bookworm
   forgejo-runner daemon --config config.yml        # or run it as a service
   ```

The first run builds MAME from source: give the runner about 6 GB of free disk and as many cores as you can spare. The
binary is cached afterwards, keyed on the MAME tag and the patches, so later runs skip the build.

## 3. Sync from GitHub

On the machine with the deploy key (needs `git`, `bash` and `flock`), get the script. Either use a checkout of this
repository, or copy `tools/forgejo/sync-github-to-forgejo.sh` somewhere on its own; it doesn't need the rest of the repo.

```bash
export FORGEJO_URL=ssh://git@<your forgejo>:<ssh port>/<you>/arcade-cabinet-simulator.git
export GIT_SSH_COMMAND="ssh -i ~/.ssh/acs_forgejo_deploy -o IdentitiesOnly=yes"
./sync-github-to-forgejo.sh          # first run copies everything; later runs print only refs that moved
```

Then run it every few minutes. With cron (`crontab -e`):

```
*/5 * * * * FORGEJO_URL=ssh://git@<host>:<port>/<you>/arcade-cabinet-simulator.git GIT_SSH_COMMAND="ssh -i $HOME/.ssh/acs_forgejo_deploy -o IdentitiesOnly=yes" $HOME/bin/sync-github-to-forgejo.sh
```

The script prints nothing when nothing changed, so cron only mails you when something moved or failed. Push your work to
GitHub, not to the Forgejo copy: the next sync overwrites anything pushed straight to Forgejo. `SYNC_PRUNE=1` also
deletes branches that were deleted on GitHub.

## 4. Optional: a Windows runner

The workflow's `windows` job runs only when the repository variable `CABSIM_WINDOWS` is `true` (**Settings → Actions →
Variables**), so it never waits for a runner you don't have.

On the Windows machine:

1. Install Git for Windows, Node.js LTS, PowerShell 7 (`pwsh`) and Python 3.12 (with "Add to PATH").
2. Install [MSYS2](https://www.msys2.org/) to `C:\msys64`. In its **MINGW64** shell, install what MAME's own Windows
   build uses:

   ```bash
   pacman -S --needed git make mingw-w64-x86_64-gcc mingw-w64-x86_64-python mingw-w64-x86_64-lld \
       mingw-w64-x86_64-llvm mingw-w64-x86_64-libc++
   ```

3. Install `forgejo-runner` for Windows and register it with the label `windows:host` (host mode: jobs run straight on
   the machine, no Docker).
4. Set the repository variable `CABSIM_WINDOWS` to `true`.

Windows host mode is less documented upstream than Linux, so expect some trial and error the first time. The same
machine is the one PLAN v0.3 wants for the Stage 2 frame-transport measurements.

## 5. Optional: real-game tests on the homelab

The real-game effect tests skip in CI unless they find a ROM set. To run them on your runner, keep the ROMs in a folder
on the runner host and let the job see it:

1. In the runner's `config.yml`, under `container:`, allow and mount the folder read-only:

   ```yaml
   container:
     valid_volumes: ["/srv/roms"]
     options: "-v /srv/roms:/roms:ro"
   ```

2. Set the repository variable `CABSIM_ROMPATH` to `/roms`. For the Windows runner, use a local folder path instead.

The ROM files stay on that machine. The job's evidence artifact holds screenshots and hashes only.

## Reading results

Each run is under the repository's **Actions** tab. The evidence (each test's `result.json` and its images) is attached to
the run as `effect-evidence-linux` and `effect-evidence-windows`. To show a run to a Claude session that can't reach your
Forgejo, paste the failing step's log or upload the artifact.

## If something goes wrong

- **"action not found" for `actions/checkout` or `actions/cache`**: the instance looks actions up on
  `code.forgejo.org` by default. Set `[actions] DEFAULT_ACTIONS_URL = github` in Forgejo's `app.ini` to use GitHub
  instead.
- **The cache never hits**: the runner's built-in cache server must be on (`cache: enabled: true` in `config.yml`) and
  reachable from the job containers.
- **Artifact upload fails with "GHES not supported"**: the workflow must use Forgejo's build of the action
  (`https://code.forgejo.org/forgejo/upload-artifact@v4`), which it does.
- **The sync prints `!` lines**: Forgejo refused a push. Check that the deploy key has write access and that branch
  protection on the Forgejo copy allows force pushes.
