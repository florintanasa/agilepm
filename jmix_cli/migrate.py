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
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from jmix_cli.utils import COMPANY, PROIECT_PATH, company_path, ensure_dir, project_name, write_file
from jmix_cli.utils import get_logger
from jmix_cli.entity import get_entities_from_csv, get_relations_from_csv

logger = get_logger("jmix_cli.migrate")


def get_table_name(entity_name: str) -> str:
    """Get the database table name for an entity.

    User entity uses USER_ table (Jmix convention).
    """
    return "USER_" if entity_name == "User" else entity_name.upper()


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
    Processes changelogs in filename order to correctly track add/drop sequence:
    a column that was added, dropped, then re-added will be included.
    """
    import re
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
    
    # Process files in sorted order to respect add/drop sequence
    xml_files = sorted(changelog_dir.rglob("*.xml"))
    
    for xml_file in xml_files:
        try:
            content = xml_file.read_text(encoding="utf-8")
            
            # Extract columns only for this specific table
            # Pattern for createTable: <changeSet ...> <createTable tableName="TABLE_NAME"> ... <column name="COL" ...>
            create_table_pattern = rf'<changeSet[^>]*>.*?<createTable\s+tableName="{table_upper}">(.*?)</createTable>'
            
            # Pattern for addColumn: <changeSet ...> <addColumn tableName="TABLE_NAME"> ... <column name="COL" ...>
            add_column_pattern = rf'<addColumn\s+tableName="{table_upper}">(.*?)</addColumn>'
            
            # Pattern for dropColumn: <dropColumn tableName="TABLE_NAME" columnName="COL"/>
            drop_column_pattern = rf'<dropColumn\s+tableName="{table_upper}"\s+columnName="([^"]+)"'
            
            # Extract all matches
            for pattern in [create_table_pattern, add_column_pattern]:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    # Extract column names from the matched section
                    col_pattern = r'column\s+name="([A-Z_][A-Z0-9_]*)"'
                    col_matches = re.findall(col_pattern, match)
                    for col in col_matches:
                        col_upper = col.upper()
                        existing_columns.add(col_upper)
                        # If this column was previously dropped, it's now re-added
                        dropped_columns.discard(col_upper)
            
            # Collect dropped columns
            drop_matches = re.findall(drop_column_pattern, content, re.IGNORECASE)
            for col in drop_matches:
                col_upper = col.upper()
                dropped_columns.add(col_upper)
                # Remove from existing if it was added before
                existing_columns.discard(col_upper)
                
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


def _read_all_relations() -> list[dict[str, Any]]:
    """Read all relations from relations.csv with full source/target info.

    Unlike get_relations_from_csv (which filters by source entity), this
    returns every row so callers can also check relations where the entity
    is the *target*.
    """
    relations_list: list[dict[str, Any]] = []
    csv_file = Path("relations.csv")
    if not csv_file.exists():
        return relations_list
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel_dict: dict[str, Any] = {
                "source": row["source_entity"].strip(),
                "type": row["relation_type"].strip(),
                "target": row["target_entity"].strip(),
                "field": row["field_name"].strip(),
                "mandatory": row["mandatory"].strip().lower() == "true",
            }
            if "ownership" in (reader.fieldnames or []):
                rel_dict["ownership"] = row.get("ownership", "").strip()
            relations_list.append(rel_dict)
    return relations_list


def _get_relation_field_names(entity_name: str) -> set[str]:
    """Get field names from relations.csv for the given entity (as source or target).

    For N:1, 1:1 relations: the forward field is on the *source* entity.
    For COMPOSITION_1:1: ``_finalize_composition_relationships`` injects the
    forward field (``{field}``, type = target) into the *source* entity, and
    ``_inject_composition_into_parent`` may inject the inverse field
    (``{source_entity_camelCase}``) into the *source* entity.  When the entity
    is the *target* of a COMPOSITION_1:1, the forward field and/or the inverse
    field may also be present (from previous ``build-all`` runs), so both are
    excluded here as well.
    List<T> fields (COMPOSITION_1:N, N:N) are excluded since they are already
    skipped by _get_fields_from_existing_java.
    """
    from jmix_cli.entity import get_relations_from_csv
    relations = get_relations_from_csv("relations.csv", entity_name)
    field_names: set[str] = set()
    for rel in relations:
        rel_type = rel["type"]
        field = rel["field"]
        if rel_type in ("N:1", "1:1"):
            field_names.add(field.upper())
        elif rel_type == "COMPOSITION_1:1":
            # Forward field injected by _finalize_composition_relationships
            field_names.add(field.upper())
            # Inverse field injected by _inject_composition_into_parent
            inv_field = entity_name[0].lower() + entity_name[1:]
            field_names.add(inv_field.upper())
        # COMPOSITION_1:N and N:N generate List<T> fields, already skipped

    # Also check relations where entity is the TARGET of COMPOSITION_1:1
    for rel in _read_all_relations():
        if rel["target"].upper() != entity_name.upper():
            continue
        if rel["type"] == "COMPOSITION_1:1":
            # Forward field on target (if present from previous builds)
            field_names.add(rel["field"].upper())
            # Inverse field on target (if present from previous builds)
            inv_field = rel["source"][0].lower() + rel["source"][1:]
            field_names.add(inv_field.upper())

    return field_names


def _get_relation_column_names(entity_name: str) -> set[str]:
    """Get FK column names from relations.csv for the given entity (as source).

    For N:1, 1:1, and COMPOSITION_1:1 relations where the entity is the
    *source*: ``_finalize_composition_relationships`` injects
    ``@JoinColumn(name = "{field}_ID")`` into the source entity, so the FK
    column ``{field}_ID`` lives on the source entity's table.

    When the entity is the *target* of a COMPOSITION_1:1, the FK column is on
    the *source* entity's table, so nothing is added for the target.
    """
    from jmix_cli.entity import get_relations_from_csv
    relations = get_relations_from_csv("relations.csv", entity_name)
    column_names: set[str] = set()
    for rel in relations:
        rel_type = rel["type"]
        field = rel["field"].upper()
        if rel_type in ("N:1", "1:1", "COMPOSITION_1:1"):
            column_names.add(f"{field}_ID")
    return column_names


def detect_missing_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[dict[str, Any]]:
    """Detect columns that exist in entity but not in database or existing changelogs."""
    table_name = get_table_name(entity_name)
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


def _get_unique_columns_from_java(content: str) -> set[str]:
    """Extract column names that have a unique constraint from the @Table annotation.

    Parses @Index entries with unique=true and returns the column names
    (uppercased) from their columnList attribute.
    """
    unique_columns: set[str] = set()
    for match in re.finditer(r'@Index\s*\(([^)]*)\)', content, re.DOTALL):
        index_body = match.group(1)
        if re.search(r'unique\s*=\s*true', index_body):
            col_match = re.search(r'columnList\s*=\s*"([^"]+)"', index_body)
            if col_match:
                for col in col_match.group(1).split(','):
                    unique_columns.add(col.strip().upper())
    return unique_columns


def _get_fields_from_existing_java(entity_name: str) -> list[dict[str, Any]]:
    """Extract business field metadata from an existing Java entity file."""
    entity_path = (
        PROIECT_PATH
        / "src"
        / "main"
        / "java"
        / company_path
        / project_name
        / "entity"
        / f"{entity_name}.java"
    )
    fields: list[dict[str, Any]] = []
    if not entity_path.exists():
        return fields

    content = entity_path.read_text(encoding="utf-8")
    unique_columns = _get_unique_columns_from_java(content)
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("private "):
            continue
        if "<" in stripped:
            continue

        declaration = stripped.strip(";")
        parts = declaration.split()
        if len(parts) >= 2:
            f_type = parts[1]
            f_name = parts[2].strip(";")
            # Skip system/audit fields that are not defined in entities.csv
            if f_name in (
                "id", "version", "createdBy", "createdDate",
                "lastModifiedBy", "lastModifiedDate",
                "deletedBy", "deletedDate",
            ):
                continue
            # Find the block between the previous field declaration and this one
            block_start = idx - 1
            while block_start >= 0 and not lines[block_start].strip().startswith("private "):
                block_start -= 1
            block_start += 1
            block = "\n".join(lines[block_start:idx])
            mandatory = "@NotNull" in block
            fields.append(
                {
                    "name": f_name,
                    "type": f_type,
                    "mandatory": mandatory,
                    "unique": f_name.upper() in unique_columns,
                }
            )

    return fields


def _names_are_similar(name1: str, name2: str) -> bool:
    """Check if two field names are similar enough to be considered a rename.

    Uses common prefix length as a heuristic — fields must share at least
    3 characters in a common prefix to be considered a rename. This prevents
    false-positive renames between unrelated fields of the same type
    (e.g. companyName -> address).
    """
    if not name1 or not name2:
        return False
    min_len = min(len(name1), len(name2))
    common_prefix_len = 0
    for i in range(min_len):
        if name1[i].lower() == name2[i].lower():
            common_prefix_len += 1
        else:
            break
    return common_prefix_len >= 3


def detect_changed_fields(entity_name: str) -> tuple[list[dict[str, Any]], list[str], list[tuple[str, str]]]:
    """Detect dropped, added, and renamed fields for an entity.

    Returns:
        added_fields: fields in entities.csv but missing from existing Java
        dropped_fields: fields in existing Java but missing from entities.csv
        renamed_fields: list of (old_name, new_name) where a likely rename was detected
    """
    csv_fields = _read_entity_fields(entity_name)
    csv_by_name = {f["name"].upper(): f for f in csv_fields}
    java_fields = _get_fields_from_existing_java(entity_name)
    java_by_name = {f["name"].upper(): f for f in java_fields}

    # Exclude relation fields (N:1, 1:1, COMPOSITION_1:1) from dropped detection
    # since they are defined in relations.csv, not entities.csv
    relation_field_names = _get_relation_field_names(entity_name)

    dropped = []
    for f in java_fields:
        if f["name"].upper() not in csv_by_name and f["name"].upper() not in relation_field_names:
            dropped.append(f["name"])

    added = []
    for f in csv_fields:
        if f["name"].upper() not in java_by_name:
            added.append(f)

    renamed: list[tuple[str, str]] = []
    unmatched_dropped = []
    unmatched_added = []
    for dropped_name in dropped:
        match = None
        for added_field in added:
            if added_field["type"] == next(
                (f["type"] for f in java_fields if f["name"].upper() == dropped_name.upper()),
                None,
            ) and _names_are_similar(dropped_name, added_field["name"]):
                match = added_field
                break
        if match:
            renamed.append((dropped_name, match["name"]))
        else:
            unmatched_dropped.append(dropped_name)

    unmatched_added = [f["name"] for f in added if f["name"].upper() not in [n.upper() for _, n in renamed]]

    return unmatched_added, unmatched_dropped, renamed


def detect_field_metadata_changes(entity_name: str) -> list[dict[str, Any]]:
    """Detect type/mandatory/unique changes for existing fields."""
    csv_fields = _read_entity_fields(entity_name)
    java_fields = _get_fields_from_existing_java(entity_name)
    java_by_name = {f["name"].upper(): f for f in java_fields}

    changes: list[dict[str, Any]] = []
    for csv_field in csv_fields:
        upper_name = csv_field["name"].upper()
        if upper_name not in java_by_name:
            continue
        java_field = java_by_name[upper_name]
        if csv_field["type"] != java_field["type"]:
            changes.append(
                {
                    "name": csv_field["name"],
                    "change": "type",
                    "old": java_field["type"],
                    "new": csv_field["type"],
                }
            )
        if csv_field["mandatory"] != java_field["mandatory"]:
            changes.append(
                {
                    "name": csv_field["name"],
                    "change": "nullable",
                    "old": java_field["mandatory"],
                    "new": csv_field["mandatory"],
                }
            )
        if csv_field["unique"] != java_field["unique"]:
            changes.append(
                {
                    "name": csv_field["name"],
                    "change": "unique",
                    "old": java_field["unique"],
                    "new": csv_field["unique"],
                }
            )
    return changes


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
        field_name = change["name"].upper()
        change_type = change["change"]

        if change_type == "type":
            sql_type = map_type_to_sql(change["new"])
            change_id = f"{entity_name.lower()}-modify-{change['name'].lower()}-type"
            change_sets.append(
                f"""    <changeSet id="{change_id}" author="{project_name}">
        <modifyDataType tableName="{table_name}" columnName="{change['name']}" newDataType="{sql_type}"/>
    </changeSet>"""
            )
        elif change_type == "nullable":
            change_id = f"{entity_name.lower()}-modify-{change['name'].lower()}-nullable"
            if change["new"]:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <dropNullableConstraint
            tableName="{table_name}"
            columnName="{change['name']}"
            constraintName="{table_name}_{change['name'].upper()}_NOT_NULL"
        />
    </changeSet>"""
                )
            else:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <addNotNullConstraint
            tableName="{table_name}"
            columnName="{change['name']}"
            constraintName="{table_name}_{change['name'].upper()}_NOT_NULL"
        />
    </changeSet>"""
                )
        elif change_type == "unique":
            change_id = f"{entity_name.lower()}-modify-{change['name'].lower()}-unique"
            if change["new"]:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <addUniqueConstraint
            tableName="{table_name}"
            columnNames="{change['name'].upper()}"
            constraintName="{table_name}_{change['name'].upper()}_UNQ"
        />
    </changeSet>"""
                )
            else:
                change_sets.append(
                    f"""    <changeSet id="{change_id}" author="{project_name}">
        <dropUniqueConstraint
            tableName="{table_name}"
            constraintName="{table_name}_{change['name'].upper()}_UNQ"
        />
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


def _get_already_dropped_columns(table_name: str) -> set[str]:
    """Get columns that have already been dropped by previous drop changelogs.

    Parses all changelog XML files for dropColumn changesets targeting the
    given table, so we don't repeatedly try to drop the same column.
    """
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
    dropped: set[str] = set()
    if not changelog_dir.exists():
        return dropped

    for xml_file in changelog_dir.rglob("*.xml"):
        try:
            content = xml_file.read_text(encoding="utf-8")
        except OSError:
            continue
        # Look for dropColumn changesets targeting this table
        if f"tableName=\"{table_name}\"" not in content:
            continue
        # Extract columnName from dropColumn entries
        import re
        for match in re.finditer(
            r'<dropColumn[^>]*tableName="' + re.escape(table_name) + r'"[^>]*>',
            content,
        ):
            tag = match.group(0)
            col_match = re.search(r'columnName="([^"]+)"', tag)
            if col_match:
                dropped.add(col_match.group(1).upper())
    return dropped


def detect_dropped_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[str]:
    """Detect columns that exist in database/changelogs but not in entity (soft warning)."""
    table_name = get_table_name(entity_name)
    entity_fields = _read_entity_fields(entity_name)
    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)

    entity_columns = {f["name"].upper() for f in entity_fields}
    # Filter out system columns
    system_cols = {"ID", "VERSION", "CREATED_BY", "CREATED_DATE", "LAST_MODIFIED_BY", "LAST_MODIFIED_DATE", "DELETED_BY", "DELETED_DATE"}
    # Filter out relation FK columns (N:1, 1:1, COMPOSITION_1:1)
    relation_cols = _get_relation_column_names(entity_name)

    # Exclude columns already dropped by previous drop changelogs
    already_dropped = _get_already_dropped_columns(table_name)

    # Combine DB columns and changelog columns for comprehensive detection
    all_existing = db_columns | changelog_columns
    dropped = [
        col for col in all_existing
        if col not in entity_columns
        and col not in system_cols
        and col not in relation_cols
        and col not in already_dropped
    ]
    return dropped


def gen_add_column_changelog(entity_name: str, fields: list[dict[str, Any]]) -> str:
    """Generate Liquibase changelog for adding columns."""
    table_name = get_table_name(entity_name)
    change_sets = []
    
    # Deduplicate fields by name (case-insensitive) to prevent duplicate changesets
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
        
        # Build field with correct syntax
        if field["mandatory"]:
            column_annotation = f'    @Column(name = "{f_name.upper()}", nullable = false)\n'
        else:
            column_annotation = f'    @Column(name = "{f_name.upper()}")\n'
        field_declaration = f"    private {f_type} {f_name};\n\n"
        
        field_block = f"{validation_anno}{column_annotation}{field_declaration}"
        
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


def _remove_fields_from_java(entity_name: str, fields_to_remove: list[str]) -> None:
    """Remove fields, getters, and setters from an existing Java entity file."""
    entity_path = (
        PROIECT_PATH
        / "src"
        / "main"
        / "java"
        / company_path
        / project_name
        / "entity"
        / f"{entity_name}.java"
    )
    if not entity_path.exists():
        return

    content = entity_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for field_name in fields_to_remove:
        # Find the field type from the Java entity (case-insensitive match)
        field_type = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("private ") and f" {field_name};" in stripped.lower():
                parts = stripped.replace(";", "").split()
                if len(parts) >= 3:
                    field_type = parts[1]
                break

        if field_type is None:
            continue

        # Find the actual field name as it appears in Java (camelCase)
        actual_field_name = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("private ") and f" {field_name};" in stripped.lower():
                parts = stripped.replace(";", "").split()
                if len(parts) >= 3:
                    actual_field_name = parts[2]
                break

        if actual_field_name is None:
            continue

        caps = actual_field_name[0].upper() + actual_field_name[1:]

        # Remove field declaration and preceding annotations
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("private ") and f" {field_name};" in stripped.lower():
                # Remove preceding annotation lines
                while new_lines and new_lines[-1].strip().startswith("@"):
                    new_lines.pop()
                # Also remove preceding blank line if present
                if new_lines and new_lines[-1].strip() == "":
                    new_lines.pop()
                continue
            new_lines.append(line)
        lines = new_lines

        # Remove getter and setter using string replacement
        content = "\n".join(lines)

        # Remove getter
        getter = f"    public {field_type} get{caps}() {{\n        return {actual_field_name};\n    }}\n\n"
        content = content.replace(getter, "")

        # Remove setter
        setter = f"    public void set{caps}({field_type} {actual_field_name}) {{\n        this.{actual_field_name} = {actual_field_name};\n    }}\n\n"
        content = content.replace(setter, "")

        lines = content.splitlines()

    entity_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"✅ Removed dropped fields from {entity_name}.java: {fields_to_remove}")


def migrate_entity(entity_name: str, mode: str = "prompt") -> None:
    """Generate incremental Liquibase migrations for an entity.
    
    Args:
        entity_name: Name of the entity to migrate
        mode: 'prompt' (ask for confirmation on drop), 'force' (apply all), 'dry-run' (no write), 'quiet' (only log on changes)
    """
    from jmix_cli.i18n import update_messages_entity
    
    db_adapter = HSQLDBAdapter()
    
    # Detect added, dropped, and renamed fields BEFORE injecting anything.
    # This is critical: if we inject new fields first, rename detection
    # won't work because the new field will already be in the Java file.
    added_fields, dropped_from_csv, renamed_fields = detect_changed_fields(entity_name)
    metadata_changes = detect_field_metadata_changes(entity_name)
    
    # Build sets of renamed field names for exclusion
    renamed_old_names = {old for old, _ in renamed_fields}
    renamed_new_names = {new for _, new in renamed_fields}
    
    # Detect missing columns from DB/changelogs (excluding renamed fields)
    all_missing = detect_missing_columns(entity_name, db_adapter)
    missing_fields = [f for f in all_missing if f["name"] not in renamed_new_names]
    
    table_name = get_table_name(entity_name)
    
    # Exclude added_fields that are already in changelogs as addColumn
    # (prevents re-adding fields that were added, dropped, and re-added)
    changelog_cols = get_existing_columns_from_changelogs(table_name)
    added_fields = [
        name for name in added_fields
        if name.upper() not in changelog_cols
    ]
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Handle renamed fields: update Java entity in-place
    if renamed_fields:
        entity_path = (
            PROIECT_PATH
            / "src"
            / "main"
            / "java"
            / company_path
            / project_name
            / "entity"
            / f"{entity_name}.java"
        )
        if entity_path.exists():
            java_content = entity_path.read_text(encoding="utf-8")
            csv_fields = _read_entity_fields(entity_name)
            for old_name, new_name in renamed_fields:
                field_type = next(f["type"] for f in csv_fields if f["name"] == new_name)
                old_caps = old_name[0].upper() + old_name[1:]
                new_caps = new_name[0].upper() + new_name[1:]
                # Rename field declaration
                java_content = java_content.replace(
                    f"private {field_type} {old_name};",
                    f"private {field_type} {new_name};",
                )
                # Rename getter return statement
                java_content = java_content.replace(
                    f"return {old_name};",
                    f"return {new_name};",
                )
                # Rename getter method name
                java_content = java_content.replace(
                    f"public {field_type} get{old_caps}()",
                    f"public {field_type} get{new_caps}()",
                )
                # Rename setter method name and parameter
                java_content = java_content.replace(
                    f"public void set{old_caps}({field_type} {old_name})",
                    f"public void set{new_caps}({field_type} {new_name})",
                )
                # Rename setter body (both this.field and parameter)
                java_content = java_content.replace(
                    f"this.{old_name} = {old_name};",
                    f"this.{new_name} = {new_name};",
                )
                # Rename any remaining this.field references
                java_content = java_content.replace(
                    f"this.{old_name}",
                    f"this.{new_name}",
                )
                entity_path.write_text(java_content, encoding="utf-8")
                logger.info(f"✅ Renamed field in Java: {old_name} -> {new_name}")
    
    # Inject new fields (excluding renamed ones)
    if missing_fields:
        if mode != "quiet":
            logger.info(f"Injecting {len(missing_fields)} new fields into {entity_name}.java...")
        inject_new_fields_into_existing_entity(entity_name, missing_fields)
        
        # Update messages for new fields
        if mode != "dry-run" and mode != "quiet":
            new_field_names = [f["name"] for f in missing_fields]
            update_messages_entity(str(PROIECT_PATH), f"{COMPANY}.{project_name}", entity_name, new_field_names, [])
    
    # Also inject fields that are in CSV + changelog but missing from Java
    # (e.g., field was added, dropped, and re-added to CSV)
    csv_fields = _read_entity_fields(entity_name)
    java_fields = _get_fields_from_existing_java(entity_name)
    java_field_names = {f["name"].upper() for f in java_fields}
    re_added_fields = [
        f for f in csv_fields
        if f["name"].upper() not in java_field_names
        and f["name"].upper() in changelog_cols
    ]
    if re_added_fields:
        if mode != "quiet":
            logger.info(f"Injecting {len(re_added_fields)} re-added fields into {entity_name}.java...")
        inject_new_fields_into_existing_entity(entity_name, re_added_fields)
        
        if mode != "dry-run" and mode != "quiet":
            new_field_names = [f["name"] for f in re_added_fields]
            update_messages_entity(str(PROIECT_PATH), f"{COMPANY}.{project_name}", entity_name, new_field_names, [])
    
    # Detect dropped columns from DB
    dropped_columns = detect_dropped_columns(entity_name, db_adapter)
    
    # Generate changelog for missing/added fields
    # Convert added_fields (list of names) to dicts for changelog generation
    csv_fields_by_name = {f["name"].lower(): f for f in _read_entity_fields(entity_name)}
    added_field_dicts = [
        csv_fields_by_name[name.lower()]
        for name in added_fields
        if name.lower() in csv_fields_by_name
    ]
    
    if missing_fields or added_field_dicts:
        new_fields = missing_fields + added_field_dicts
        # Deduplicate by field name (case-insensitive) to prevent duplicate changelogs
        seen_names: set[str] = set()
        new_fields = [
            f for f in new_fields
            if f["name"].upper() not in seen_names
            and not seen_names.add(f["name"].upper())
        ]
        content = gen_add_column_changelog(entity_name, new_fields)
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
            logger.info(f"Generating incremental migration for {entity_name}: add columns {new_fields}")
        if mode != "dry-run":
            write_file(filename, content)
            if mode != "quiet":
                logger.info(f"✨ Created incremental changelog: {filename}")
        else:
            logger.info(f"[dry-run] Would create: {filename}")
    
    # Generate rename changelog
    if renamed_fields:
        rename_content = gen_rename_column_changelog(entity_name, renamed_fields)
        if rename_content:
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
            filename = target_dir / f"{timestamp}-alter-{table_name}-renameField.xml"
            if mode != "dry-run":
                write_file(filename, rename_content)
                if mode != "quiet":
                    logger.info(f"✨ Created rename changelog: {filename}")
            else:
                logger.info(f"[dry-run] Would create: {filename}")
    
    # Generate metadata changes changelog
    if metadata_changes:
        changes_content = gen_modify_column_changelog(entity_name, metadata_changes)
        if changes_content:
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
            filename = target_dir / f"{timestamp}-alter-{table_name}-modifyField.xml"
            if mode != "dry-run":
                write_file(filename, changes_content)
                if mode != "quiet":
                    logger.info(f"✨ Created modify changelog: {filename}")
            else:
                logger.info(f"[dry-run] Would create: {filename}")
    
    # Handle dropped columns (case-insensitive dedup between DB and Java sources)
    # Exclude renamed fields — they are handled by the rename changelog
    # Exclude standard User fields that should never be dropped
    user_standard_cols = set()
    if entity_name == "User":
        user_standard_cols = {
            "USERNAME", "PASSWORD", "FIRST_NAME", "LAST_NAME",
            "EMAIL", "ACTIVE", "TIME_ZONE_ID",
            "FIRSTNAME", "LASTNAME", "TIMEZONEID", "USERPROFILE",
        }
    dropped_upper = {name.upper() for name in dropped_columns}
    all_dropped = [
        name for name in dropped_columns
        if name.upper() not in user_standard_cols
    ] + [
        name for name in dropped_from_csv
        if name.upper() not in dropped_upper
        and name.upper() not in user_standard_cols
        and name not in renamed_old_names
    ]
    if all_dropped:
        if mode == "prompt":
            response = input(f"⚠️  Warning: Columns {all_dropped} will be DROPPED from {table_name} (data loss!). Continue? [y/N]: ")
            if response.lower() != "y":
                logger.info("Skipped dropping columns.")
                return
        
        # Remove dropped fields from Java entity (normalize to lowercase)
        if mode != "dry-run":
            _remove_fields_from_java(entity_name, [name.lower() for name in all_dropped])
        
        if mode != "dry-run":
            content = gen_drop_column_changelog(entity_name, all_dropped)
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
            
            logger.info(f"Generating incremental migration for {entity_name}: drop columns {all_dropped}")
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
        logger.info(f"\n   → Migrating: {entity}")
        migrate_entity(entity, mode)
    
    logger.info("\n✅ Incremental migration completed!")