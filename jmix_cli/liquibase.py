import csv
import os
from datetime import datetime
from typing import Any

from jmix_cli.utils import COMPANY, PROIECT_PATH, company_path, ensure_dir, project_name, write_file


def map_type(java_type: str) -> str:
    jt = java_type.lower()
    if jt in ["string", "text"]:
        return "VARCHAR(255)"
    if jt in ["integer", "int"]:
        return "INT"
    if jt in ["long"]:
        return "BIGINT"
    if jt in ["boolean", "bool"]:
        return "BOOLEAN"
    if jt in ["date", "localdate"]:
        return "date"
    if jt in ["datetime", "localdatetime", "offsetdatetime"]:
        return "timestamp with time zone"
    if jt in ["uuid"]:
        return "UUID"
    if jt in ["double"]:
        return "double precision"
    if jt in ["bigdecimal"]:
        return "NUMERIC(19, 2)"
    return "VARCHAR(255)"


def gen_liquibase_changelog_from_csv(
    name: str, fields_list: list[dict[str, Any]], traits: dict[str, Any]
) -> None:
    timestamp_id = datetime.now().strftime("%Y%m%d%H%M%S")
    table_name = name.upper()

    xml_traits_columns = '            <column name="ID" type="UUID">\n'
    xml_traits_columns += f'                <constraints nullable="false" primaryKey="true" primaryKeyName="PK_{table_name}"/>\n'
    xml_traits_columns += "            </column>\n"

    if traits["versioned"]:
        xml_traits_columns += '            <column name="VERSION" type="INT">\n                <constraints nullable="false" />\n            </column>\n'
    if traits["audit_of_creation"]:
        xml_traits_columns += '            <column name="CREATED_BY" type="VARCHAR(255)" />\n'
        xml_traits_columns += '            <column name="CREATED_DATE" type="timestamp with time zone" />\n'
    if traits["audit_of_modification"]:
        xml_traits_columns += '            <column name="LAST_MODIFIED_BY" type="VARCHAR(255)" />\n'
        xml_traits_columns += '            <column name="LAST_MODIFIED_DATE" type="timestamp with time zone" />\n'
    if traits["soft_delete"]:
        xml_traits_columns += '            <column name="DELETED_BY" type="VARCHAR(255)" />\n'
        xml_traits_columns += '            <column name="DELETED_DATE" type="timestamp with time zone" />\n'

    xml_business_columns = ""
    xml_indexes = ""

    for field in fields_list:
        sql_col_name = field["name"].upper()
        sql_type = map_type(field["type"])
        constraints = ""
        if field["mandatory"]:
            constraints = '                <constraints nullable="false" />\n'
        if constraints:
            xml_business_columns += f'            <column name="{sql_col_name}" type="{sql_type}">\n{constraints}            </column>\n'
        else:
            xml_business_columns += (
                f'            <column name="{sql_col_name}" type="{sql_type}" />\n'
            )
        if field["unique"]:
            index_name = f"IDX_{table_name}_UNQ_{sql_col_name}"
            xml_indexes += f"""
    <changeSet id="{timestamp_id}-idx-{field["name"].lower()}" author="{project_name}">
        <createIndex tableName="{table_name}" indexName="{index_name}" unique="true">
            <column name="{sql_col_name}"/>
        </createIndex>
    </changeSet>"""

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
	xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
	objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
    <changeSet id="{timestamp_id}-1" author="{project_name}">
        <createTable tableName="{table_name}">
{xml_traits_columns}{xml_business_columns}        </createTable>
    </changeSet>{xml_indexes}
