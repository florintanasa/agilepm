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
import re
from abc import ABC, abstractmethod
from pathlib import Path

from jmix_cli.core.project import PROIECT_PATH, company_path, project_name
from jmix_cli.core.logger import get_logger

logger = get_logger("jmix_cli.migrate")


class DatabaseAdapter(ABC):
    """Abstract adapter for database schema introspection."""

    @abstractmethod
    def get_columns(self, table_name: str) -> set[str]:
        """Return set of column names (uppercase) for the given table."""
        pass

    @abstractmethod
    def get_table_names(self) -> set[str]:
        """Return set of table names (uppercase) in the database."""
        pass


class HSQLDBAdapter(DatabaseAdapter):
    """HSQLDB database adapter for schema introspection."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path(".jmix/")

    def get_columns(self, table_name: str) -> set[str]:
        """Read columns from HSQLDB .script file by parsing CREATE TABLE statements."""
        table_upper = table_name.upper()
        columns = set()

        script_file = Path(".jmix/hsqldb.script")
        if not script_file.exists():
            script_file = Path(".jmix") / f"{table_upper}.script"
        if not script_file.exists():
            script_file = Path(".jmix") / f"{project_name}.script"
        if not script_file.exists():
            return columns

        try:
            content = script_file.read_text(encoding="utf-8")
            pattern = rf"CREATE TABLE {table_upper}\s*\((.*?)\)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                table_def = match.group(1)
                col_pattern = r"([A-Z_][A-Z0-9_]*)\s+"
                col_matches = re.findall(col_pattern, table_def)
                system_cols = {"ID", "VERSION", "CREATED_BY", "CREATED_DATE",
                               "LAST_MODIFIED_BY", "LAST_MODIFIED_DATE", "DELETED_BY", "DELETED_DATE"}
                columns = {col for col in col_matches if col not in system_cols}
        except OSError:
            pass

        return columns

    def get_table_names(self) -> set[str]:
        tables = set()
        script_file = Path(".jmix/hsqldb.script")
        if not script_file.exists():
            script_file = Path(".jmix") / f"{project_name}.script"
        if script_file.exists():
            try:
                content = script_file.read_text(encoding="utf-8")
                pattern = r"CREATE TABLE ([A-Z_][A-Z0-9_]*)\s*\("
                matches = re.findall(pattern, content, re.IGNORECASE)
                system_tables = {"USER_", "DATABASECHANGELOG", "DATABASECHANGELOGLOCK"}
                tables = {t for t in matches if t not in system_tables}
            except OSError:
                pass
        return tables


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter for schema introspection."""

    def __init__(self, connection_url: str | None = None):
        self.connection_url = connection_url

    def get_columns(self, table_name: str) -> set[str]:
        """Query INFORMATION_SCHEMA for table columns."""
        return set()

    def get_table_names(self) -> set[str]:
        """Query INFORMATION_SCHEMA for tables."""
        return set()


def get_existing_columns_from_changelogs(table_name: str) -> set[str]:
    """Read existing column names from Liquibase changelog files.

    Parses all XML changelog files to find columns already defined for the given table.
    Only extracts columns for the specific table, not all tables.
    Processes changelogs in filename order to correctly track add/drop sequence:
    a column that was added, dropped, then re-added will be included.
    """
    existing_columns = set()
    dropped_columns = set()

    changelog_dir = (
        PROIECT_PATH
        / "src"
        / "main"
        / "resources"
        / company_path
        / project_name
        / "liquibase"
        / "changelog"
    )

    if not changelog_dir.exists():
        return existing_columns

    table_upper = table_name.upper()

    xml_files = sorted(changelog_dir.rglob("*.xml"))

    for xml_file in xml_files:
        try:
            content = xml_file.read_text(encoding="utf-8")

            create_table_pattern = rf'<changeSet[^>]*>.*?<createTable\s+tableName="{table_upper}">(.*?)</createTable>'
            add_column_pattern = rf'<addColumn\s+tableName="{table_upper}">(.*?)</addColumn>'
            drop_column_pattern = rf'<dropColumn\s+tableName="{table_upper}"\s+columnName="([^"]+)"'

            for pattern in [create_table_pattern, add_column_pattern]:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    col_pattern = r'column\s+name="([A-Z_][A-Z0-9_]*)"'
                    col_matches = re.findall(col_pattern, match)
                    for col in col_matches:
                        col_upper = col.upper()
                        existing_columns.add(col_upper)
                        dropped_columns.discard(col_upper)

            drop_matches = re.findall(drop_column_pattern, content, re.IGNORECASE)
            for col in drop_matches:
                col_upper = col.upper()
                dropped_columns.add(col_upper)
                existing_columns.discard(col_upper)

        except OSError:
            continue

    return existing_columns


def get_executed_changelog_ids() -> set[str]:
    """Read executed changeset IDs from DATABASECHANGELOG table in HSQLDB."""
    executed = set[str]()
    db_changelog = Path(".jmix/DATABASECHANGELOG")

    if db_changelog.exists():
        try:
            content = db_changelog.read_text(encoding="utf-8")
            pattern = r"VALUES\('([^']+)',"
            matches = re.findall(pattern, content)
            executed.update(matches)
        except OSError:
            pass

    return executed
