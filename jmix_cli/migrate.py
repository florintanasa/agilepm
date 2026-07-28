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

import csv
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from jmix_cli.utils import COMPANY, PROIECT_PATH, company_path, ensure_dir, project_name, write_file
from jmix_cli.utils import get_logger
from jmix_cli.entity import get_entities_from_csv, get_relations_from_csv

logger = get_logger("jmix_cli.migrate")


def map_type_to_sql(java_type: str) -> str:
    """Map Java field type to SQL column type for Liquibase."""
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

        # HSQLDB stores schema in .script file under .jmix/hsqldb/
        script_file = Path(".jmix/hsqldb.script")
        if not script_file.exists():
            # Try alternative locations
            script_file = Path(".jmix") / f"{table_upper}.script"
        if not script_file.exists():
            script_file = Path(".jmix") / f"{project_name}.script"
        if not script_file.exists():
            return columns

        try:
            content = script_file.read_text(encoding="utf-8")
            import re
            # Pattern: CREATE TABLE PROJECT (ID UUID, VERSION INT, ...)
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
        """Check which tables exist in HSQLDB schema."""
        tables = set()
        script_file = Path(".jmix/hsqldb.script")
        if not script_file.exists():
            script_file = Path(".jmix") / f"{project_name}.script"
        if script_file.exists():
            try:
                content = script_file.read_text(encoding="utf-8")
                import re
                pattern = r"CREATE TABLE ([A-Z_][A-Z0-9_]*)\s*\("
                matches = re.findall(pattern, content, re.IGNORECASE)
                system_tables = {"USER_", "DATABASECHANGELOG", "DATABASECHANGELOGLOCK"}
                tables = {t for t in matches if t not in system_tables}
            except OSError:
                pass
        return tables


