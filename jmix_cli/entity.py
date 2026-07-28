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

from jmix_cli.exceptions import ConfigurationError, GenerationError, InvalidCsvError
from jmix_cli.utils import get_logger
from jmix_cli.utils import (
    COMPANY,
    PROIECT_PATH,
    append_unique,
    company_path,
    inject_import_if_missing,
    project_name,
    to_camel_case_lower,
    validate_csv_path,
    write_file,
)

logger = get_logger("jmix_cli.entity")


def get_traits_from_csv(csv_path: str, target_entity_name: str) -> dict[str, Any]:
    traits = {
        "versioned": True,
        "audit_of_creation": True,
        "audit_of_modification": True,
        "soft_delete": False,
    }
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return traits
    validate_csv_path(csv_path, ["entity_name", "versioned", "audit_of_creation", "audit_of_modification", "soft_delete"])
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["entity_name"].strip().lower() == target_entity_name.lower():
                traits["versioned"] = row["versioned"].strip().lower() == "true"
                traits["audit_of_creation"] = (
                    row["audit_of_creation"].strip().lower() == "true"
                )
                traits["audit_of_modification"] = (
                    row["audit_of_modification"].strip().lower() == "true"
                )
                traits["soft_delete"] = row["soft_delete"].strip().lower() == "true"
                break
    return traits


def get_entities_from_csv(csv_path: str, target_entity_name: str) -> list[dict[str, Any]]:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise InvalidCsvError(csv_path, message=f"CSV file not found: {csv_path}")
    validate_csv_path(csv_path, ["entity_name", "field_name", "field_type", "mandatory", "unique"])
    fields_list: list[dict[str, Any]] = []
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["entity_name"].strip().lower() == target_entity_name.lower():
                fields_list.append(
                    {
                        "name": row["field_name"].strip(),
                        "type": row["field_type"].strip(),
                        "mandatory": row["mandatory"].strip().lower() == "true",
                        "unique": row["unique"].strip().lower() == "true",
                    }
                )
    return fields_list


