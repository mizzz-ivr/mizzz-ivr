# Profile Signal Wiki

Profile Signal は、公開 GitHub Activity をもとに GitHub Profile README を自動更新するための self-contained runtime です。

推奨導入方法は **GitHub Release の ZIP を、自分の GitHub Profile Repository に展開して使う方法**です。

```text
GitHub Release ZIP
        ↓
<username>/<username>
        ↓
.profile-signal/
.github/profile-signal.yml
.github/workflows/profile-signal.yml
        ↓
uses: ./.profile-signal
```

導入後は利用者自身のRepository内だけでruntimeを実行し、GitHub ActionsからREADMEを更新します。

## 現在の安定版

- `v0.1.0`
- public-only
- API Secret 不要
- GitHub Actions による定期更新
- README の既存本文は ZIP 展開時に上書きしない

## Wiki

- [導入手順](Installation)
- [設定リファレンス](Configuration)
- [プリセットとテンプレート](Presets)
- [ライセンス](License)

## 主な表示

現在の runtime では以下の Widget を組み合わせられます。

- LIVE SIGNAL
- TODAY
- CURRENT FOCUS
- DEV PULSE
- NOW BUILDING
- ACTIVITY STREAM
- DEV RECAP

表示内容は `preset` を起点にしつつ、`widgets` で個別に上書きできます。

## 配布方針

Release ZIP を標準導入経路とします。Fork は完成形プロフィール全体を参考にしたい場合の補助的な方法です。

Profile Signal の実行コードを利用者自身の Profile Repository に保持することで、導入内容を確認しやすくし、外部 Action Repository の可用性に毎回依存しない構成にしています。