def get_existing_columns_from_changelogs(table_name: str) -> set[str]:
    """Read existing column names from Liquibase changelog files.
    
    Parses all XML changelog files to find columns already defined for the given table.
    Only extracts columns for the specific table, not all tables.
    """
    import re
    existing_columns = set()
    
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
    
    for xml_file in changelog_dir.rglob("*.xml"):
        try:
            content = xml_file.read_text(encoding="utf-8")
            
            # Extract columns only for this specific table
            # Pattern for createTable: <changeSet ...> <createTable tableName="TABLE_NAME"> ... <column name="COL" ...>
            create_table_pattern = rf'<changeSet[^>]*>.*?<createTable\s+tableName="{table_upper}">(.*?)</createTable>'
            
            # Pattern for addColumn: <changeSet ...> <addColumn tableName="TABLE_NAME"> ... <column name="COL" ...>
            add_column_pattern = rf'<addColumn\s+tableName="{table_upper}">(.*?)</addColumn>'
            
            # Extract all matches
            for pattern in [create_table_pattern, add_column_pattern]:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    # Extract column names from the matched section
                    col_pattern = r'column\s+name="([A-Z_][A-Z0-9_]*)"'
                    col_matches = re.findall(col_pattern, match)
                    for col in col_matches:
                        existing_columns.add(col.upper())
                
        except OSError:
            continue
    
    return existing_columns


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter for schema introspection.
    
    For future support - requires psycopg2 or asyncpg.
    """

    def __init__(self, connection_url: str | None = None):
        # Will be implemented when PostgreSQL support is added
        self.connection_url = connection_url

    def get_columns(self, table_name: str) -> set[str]:
        """Query INFORMATION_SCHEMA for table columns."""
        # TODO: Implement with psycopg2/jdbc
        # SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        # WHERE TABLE_NAME = %s AND TABLE_SCHEMA = 'PUBLIC'
        return set()

    def get_table_names(self) -> set[str]:
        """Query INFORMATION_SCHEMA for tables."""
        # TODO: Implement
        return set()


def get_executed_changelog_ids() -> set[str]:
    """Read executed changeset IDs from DATABASECHANGELOG table in HSQLDB."""
    executed = set()
    db_changelog = Path(".jmix/DATABASECHANGELOG")
    
    if db_changelog.exists():
        try:
            # HSQLDB stores entries in a properties-like format
            # Format in .script file: VALUES('id', 'author', 'filename', ...)
            content = db_changelog.read_text(encoding="utf-8")
            import re
            # Match changeset IDs in HSQLDB format
            pattern = r"VALUES\('([^']+)',"
            matches = re.findall(pattern, content)
            executed.update(matches)
        except OSError:
            pass
    
    return executed


def _read_entity_fields(entity_name: str) -> list[dict[str, Any]]:
    """Read entity fields from entities.csv."""
    return get_entities_from_csv("entities.csv", entity_name)


def _read_entity_traits(entity_name: str) -> dict[str, Any]:
    """Read entity traits from traits.csv."""
    from jmix_cli.entity import get_traits_from_csv
    return get_traits_from_csv("traits.csv", entity_name)


def detect_missing_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[dict[str, Any]]:
    """Detect columns that exist in entity but not in database or existing changelogs."""
    table_name = entity_name.upper()
    entity_fields = _read_entity_fields(entity_name)
    
    # Get columns from both database and existing changelogs
    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)
    
    # Combine both sources - if column exists in either, it's not missing
    existing_columns = db_columns | changelog_columns
    
    missing = []
    for field in entity_fields:
        sql_col = field["name"].upper()
        if sql_col not in existing_columns:
            missing.append(field)
    
    return missing


def detect_missing_relations(entity_name: str) -> list[dict[str, Any]]:
    """Check if entity has relations defined but missing changelog entries.
    
    For N:N both-owning, we need to check if inverse relation also has changelog.
    """
    relations_list = get_relations_from_csv("relations.csv", entity_name)
    missing_rels = []
    
    for rel in relations_list:
        rel_type = rel["type"]
        tgt = rel["target"].upper()
        field = rel["field"].upper()
        
        if rel_type == "N:1":
            # Check if FK column exists in changelog
            fk_col = f"{field}_ID"
            if fk_col not in get_existing_columns_from_changelogs(entity_name.upper()):
                missing_rels.append(rel)
        elif rel_type == "N:N":
            ownership = rel.get("ownership", "owning")
            if ownership == "both-owning":
                # Check if table has inverse field
                inv_field_name = entity_name.lower() + ("s" if not entity_name.endswith("s") else "")
                inv_columns = get_existing_columns_from_changelogs(tgt)
                if f"{inv_field_name.upper()}" not in str(inv_columns):
                    missing_rels.append(rel)
    
    return missing_rels


def detect_dropped_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[str]:
    """Detect columns that exist in database but not in entity (soft warning)."""
    table_name = entity_name.upper()
    entity_fields = _read_entity_fields(entity_name)
    db_columns = db_adapter.get_columns(table_name)
    
    entity_columns = {f["name"].upper() for f in entity_fields}
    # Filter out system columns
    system_cols = {"ID", "VERSION", "CREATED_BY", "CREATED_DATE", "LAST_MODIFIED_BY", "LAST_MODIFIED_DATE", "DELETED_BY", "DELETED_DATE"}
    
    dropped = [col for col in db_columns if col not in entity_columns and col not in system_cols]
    return dropped


def gen_add_column_changelog(entity_name: str, fields: list[dict[str, Any]]) -> str:
    """Generate Liquibase changelog for adding columns."""
    table_name = entity_name.upper()
    change_sets = []
    
    for field in fields:
        field_name = field["name"]
        sql_type = map_type_to_sql(field["type"])
        nullable = "false" if field["mandatory"] else "true"
        
        # Unique constraint
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
    import os
    table_name = entity_name.upper()
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


def inject_new_fields_into_existing_entity(entity_name: str, new_fields: list[dict[str, Any]]) -> None:
    """Inject new fields into existing Java entity file."""
    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    
    if not entity_path.exists():
        return
    
    content = entity_path.read_text(encoding="utf-8")
    
    for field in new_fields:
        f_name = field["name"]
        f_type = field["type"]
        
        # Check if field already exists
        if f"private {f_type} {f_name};" in content:
            continue
        
        # Add field
        validation_anno = ""
        if field["mandatory"]:
            validation_anno = "    @NotNull\n"
        
        field_block = f"{validation_anno}    @Column(name = \"{f_name.upper()}\")"
        if field["mandatory"]:
            field_block += ", nullable = false"
        field_block += f")\n    private {f_type} {f_name};\n\n"
        
        # Find insertion point (before getId())
        if "    public UUID getId()" in content:
            content = content.replace(
                "    public UUID getId()",
                f"{field_block}    public UUID getId()"
            )
        
        # Add getter/setter
        f_caps = f_name[0].upper() + f_name[1:]
        getter = f"    public {f_type} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
        setter = f"    public void set{f_caps}({f_type} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
        
        # Insert before closing brace
        last_brace = content.rfind("}")
        if last_brace != -1:
            content = content[:last_brace] + getter + setter + content[last_brace:]
    
    entity_path.write_text(content, encoding="utf-8")
    logger.info(f"✅ Injected new fields into {entity_name}.java")


def migrate_entity(entity_name: str, mode: str = "prompt") -> None:
    """Generate incremental Liquibase migrations for an entity.
    
    Args:
        entity_name: Name of the entity to migrate
        mode: 'prompt' (ask for confirmation on drop), 'force' (apply all), 'dry-run' (no write), 'quiet' (only log on changes)
    """
    db_adapter = HSQLDBAdapter()
    
    # Inject new fields into existing Java entity first
    if missing_fields := detect_missing_columns(entity_name, db_adapter):
        if mode != "quiet":
            logger.info(f"Injecting {len(missing_fields)} new fields into {entity_name}.java...")
        inject_new_fields_into_existing_entity(entity_name, missing_fields)
    
    # Detect dropped columns
    dropped_columns = detect_dropped_columns(entity_name, db_adapter)
    
    table_name = entity_name.upper()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Generate changelog for missing fields
    if missing_fields:
        content = gen_add_column_changelog(entity_name, missing_fields)
        target_dir = (
            PROIECT_PATH
            / "src"
            / "main"
            / "resources"
            / company_path
            / project_name
            / "liquibase"
            / "changelog"
            / datetime.now().strftime("%Y")
            / datetime.now().strftime("%m")
        )
        ensure_dir(str(target_dir))
        filename = target_dir / f"{timestamp}-alter-{table_name}-addField.xml"
        
        if mode != "quiet":
            logger.info(f"Generating incremental migration for {entity_name}: add columns {missing_fields}")
        if mode != "dry-run":
            write_file(filename, content)
            if mode != "quiet":
                logger.info(f"✨ Created incremental changelog: {filename}")
        else:
            logger.info(f"[dry-run] Would create: {filename}")
    
    # Handle dropped columns
    if dropped_columns:
        if mode == "prompt":
            response = input(f"⚠️  Warning: Columns {dropped_columns} will be DROPPED from {table_name} (data loss!). Continue? [y/N]: ")
            if response.lower() != "y":
                logger.info("Skipped dropping columns.")
                return
        
        if mode != "dry-run":
            content = gen_drop_column_changelog(entity_name, dropped_columns)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target_dir = (
                PROIECT_PATH
                / "src"
                / "main"
                / "resources"
                / company_path
                / project_name
                / "liquibase"
                / "changelog"
                / datetime.now().strftime("%Y")
                / datetime.now().strftime("%m")
            )
            ensure_dir(str(target_dir))
            filename = target_dir / f"{timestamp}-alter-{table_name}-dropField.xml"
            
            logger.info(f"Generating incremental migration for {entity_name}: drop columns {dropped_columns}")
            write_file(filename, content)
            logger.info(f"⚠️ Created DROP changelog (data will be lost!): {filename}")


def migrate_all_entities(mode: str = "prompt") -> None:
    """Run migration for all entities defined in entities.csv."""
    from jmix_cli.entity import get_sorted_entities_by_dependency
    
    entities = get_sorted_entities_by_dependency()
    
    if not entities:
        logger.info("[migrate] No entities found in entities.csv")
        return
    
    logger.info(f"[*] Running incremental migration for {len(entities)} entities...")
    
    for entity in entities:
        if entity != "User":  # Skip built-in User for now
            logger.info(f"\n   → Migrating: {entity}")
            migrate_entity(entity, mode)
    
    logger.info("\n✅ Incremental migration completed!")