def _build_imports_and_fields(fields_list: list[dict[str, Any]], traits: dict[str, Any]) -> tuple[str, str, str, set[str]]:
    java_traits_fields = ""
    java_traits_methods = ""
    java_business_fields = ""
    java_business_methods = ""
    dinamic_imports: set[str] = set()
    is_first_text = True

    if traits["versioned"]:
        java_traits_fields += '    @Column(name = "VERSION", nullable = false)\n    @Version\n    private Integer version;\n\n'
        java_traits_methods += "    public Integer getVersion() {\n        return version;\n    }\n\n    public void setVersion(Integer version) {\n        this.version = version;\n    }\n\n"

    if traits["audit_of_creation"]:
        java_traits_fields += '    @CreatedBy\n    @Column(name = "CREATED_BY")\n    private String createdBy;\n\n    @CreatedDate\n    @Column(name = "CREATED_DATE")\n    private OffsetDateTime createdDate;\n\n'
        java_traits_methods += "    public String getCreatedBy() {\n        return createdBy;\n    }\n\n    public void setCreatedBy(String createdBy) {\n        this.createdBy = createdBy;\n    }\n\n"
        java_traits_methods += "    public OffsetDateTime getCreatedDate() {\n        return createdDate;\n    }\n\n    public void setCreatedDate(OffsetDateTime createdDate) {\n        this.createdDate = createdDate;\n    }\n\n"
        dinamic_imports.add("import org.springframework.data.annotation.CreatedBy;")
        dinamic_imports.add("import org.springframework.data.annotation.CreatedDate;")
        dinamic_imports.add("import java.time.OffsetDateTime;")

    if traits["audit_of_modification"]:
        java_traits_fields += '    @LastModifiedBy\n    @Column(name = "LAST_MODIFIED_BY")\n    private String lastModifiedBy;\n\n    @LastModifiedDate\n    @Column(name = "LAST_MODIFIED_DATE")\n    private OffsetDateTime lastModifiedDate;\n\n'
        java_traits_methods += "    public String getLastModifiedBy() {\n        return lastModifiedBy;\n    }\n\n    public void setLastModifiedBy(String lastModifiedBy) {\n        this.lastModifiedBy = lastModifiedBy;\n    }\n\n"
        java_traits_methods += "    public OffsetDateTime getLastModifiedDate() {\n        return lastModifiedDate;\n    }\n\n    public void setLastModifiedDate(OffsetDateTime lastModifiedDate) {\n        this.lastModifiedDate = lastModifiedDate;\n    }\n\n"
        dinamic_imports.add("import org.springframework.data.annotation.LastModifiedBy;")
        dinamic_imports.add("import org.springframework.data.annotation.LastModifiedDate;")
        dinamic_imports.add("import java.time.OffsetDateTime;")

    if traits["soft_delete"]:
        java_traits_fields += '    @DeletedBy\n    @Column(name = "DELETED_BY")\n    private String deletedBy;\n\n    @DeletedDate\n    @Column(name = "DELETED_DATE")\n    private OffsetDateTime deletedDate;\n\n'
        java_traits_methods += "    public String getDeletedBy() {\n        return deletedBy;\n    }\n\n    public void setDeletedBy(String deletedBy) {\n        this.deletedBy = deletedBy;\n    }\n\n"
        java_traits_methods += "    public OffsetDateTime getDeletedDate() {\n        return deletedDate;\n    }\n\n    public void setDeletedDate(OffsetDateTime deletedDate) {\n        this.deletedDate = deletedDate;\n    }\n\n"
        dinamic_imports.add("import io.jmix.core.annotation.DeletedBy;")
        dinamic_imports.add("import io.jmix.core.annotation.DeletedDate;")

    for field in fields_list:
        f_name = field["name"]
        f_type = field["type"]
        sql_col_name = f_name.upper()
        if f_type == "BigDecimal":
            dinamic_imports.add("import java.math.BigDecimal;")
        elif f_type == "LocalDate":
            dinamic_imports.add("import java.time.LocalDate;")
        elif f_type == "LocalDateTime":
            dinamic_imports.add("import java.time.LocalDateTime;")

        column_props = f'name = "{sql_col_name}"'
        validation_annotation = ""
        if field["mandatory"]:
            column_props += ", nullable = false"
            validation_annotation = "    @NotNull\n"
            dinamic_imports.add("import jakarta.validation.constraints.NotNull;")

        instance_name_annotation = ""
        if f_type.lower() == "string" and is_first_text:
            instance_name_annotation = "    @InstanceName\n"
            is_first_text = False

        java_business_fields += f"{instance_name_annotation}{validation_annotation}    @Column({column_props})\n    private {f_type} {f_name};\n\n"

        f_caps = f_name[0].upper() + f_name[1:]
        java_business_methods += f"    public {f_type} get{f_caps}() {{\n        return {f_name};\n    }}\n\n    public void set{f_caps}({f_type} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

    return java_traits_fields, java_traits_methods, java_business_fields, java_business_methods, dinamic_imports


