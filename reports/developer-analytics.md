<p align="right"><strong>日本語</strong> · <a href="./developer-analytics.en.md">English</a></p>

# Developer Analytics — 詳細分析

生成日時: `2026-08-27T10:02:46Z`

## 集計概要

| 項目 | 値 |
| --- | ---: |
| 対象公開Project | 9 |
| 技術要素 | 40 |
| 開発プラクティス | 22 |
| 案件タイプ | 5 |

## 技術別の公開実績

| 技術 | 公開実績 | Project数 |
| --- | --- | ---: |
| React | REPEATED | 6 |
| Docker | REPEATED | 5 |
| TypeScript | REPEATED | 5 |
| PostgreSQL | REPEATED | 4 |
| Next.js | ESTABLISHED | 3 |
| Python | ESTABLISHED | 3 |
| Tailwind CSS | ESTABLISHED | 3 |
| Playwright | ESTABLISHED | 2 |
| Vitest | ESTABLISHED | 2 |
| GitHub Actions | EMERGING | 2 |
| GitHub API | EMERGING | 2 |
| Go | EMERGING | 2 |
| YAML | EMERGING | 2 |
| AWS Lightsail | EMERGING | 2 |
| Discord.js | EMERGING | 2 |
| Node.js | EMERGING | 2 |
| Vercel | EMERGING | 2 |

## 開発プラクティス

| プラクティス | 主な公開Project |
| --- | --- |
| Repository中心の開発 | Herta / IVRM Dashboard / ivmz-home / QuizVerse / RooMate Voice |
| セキュリティを設計段階で考慮 | Herta / IVRM Dashboard / ivRooom Member Site / QuizVerse / RooMate Voice |
| 自動テスト | ivRooom Member Site / ivmz-home / profile-signal / QuizVerse |
| アクセシビリティ | ivRooom Member Site / ivmz-home |
| 可観測性 | IVRM Dashboard |
| 最小権限 | IVRM Dashboard |
| Fail-close設計 | RooMate Voice |
| リリース自動化 | profile-signal |
| Graceful Shutdown | Site Sentry Go |
| Performance Budget | ivRooom Member Site |

## 案件タイプ別

| 分野 | 公開実績カバー率 | 現在の不足シグナル |
| --- | ---: | --- |
| Discord / コミュニティ基盤 | 100% | なし |
| フルスタック開発 | 100% | なし |
| プラットフォーム / 開発ツール | 100% | なし |
| リアルタイムAI / 音声 | 100% | なし |
| DevOps / 可観測性 | 86% | ci-cd |

## Project別

| Project | 主な領域 | 主な技術 |
| --- | --- | --- |
| [Herta](https://github.com/ivRooom/Herta) | Discord / Platform / Backend | TypeScript / NestJS / Next.js / PostgreSQL / Redis / Docker |
| [RooMate Voice](https://github.com/mizzz-ivr/roomate-voice) | Realtime AI / Voice / Desktop | TypeScript / OpenAI Realtime / Discord Voice / Electron / Docker |
| [ivmz-home](https://github.com/mizzz-ivr/ivmz-home) | Web Product / CMS / Portfolio | Next.js / React / Payload / PostgreSQL / Playwright |
| [QuizVerse](https://github.com/mizzz-ivr/quizverse) | Web Product / Learning | React / Flask / PostgreSQL / Docker |
| [IVRM Dashboard](https://github.com/ivRooom/ivrm-dashboard) | Operations / Observability | TypeScript / Next.js / Go / Supabase / Docker |
| [ivRooom Member Site](https://github.com/ivRooom/ivrm-member-site) | Web / Creative Frontend | Astro / React / Three.js / Cloudflare Workers |
| [Site Sentry Go](https://github.com/mizzz-ivr/site-sentry-go) | Monitoring / Backend Tool | Go / SQLite / HTTP / Docker |
| [Profile Signal](https://github.com/mizzz-ivr/profile-signal) | Developer Tooling / Analytics | Python / GitHub Actions / GitHub API |
| [Tech Writing](https://github.com/mizzz-ivr/tech-writing) | Technical Writing / Automation | Python / GitHub Actions / Markdown |

## 補足

- 集計対象は公開GitHub上で確認できる情報のみです。
- 非公開Repositoryや顧客情報は出力しません。
- 公開実績の不足は未経験を意味しません。
- `tech-writing` はDeveloper Analyticsの実績には含めますが、Profile Signalの「現在のフォーカス / 活動中Repository / 最近のアクティビティ」ランキングからは `.profile-signalignore` により除外します。
