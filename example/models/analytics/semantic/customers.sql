{{ config(
  materialized='view'
) }}

-- サンプル顧客モデル
-- raw_customersシードデータから顧客情報を取得
SELECT
    customer_id,
    customer_name,
    email,
    total_orders,
    total_revenue,
    created_at::timestamp as created_at
FROM {{ ref('raw_customers') }}
