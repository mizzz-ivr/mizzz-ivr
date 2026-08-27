# Developer Analytics / Skill Sheet

`mizzz-ivr/mizzz-ivr` 専用のDeveloper Analytics基盤です。

## 目的

GitHub Profileを単なる活動量表示ではなく、公開Repositoryから確認できる開発Evidenceを使って次を継続的に整理します。

- よく使う技術とRepository breadth
- 最近使っている技術 / recency
- Web / AI / Platform / Operations等の開発領域
- Testing / CI/CD / Security / Observability / Documentation等の開発手法
- Architecture / Implementation / Testing / Delivery / Operations等のOwnership
- フリーランス・受託・案件アサイン時に使えるPublic Evidence Coverage
- 時系列snapshotによるEvidenceの変化
- Markdown Skill Sheet

## 境界

### Profile Signal

`.profile-signal/` と `mizzz-ivr/profile-signal` はDeveloper Analyticsの実装対象外です。

Profile Signalは引き続き `LIVE SIGNAL / TODAY / CURRENT FOCUS / DEV PULSE / NOW BUILDING / ACTIVITY STREAM / DEV RECAP` の「今の活動」を担当します。

Developer Analyticsは「何を作れるか / どの領域のEvidenceがあるか」を担当します。

### Public / Private

Committed outputは **public-safe GitHub evidenceのみ** を対象にします。

- `projects[].public: true` が必須
- GitHub APIでPrivate Repositoryと判定された場合は生成を失敗させる
- Forkは明示許可しない限りOriginal Evidenceとして扱わない
- Private Repository名、顧客情報、秘密情報は公開JSON/Markdownへ出力しない
- 公開Evidenceが無いことを「未経験」と解釈しない

## Evidence Score

`Evidence Score` は能力値・習熟度・経験年数ではありません。

公開GitHub上で確認できる次のSignalを合成した **Evidence strength** です。

- Repository breadth
- user-authored PR / Issue
- merged / completed evidence
- recency
- CI / Test / Docs / Docker / Migration / Security / Observability / Release等のdelivery signal

営業利用時はScoreそのものよりEvidence Repositoryと実装内容を説明するために使います。

## Assignment fit

`assignment_profiles` は案件タイプごとに「公開Repositoryで証明したいSignal」を定義します。

Coverageは configured signals のうち現在のPublic Evidence setで何%を確認できるかを示します。採用可能性、単価、実務能力を自動判定する値ではありません。

## Files

```text
.github/developer-analytics.yml       # public-safe Evidence mapping / assignment profiles
scripts/developer_analytics.py       # collector / analytics / renderer
tests/test_developer_analytics.py    # deterministic unit tests
.github/workflows/developer-analytics.yml
SKILL_SHEET.md                       # 営業・案件アサイン向けMarkdown
reports/developer-analytics.md       # 詳細分析レポート
data/developer-analytics/latest.json # latest machine-readable state
data/developer-analytics/snapshots/  # manual runごとのhistory
```

## Execution policy

### Pull Request

PRでは設定・unit test・offline renderだけを検証し、生成物をcommitしません。

### Manual

Skill Sheet / Analyticsのユーザー向け再生成は **GitHub Actions `workflow_dispatch` の手動実行のみ** です。Schedule triggerは設定しません。

手動実行時はGitHub APIでPublic Repositoryの現状を再取得して次を更新します。

1. `README.md` の `ENGINEERING PROFILE`
2. `SKILL_SHEET.md`
3. `reports/developer-analytics.md`
4. `data/developer-analytics/latest.json`
5. `data/developer-analytics/snapshots/<timestamp>.json`
6. 同じ内容をGitHub Actions artifactとして30日保持

## Maintenance

新しいPublic ProjectをEvidenceへ加えるときはRepositoryを自動推測で分類せず `.github/developer-analytics.yml` に明示的に追加します。

`technologies / domains / capabilities / practices / ownership` はREADME・Docs・実装・PRなどで根拠が確認できるものだけを登録します。
