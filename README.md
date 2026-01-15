# dbt Semantic View Generator

[![dbt](https://img.shields.io/badge/dbt-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

dbt SQLモデルからSnowflake Semantic Viewを自動生成するツールです。

GPTを使用してdbtモデルを解析し、Snowflake Cortex Analystで自然言語クエリを可能にするセマンティックビューを生成します。

## 特徴

- **自動分類**: GPTモデルがカラムをFACTまたはDIMENSIONに自動分類
- **YML連携**: 既存のdbtモデルドキュメントを活用
- **バージョン管理**: セマンティックビューを自動的にバージョン管理（v1, v2, v3...）

## 前提条件

### dbt_semantic_viewパッケージのインストール

このツールを使用する前に、dbtプロジェクトに [dbt_semantic_view](https://hub.getdbt.com/Snowflake-Labs/dbt_semantic_view/latest/)パッケージをインストールする必要があります。

`packages.yml`に以下を追加：

```yaml
packages:
  - package: Snowflake-Labs/dbt_semantic_view
    version: 1.0.3
```

インストール：

```bash
dbt deps
```

## クイックスタート

### 1. ディレクトリ構造の準備

dbtモデルディレクトリに`semantic/`フォルダを作成します：

```bash
mkdir -p models/your_project/semantic
```

このフォルダにdbt SQLモデルとオプションのYMLファイルを配置します：

```
models/your_project/
└── semantic/                      # セマンティックビュー対象モデル置き場
    ├── customers.sql              # SQLモデル
    ├── customers.yml              # カラム説明
    └── semantic_views/            # 自動生成されるフォルダ
        └── customers_semantic_view.sql
```

**重要なポイント:**
- **`models/<project>/semantic/`**: ユーザーが作成・管理するフォルダ
- **`models/<project>/semantic/semantic_views/`**: スクリプトが自動生成（手動作成不要）

### 2. ローカル実行

```bash
# 依存関係をインストール
pip install openai pyyaml

# OpenAI APIキーを設定
export OPENAI_API_KEY="your-api-key"

# プロジェクトルートから実行
python scripts/generate_semantic_view.py
```

スクリプトは自動的に`models/*/semantic/`を検索して処理します。

### 3. GitHub Actionsのセットアップ

ワークフローファイルをリポジトリにコピー：

```bash
cp .github/workflows/generate_semantic_views.yml your-repo/.github/workflows/
cp scripts/generate_semantic_view.py your-repo/scripts/
```

GitHub Secretsにキーを追加：
- Settings → Secrets and variables → Actions
- `OPENAI_API_KEY`を追加

## 使い方

### ステップ1: dbtモデルの配置

セマンティックビューを作成したいdbtモデルを`semantic/`フォルダに配置：

```sql
-- models/analytics/semantic/customers.sql
{{ config(
  materialized='view'
) }}

SELECT
    customer_id,
    customer_name,
    email,
    total_orders,
    total_revenue,
    created_at
FROM {{ ref('stg_customers') }}
```

### ステップ2: カラム説明の追加

同名のYMLファイルを作成してカラム説明を提供：

```yaml
# models/analytics/semantic/customers.yml
version: 2

models:
  - name: customers
    description: "顧客分析モデル"
    columns:
      - name: customer_id
        description: "顧客ID"
      - name: customer_name
        description: "顧客名"
      - name: email
        description: "メールアドレス"
      - name: total_orders
        description: "注文総数"
      - name: total_revenue
        description: "累計売上"
      - name: created_at
        description: "登録日時"
```

### ステップ3: 生成実行

#### ローカル実行

```bash
export OPENAI_API_KEY="your-api-key"
python scripts/generate_semantic_view.py
```

#### GitHub Actions

以下の場合に自動実行されます：
- `models/**/semantic/*.sql`の変更をプッシュ
- `models/**/semantic/*.yml`の変更をプッシュ

または手動実行：
- GitHub UI → Actions → "Generate Semantic Views" → Run workflow

### ステップ4: 生成結果の確認

`semantic_views/`フォルダにセマンティックビューが生成されます：

```sql
-- models/analytics/semantic/semantic_views/customers_semantic_view.sql
{{ config(
  materialized = 'semantic_view',
  copy_grants = true
) }}

TABLES (
  model AS {{ ref('customers') }}
    PRIMARY KEY (CUSTOMER_ID)
)

FACTS (
  model.TOTAL_ORDERS AS TOTAL_ORDERS
    COMMENT = '注文総数',
  model.TOTAL_REVENUE AS TOTAL_REVENUE
    COMMENT = '累計売上',
  model.CREATED_AT AS CREATED_AT
    COMMENT = '登録日時'
)

DIMENSIONS (
  model.CUSTOMER_ID AS CUSTOMER_ID
    COMMENT = '顧客ID',
  model.CUSTOMER_NAME AS CUSTOMER_NAME
    COMMENT = '顧客名',
  model.EMAIL AS EMAIL
    COMMENT = 'メールアドレス'
)
COMMENT = 'Semantic view for customers model. Enables natural language queries via Cortex Analyst'
```

## 動作の仕組み

1. **SQLモデルのパース**: dbt SQLファイルからカラム情報を抽出
2. **YMLドキュメントの読み込み**: カラム説明があれば読み込み
3. **GPT-4による分析**: カラムをFACTまたはDIMENSIONに分類
4. **セマンティックビューの生成**: `ref()`を使用した本番対応SQLを作成
5. **バージョン管理**: バージョン番号を自動インクリメント

## バージョン管理

同じモデルに対して再生成すると、自動的にバージョン番号が付与されます：

- 初回生成: `customers_semantic_view.sql`
- 2回目: `customers_semantic_view_v2.sql`
- 3回目: `customers_semantic_view_v3.sql`

全てのバージョンが保持されるため、履歴を追跡できます。

## 複数プロジェクト対応

1つのdbtリポジトリで複数プロジェクトをサポート：

```
models/
├── analytics/
│   └── semantic/
│       ├── customers.sql
│       └── semantic_views/
│           └── customers_semantic_view.sql
├── finance/
│   └── semantic/
│       ├── revenue.sql
│       └── semantic_views/
│           └── revenue_semantic_view.sql
└── marketing/
    └── semantic/
        ├── campaigns.sql
        └── semantic_views/
            └── campaigns_semantic_view.sql
```

スクリプトが自動的に全ての`semantic/`フォルダを検出して処理します。

## ベストプラクティス

### 1. 意味のあるカラム名を使用

GPT-4はカラム名を使って分類します。明確な名前を使用してください：

- 良い例: `total_revenue`, `order_count`, `customer_id`
- 避ける: `col1`, `val`, `x`

### 2. YML説明を提供

カラム説明はGPT-4がより良い判断をするのに役立ちます：

```yaml
columns:
  - name: status
    description: "注文ステータスコード（pending, completed, cancelled）"
```

### 3. モデルを事前にクリーンアップ

セマンティックビューは整備されたデータで最も効果的：

- staging → intermediate → martのレイヤー構造を使用
- martモデルにセマンティックビューを適用
- 適切なデータ型と制約を確保

### 4. 生成されたビューをレビュー

デプロイ前に必ず生成されたセマンティックビューをレビュー：

- FACT vs DIMENSIONの分類を確認
- PRIMARY KEYの選択を検証
- コメントが正確か確認

## トラブルシューティング

### 問題: セマンティックビューが生成されない

**解決策:**
1. `models/<project>/semantic/`フォルダが存在するか確認
2. SQLファイルが`semantic/`直下にあるか確認
3. `OPENAI_API_KEY`が正しく設定されているか確認

## 必要要件

- Python 3.8以上
- dbt-core 1.0以上
- dbt-snowflake
- **dbt_semantic_view 
- OpenAI APIキー
- Snowflake（Cortex Analyst有効化済み）

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/RyutoYoda/dbt-semantic-view-generator.git

# 依存関係をインストール
pip install -r requirements.txt

# dbtプロジェクトにコピー
cp -r scripts your-dbt-project/
cp -r .github/workflows your-dbt-project/.github/
```

## サンプルプロジェクト

`example/`ディレクトリにサンプルdbtプロジェクトが含まれています。

```bash
# サンプルプロジェクトで試す
cd example
dbt deps

# セマンティックビューを生成
export OPENAI_API_KEY="your-api-key"
cd ..
python scripts/generate_semantic_view.py
```

詳細は[example/README.md](example/README.md)を参照してください。

## コントリビューション

プルリクエストを歓迎します！

## ライセンス

このプロジェクトはMITライセンスの下でライセンスされています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 謝辞

以下のツールと共に使用するために構築されています：
- [Snowflake Semantic Views](https://docs.snowflake.com/en/user-guide/semantic-views)
- [Snowflake Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)
- [dbt](https://www.getdbt.com/)
- [OpenAI GPT-4](https://openai.com/)
