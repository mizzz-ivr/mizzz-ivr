# Profile Signal — Release installation

Profile Signal is distributed as a self-contained ZIP that you extract into your own GitHub Profile Repository.

The recommended path is **Release ZIP installation**. Forking the showcase profile is supported only as a reference because the showcase contains personal README content and assets.

## Requirements

- A public GitHub Profile Repository named `<username>/<username>`
- GitHub Actions enabled
- Repository Actions permission that can write repository contents
- No API key or secret is required for the default public-only mode

## Install

1. Download the latest `profile-signal-<version>.zip` from Releases.
2. Extract the archive into the root of your Profile Repository.
3. Edit `.github/profile-signal.yml`.
4. Replace `YOUR_GITHUB_USERNAME` with your GitHub login.
5. Choose a preset/theme and optional widget overrides.
6. Commit and push the extracted files.
7. Open **Actions → Profile Signal → Run workflow** once.
8. Confirm README, `assets/`, and `data/` were generated.

The archive adds these files and does not replace your README:

```text
.profile-signal/
├─ action.yml
├─ LICENSE
├─ src/
│  └─ orchestrator.py
└─ scripts/
   ├─ update-profile-activity.py
   ├─ profile_signal.py
   ├─ update-profile-signal.py
   ├─ profile_signal_operations.py
   └─ profile_signal_history.py

.github/
├─ profile-signal.yml
└─ workflows/
   └─ profile-signal.yml

PROFILE_SIGNAL_INSTALL.md
```

## Presets

- `minimal` — LIVE SIGNAL + CURRENT FOCUS
- `standard` — LIVE SIGNAL + TODAY + CURRENT FOCUS + DEV PULSE
- `full` — all widgets
- `terminal` — all widgets with terminal theme by default

## Themes

- `signal`
- `minimal`
- `terminal`

## README placement

With `auto_insert_markers: true`, enabled widgets are inserted automatically.

The default release config uses an empty `insert_before`, so widgets are appended to the README rather than guessing one of your headings. To place them before a known section, configure for example:

```yaml
readme:
  auto_insert_markers: true
  insert_before: "## About me"
```

You can also set `auto_insert_markers: false` and place markers yourself.

## Updating

When a new release is published:

1. Back up or commit your current repository state.
2. Download the new release archive.
3. Replace only `.profile-signal/` with the new runtime.
4. Keep your existing `.github/profile-signal.yml` unless the release notes require a config migration.
5. Review the workflow template before replacing your existing workflow.
6. Run `Profile Signal` manually and inspect the generated diff.

## Uninstalling

1. Delete `.profile-signal/`.
2. Delete `.github/profile-signal.yml` and `.github/workflows/profile-signal.yml` if no longer needed.
3. Remove generated Profile Signal marker blocks from README if you do not want to keep the last rendered output.
4. Optionally remove `assets/dev-pulse.svg` and `data/` history.

## Privacy

Profile Signal v0 requires:

```yaml
privacy:
  public_only: true
```

The runtime reads public GitHub activity only. Private repository information is not collected and then masked later.
