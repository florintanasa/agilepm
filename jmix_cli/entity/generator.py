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
from pathlib import Path
from typing import Any

from jmix_cli.core.files import write_file
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.csv import validate_csv_path
from jmix_cli.entity.fields import get_entities_from_csv, _build_imports_and_fields
from jmix_cli.entity.traits import get_traits_from_csv
from jmix_cli.entity.relations.base import get_relations_from_csv


def get_sorted_entities_by_dependency() -> list[str]:
    entities_path = Path("entities.csv")
    if not entities_path.exists():
        return []
    validate_csv_path("entities.csv", ["entity_name"])
    all_entities = set()
    with entities_path.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["entity_name"].strip()
            if name:
                all_entities.add(name)
    dependencies = {ent: set() for ent in all_entities}
    relations_path = Path("relations.csv")
    if relations_path.exists():
        validate_csv_path("relations.csv", ["source_entity", "relation_type", "target_entity", "field_name", "mandatory"])
        with relations_path.open(mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = row["source_entity"].strip()
                tgt = row["target_entity"].strip()
                r_type = row["relation_type"].strip().upper()
                if src == tgt:
                    continue
                if src in dependencies and tgt in all_entities:
                    if r_type in ["N:1", "1:1", "COMPOSITION_1:1"] or "1:N" in r_type:
                        dependencies[src].add(tgt)
    sorted_entities = []
    visiting = set()
    visited = set()

    def visit(entity: str) -> None:
        if entity in visiting:
            return
        if entity in visited:
            return
        visiting.add(entity)
        for dep in dependencies.get(entity, []):
            if dep != entity:
                visit(dep)
        visiting.remove(entity)
        visited.add(entity)
        sorted_entities.append(entity)

    for entity in sorted(list(all_entities)):
        if entity not in visited:
            visit(entity)
    if "User" not in all_entities and relations_path.exists():
        sorted_entities.append("User")
    return sorted_entities


def has_existing_entity_and_changelog(name: str) -> bool:
    from jmix_cli.core.project import PROIECT_PATH, company_path, project_name
    entity_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{name}.java"
    changelog_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "liquibase" / "changelog"
    if not entity_path.exists():
        return False
    if changelog_dir.exists():
        pattern = f"*{name.lower()}*.xml"
        for f in changelog_dir.rglob(pattern):
            return True
    return False


def _build_relation_fields_and_methods(relations_list: list[dict[str, Any]], name: str) -> tuple[str, str, set[str]]:
    from jmix_cli.entity.relations.n1 import build_n1_fields
    from jmix_cli.entity.relations.one_one import build_one_one_fields
    from jmix_cli.entity.relations.nn import build_nn_fields

    java_relation_fields = ""
    java_relation_methods = ""
    dinamic_imports: set[str] = set()

    for rel in relations_list:
        if rel["type"] == "N:1":
            field, methods, imports = build_n1_fields(rel)
            java_relation_fields += field
            java_relation_methods += methods
            dinamic_imports.update(imports)

        elif rel["type"] == "1:N":
            from jmix_cli.core.java import to_camel_case_lower
            f_name = rel["field"]
            tgt_class = rel["target"]
            mapped_by_field = to_camel_case_lower(tgt_class)
            if mapped_by_field.endswith("_"):
                mapped_by_field = mapped_by_field[:-1]
            dinamic_imports.add("import jakarta.persistence.OneToMany;")
            dinamic_imports.add("import java.util.List;")
            java_relation_fields += f'    @OneToMany(mappedBy = "{mapped_by_field}")\n'
            java_relation_fields += f"    private List<{tgt_class}> {f_name};\n\n"
            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public List<{tgt_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}(List<{tgt_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

        elif rel["type"].strip().upper() == "1:1":
            field, methods, imports = build_one_one_fields(rel, name)
            java_relation_fields += field
            java_relation_methods += methods
            dinamic_imports.update(imports)

        elif rel["type"] == "N:N":
            field, methods, imports = build_nn_fields(rel, name)
            java_relation_fields += field
            java_relation_methods += methods
            dinamic_imports.update(imports)

    return java_relation_fields, java_relation_methods, dinamic_imports


def _inject_composition_into_parent(name: str, relations_list: list[dict[str, Any]]) -> None:
    for rel in relations_list:
        if not rel["type"].startswith("COMPOSITION_"):
            continue
        if rel["type"] == "COMPOSITION_1:1":
            from jmix_cli.entity.relations.composition_11 import inject_composition_11
            inject_composition_11(name, rel)
        elif rel["type"] == "COMPOSITION_1:N":
            from jmix_cli.entity.relations.composition_1n import inject_composition_1n
            inject_composition_1n(name, rel)


def gen_entity_mechanic_from_csv(
    name: str, fields_list: list[dict[str, Any]], traits: dict[str, Any], relations_list: list[dict[str, Any]] = []
) -> None:
    table_name = name.upper()
    unique_indexes = []
    for field in fields_list:
        if field["unique"]:
            col_name = field["name"].upper()
            unique_indexes.append(
                f'@Index(name = "IDX_{table_name}_UNQ_{col_name}", columnList = "{col_name}", unique = true)'
            )
    if unique_indexes:
        indexes_str = ",\n        ".join(unique_indexes)
        table_annotation = (
            f'@Table(name = "{table_name}", indexes = {{\n        {indexes_str}\n}})'
        )
    else:
        table_annotation = f'@Table(name = "{table_name}")'

    (
        java_traits_fields,
        java_traits_methods,
        java_business_fields,
        java_business_methods,
        dinamic_imports,
    ) = _build_imports_and_fields(fields_list, traits)

    java_relation_fields, java_relation_methods, rel_imports = _build_relation_fields_and_methods(relations_list, name)
    dinamic_imports.update(rel_imports)

    imports_block = "\n".join(sorted(list(dinamic_imports)))
    if imports_block:
        imports_block += "\n"

    java_content = f"""package {COMPANY}.{project_name}.entity;

import io.jmix.core.entity.annotation.JmixGeneratedValue;
import io.jmix.core.metamodel.annotation.InstanceName;
import io.jmix.core.metamodel.annotation.JmixEntity;
import jakarta.persistence.*;
import java.util.UUID;

{imports_block}
@JmixEntity
{table_annotation}
@Entity
public class {name} {{

    @Id
    @Column(name = "ID", nullable = false)
    @JmixGeneratedValue
    private UUID id;

{java_traits_fields}{java_business_fields}{java_relation_fields}    public UUID getId() {{
        return id;
    }}

    public void setId(UUID id) {{
        this.id = id;
    }}

{java_traits_methods}{java_business_methods}{java_relation_methods}}}
"""

    td = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity"
    write_file(td / f"{name}.java", java_content)
