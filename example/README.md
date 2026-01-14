# サンプルdbtプロジェクト

このディレクトリには、dbt Semantic View Generatorを試すためのサンプルプロジェクトが含まれています。

## 構成

```
example/
├── dbt_project.yml          # dbtプロジェクト設定
├── packages.yml             # dbt_semantic_viewパッケージを含む
├── seeds/
│   └── raw_customers.csv    # サンプルデータ
└── models/
    └── analytics/
        └── semantic/
            ├── customers.sql      # サンプルSQLモデル
            └── customers.yml      # カラム説明
```

## 試してみる

### 1. 依存関係のインストール

```bash
cd example
dbt deps
```

### 2. シードデータのロード

```bash
dbt seed
```

### 3. 顧客モデルのビルド

```bash
dbt run --select customers
```

### 4. セマンティックビューの生成

プロジェクトルートから実行：

```bash
export OPENAI_API_KEY="your-api-key"
python scripts/generate_semantic_view.py
```

### 5. 生成結果の確認

`models/analytics/semantic/semantic_views/customers_semantic_view.sql`が生成されます。

### 6. セマンティックビューのビルド

```bash
cd example
dbt run --select customers_semantic_view
```

## 期待される出力

生成されるセマンティックビューの例：

```sql
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
    COMMENT = '累計注文数',
  model.TOTAL_REVENUE AS TOTAL_REVENUE
    COMMENT = '累計売上金額',
  model.CREATED_AT AS CREATED_AT
    COMMENT = '顧客登録日時'
)

DIMENSIONS (
  model.CUSTOMER_ID AS CUSTOMER_ID
    COMMENT = '顧客ID（主キー）',
  model.CUSTOMER_NAME AS CUSTOMER_NAME
    COMMENT = '顧客名',
  model.EMAIL AS EMAIL
    COMMENT = 'メールアドレス'
)
COMMENT = 'Semantic view for customers model. Enables natural language queries via Cortex Analyst'
```
