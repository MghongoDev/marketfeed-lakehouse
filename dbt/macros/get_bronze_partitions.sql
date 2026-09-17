{% macro get_bronze_partitions(glob_pattern) %}
  {%- call statement('bronze_partitions', fetch_result=True) -%}
    with files as (
        select * from glob('{{ glob_pattern }}')
    )
    select distinct regexp_extract(file, 'ingest_date=([0-9-]+)', 1) as ingest_date
    from files
    where regexp_matches(file, 'ingest_date=([0-9-]+)')
    order by 1
  {%- endcall -%}
  {%- set partitions = load_result('bronze_partitions')['data'] -%}
  {%- set partition_list = [] -%}
  {%- for row in partitions -%}
    {%- do partition_list.append(row[0]) -%}
  {%- endfor -%}
  {{ return(partition_list) }}
{% endmacro %}
