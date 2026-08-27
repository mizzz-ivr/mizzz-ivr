# Developer Analytics / Skill Sheet

`mizzz-ivr/mizzz-ivr` 専用のDeveloper Analytics基盤です。

## 目的

公開GitHub Repositoryから、技術・開発領域・開発手法・Ownership・案件タイプ別の公開実績を整理し、GitHub Profileと案件向けSkill Sheetへ再利用します。

## 表示言語

日本語を既定にします。

- `README.md` — 日本語Profile
- `README.en.md` — English Profile
- `SKILL_SHEET.md` — 日本語Skill Sheet
- `SKILL_SHEET.en.md` — English Skill Sheet
- `reports/developer-analytics.md` — 日本語詳細分析
- `reports/developer-analytics.en.md` — English detailed report

GitHub READMEではJavaScriptによるタブ切替は使わず、各Markdown上部の `日本語 / English` リンクで切り替えます。

## 構成

```text
.github/developer-analytics.yml        # Public-safe Evidence設定
scripts/developer_analytics.py         # GitHub Evidence収集 / 集計
scripts/render_developer_profile.py    # 日本語優先 + ENドキュメント生成
tests/test_developer_analytics.py
tests/test_developer_profile_renderer.py
SKILL_SHEET.md
SKILL_SHEET.en.md
reports/developer-analytics.md
reports/developer-analytics.en.md
data/developer-analytics/latest.json
data/developer-analytics/snapshots/
```

## Skill Sheet方針

Skill Sheetは詳細分析のコピーではなく、短時間で把握できる情報だけに絞ります。

1. 概要
2. 主な技術
3. 強み
4. 代表Public Project
5. 案件タイプ
6. 連絡先

技術ごとのEvidence Scoreや全Project一覧などは `reports/developer-analytics*.md` 側へ分離します。

## Public / Private

Committed outputはPublic-safeな情報だけを対象にします。

- `.github/developer-analytics.yml` の `projects[].public: true` が必須
- Private Repositoryは生成対象外
- Forkは明示許可しない限りOriginal Evidenceとして扱わない
- 顧客情報・秘密情報・非公開案件名を出力しない

## Profile Signalとの境界

Profile Signalは「今の活動」、Developer Analyticsは「何を作れるか / 公開実績」を担当します。

技術記事用Repositoryなど、活動量はあるが `CURRENT FOCUS` として表示したくないRepositoryは `.profile-signalignore` で除外します。

現在:

```text
mizzz-ivr/tech-writing
```

`.profile-signalignore` は空行と `#` コメントを無視し、`*` / `?` のglob patternを利用できます。

除外対象:

- 現在のフォーカス
- 現在動いているRepository
- 最近の公開アクティビティ

TODAY / weekly / monthlyの総活動量はGitHub全体の活動履歴として残します。

## 実行ポリシー

### Pull Request

PRでは以下を検証します。

- Developer Analytics config
- unit tests
- offline render
- Public GitHub live validation
- JP / EN document render
- Profile Signal日本語Consumer render
- `.profile-signalignore` filter

### Manual

Developer Analyticsのユーザー向け再生成は `workflow_dispatch` の手動実行だけです。

手動実行すると以下を更新します。

- `README.md`
- `README.en.md`
- `SKILL_SHEET.md`
- `SKILL_SHEET.en.md`
- `reports/developer-analytics.md`
- `reports/developer-analytics.en.md`
- `data/developer-analytics/latest.json`
- `data/developer-analytics/snapshots/<timestamp>.json`

Profile Signal側は既存scheduleの後に `scripts/profile_signal_customize.py` を実行し、日本語表示とRepository除外を適用します。