def _build_relation_fields_and_methods(relations_list: list[dict[str, Any]], name: str) -> tuple[str, str, set[str]]:
    java_relation_fields = ""
    java_relation_methods = ""
    dinamic_imports: set[str] = set()

    for rel in relations_list:
        if rel["type"] == "N:1":
            f_name = rel["field"]
            tgt_class = rel["target"]
            sql_fk_col = f"{f_name.upper()}_ID"
            dinamic_imports.add("import jakarta.persistence.FetchType;")
            dinamic_imports.add("import jakarta.persistence.ManyToOne;")
            dinamic_imports.add("import jakarta.persistence.JoinColumn;")
            join_props = f'name = "{sql_fk_col}"'
            validation_annotation = ""
            if rel["mandatory"]:
                join_props += ", nullable = false"
                validation_annotation = "    @NotNull\n"
                dinamic_imports.add("import jakarta.validation.constraints.NotNull;")
            java_relation_fields += f"    @JoinColumn({join_props})\n"
            java_relation_fields += f"{validation_annotation}"
            java_relation_fields += "    @ManyToOne(fetch = FetchType.LAZY)\n"
            java_relation_fields += f"    private {tgt_class} {f_name};\n\n"
            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public {tgt_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

        elif rel["type"] == "1:N":
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
            f_name = rel["field"].strip()
            tgt_class = rel["target"].strip()
            dinamic_imports.add("import jakarta.persistence.OneToOne;")
            dinamic_imports.add("import jakarta.persistence.JoinColumn;")
            dinamic_imports.add("import jakarta.persistence.FetchType;")
            sql_fk_col = f"{f_name.upper()}_ID"
            java_relation_fields += f'    @JoinColumn(name = "{sql_fk_col}")\n    @OneToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public {tgt_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

            tgt_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
            if tgt_file_path.exists():
                java_tgt_content = tgt_file_path.read_text(encoding="utf-8")
                inv_field_name = name[0].lower() + name[1:]
                if f"private {name} {inv_field_name};" not in java_tgt_content:
                    logger.info(f" 🔗 Infiltrating inverse 1:1 association into the parent class: {tgt_class}")
                    inv_field = f'    @OneToOne(fetch = FetchType.LAZY, mappedBy = "{f_name}")\n    private {name} {inv_field_name};\n\n'
                    inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
                    inv_methods = f"    public {name} get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
                    inv_methods += f"    public void set{inv_caps}({name} {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
                    tgt_last_brace = java_tgt_content.rfind("}")
                    if tgt_last_brace != -1:
                        java_tgt_content = (
                            java_tgt_content[:tgt_last_brace]
                            + inv_field
                            + inv_methods
                            + java_tgt_content[tgt_last_brace:]
                        )
                        if "import jakarta.persistence.OneToOne;" not in java_tgt_content:
                            java_tgt_content = java_tgt_content.replace(
                                f"package {COMPANY}.{project_name}.entity;",
                                f"package {COMPANY}.{project_name}.entity;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.FetchType;",
                            )
                        tgt_file_path.write_text(java_tgt_content, encoding="utf-8")

        elif rel["type"] == "N:N":
            ownership = rel.get("ownership", "owning")
            f_name = rel["field"]
            tgt_class = rel["target"]
            join_table_name = f"{name.upper()}_{tgt_class.upper()}_LINK"
            src_fk_col = f"{name.upper()}_ID"
            tgt_fk_col = f"{tgt_class.upper()}_ID"
            dinamic_imports.add("import jakarta.persistence.ManyToMany;")
            dinamic_imports.add("import jakarta.persistence.JoinTable;")
            dinamic_imports.add("import jakarta.persistence.JoinColumn;")
            dinamic_imports.add("import java.util.List;")
            java_relation_fields += "    @ManyToMany\n"
            java_relation_fields += f'    @JoinTable(name = "{join_table_name}",\n'
            java_relation_fields += f'            joinColumns = @JoinColumn(name = "{src_fk_col}"),\n'
            java_relation_fields += f'            inverseJoinColumns = @JoinColumn(name = "{tgt_fk_col}"))\n'
            java_relation_fields += f"    private List<{tgt_class}> {f_name};\n\n"
            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public List<{tgt_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}(List<{tgt_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

            inv_field_name = name.lower() + "s" if not name.endswith("s") else name.lower()
            tgt_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
            if tgt_file_path.exists():
                java_tgt_content = tgt_file_path.read_text(encoding="utf-8")
                if f"private List<{name}> {inv_field_name};" not in java_tgt_content:
                    logger.info(f" 🔗 Injecting inverse N:N association into the target class: {tgt_class}")
                    if ownership == "both-owning":
                        # both-owning: target also has JoinTable - same table name as source
                        join_table_name = f"{name.upper()}_{tgt_class.upper()}_LINK"
                        tgt_src_fk = f"{tgt_class.upper()}_ID"
                        tgt_tgt_fk = f"{name.upper()}_ID"
                        inv_field = f'    @ManyToMany\n'
                        inv_field += f'    @JoinTable(name = "{join_table_name}",\n'
                        inv_field += f'            joinColumns = @JoinColumn(name = "{tgt_src_fk}"),\n'
                        inv_field += f'            inverseJoinColumns = @JoinColumn(name = "{tgt_tgt_fk}"))\n'
                        java_tgt_content = inject_import_if_missing(java_tgt_content, "jakarta.persistence.JoinTable")
                        java_tgt_content = inject_import_if_missing(java_tgt_content, "jakarta.persistence.JoinColumn")
                    else:
                        inv_field = f'    @ManyToMany(mappedBy = "{f_name}")\n'
                    inv_field += f"    private List<{name}> {inv_field_name};\n\n"
                    inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
                    inv_methods = f"    public List<{name}> get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
                    inv_methods += f"    public void set{inv_caps}(List<{name}> {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
                    java_tgt_content = inject_import_if_missing(java_tgt_content, "jakarta.persistence.ManyToMany")
                    java_tgt_content = inject_import_if_missing(java_tgt_content, "java.util.List")
                    if "    public UUID getId()" in java_tgt_content:
                        java_tgt_content = java_tgt_content.replace(
                            "    public UUID getId()",
                            f"{inv_field}    public UUID getId()",
                        )
                    last_brace = java_tgt_content.rfind("}")
                    if last_brace != -1:
                        java_tgt_content = (
                            java_tgt_content[:last_brace]
                            + "\n"
                            + inv_methods
                            + java_tgt_content[last_brace:]
                        )
                    tgt_file_path.write_text(java_tgt_content, encoding="utf-8")

    return java_relation_fields, java_relation_methods, dinamic_imports


def _inject_composition_into_parent(name: str, relations_list: list[dict[str, Any]]) -> None:
    for rel in relations_list:
        if not rel["type"].startswith("COMPOSITION_"):
            continue
        tgt_class = rel["target"]
        f_name = rel["field"]
        src_class = name
        tgt_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
        if not tgt_file_path.exists():
            continue
        java_tgt_content = tgt_file_path.read_text(encoding="utf-8")
        if (
            f"private List<{src_class}> {f_name};" in java_tgt_content
            or f"private {src_class} {f_name};" in java_tgt_content
        ):
            continue

        logger.info(f" 🔗 Injection of @Composition ({rel['type']}) into the class: {tgt_class}")
        new_field = ""
        new_methods = ""
        f_caps = f_name[0].upper() + f_name[1:]
        mapped_by_prop = "user" if tgt_class.lower() == "user" else tgt_class.lower() + tgt_class[1:]

        if rel["type"] == "COMPOSITION_1:N":
            first_char_lower = tgt_class[0].lower()
            remaining_chars = tgt_class[1:]
            mapped_by_prop = first_char_lower + remaining_chars
            new_field = f'    @Composition\n    @OneToMany(mappedBy = "{mapped_by_prop}")\n    private List<{src_class}> {f_name};\n\n'
            new_methods = f"    public List<{src_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            new_methods += f"    public void set{f_caps}(List<{src_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
            if "import java.util.List;" not in java_tgt_content:
                package_end_idx = java_tgt_content.find(";")
                if package_end_idx != -1:
                    java_tgt_content = (
                        java_tgt_content[: package_end_idx + 1]
                        + "\nimport java.util.List;"
                        + java_tgt_content[package_end_idx + 1 :]
                    )

        elif rel["type"] == "COMPOSITION_1:1":
            sql_fk_col = f"{f_name.upper()}_ID"
            new_field = f'@Composition\n    @JoinColumn(name = "{sql_fk_col}")\n    @OneToOne(fetch = FetchType.LAZY)\n    private {src_class} {f_name};\n\n'
            new_methods = f"    public {src_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n    public void set{f_caps}({src_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

            src_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{src_class}.java"
            if src_file_path.exists():
                java_src_content = src_file_path.read_text(encoding="utf-8")
                inv_field_name = name[0].lower() + name[1:]
                if f"private {name} {inv_field_name};" not in java_src_content:
                    logger.info(f" 🔗 Infiltrating inverse 1:1 mappedBy link into the child composition class: {src_class}")
                    inv_field = f'    @OneToOne(fetch = FetchType.LAZY, mappedBy = "{f_name}")\n    private {name} {inv_field_name};\n\n'
                    inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
                    inv_methods = f"    public {name} get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
                    inv_methods += f"    public void set{inv_caps}({name} {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
                    src_last_brace = java_src_content.rfind("}")
                    if src_last_brace != -1:
                        java_src_content = (
                            java_src_content[:src_last_brace]
                            + inv_field
                            + inv_methods
                            + java_src_content[src_last_brace:]
                        )
                        if "import jakarta.persistence.OneToOne;" not in java_src_content:
                            java_src_content = java_src_content.replace(
                                f"package {COMPANY}.{project_name}.entity;",
                                f"package {COMPANY}.{project_name}.entity;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.FetchType;",
                            )
                        src_file_path.write_text(java_src_content, encoding="utf-8")

        if "import io.jmix.core.metamodel.annotation.Composition;" not in java_tgt_content:
            java_tgt_content = java_tgt_content.replace(
                f"package {COMPANY}.{project_name}.entity;",
                f"package {COMPANY}.{project_name}.entity;\nimport io.jmix.core.metamodel.annotation.Composition;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.JoinColumn;\nimport jakarta.persistence.FetchType;",
            )

        if "    public UUID getId()" in java_tgt_content:
            old_anchor = "    public UUID getId()"
            replacement = "    " + new_field + "    public UUID getId()"
            java_tgt_content = java_tgt_content.replace(old_anchor, replacement)
        elif "    public final UUID getId()" in java_tgt_content:
            old_anchor = "    public final UUID getId()"
            replacement = "    " + new_field + "    public final UUID getId()"
            java_tgt_content = java_tgt_content.replace(old_anchor, replacement)

        last_brace_index = java_tgt_content.rfind("}")
        if last_brace_index != -1:
            java_tgt_content = (
                java_tgt_content[:last_brace_index]
                + "\n"
                + new_methods
                + java_tgt_content[last_brace_index:]
            )
        tgt_file_path.write_text(java_tgt_content, encoding="utf-8")


def get_relations_from_csv(csv_path: str, target_entity_name: str) -> list[dict[str, Any]]:
    relations_list: list[dict[str, Any]] = []
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return relations_list
    required = ["source_entity", "relation_type", "target_entity", "field_name", "mandatory"]
    validate_csv_path(csv_path, required)
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["source_entity"].strip().lower() == target_entity_name.lower():
                rel_dict = {
                    "type": row["relation_type"].strip(),
                    "target": row["target_entity"].strip(),
                    "field": row["field_name"].strip(),
                    "mandatory": row["mandatory"].strip().lower() == "true",
                }
                if "ownership" in (reader.fieldnames or []):
                    rel_dict["ownership"] = row.get("ownership", "").strip()
                relations_list.append(rel_dict)
    return relations_list


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
                    if r_type in ["N:1", "1:1"] or "1:N" in r_type:
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
    """Check if entity Java file and changelog already exist."""
    entity_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{name}.java"
    changelog_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "liquibase" / "changelog"
    
    if not entity_path.exists():
        return False
    
    # Check if there's at least one changelog for this table
    if changelog_dir.exists():
        pattern = f"*{name.lower()}*.xml"
        for f in changelog_dir.rglob(pattern):
            return True
    return False


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
    logger.info("✨ Entity saved successfully in: " + str(td / f"{name}.java"))
