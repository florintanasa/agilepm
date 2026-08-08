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
from jmix_cli.core.project import PROIECT_PATH, company_path, project_name
from jmix_cli.migrate.diff import get_table_name, map_type_to_sql


def gen_add_column_changelog(entity_name: str, fields: list[dict[str, Any]]) -> str:
    """Generate Liquibase changelog for adding columns."""
    table_name = get_table_name(entity_name)
    change_sets = []

    seen_names: set[str] = set()
    unique_fields: list[dict[str, Any]] = []
    for field in fields:
        name_upper = field["name"].upper()
        if name_upper in seen_names:
            continue
        seen_names.add(name_upper)
        unique_fields.append(field)

    for field in unique_fields:
        field_name = field["name"]
        sql_type = map_type_to_sql(field["type"])
        nullable = "false" if field["mandatory"] else "true"

        unique_idx = ""
        if field["unique"]:
            idx_name = f"IDX_{table_name}_UNQ_{field_name.upper()}"
            unique_idx = f"""
    <changeSet id="{entity_name.lower()}-add-idx-{field_name.lower()}" author="{project_name}">
        <createIndex tableName="{table_name}" indexName="{idx_name}" unique="true">
            <column name="{field_name.upper()}"/>
        </createIndex>
    </changeSet>"""

        change_id = f"{entity_name.lower()}-add-{field_name.lower()}"
        change_set = f"""    <changeSet id="{change_id}" author="{project_name}">
        <addColumn tableName="{table_name}">
            <column name="{field_name.upper()}" type="{sql_type}">
                <constraints nullable="{nullable}"/>
            </column>
        </addColumn>
    </changeSet>"""

        change_sets.append(change_set + unique_idx)

    content = f"""<?xml version="1.0" encoding="UTF-8" ?>
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
    return content


def gen_drop_column_changelog(entity_name: str, columns: list[str]) -> str:
    """Generate Liquibase changelog for dropping columns (with warning)."""
    table_name = get_table_name(entity_name)
    change_sets = []

    for col in columns:
        change_id = f"{entity_name.lower()}-drop-{col.lower()}"
        change_set = f"""    <changeSet id="{change_id}" author="{project_name}">
        <dropColumn tableName="{table_name}" columnName="{col}"/>
    </changeSet>"""
        change_sets.append(change_set)

    content = f"""<?xml version="1.0" encoding="UTF-8" ?>
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
    return content


def gen_rename_column_changelog(entity_name: str, renames: list[tuple[str, str]]) -> str | None:
    """Generate Liquibase changelog for renaming columns."""
    if not renames:
        return None

    table_name = get_table_name(entity_name)
    change_sets = []
    for old_name, new_name in renames:
        change_id = f"{entity_name.lower()}-rename-{old_name.lower()}-to-{new_name.lower()}"
        change_sets.append(
            f"""    <changeSet id="{change_id}" author="{project_name}">
        <renameColumn tableName="{table_name}" oldColumnName="{old_name.upper()}" newColumnName="{new_name.upper()}"/>
    </changeSet>"""
        )

    content = f"""<?xml version="1.0" encoding="UTF-8" ?>
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
    return content


def gen_modify_column_changelog(entity_name: str, changes: list[dict[str, Any]]) -> str | None:
    """Generate Liquibase changelog for modifying column type/nullable/unique constraints."""
    if not changes:
        return None

    table_name = get_table_name(entity_name)
    change_sets = []
    for change in changes:
        is_relation = change.get("is_relation", False)
        field_name_lower = change["field_name"].lower() if is_relation else change["name"].lower()
        column_name = change["column_name"] if is_relation else change["name"].upper()
        change_type = change["change"]

        if change_type == "type":
            sql_type = map_type_to_sql(change["new"])
            change_id = f"{entity_name.lower()}-modify-{field_name_lower}-type"
            change_sets.append(
                f"""    <changeSet id="{change_id}" author="{project_name}">
        <modifyDataType tableName="{table_name}" columnName="{column_name}" newDataType="{sql_type}"/>
    </changeSet>"""
            )
        elif change_type == "nullable":
            change_id = f"{entity_name.lower()}-modify-{field_name_lower}-nullable"
            if change["new"]:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <addNotNullConstraint
            tableName="{table_name}"
            columnName="{column_name}"
            constraintName="{table_name}_{column_name}_NOT_NULL"
        />
    </changeSet>"""
                )
            else:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <dropNotNullConstraint
            tableName="{table_name}"
            columnName="{column_name}"
            constraintName="{table_name}_{column_name}_NOT_NULL"
        />
    </changeSet>"""
                )
        elif change_type == "unique":
            change_id = f"{entity_name.lower()}-modify-{field_name_lower}-unique"
            index_name = f"IDX_{table_name}_UNQ_{column_name}"
            if change["new"]:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <createIndex tableName="{table_name}" indexName="{index_name}" unique="true">
            <column name="{column_name}"/>
        </createIndex>
    </changeSet>"""
                )
            else:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <dropIndex indexName="{index_name}" tableName="{table_name}"/>
    </changeSet>"""
                )

    if not change_sets:
        return None

    content = f"""<?xml version="1.0" encoding="UTF-8" ?>
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
    return content
