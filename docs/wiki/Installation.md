# 導入手順

## 前提

- GitHub Profile Repository があること
  - `<username>/<username>` 形式
- GitHub Actions が有効であること
- Workflow が Repository contents へ書き込めること
- v0.x は公開 GitHub Activity のみを対象とすること

API Key や PAT は、標準の public-only 構成では不要です。

## 1. Release ZIP を取得

GitHub Releases から最新の `profile-signal-<version>.zip` をダウンロードします。

`v0.1.0` の場合:

```text
profile-signal-v0.1.0.zip
```

## 2. Profile Repository の root へ展開

ZIP を展開すると、主に以下が追加されます。

```text
.profile-signal/
├─ action.yml
├─ LICENSE
├─ src/
└─ scripts/

.github/
├─ profile-signal.yml
└─ workflows/
   └─ profile-signal.yml

PROFILE_SIGNAL_INSTALL.md
PROFILE_SIGNAL_VERSION
```

Release ZIP に `README.md` 自体は含まれていません。既存プロフィール本文を ZIP 展開だけで上書きしないためです。

## 3. GitHub username を設定

`.github/profile-signal.yml` を開きます。

```yaml
profile:
  username: YOUR_GITHUB_USERNAME
  timezone: Asia/Tokyo
```

`YOUR_GITHUB_USERNAME` を自分の GitHub login に変更します。

## 4. Preset / Theme を選択

初期設定は以下です。

```yaml
preset: standard
theme: signal
```

最初は `standard` を推奨します。

利用可能な preset と追加予定の考え方は [プリセットとテンプレート](Presets) を参照してください。

## 5. GitHub Actions の書き込み権限を確認

Repository の設定で、Workflow が contents を更新できる必要があります。

GitHub UI:

```text
Settings
  → Actions
    → General
      → Workflow permissions
        → Read and write permissions
```

Organization / Repository policy で書き込みが禁止されている場合は、Profile Signal の生成自体は成功しても README への commit / push が失敗します。

## 6. commit / push

展開したファイルと設定を commit します。

```bash
git add .profile-signal .github/profile-signal.yml .github/workflows/profile-signal.yml PROFILE_SIGNAL_INSTALL.md PROFILE_SIGNAL_VERSION
git commit -m "feat: install Profile Signal"
git push
```

## 7. 初回実行

GitHub UI から:

```text
Actions
  → Profile Signal
    → Run workflow
```

を実行します。

## 8. 生成結果を確認

正常に動くと、設定した preset に応じて以下が更新・生成されます。

- `README.md`
- `data/`
- `assets/dev-pulse.svg` などの生成 Asset

`minimal` のように SVG を使わない構成では `assets/` が存在しない場合があります。これは正常です。

## README の挿入位置

標準配布設定では:

```yaml
readme:
  path: README.md
  auto_insert_markers: true
  insert_before: ""
  empty_disabled: true
```

となっており、既存見出しを推測せず README 末尾へ追加します。

特定見出しの前へ入れたい場合:

```yaml
readme:
  auto_insert_markers: true
  insert_before: "## About me"
```

のように変更できます。

## 更新

新Releaseへ更新する場合は、まず現在のRepositoryをcommitしてRollbackできる状態にしてください。

推奨手順:

1. 新しいRelease ZIPを取得
2. `.profile-signal/` を新しいruntimeへ差し替える
3. 既存 `.github/profile-signal.yml` は原則維持
4. Release Notes にconfig migrationがある場合だけ設定を変更
5. Workflow templateの差分を確認
6. `Profile Signal` を手動実行
7. README / data / assets のdiffを確認

## アンインストール

1. `.profile-signal/` を削除
2. `.github/profile-signal.yml` を削除
3. `.github/workflows/profile-signal.yml` を削除
4. README の Profile Signal marker block を必要に応じて削除
5. 不要なら `assets/` と `data/` の生成物を削除
