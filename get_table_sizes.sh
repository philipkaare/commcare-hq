#!/bin/bash

DATABASE=commcarehq

function output_sample_row() {
    table=$1
    echo -e "\n$table Sample\n================"
    psql $DATABASE -Atc "select row_to_json(row) from (select * from $table limit 1) as row" | python -m json.tool
}

output_sample_row form_processor_xforminstancesql
output_sample_row form_processor_commcarecasesql

psql $DATABASE -c "analyze;"
psql $DATABASE -c "vacuum;"

echo -e "\nTable Sizes\n================"
psql $DATABASE -c "copy (SELECT relname AS relation,
    pg_relation_size(C.oid) AS size
  FROM pg_class C
  LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
  WHERE nspname NOT IN ('pg_catalog', 'information_schema') and (nspname = 'public' or C.reltuples > 0)
  ORDER BY relname) to STDOUT with CSV;"

echo -e "\nToast Tables\n================"
psql $DATABASE -c "select t1.relname, pg_relation_size(t1.oid), t1.relpages, t1.reltuples, t2.relname, pg_relation_size(t2.oid), t2.relpages, t2.reltuples
from pg_class t1
inner join pg_class t2
on t1.reltoastrelid = t2.oid
where t1.relkind = 'r'
  and t2.relkind = 't' and t2.relpages > 0;"
