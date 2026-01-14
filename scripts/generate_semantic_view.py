#!/usr/bin/env python3
"""
Semantic View Generator for dbt models

This script analyzes dbt SQL models and their YAML configurations,
then generates Snowflake Semantic Views using OpenAI API.
"""

import os
import re
import yaml
from pathlib import Path
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def parse_sql_file(file_path):
    """Parse SQL file and extract column information."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract final SELECT columns
    select_pattern = r'select\s+(.*?)\s+from\s+.*?(?:left\s+join|inner\s+join|$)'
    matches = re.findall(select_pattern, content, re.IGNORECASE | re.DOTALL)

    columns = []
    if matches:
        # Get the last select (final output)
        final_select = matches[-1]
        # Parse column names
        for line in final_select.split(','):
            line = line.strip()
            # Extract column name (handle aliases)
            if ' as ' in line.lower():
                col_name = line.lower().split(' as ')[-1].strip()
            else:
                col_name = line.split('.')[-1].strip()

            col_name = col_name.replace('"', '').replace("'", '')
            if col_name and not col_name.startswith('--'):
                columns.append(col_name)

    return columns, content

def parse_model_yml(yml_path):
    """Parse model YML file to get column descriptions."""
    if not yml_path.exists():
        return {}

    with open(yml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    column_descriptions = {}
    if config and 'models' in config:
        for model in config['models']:
            if 'columns' in model:
                for column in model['columns']:
                    col_name = column.get('name', '').lower()
                    description = column.get('description', '')
                    if col_name and description:
                        column_descriptions[col_name] = description

    return column_descriptions

def classify_columns_with_gpt(columns, sql_content, source_model_name, column_descriptions=None):
    """Use GPT to classify columns as FACTS or DIMENSIONS."""

    # Build column descriptions section if available
    descriptions_section = ""
    if column_descriptions:
        descriptions_section = "\n\nColumn descriptions from dbt YML:\n"
        for col, desc in column_descriptions.items():
            if col in [c.lower() for c in columns]:
                descriptions_section += f"- {col}: {desc}\n"

    prompt = f"""
You are a data modeling expert. Analyze the following dbt SQL model and classify each column as either a FACT or a DIMENSION for a Snowflake Semantic View.

Guidelines:
- FACTS: Measures, metrics, timestamps, numeric values that change over time, status codes
- DIMENSIONS: Attributes used for grouping/filtering like IDs, names, emails, organizational hierarchies

SQL Content:
```sql
{sql_content}
```

Columns to classify:
{', '.join(columns)}
{descriptions_section}
For each column, provide:
1. Classification (FACT or DIMENSION)
2. A brief comment describing the column (use English for descriptions)
   - Use the dbt YML descriptions above if available
   - Otherwise infer from the SQL content

Also suggest:
- Which columns should be the PRIMARY KEY (typically ID + timestamp)

The source dbt model name is: {source_model_name}

