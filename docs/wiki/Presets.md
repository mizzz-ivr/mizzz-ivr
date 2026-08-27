# プリセットとテンプレート

Profile Signal では、プロフィールへ挿入する表示セットを `preset` として管理します。

## 現在のPreset

### `minimal`

最小構成です。

- LIVE SIGNAL
- CURRENT FOCUS

### `standard`

初回導入向けの標準構成です。

- LIVE SIGNAL
- TODAY
- CURRENT FOCUS
- DEV PULSE

### `full`

現在利用できる全Widgetを表示します。

- LIVE SIGNAL
- TODAY
- CURRENT FOCUS
- DEV PULSE
- NOW BUILDING
- ACTIVITY STREAM
- DEV RECAP

### `terminal`

Widget構成は `full` 相当で、Theme指定が無い場合に `terminal` themeを使用します。

## Widget override

Presetを選んだ後でも個別変更できます。

```yaml
preset: standard

widgets:
  now_building:
    enabled: true
  dev_pulse:
    enabled: false
```

このためPresetは固定レイアウトではなく、**開始点となるテンプレート**として扱います。

## Preset Registry

Preset定義はruntimeコードから分離し、`.profile-signal/presets/*.yml` から読み込みます。

```text
.profile-signal/
└─ presets/
   ├─ minimal.yml
   ├─ standard.yml
   ├─ full.yml
   └─ terminal.yml
```

例えば `standard.yml` は次のような構造です。

```yaml
version: 1
id: standard
description: Balanced default profile signal.
theme: signal
widgets:
  - live_signal
  - today
  - current_focus
  - dev_pulse
```

Registry loaderが起動時に全YAMLを検証し、OrchestratorへWidget集合と既定Themeを渡します。

## 新しい公式Presetを追加する場合

新しいProfile templateは原則としてPreset YAMLの追加だけで定義できます。

例:

```yaml
version: 1
id: compact
description: Compact profile template.
theme: minimal
widgets:
  - today
  - current_focus
```

ファイル名はPreset IDと一致させます。

```text
.profile-signal/presets/compact.yml
```

runtime本体へ `if preset == "compact"` のような分岐を追加する必要はありません。

## Registry validation

Preset追加時は以下を自動検証します。

- YAMLがmappingであること
- schema `version: 1` であること
- `id` とファイル名が一致すること
- `widgets` が空ではないこと
- Widget名が既存Widget contractに存在すること
- Widgetの重複がないこと
- Themeが `signal / minimal / terminal` のいずれかであること
- `minimal / standard / full / terminal` の既存Presetが欠落していないこと

CIでは既存4PresetのWidget構成も固定し、Preset追加で既存ユーザーの表示が変わらないようにします。

## 拡張時の互換性ルール

Profile Signal は用途別のPresetを継続追加できる設計にします。

1. **Presetは既存Widgetの組み合わせと既定Themeを定義する**
2. **データ収集のPrivacyルールをPresetで弱めない**
3. **`widgets` によるユーザー指定をPresetより優先する**
4. **既存Presetの意味を破壊的に変更しない**
5. **大きな構成変更が必要な場合は新Preset名を追加する**
6. **Preset追加だけで既存READMEを勝手に書き換えない**
7. **Release ZIPへ全Preset定義を同梱する**

将来的には `compact / developer / portfolio / activity / oss` など、用途別Profile templateを追加できます。名称とWidget構成は実際の利用ケースを確認しながら決定します。

## PresetとThemeの責務

```text
Preset
  = どのWidgetを使うか + 既定Theme

Theme
  = Widgetをどう見せるか

Widget override
  = 利用者が最終的に何をON/OFFするか
```

この分離を維持することで、Preset数が増えてもcollector / analyticsへ不要な分岐を増やさない方針です。

## 利用者独自Presetについて

現行Releaseの推奨カスタマイズ方法は `widgets` overrideです。

`.profile-signal/` はRelease更新時にruntimeごと差し替える領域なので、利用者独自Presetを直接そこへ追加するとUpdate時に失われる可能性があります。利用者専用Presetを安全に外部定義する仕組みは、公式Preset Registryとは分けて今後検討します。
