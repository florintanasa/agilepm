# -
# Copyright (c) 2026 Florin Tanasă <florin.tanasa@gmail.com>
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# -

import os
from datetime import datetime
from typing import Any

from jmix_cli.core.files import ensure_dir, write_file
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.logger import get_logger

logger = get_logger("jmix_cli.liquibase")


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
        return "DECIMAL"
    return "VARCHAR(255)"


def _stable_changeset_id(name: str, suffix: str) -> str:
    return f"{name.lower()}-{suffix}"


def gen_liquibase_changelog_from_csv(
    name: str, fields_list: list[dict[str, Any]], traits: dict[str, Any]
) -> None:
    table_name = name.upper()
    stable_id = _stable_changeset_id(name, "base")

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
    change_sets = []

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
            change_sets.append(
                f"""    <changeSet id="{_stable_changeset_id(name, f"idx-{field['name'].lower()}")}" author="{project_name}">
        <createIndex tableName="{table_name}" indexName="{index_name}" unique="true">
            <column name="{sql_col_name}"/>
        </createIndex>
    </changeSet>"""
            )

    change_sets.insert(
        0,
        f"""    <changeSet id="{stable_id}-1" author="{project_name}">
        <createTable tableName="{table_name}">
{xml_traits_columns}{xml_business_columns}        </createTable>
    </changeSet>""",
    )

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
	xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
	objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
{os.linesep.join(change_sets)}
</databaseChangeLog>
"""

    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%m")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = (
        str(PROIECT_PATH)
        + f"/src/main/resources/{company_path}/{project_name}/liquibase/changelog/{current_year}/{current_month}"
    )
    ensure_dir(target_dir)
    filename = f"{target_dir}/{timestamp}-01-base-{name.lower()}.xml"
    write_file(filename, xml_content)
    logger.info(f" -> Generated Liquibase XML with Constraints & Indexes: {filename}")