</databaseChangeLog>
"""

    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%m")
    target_dir = (
        PROIECT_PATH
        + f"/src/main/resources/{company_path}/{project_name}/liquibase/changelog/{current_year}/{current_month}"
    )
    ensure_dir(target_dir)
    filename = f"{target_dir}/{timestamp_id}-01_base-{name.lower()}.xml"
    write_file(filename, xml_content)
    print(f" -> Generated Liquibase XML with Constraints & Indexes: {filename}")


def gen_liquibase_relations_changelog(name: str, relations_list: list[dict[str, Any]]) -> None:
    if not relations_list:
        return

    timestamp_id = datetime.now().strftime("%Y%m%d%H%M%S")
    src_table = name.upper()
    xml_fk_content = ""

    for rel in relations_list:
        tgt_table = rel["target"].upper()
        if tgt_table == "USER":
            tgt_table = "USER_"
        if src_table == "USER":
            src_table = "USER_"
        if rel["type"] == "N:1":
            f_name = rel["field"].upper()
            col_name = f"{f_name}_ID"
            fk_name = f"FK_{src_table}_ON_{f_name}"
            nullable_val = "false" if rel["mandatory"] else "true"
            xml_fk_content += f"""
    <changeSet id="{timestamp_id}-add-fk-{rel["field"].lower()}" author="{project_name}">
        <addColumn tableName="{src_table}">
            <column name="{col_name}" type="UUID">
                <constraints nullable="{nullable_val}"/>
            </column>
        </addColumn>
        <addForeignKeyConstraint baseTableName="{src_table}"
                                  baseColumnNames="{col_name}"
                                  constraintName="{fk_name}"
                                  referencedTableName="{tgt_table}"
                                  referencedColumnNames="ID"/>
    </changeSet>"""
        elif rel["type"] == "1:1" or rel["type"] == "COMPOSITION_1:1":
            f_name = rel["field"].upper()
            col_name = f"{f_name}_ID"
            fk_name = f"FK_{src_table}_ON_{f_name}"
            nullable_val = "false" if rel["mandatory"] else "true"
            if rel["type"] == "COMPOSITION_1:1":
                xml_fk_content += f"""
    <changeSet id="{timestamp_id}-add-11-{rel["field"].lower()}" author="{project_name}">
        <addColumn tableName="{src_table}">
            <column name="{col_name}" type="UUID">
                <constraints nullable="{nullable_val}"/>
            </column>
        </addColumn>
        <createIndex tableName="{src_table}" indexName="IDX_{src_table}_UNQ_{col_name}" unique="true">
            <column name="{col_name}"/>
        </createIndex>
    </changeSet>"""
            else:
                xml_fk_content += f"""
    <changeSet id="{timestamp_id}-add-11-{rel["field"].lower()}" author="{project_name}">
        <addColumn tableName="{src_table}">
            <column name="{col_name}" type="UUID">
                <constraints nullable="{nullable_val}"/>
            </column>
        </addColumn>
        <createIndex tableName="{src_table}" indexName="IDX_{src_table}_UNQ_{col_name}" unique="true">
            <column name="{col_name}"/>
        </createIndex>
        <addForeignKeyConstraint baseTableName="{src_table}"
                                  baseColumnNames="{col_name}"
                                  constraintName="{fk_name}"
                                  referencedTableName="{tgt_table}"
                                  referencedColumnNames="ID"/>
    </changeSet>"""
        elif rel["type"] == "N:N":
            join_table = f"{src_table}_{tgt_table}_LINK"
            src_fk = f"{src_table}_ID"
            tgt_fk = f"{tgt_table}_ID"
            xml_fk_content += f"""
    <changeSet id="{timestamp_id}-create-nn-{join_table.lower()}" author="{project_name}">
        <createTable tableName="{join_table}">
            <column name="{src_fk}" type="UUID">
                <constraints nullable="false"/>
            </column>
            <column name="{tgt_fk}" type="UUID">
                <constraints nullable="false"/>
            </column>
        </createTable>
        <addPrimaryKey tableName="{join_table}" columnNames="{src_fk}, {tgt_fk}" constraintName="PK_{join_table}"/>
        <addForeignKeyConstraint baseTableName="{join_table}" baseColumnNames="{src_fk}"
                                  constraintName="FK_{join_table}_ON_{src_table}"
                                  referencedTableName="{src_table}" referencedColumnNames="ID"/>
        <addForeignKeyConstraint baseTableName="{join_table}" baseColumnNames="{tgt_fk}"
                                  constraintName="FK_{join_table}_ON_{tgt_table}"
                                  referencedTableName="{tgt_table}" referencedColumnNames="ID"/>
    </changeSet>"""

    if not xml_fk_content:
        return

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
	xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
	objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
{xml_fk_content}
</databaseChangeLog>
"""

    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%m")
    target_dir = (
        PROIECT_PATH
        + f"/src/main/resources/{company_path}/{project_name}/liquibase/changelog/{current_year}/{current_month}"
    )
    ensure_dir(target_dir)
    filename = f"{target_dir}/{timestamp_id}-02-relations_{name.lower()}.xml"
    write_file(filename, xml_content)
    print(f" -> Generated Liquibase Relations XML: {filename}")
