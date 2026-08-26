# Profile Signal — Action staging package

GitHubのPublic ActivityからProfile README用のライブ開発ダッシュボードを生成する、config-driven GitHub Actionです。

> このディレクトリは `mizzz-ivr/profile-signal` へ切り出す前のDogfooding版です。現在の `mizzz-ivr/mizzz-ivr` 自身でlocal actionとして検証します。

## What it generates

Widgetは好きなものだけ選べます。

- `live_signal` — DEV STATUS / CODE WEATHER / BUILD STREAK
- `today` — Commit / PR / Issue counters
- `current_focus` — weighted repository focus / TODAY'S STACK
- `dev_pulse` — 7-day activity + CI SIGNAL
- `now_building` — top active repositories + PROJECT HEALTH
- `activity_stream` — latest public development events
- `dev_recap` — Weekly / Monthly / Achievements

## Presets

| preset | widgets |
| --- | --- |
| `minimal` | LIVE SIGNAL + CURRENT FOCUS |
| `standard` | LIVE SIGNAL + TODAY + CURRENT FOCUS + DEV PULSE |
| `full` | all widgets |
| `terminal` | all widgets + terminal theme |

## Themes

- `signal` — table / SVG based default theme
- `minimal` — compact text based renderer
- `terminal` — terminal-like fenced text renderer

## Installation target

最終的な配布版では次の3ステップを基本にします。

### 1. Config

`.github/profile-signal.yml`

```yaml
version: 1

profile:
  username: octocat
  timezone: Asia/Tokyo

privacy:
  public_only: true

preset: standard
theme: signal

widgets:
  activity_stream:
    enabled: false

readme:
  path: README.md
  auto_insert_markers: true
  insert_before: "## NOW // What I build"
  empty_disabled: true
```

### 2. Workflow

切り出し後の想定形です。

```yaml
name: Profile Signal

on:
  schedule:
    - cron: "17 */3 * * *"
      timezone: "Asia/Tokyo"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  profile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: mizzz-ivr/profile-signal@v1
        with:
          config: .github/profile-signal.yml

      - name: Commit Profile Signal
        shell: bash
        run: |
          if [ -z "$(git status --porcelain -- README.md assets data)" ]; then
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add README.md assets data
          git commit -m "chore(profile): refresh Profile Signal [skip ci]"
          git pull --rebase origin main
          git push origin HEAD:main
```

### 3. README

`auto_insert_markers: true` の場合、選択したWidgetのMarkerが不足していれば `insert_before` の直前へ自動挿入します。

手動配置したい場合は `auto_insert_markers: false` にして、次のようなMarkerを好きな位置へ置きます。

```md
<!-- PROFILE-SIGNAL:LIVE-SIGNAL:START -->
<!-- PROFILE-SIGNAL:LIVE-SIGNAL:END -->

<!-- PROFILE-SIGNAL:FOCUS:START -->
<!-- PROFILE-SIGNAL:FOCUS:END -->
```

## Widget override

Presetから一部だけ変更できます。

```yaml
preset: standard

widgets:
  today:
    enabled: false
  now_building:
    enabled: true
  activity_stream:
    enabled: true
```

OFFにしたWidgetのMarkerが既にREADMEにある場合、デフォルトではMarker pairだけ残して中身を空にします。再度ONにすると同じ位置へ復元できます。

## Privacy contract

v0では `privacy.public_only: true` が必須です。

Private Activityを取得してからmaskするのではなく、最初からPublic APIだけをCollection対象にします。

## Data

生成データは現在のProfile Signalと互換です。

```text
data/
├─ activity/YYYY/MM/YYYY-MM-DD.json
├─ weekly/YYYY-Www.json
├─ monthly/YYYY-MM.json
└─ profile-signal-state.json

assets/
├─ activity-7d.svg
└─ dev-pulse.svg
```

## Extraction plan

Dogfooding完了後、このpackageと既存の`/scripts`を `mizzz-ivr/profile-signal` へ移し、以下を追加してv1へ進めます。

- Repository release / `v1` tag
- action metadata finalization
- examples gallery
- config reference
- reusable test fixtures
- installation smoke test against a sample profile repository
- Qiita #3
