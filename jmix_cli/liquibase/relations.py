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
from pathlib import Path
from typing import Any

from jmix_cli.core.files import ensure_dir, write_file
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.logger import get_logger
from jmix_cli.liquibase.base import _stable_changeset_id

logger = get_logger("jmix_cli.liquibase")


def gen_liquibase_relations_changelog(name: str, relations_list: list[dict[str, Any]]) -> None:
    if not relations_list:
        return

    src_table = name.upper()
    src_table_for_join = src_table
    xml_fk_content = ""
    change_sets = []

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
            change_sets.append(
                f"""    <changeSet id="{_stable_changeset_id(name, f"add-fk-{rel['field'].lower()}")}" author="{project_name}">
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
            )
        elif rel["type"] == "1:1" or rel["type"] == "COMPOSITION_1:1":
            f_name = rel["field"].upper()
            col_name = f"{f_name}_ID"
            fk_name = f"FK_{src_table}_ON_{f_name}"
            nullable_val = "false" if rel["mandatory"] else "true"
            stable_change_id = _stable_changeset_id(name, f"add-11-{rel['field'].lower()}")
            if rel["type"] == "COMPOSITION_1:1":
                change_sets.append(
                    f"""    <changeSet id="{stable_change_id}" author="{project_name}">
        <addColumn tableName="{src_table}">
            <column name="{col_name}" type="UUID">
                <constraints nullable="{nullable_val}"/>
            </column>
        </addColumn>
        <createIndex tableName="{src_table}" indexName="IDX_{src_table}_UNQ_{col_name}" unique="true">
            <column name="{col_name}"/>
        </createIndex>
        <addForeignKeyConstraint baseTableName="{src_table}" baseColumnNames="{col_name}"
                                  constraintName="{fk_name}"
                                  referencedTableName="{tgt_table}" referencedColumnNames="ID"/>
    </changeSet>"""
                )
            else:
                change_sets.append(
                    f"""    <changeSet id="{stable_change_id}" author="{project_name}">
        <addColumn tableName="{src_table}">
            <column name="{col_name}" type="UUID">
                <constraints nullable="{nullable_val}"/>
            </column>
        </addColumn>
        <createIndex tableName="{src_table}" indexName="IDX_{src_table}_UNQ_{col_name}" unique="true">
            <column name="{col_name}"/>
        </createIndex>
        <addForeignKeyConstraint baseTableName="{src_table}" baseColumnNames="{col_name}"
                                  constraintName="{fk_name}"
                                  referencedTableName="{tgt_table}" referencedColumnNames="ID"/>
    </changeSet>"""
                )
        elif rel["type"] == "N:N":
            join_table = f"{src_table_for_join}_{tgt_table}_LINK"
            src_fk = f"{src_table_for_join}_ID"
            tgt_fk = f"{tgt_table}_ID"
            change_sets.append(
                f"""    <changeSet id="{_stable_changeset_id(name, f"create-nn-{join_table.lower()}")}" author="{project_name}">
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
            )

    if not change_sets:
        return

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
    filename = f"{target_dir}/{timestamp}-02-relations-{name.lower()}.xml"
    for existing in Path(target_dir).glob(f"*-02-relations-{name.lower()}.xml"):
        if existing.read_text(encoding="utf-8").strip() == xml_content.strip():
            logger.info(f" -> Relations changelog already exists and is up-to-date: {existing}")
            return
    write_file(filename, xml_content)
    logger.info(f" -> Generated Liquibase Relations XML: {filename}")
