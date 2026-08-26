# 設定リファレンス

設定ファイルは `.github/profile-signal.yml` です。

## 標準設定

```yaml
version: 1

profile:
  username: YOUR_GITHUB_USERNAME
  timezone: Asia/Tokyo

privacy:
  public_only: true

preset: standard
theme: signal

widgets: {}

readme:
  path: README.md
  auto_insert_markers: true
  insert_before: ""
  empty_disabled: true
```

## profile

### `profile.username`

対象GitHub loginです。必須です。

### `profile.timezone`

TODAYなどの日付境界に使用します。

例:

```yaml
profile:
  timezone: Asia/Tokyo
```

## privacy

v0.x では以下のみ対応します。

```yaml
privacy:
  public_only: true
```

`false` はエラーになります。

Private Repository 情報を取得して後からマスクするのではなく、最初から公開情報だけを収集します。

## preset

Widget の標準組み合わせを選びます。

```yaml
preset: standard
```

詳細は [プリセットとテンプレート](Presets) を参照してください。

## theme

現在:

- `signal`
- `minimal`
- `terminal`

を利用できます。

Preset は「何を表示するか」、Theme は「どう表示するか」を担当します。

## widgets

Preset の選択結果を個別上書きできます。

例:

```yaml
preset: standard

widgets:
  activity_stream:
    enabled: true
  dev_pulse:
    enabled: false
```

Widget override は preset より優先されます。

## readme

### `path`

更新対象READMEです。

```yaml
path: README.md
```

### `auto_insert_markers`

有効Widgetのmarkerが無い場合に、自動挿入するかを指定します。

### `insert_before`

指定文字列がREADME内に存在する場合、その直前へWidget群を追加します。

空文字の場合はREADME末尾へ追加します。

### `empty_disabled`

無効化されたWidgetのmarker pairを残し、中身だけ空にします。再度有効化したとき同じ位置へ戻しやすくするため、標準では `true` です。