Return your response in this exact JSON format:
{{
  "primary_keys": ["col1", "col2"],
  "columns": {{
    "column_name": {{"type": "FACT/DIMENSION", "comment": "description"}},
    ...
  }}
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a data modeling expert specializing in Snowflake Semantic Views."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    import json
    result = json.loads(response.choices[0].message.content)
    return result

def generate_semantic_view_sql(model_name, classification, ref_model_name):
    """Generate Semantic View SQL based on classification."""
    primary_keys = classification.get('primary_keys', [])
    columns_info = classification.get('columns', {})

    # Build SQL
    sql_parts = []

    # Config
    sql_parts.append("{{ config(")
    sql_parts.append("  materialized = 'semantic_view',")
    sql_parts.append("  copy_grants = true")
    sql_parts.append(") }}")
    sql_parts.append("")

    # TABLES section
    sql_parts.append("TABLES (")
    pk_str = ', '.join([col.upper() for col in primary_keys])
    sql_parts.append(f"  model AS {{{{ ref('{ref_model_name}') }}}}")
    if pk_str:
        sql_parts.append(f"    PRIMARY KEY ({pk_str})")
    sql_parts.append(")")
    sql_parts.append("")

    # FACTS section
    facts = [(col, info) for col, info in columns_info.items() if info['type'] == 'FACT']
    if facts:
        sql_parts.append("FACTS (")
        for i, (col, info) in enumerate(facts):
            comment = info.get('comment', '')
            comma = ',' if i < len(facts) - 1 else ''
            sql_parts.append(f"  model.{col.upper()} AS {col.upper()}")
            sql_parts.append(f"    COMMENT = '{comment}'{comma}")
        sql_parts.append(")")
        sql_parts.append("")

    # DIMENSIONS section
    dimensions = [(col, info) for col, info in columns_info.items() if info['type'] == 'DIMENSION']
    if dimensions:
        sql_parts.append("DIMENSIONS (")
        for i, (col, info) in enumerate(dimensions):
            comment = info.get('comment', '')
            comma = ',' if i < len(dimensions) - 1 else ''
            sql_parts.append(f"  model.{col.upper()} AS {col.upper()}")
            if comment:
                sql_parts.append(f"    COMMENT = '{comment}'{comma}")
            else:
                sql_parts[-1] += comma
        sql_parts.append(")")

    # Overall comment
    sql_parts.append(f"COMMENT = 'Semantic view for {model_name} model. Enables natural language queries via Cortex Analyst'")

    return '\n'.join(sql_parts)

def get_next_version(models_dir, base_name):
    """Find the next available version number for a semantic view."""
    # Check for existing semantic view files with version numbers
    pattern = f"{base_name}_semantic_view*.sql"
    existing_files = list(models_dir.glob(pattern))

    if not existing_files:
        return 1

    # Extract version numbers
    versions = []
    for f in existing_files:
        # Match patterns like: model_semantic_view_v2.sql
        match = re.search(r'_v(\d+)\.sql$', f.name)
        if match:
            versions.append(int(match.group(1)))
        else:
            # If no version number, treat as v1
            versions.append(1)

    return max(versions) + 1 if versions else 1

def process_semantic_directory(semantic_dir):
    """Process a single semantic directory."""
    print(f"\nProcessing semantic directory: {semantic_dir}")

    # Create output directory for semantic views
    output_dir = semantic_dir / 'semantic_views'
    output_dir.mkdir(exist_ok=True)

    # Find SQL files in semantic directory (not in semantic_views subdirectory)
    sql_files = [f for f in semantic_dir.glob('*.sql')
                 if f.parent == semantic_dir]

    if not sql_files:
        print("  No SQL models found in this semantic folder")
        return

    print(f"  Found {len(sql_files)} model(s) to analyze")

    for sql_file in sql_files:
        print(f"  Processing {sql_file.name}...")

        # Parse SQL
        columns, sql_content = parse_sql_file(sql_file)
        print(f"    Found {len(columns)} columns")

        # Get model name for ref()
        model_name = sql_file.stem

        # Check for corresponding YML file
        yml_file = sql_file.with_suffix('.yml')
        column_descriptions = {}
        if yml_file.exists():
            column_descriptions = parse_model_yml(yml_file)
            print(f"    Loaded {len(column_descriptions)} column descriptions from {yml_file.name}")

        # Classify with GPT
        print("    Analyzing with GPT-4...")
        classification = classify_columns_with_gpt(columns, sql_content, model_name, column_descriptions)

        # Generate semantic view
        semantic_view_sql = generate_semantic_view_sql(model_name, classification, model_name)

        # Get next version number
        version = get_next_version(output_dir, model_name)

        # Write semantic view file with version
        if version == 1:
            output_file = output_dir / f"{model_name}_semantic_view.sql"
        else:
            output_file = output_dir / f"{model_name}_semantic_view_v{version}.sql"

        # Check if content has changed (compare with latest version)
        needs_update = True
        if version > 1:
            # Always create new version
            needs_update = True
        elif output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            if existing_content.strip() == semantic_view_sql.strip():
                needs_update = False
                print(f"    Semantic view already up to date")

        if needs_update:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(semantic_view_sql)
            print(f"    Generated {output_file.name}")

def main():
    """Main execution function."""
    print("Scanning for semantic folders in models directory...")

    models_dir = Path('models')

    if not models_dir.exists():
        print(f"Models directory not found: {models_dir}")
        return

    # Find all semantic directories under models/*
    semantic_dirs = list(models_dir.glob('*/semantic'))

    if not semantic_dirs:
        print("No semantic directories found under models/")
        print("Expected structure: models/<project>/semantic/")
        return

    print(f"Found {len(semantic_dirs)} semantic director(ies)")

    # Process each semantic directory
    for semantic_dir in semantic_dirs:
        process_semantic_directory(semantic_dir)

    print("\n=== Semantic view generation complete ===")

if __name__ == "__main__":
    main()
