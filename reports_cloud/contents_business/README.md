# コンテンツビジネス レポート クラウド移行 PoC

最初のゴールは、Mac の Desktop や Google Drive 同期フォルダに依存せず、スマホから Codex Cloud に頼んで「テストSlackへ日次レポートを送る」ことです。

## いま対応した範囲

- LMES cross-analysis を MCP API から取得する
- Google Sheets CSV から広告数値を読む
- コンテンツビジネスの日次レポート本文を作る
- テストSlackまたは本番Slackへ送る
- Slack webhook はコードに直書きせず、環境変数から読む

画像生成、Google Drive アップロード、本番向けの最終調整は次の段階です。

## ローカルでの確認

```bash
node reports_cloud/contents_business/fetch_lmes_crosslytics.mjs \
  --out reports_cloud/contents_business/data/contents_crosslytics_14869.json

python3 reports_cloud/contents_business/build_contents_report.py \
  --crosslytics-json reports_cloud/contents_business/data/contents_crosslytics_14869.json \
  --mode test \
  --out-blocks reports_cloud/contents_business/data/slack_blocks.json
```

テストSlackに送る場合:

```bash
export CONTENTS_TEST_SLACK_WEBHOOK="https://hooks.slack.com/services/..."

python3 reports_cloud/contents_business/build_contents_report.py \
  --crosslytics-json reports_cloud/contents_business/data/contents_crosslytics_14869.json \
  --mode test \
  --send
```

本番Slackに送る場合:

```bash
export CONTENTS_PROD_SLACK_WEBHOOK="https://hooks.slack.com/services/..."

python3 reports_cloud/contents_business/build_contents_report.py \
  --crosslytics-json reports_cloud/contents_business/data/contents_crosslytics_14869.json \
  --mode prod \
  --send
```

## クラウド実行で必要になる秘密情報

- `LMES_ACCESS_TOKEN` または `LMES_TOKEN_FILE`
- `CONTENTS_TEST_SLACK_WEBHOOK`
- `CONTENTS_PROD_SLACK_WEBHOOK`

GitHub に置く場合、これらは repo にコミットせず、GitHub Secrets や Codex Cloud の環境変数に入れます。

## スマホからGitHub Actionsで送る

GitHub repo に push した後、repo の Settings > Secrets and variables > Actions に以下を登録します。

- `LMES_ACCESS_TOKEN`
- `CONTENTS_TEST_SLACK_WEBHOOK`
- `CONTENTS_PROD_SLACK_WEBHOOK`

スマホで送るときは:

1. GitHubでrepoを開く
2. `Actions` を開く
3. `Contents Business Report` を選ぶ
4. `Run workflow` を押す
5. `mode` を `test` または `prod` にして実行

自然言語で調整したい場合は、Codex Cloudでこのrepoを開いて「コンテンツビジネスのレポートをテストSlackに送って。READMEに従って。」と依頼します。
