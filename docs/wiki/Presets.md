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

## 今後の拡張方針

Profile Signal は将来、用途別のPresetを継続追加できる設計にします。

候補の名前や内容を固定する前に、以下の互換性ルールを守ります。

1. **Presetは既存Widgetの組み合わせと既定Themeを定義する**
2. **データ収集のPrivacyルールをPresetで弱めない**
3. **`widgets` によるユーザー指定をPresetより優先する**
4. **既存Presetの意味を破壊的に変更しない**
5. **大きな構成変更が必要な場合は新Preset名を追加する**
6. **Preset追加だけで既存READMEを勝手に書き換えない**

## v0.2系での設計目標

現在のPreset定義はruntimeコード内のregistryです。将来的には、Preset追加をRenderer本体の修正から分離できるようにします。

想定:

```text
.profile-signal/
└─ presets/
   ├─ minimal.yml
   ├─ standard.yml
   ├─ full.yml
   └─ terminal.yml
```

将来はこのregistryへ新しいProfile templateを追加しやすくし、さらに必要であれば利用者独自Presetも検討します。

## PresetとThemeの責務

```text
Preset
  = どのWidgetを使うか

Theme
  = Widgetをどう見せるか

Widget override
  = 利用者が最終的に何をON/OFFするか
```

この分離を維持することで、Preset数が増えてもcollector / analyticsへ不要な分岐を増やさない方針です。
