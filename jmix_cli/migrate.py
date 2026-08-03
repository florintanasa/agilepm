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

    # Also check relations where entity is the TARGET of a plain 1:1 (auto-inverse)
    for rel in _read_all_relations():
        if rel["target"].upper() != entity_name.upper():
            continue
        if rel["type"].strip().upper() == "1:1":
            # Auto-inverse field: source entity lowerCamelCase
            src = rel["source_entity"]
            inv_field = src[0].lower() + src[1:] if src else src.lower()
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

    Also reads existing @JoinColumn column names from the Java entity file,
    so that relation field renames (e.g. priority → mumu) don't cause the old
    FK column (PRIORITY_ID) to be falsely detected as dropped.
    """
    from jmix_cli.entity import get_relations_from_csv
    relations = get_relations_from_csv("relations.csv", entity_name)
    column_names: set[str] = set()
    for rel in relations:
        rel_type = rel["type"]
        field = rel["field"].upper()
        if rel_type in ("N:1", "1:1", "COMPOSITION_1:1"):
            column_names.add(f"{field}_ID")

    # Also scan existing Java entity for @JoinColumn column names
    # to catch relation field renames (old column names that still exist in DB)
    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    if entity_path.exists():
        content = entity_path.read_text(encoding="utf-8")
        for match in re.finditer(r'@JoinColumn\(name\s*=\s*"([^"]+)"', content):
            column_names.add(match.group(1).upper())

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


def _add_import_after(content: str, class_name: str) -> str:
    """Add an import for ``class_name`` after the last existing import line.

    If the import already exists, the content is returned unchanged.
    """
    full_import = f"import {class_name};"
    if full_import in content:
        return content
    # Find the last import line and add after it
    match = re.search(r'(import [^\n;]+;\n)(?!import)', content)
    if match:
        return content[:match.end()] + full_import + "\n" + content[match.end():]
    # Fallback: add after package declaration
    match = re.search(r'package [^;]+;\n', content)
    if match:
        return content[:match.end()] + "\n" + full_import + "\n" + content[match.end():]
    return content


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
                    "field_type": csv_field["type"],
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

def detect_relation_metadata_changes(entity_name: str) -> list[dict[str, Any]]:
    """Detect mandatory (nullable) changes for relation fields defined in relations.csv.

    For N:1, 1:1, and COMPOSITION_1:1 relations, the FK column lives on the
    *source* entity's table.  For COMPOSITION_1:N, the FK column lives on the
    *target* entity's table.

    The detection compares the ``mandatory`` flag from ``relations.csv``
    against the presence of ``@NotNull`` directly above the ``@JoinColumn`` /
    ``@ManyToOne`` / ``@OneToOne`` annotation block in the existing Java file.

    Each returned change dict uses the FK column name (``<field>_ID``) as
    ``column_name`` so it can flow through the same changelog / Java-update
    pipeline as regular field nullable changes.
    """
    from jmix_cli.entity import get_relations_from_csv

    relations = get_relations_from_csv("relations.csv", entity_name)
    # For COMPOSITION_1:N the FK column is on the TARGET entity's table, so
    # we also need relations where this entity is the TARGET.
    target_relations = _read_target_relations_from_csv(entity_name, "COMPOSITION_1:N")
    all_relations = relations + target_relations

    if not all_relations:
        return []

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
        return []

    content = entity_path.read_text(encoding="utf-8")

    # Collect FK columns that already exist in DB/changelog so we don't
    # generate metadata changes for columns that haven't been created yet.
    db_adapter = HSQLDBAdapter()
    table_name = get_table_name(entity_name)
    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)
    existing_columns = db_columns | changelog_columns

    changes: list[dict[str, Any]] = []
    for rel in all_relations:
        rel_type = rel["type"].strip().upper()
        if rel_type not in ("N:1", "1:1", "COMPOSITION_1:1", "COMPOSITION_1:N"):
            continue
        f_name = rel["field"]
        csv_col_name = f"{f_name.upper()}_ID"

        # Skip if FK column doesn't exist yet in DB/changelog — a separate
        # addColumn changelog needs to be generated first.
        if csv_col_name not in existing_columns:
            continue

        # Read the actual @JoinColumn column name from Java to handle renames
        # (e.g., field renamed from 'priority' to 'mumu' but DB column stays PRIORITY_ID)
        field_pattern = (
            r'(@JoinColumn\(name\s*=\s*"(\w+_ID)"[^)]*\)\s*\n'
            r'(?:    @NotNull\n)?\s*'
            r'@(?:ManyToOne|OneToOne)\(fetch = FetchType\.LAZY\)\s*\n    )'
            f'private {rel["target"]} {f_name};'
        )
        join_match = re.search(field_pattern, content)
        if join_match:
            col_name = join_match.group(2)
        else:
            col_name = csv_col_name

        # Check if @NotNull is present in the annotation block for this FK column.
        # Generated code has @JoinColumn first, then @NotNull, then @ManyToOne/@OneToOne.
        # Pattern: @JoinColumn(name = "COL_NAME"...) optionally with nullable=false,
        # followed by optional @NotNull, then @ManyToOne or @OneToOne
        pattern = (
            rf'    @JoinColumn\(name\s*=\s*"' + col_name + r'"(?:,\s*nullable\s*=\s*false)?\)\s*\n'
            r'(    @NotNull\n)?'
            r'    @(ManyToOne|OneToOne)'
        )
        match = re.search(pattern, content)
        # Also check for @NotNull BEFORE @JoinColumn (alternative ordering)
        if match is None or match.group(1) is None:
            pattern_pre = (
                r'    @NotNull\n'
                rf'    @JoinColumn\(name\s*=\s*"' + col_name + r'"(?:,\s*nullable\s*=\s*false)?\)\s*\n'
                r'    @(ManyToOne|OneToOne)'
            )
            match_pre = re.search(pattern_pre, content)
            if match_pre:
                java_mandatory = True
            elif match:
                java_mandatory = bool(match.group(1))
            else:
                java_mandatory = False
        else:
            java_mandatory = True

        csv_mandatory = rel.get("mandatory", False)

        if java_mandatory != csv_mandatory:
            changes.append(
                {
                    "name": col_name.lower(),
                    "column_name": col_name,
                    "field_name": f_name,
                    "change": "nullable",
                    "old": java_mandatory,
                    "new": csv_mandatory,
                    "is_relation": True,
                }
            )

    return changes


def _read_target_relations_from_csv(entity_name: str, rel_type_filter: str | None = None) -> list[dict[str, Any]]:
    """Read relations from relations.csv where ``entity_name`` is the TARGET.

    Optionally filter by relation type.  Returns the same dict shape as
    ``get_relations_from_csv``, with the source/target swapped so that the
    returned relations behave like source relations from the perspective of
    the caller entity.
    """
    relations: list[dict[str, Any]] = []
    csv_file = Path("relations.csv")
    if not csv_file.exists():
        return relations
    required = ["source_entity", "relation_type", "target_entity", "field_name", "mandatory"]
    validate_csv_path("relations.csv", required)
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["target_entity"].strip().lower() != entity_name.lower():
                continue
            if rel_type_filter and row["relation_type"].strip().upper() != rel_type_filter.upper():
                continue
            relations.append(
                {
                    "type": row["relation_type"].strip(),
                    "target": row["source_entity"].strip(),
                    "field": row["field_name"].strip(),
                    "mandatory": row["mandatory"].strip().lower() == "true",
                }
            )
    return relations


def detect_missing_relation_columns(entity_name: str) -> list[dict[str, Any]]:
    """Detect relation FK columns that don't exist yet in DB/changelog.

    For N:1, 1:1, and COMPOSITION_1:1 relations where the entity is the
    *source*, the FK column ``<FIELD>_ID`` lives on the entity's table.
    For COMPOSITION_1:N, the FK column lives on the *target* entity's table.

    When that column is missing from both the database and existing
    changelogs, it means the relation was just added to ``relations.csv``
    and needs an ``addColumn`` changelog.

    Returns a list of dicts compatible with ``gen_add_column_changelog``.
    """
    from jmix_cli.entity import get_relations_from_csv

    relations = get_relations_from_csv("relations.csv", entity_name)
    # For COMPOSITION_1:N the FK column is on the TARGET table, so we also
    # need relations where this entity is the TARGET.
    target_relations = _read_target_relations_from_csv(entity_name, "COMPOSITION_1:N")
    all_relations = relations + target_relations

    if not all_relations:
        return []

    db_adapter = HSQLDBAdapter()
    table_name = get_table_name(entity_name)
    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)
    existing_columns = db_columns | changelog_columns

    missing: list[dict[str, Any]] = []
    for rel in all_relations:
        rel_type = rel["type"].strip().upper()
        if rel_type not in ("N:1", "1:1", "COMPOSITION_1:1", "COMPOSITION_1:N"):
            continue
        f_name = rel["field"]
        col_name = f"{f_name.upper()}_ID"
        if col_name not in existing_columns:
            missing.append(
                {
                    "name": f_name,
                    "type": "UUID",
                    "mandatory": rel.get("mandatory", False),
                    "unique": rel_type in ("1:1", "COMPOSITION_1:1"),
                }
            )

    return missing


def _apply_relation_field_renames(entity_name: str) -> list[str]:
    """Rename relation fields in Java if the field name in relations.csv
    doesn't match the Java field name.

    For N:1 and 1:1 relations, when the field_name in relations.csv changes
    (e.g., from 'priority' to 'mumu'), this function updates the Java entity
    field name, getter, and setter accordingly. The DB column name (e.g.,
    PRIORITY_ID) stays the same, so no changelog is needed for the rename.

    Returns list of renamed field names (old -> new) for logging.
    """
    from jmix_cli.entity import get_relations_from_csv

    relations = get_relations_from_csv("relations.csv", entity_name)
    if not relations:
        return []

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
        return []

    content = entity_path.read_text(encoding="utf-8")
    renamed: list[str] = []

    for rel in relations:
        rel_type = rel["type"].strip().upper()
        if rel_type not in ("N:1", "1:1"):
            continue
        csv_field = rel["field"].strip()
        tgt_class = rel["target"].strip()

        # Find the existing relation field for this target type
        # Pattern: @JoinColumn(name = "XXX_ID"...) ... private TargetType fieldName;
        # The @JoinColumn may have nullable=false, and @NotNull may be present
        simple_pattern = rf'@JoinColumn\(name\s*=\s*"(\w+_ID)"[^)]*\)\s*\n(?:    @NotNull\n)?\s*@(ManyToOne|OneToOne)\(fetch = FetchType\.LAZY\)\s*\n\s*private {tgt_class} (\w+);'
        match = re.search(simple_pattern, content)
        if match and match.group(3) != csv_field:
            old_field = match.group(3)
            new_field = csv_field
            old_caps = old_field[0].upper() + old_field[1:]
            new_caps = new_field[0].upper() + new_field[1:]

            # Rename field declaration
            content = content.replace(
                f"private {tgt_class} {old_field};",
                f"private {tgt_class} {new_field};",
                1,
            )
            # Rename getter
            content = content.replace(
                f"public {tgt_class} get{old_caps}()",
                f"public {tgt_class} get{new_caps}()",
                1,
            )
            # Rename getter body
            content = content.replace(
                f"return {old_field};",
                f"return {new_field};",
                1,
            )
            # Rename setter
            content = content.replace(
                f"public void set{old_caps}({tgt_class} {old_field})",
                f"public void set{new_caps}({tgt_class} {new_field})",
                1,
            )
            # Rename setter body
            content = content.replace(
                f"this.{old_field} = {old_field};",
                f"this.{new_field} = {new_field};",
                1,
            )
            renamed.append(f"{old_field} -> {new_field}")

    if renamed:
        entity_path.write_text(content, encoding="utf-8")
        logger.info(f"✅ Renamed relation fields in {entity_name}.java: {renamed}")

    return renamed


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
        # For relation nullable changes, the column name is in change["column_name"]
        # (e.g. "TEAM_ID") and the field name for change_id is change["field_name"]
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
                # Field became mandatory → add NOT NULL constraint
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
                # Field became non-mandatory → drop NOT NULL constraint
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
        
        # Add import for field type if needed
        type_import_map = {
            "BigDecimal": "import java.math.BigDecimal;",
            "LocalDate": "import java.time.LocalDate;",
            "LocalDateTime": "import java.time.LocalDateTime;",
            "OffsetDateTime": "import java.time.OffsetDateTime;",
        }
        type_import = type_import_map.get(f_type)
        if type_import and type_import not in content:
            content = content.replace(
                "import java.util.UUID;",
                f"import java.util.UUID;\n{type_import}",
            )
        
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
        
        # Build the unique @Index entry if needed
        if field["unique"]:
            table_name = entity_name.upper()
            col_upper = f_name.upper()
            idx_name = f"IDX_{table_name}_UNQ_{col_upper}"
            index_entry = f'@Index(name = "{idx_name}", columnList = "{col_upper}", unique = true)'

            # Ensure import is present
            if "import jakarta.persistence.Index;" not in content:
                content = content.replace(
                    "import jakarta.persistence.*;",
                    "import jakarta.persistence.*;\nimport jakarta.persistence.Index;",
                )

            # Append to @Table indexes array (or create one)
            if re.search(r'@Table\([^)]*indexes\s*=\s*\{', content):
                content = re.sub(
                    r'(indexes\s*=\s*\{[^}]*?)(\s*\})',
                    lambda m: _append_index_entry(m, index_entry),
                    content,
                    count=1,
                )
            else:
                content = re.sub(
                    r'@Table\(name\s*=\s*"([^"]+)"\)',
                    lambda m: f'@Table(name = "{m.group(1)}", indexes = {{\n        {index_entry}\n    }})',
                    content,
                    count=1,
                )

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


def _append_index_entry(match: re.Match, index_entry: str) -> str:
    """Append an @Index entry to an existing @Table indexes array."""
    indexes_content = match.group(1).rstrip()
    closing = match.group(2)
    if indexes_content.rstrip().endswith(","):
        return indexes_content + "\n        " + index_entry + closing
    return indexes_content + ",\n        " + index_entry + closing


def _remove_index_entry(content: str, index_name: str) -> str:
    """Remove an @Index entry from the @Table indexes array.

    Handles first/last/only entry cases (with/without preceding or trailing comma).
    If the indexes array becomes empty, removes the entire indexes = { ... } from @Table.
    """
    escaped = re.escape(index_name)
    pattern = rf"(?:,)?\n[ \t]+@Index\(name\s*=\s*\"{escaped}\".*?\),?"
    new_content = re.sub(pattern, "", content, count=1)
    if re.search(r"indexes\s*=\s*\{\s*\}", new_content):
        new_content = re.sub(r',\s*indexes\s*=\s*\{\s*\}', "", new_content)
    return new_content


def _update_java_for_metadata_changes(entity_name: str, metadata_changes: list[dict[str, Any]]) -> None:
    """Update Java entity file to reflect metadata changes (mandatory, type, unique).

    For 'nullable' changes: adds/removes @NotNull and updates @Column(nullable=...).
    For 'type' changes: updates the field declaration, getter return type, and
    setter parameter type.
    """
    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    if not entity_path.exists():
        return

    content = entity_path.read_text(encoding="utf-8")

    for change in metadata_changes:
        field_name = change["name"]
        field_upper = field_name.upper()
        change_type = change["change"]

        if change_type == "nullable":
            new_mandatory = change["new"]
            is_relation = change.get("is_relation", False)

            if is_relation:
                # Relation field: work with @JoinColumn + @NotNull (no @Column)
                col_name = change["column_name"]
                if new_mandatory:
                    # Make mandatory: add nullable = false to @JoinColumn + add @NotNull
                    if f'@JoinColumn(name = "{col_name}", nullable = false)' not in content:
                        for ann in ("ManyToOne", "OneToOne"):
                            old = f'@JoinColumn(name = "{col_name}")\n    @{ann}'
                            new = f'@JoinColumn(name = "{col_name}", nullable = false)\n    @NotNull\n    @{ann}'
                            if old in content:
                                content = content.replace(old, new, 1)
                                break
                    # Ensure @NotNull import exists
                    if "import jakarta.validation.constraints.NotNull;" not in content:
                        content = _add_import_after(content, "jakarta.validation.constraints.NotNull")
                else:
                    # Make non-mandatory: remove nullable = false + @NotNull after @JoinColumn
                    old_join = f'@JoinColumn(name = "{col_name}", nullable = false)\n    @NotNull\n'
                    new_join = f'@JoinColumn(name = "{col_name}")\n'
                    content = content.replace(old_join, new_join)
                    # Remove @NotNull import if no more @NotNull annotations
                    if "@NotNull" not in content:
                        content = re.sub(
                            r'\nimport jakarta\.validation\.constraints\.NotNull;',
                            '',
                            content,
                        )
            else:
                if new_mandatory:
                    # Make mandatory: add @NotNull and nullable = false
                    old_col = f'@Column(name = "{field_upper}")'
                    new_col = f'@NotNull\n    @Column(name = "{field_upper}", nullable = false)'
                    if old_col in content and f'@Column(name = "{field_upper}", nullable = false)' not in content:
                        content = content.replace(old_col, new_col)
                    # For Boolean fields, add default value false when becoming mandatory
                    if change.get("field_type", "").lower() == "boolean":
                        old_decl = f"private Boolean {field_name};"
                        new_decl = f"private Boolean {field_name} = false;"
                        if old_decl in content and f"private Boolean {field_name} = false;" not in content:
                            content = content.replace(old_decl, new_decl)
                else:
                    # Make non-mandatory: remove @NotNull and nullable = false
                    # First, remove nullable = false from @Column
                    old_col = f'@Column(name = "{field_upper}", nullable = false)'
                    new_col = f'@Column(name = "{field_upper}")'
                    content = content.replace(old_col, new_col)

                    # Then, remove @NotNull line in the annotation block before the field
                    # Regex: @NotNull followed by any annotation lines, then @Column for this field
                    pattern = rf'(    @NotNull\n)((?:    @\w+.*\n)*)(    @Column\(name = "{field_upper}"\))'
                    content = re.sub(pattern, r'\2\3', content)

                    # For Boolean fields, remove default value false when becoming non-mandatory
                    if change.get("field_type", "").lower() == "boolean":
                        old_decl = f"private Boolean {field_name} = false;"
                        new_decl = f"private Boolean {field_name};"
                        content = content.replace(old_decl, new_decl)

        elif change_type == "type":
            old_type = change["old"]
            new_type = change["new"]
            # Update field declaration
            content = content.replace(
                f"private {old_type} {field_name};",
                f"private {new_type} {field_name};",
            )
            # Update getter return type
            f_caps = field_name[0].upper() + field_name[1:]
            content = content.replace(
                f"public {old_type} get{f_caps}()",
                f"public {new_type} get{f_caps}()",
            )
            # Update setter parameter type
            content = content.replace(
                f"public void set{f_caps}({old_type} {field_name})",
                f"public void set{f_caps}({new_type} {field_name})",
            )

        elif change_type == "unique":
            table_name = entity_name.upper()
            index_name = f"IDX_{table_name}_UNQ_{field_upper}"
            index_entry = (
                f'@Index(name = "{index_name}", columnList = "{field_upper}", unique = true)'
            )

            if change["new"]:
                if re.search(r'@Table\([^)]*indexes\s*=\s*\{', content):
                    content = re.sub(
                        r'(indexes\s*=\s*\{[^}]*?)(\s*\})',
                        lambda m: _append_index_entry(m, index_entry),
                        content,
                        count=1,
                    )
                else:
                    content = re.sub(
                        r'@Table\(name\s*=\s*"([^"]+)"\)',
                        lambda m: f'@Table(name = "{m.group(1)}", indexes = {{\n        {index_entry}\n    }})',
                        content,
                        count=1,
                    )
            else:
                content = _remove_index_entry(content, index_name)

    entity_path.write_text(content, encoding="utf-8")
    logger.info(f"✅ Updated Java metadata for {entity_name}.java")


def migrate_entity(entity_name: str, mode: str = "prompt") -> None:
    """Generate incremental Liquibase migrations for an entity.
    
    Args:
        entity_name: Name of the entity to migrate
        mode: 'prompt' (ask for confirmation on drop), 'force' (apply all), 'dry-run' (no write), 'quiet' (only log on changes)
    """
    from jmix_cli.i18n import update_messages_entity
    
    db_adapter = HSQLDBAdapter()
    messages_need_update = False
    
    # First, apply any relation field renames from relations.csv to Java
    # (e.g., priority → mumu). This must happen before field detection
    # so the Java file reflects the current relations.csv field names.
    relation_renames = _apply_relation_field_renames(entity_name)
    
    # Detect added, dropped, and renamed fields BEFORE injecting anything.
    # This is critical: if we inject new fields first, rename detection
    # won't work because the new field will already be in the Java file.
    added_fields, dropped_from_csv, renamed_fields = detect_changed_fields(entity_name)
    
    if renamed_fields or added_fields or relation_renames:
        messages_need_update = True
    
    # For User entity, exclude standard Jmix User fields from dropped detection
    # since they are defined in the base template, not in entities.csv
    if entity_name == "User":
        user_standard_fields = {
            "username", "password", "firstname", "lastname",
            "email", "active", "timezoneid", "userprofile",
        }
        dropped_from_csv = [f for f in dropped_from_csv if f.lower() not in user_standard_fields]
    
    if dropped_from_csv:
        messages_need_update = True
    
    metadata_changes = detect_field_metadata_changes(entity_name)
    metadata_changes.extend(detect_relation_metadata_changes(entity_name))
    
    # Build sets of renamed field names for exclusion
    renamed_old_names = {old for old, _ in renamed_fields}
    renamed_new_names = {new for _, new in renamed_fields}
    
    # Detect missing columns from DB/changelogs (excluding renamed fields)
    all_missing = detect_missing_columns(entity_name, db_adapter)
    missing_fields = [f for f in all_missing if f["name"] not in renamed_new_names]

    # Detect missing relation FK columns (new relations added to relations.csv
    # whose FK column/join table does not exist yet in DB or changelogs).
    missing_relation_cols = detect_missing_relation_columns(entity_name)
    missing_relation_cols = [
        f for f in missing_relation_cols if f["name"].upper() not in renamed_new_names
    ]
    
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
    
    if missing_fields or added_field_dicts or missing_relation_cols:
        new_fields = missing_fields + added_field_dicts + missing_relation_cols
        # Deduplicate by field name (case-insensitive) to prevent duplicate changelogs
        seen_names: set[str] = set()
        new_fields = [
            f for f in new_fields
            if f["name"].upper() not in seen_names
            and not seen_names.add(f["name"].upper())
        ]
        if new_fields:
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
        # Warn about potential NULL data issues for relation nullable → NOT NULL
        for change in metadata_changes:
            if (
                change.get("is_relation", False)
                and change["change"] == "nullable"
                and change.get("new") is True
            ):
                col = change["column_name"]
                tbl = table_name
                logger.warning(
                    f"⚠️  {entity_name}.{change['field_name']} → {tbl}.{col} "
                    f"is becoming NOT NULL. If existing DB rows have NULL in "
                    f"{col}, the Liquibase 'addNotNullConstraint' will fail. "
                    f"Either: (1) rm -rf .jmix/hsqldb/ then restart app, "
                    f"or (2) manually UPDATE {tbl} SET {col} = '<valid UUID>' "
                    f"WHERE {col} IS NULL before restarting."
                )
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

    # Update Java entity file to reflect metadata changes (mandatory, type, unique)
    if metadata_changes and mode != "dry-run":
        _update_java_for_metadata_changes(entity_name, metadata_changes)

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
    
    # Update messages once at the end with all current fields
    if messages_need_update and mode != "dry-run" and mode != "quiet" and entity_name != "User":
        relations_list = get_relations_from_csv("relations.csv", entity_name)
        csv_fields = _read_entity_fields(entity_name)
        all_field_names = [f["name"] for f in csv_fields]
        relation_field_names = [rel["field"] for rel in relations_list]
        all_field_names = list(set(all_field_names + relation_field_names))
        update_messages_entity(str(PROIECT_PATH), f"{COMPANY}.{project_name}", entity_name, all_field_names, relations_list)


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