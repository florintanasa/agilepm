#!/usr/bin/env python3
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
#
import csv
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Load proiect path in variable PROIECT_PATH
PROIECT_PATH = str(Path.cwd())


# Function to read the the file settings.gradle file to find and return project name
def get_project_name(settings_path: Path = Path("settings.gradle")) -> str | None:
    # Safety for an empty folder (init command case)
    if not settings_path.exists():
        return None

    text = settings_path.read_text(encoding="utf-8")
    # Find rootProject.name = 'name' or "name"
    m = re.search(r"""rootProject\.name\s*=\s*(['"])(.*?)\1""", text)
    return m.group(2) if m else None  # return only proiect name - like 'onboarding'


# Load in variable PROJECT the name of project
PROJECT = get_project_name()
project_name = (PROJECT or "").lower()  # transform project name in lower letters


# Function to read the the file settings.gradle file to find and return project name
def get_company_name(settings_path: Path = Path("build.gradle")) -> str | None:
    # Safety for an empty folder (init command case)
    if not settings_path.exists():
        return None

    text = settings_path.read_text(encoding="utf-8")
    # Find group = 'com.company' or "com.company"
    m = re.search(r"""group\s*=\s*(['"])(.*?)\1""", text)
    return m.group(2) if m else None  # return only company name - like 'com.company'


# Load in variable COMPANY the name of group
COMPANY = get_company_name() or ""
# Replace char '.' with '/' and transf. in path - like 'com/company'
company_path = COMPANY.replace(".", "/")


def to_camel_case_lower(text):
    """
    Transforms any String into a safe camelCase with the first letter strictly lowercase.
    Example: "TaskComment" -> "taskComment", "Task" -> "task"
    """
    if not text:
        return ""
    text_clean = text.strip()
    return text_clean[0].lower() + text_clean[1:]


# Function to read traits from csv file traits.casv
def get_traits_from_csv(csv_path, target_entity_name):
    """Reading traits.csv file and return global traits of entitties."""
    traits = {
        "versioned": True,
        "audit_of_creation": True,
        "audit_of_modification": True,
        "soft_delete": False,
    }
    # If not is found the traits.csv return traits default: "versioned": True,"audit_of_creation": True, "audit_of_modification": True, "soft_delete": False
    if not os.path.exists(csv_path):
        return traits

    # Open the traits.csv file and return the traits for entity
    with open(csv_path, mode="r", encoding="utf-8") as f:
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


# Funtion to return global fields of entity
def get_entities_from_csv(csv_path, target_entity_name):
    """Reading entities.csv file and return global fields of entity."""
    fields_list = []
    if not os.path.exists(csv_path):
        print(f" ! Error: The file CSV was not found at : {csv_path}")
        return fields_list

    with open(csv_path, mode="r", encoding="utf-8") as f:
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


# Function to generate java class for an entity with fileds loaded in fields_list, traits and relations from the entities
def gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list=[]):
    table_name = name.upper()  # tranform table name in upper chars

    # Generate unique indexes conform Jmix standard  @Table(indexes=...)
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

    # Generate the properties, methods, and trait imports in Java
    java_traits_fields = ""
    java_traits_methods = ""
    dinamic_imports = set()

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
        dinamic_imports.add(
            "import org.springframework.data.annotation.LastModifiedBy;"
        )
        dinamic_imports.add(
            "import org.springframework.data.annotation.LastModifiedDate;"
        )
        dinamic_imports.add("import java.time.OffsetDateTime;")

    if traits["soft_delete"]:
        java_traits_fields += '    @DeletedBy\n    @Column(name = "DELETED_BY")\n    private String deletedBy;\n\n    @DeletedDate\n    @Column(name = "DELETED_DATE")\n    private OffsetDateTime deletedDate;\n\n'
        java_traits_methods += "    public String getDeletedBy() {\n        return deletedBy;\n    }\n\n    public void setDeletedBy(String deletedBy) {\n        this.deletedBy = deletedBy;\n    }\n\n"
        java_traits_methods += "    public OffsetDateTime getDeletedDate() {\n        return deletedDate;\n    }\n\n    public void setDeletedDate(OffsetDateTime deletedDate) {\n        this.deletedDate = deletedDate;\n    }\n\n"
        dinamic_imports.add("import io.jmix.core.annotation.DeletedBy;")
        dinamic_imports.add("import io.jmix.core.annotation.DeletedDate;")

    # Generate the business fields and collect the necessary imports
    java_business_fields = ""
    java_business_methods = ""
    is_first_text = True

    for field in fields_list:
        f_name = field["name"]
        f_type = field["type"]
        sql_col_name = f_name.upper()

        # Collect the types in the unique global set
        if f_type == "BigDecimal":
            dinamic_imports.add("import java.math.BigDecimal;")
        elif f_type == "LocalDate":
            dinamic_imports.add("import java.time.LocalDate;")
        elif f_type == "LocalDateTime":
            dinamic_imports.add("import java.time.LocalDateTime;")

        column_props = f'name = "{sql_col_name}"'

        # Initialize the string for visual validation annotation
        validation_annotation = ""

        if field["mandatory"]:  # Check if the field is manadatory
            column_props += ", nullable = false"
            # Add @NotNull and import the Jakarta Validation
            validation_annotation = "    @NotNull\n"
            dinamic_imports.add("import jakarta.validation.constraints.NotNull;")

        instance_name_annotation = ""
        if f_type.lower() == "string" and is_first_text:
            instance_name_annotation = "    @InstanceName\n"
            is_first_text = False

        java_business_fields += f"{instance_name_annotation}{validation_annotation}    @Column({column_props})\n    private {f_type} {f_name};\n\n"

        f_caps = f_name[0].upper() + f_name[1:]
        java_business_methods += f"    public {f_type} get{f_caps}() {{\n        return {f_name};\n    }}\n\n    public void set{f_caps}({f_type} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

    # Generate fields and methods for relationships
    java_relation_fields = ""
    java_relation_methods = ""

    for rel in relations_list:
        # For the ManyToOne (N:1) relationship case
        if rel["type"] == "N:1":
            f_name = rel["field"]
            tgt_class = rel["target"]
            sql_fk_col = f"{f_name.upper()}_ID"

            # Add imports to the unique global set
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

        # For the OneToMany (1:N) relationship case
        elif rel["type"] == "1:N":
            f_name = rel["field"]
            tgt_class = rel["target"]

            # Use our unified safe function
            mapped_by_field = to_camel_case_lower(tgt_class)

            if mapped_by_field.endswith("_"):
                mapped_by_field = mapped_by_field[:-1]

            # Add the necessary imports to the dynamic global set
            dinamic_imports.add("import jakarta.persistence.OneToMany;")
            dinamic_imports.add("import java.util.List;")

            # 1. List<UserStep> property
            java_relation_fields += f'    @OneToMany(mappedBy = "{mapped_by_field}")\n'
            java_relation_fields += f"    private List<{tgt_class}> {f_name};\n\n"

            # 2. Getter and Setter methods specific for the collection
            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public List<{tgt_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}(List<{tgt_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

        # For the OneToOne (1:1) relationship case
        elif rel["type"].strip().upper() == "1:1":
            f_name = rel["field"].strip()
            tgt_class = rel["target"].strip()

            # 1. Populate your native 'dinamic_imports' set
            dinamic_imports.add("import jakarta.persistence.OneToOne;")
            dinamic_imports.add("import jakarta.persistence.JoinColumn;")
            dinamic_imports.add("import jakarta.persistence.FetchType;")

            # 2. Append the field to your true relationship fields accumulator
            sql_fk_col = f"{f_name.upper()}_ID"
            java_relation_fields += f'    @JoinColumn(name = "{sql_fk_col}")\n    @OneToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'

            # 3. Append the methods to your true relationship methods accumulator
            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public {tgt_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

            # 4. Inverse mapping: Infiltrate reciprocal @OneToOne into the parent entity class
            tgt_file_path = os.path.join(
                PROIECT_PATH,
                "src",
                "main",
                "java",
                company_path,
                project_name,
                "entity",
                f"{tgt_class}.java",
            )
            if os.path.exists(tgt_file_path):
                java_tgt_content = open(tgt_file_path, "r", encoding="utf-8").read()
                inv_field_name = name[0].lower() + name[1:]

                if f"private {name} {inv_field_name};" not in java_tgt_content:
                    print(
                        f" 🔗 Infiltrating inverse 1:1 association into the parent class: {tgt_class}"
                    )
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

                        if (
                            "import jakarta.persistence.OneToOne;"
                            not in java_tgt_content
                        ):
                            java_tgt_content = java_tgt_content.replace(
                                f"package {COMPANY}.{project_name}.entity;",
                                f"package {COMPANY}.{project_name}.entity;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.FetchType;",
                            )
                        with open(tgt_file_path, "w", encoding="utf-8") as f:
                            f.write(java_tgt_content)

        # For the ManyToMany (N:N) relationship case
        elif rel["type"] == "N:N":
            f_name = rel["field"]
            tgt_class = rel["target"]
            join_table_name = (
                f"{name.upper()}_{tgt_class.upper()}_LINK"  # ex: USER__ROLE_LINK
            )

            src_fk_col = f"{name.upper()}_ID"
            tgt_fk_col = f"{tgt_class.upper()}_ID"

            dinamic_imports.add("import jakarta.persistence.ManyToMany;")
            dinamic_imports.add("import jakarta.persistence.JoinTable;")
            dinamic_imports.add("import jakarta.persistence.JoinColumn;")
            dinamic_imports.add("import java.util.List;")

            java_relation_fields += "    @ManyToMany\n"
            java_relation_fields += f'    @JoinTable(name = "{join_table_name}",\n'
            java_relation_fields += (
                f'            joinColumns = @JoinColumn(name = "{src_fk_col}"),\n'
            )
            java_relation_fields += f'            inverseJoinColumns = @JoinColumn(name = "{tgt_fk_col}"))\n'
            java_relation_fields += f"    private List<{tgt_class}> {f_name};\n\n"

            f_caps = f_name[0].upper() + f_name[1:]
            java_relation_methods += f"    public List<{tgt_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            java_relation_methods += f"    public void set{f_caps}(List<{tgt_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

    # Transform the entire import set into text NOW, after everything is collected
    imports_block = "\n".join(sorted(list(dinamic_imports)))
    if imports_block:
        imports_block += "\n"

    # ======== Final Java class structure ========
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

    # Write the file directly into the correct project structure
    td = PROIECT_PATH + f"/src/main/java/{company_path}/{project_name}/entity"
    if not os.path.exists(td):
        os.makedirs(td)

    java_path = td + "/" + name + ".java"
    open(java_path, "w", encoding="utf-8").write(java_content)
    print("✨ Entity saved successfully in: " + java_path)

    # ===================================== #
    # LOGIC FOR COMPOSITIONS (1:N and 1:1)  #
    # ===================================== #
    for rel in relations_list:
        r_type = rel["type"]

        if r_type.startswith("COMPOSITION_"):
            tgt_class = rel["target"]  # ex: User
            f_name = rel["field"]  # ex: steps
            src_class = name  # ex: UserStep

            tgt_file_path = (
                PROIECT_PATH
                + f"/src/main/java/{company_path}/{project_name}/entity/{tgt_class}.java"
            )

            if os.path.exists(tgt_file_path):
                java_tgt_content = open(tgt_file_path, "r", encoding="utf-8").read()

                # Check if the property has already been injected, to avoid duplication.
                if (
                    f"private List<{src_class}> {f_name};" not in java_tgt_content
                    and f"private {src_class} {f_name};" not in java_tgt_content
                ):
                    print(
                        f" 🔗 Injection of @Composition ({r_type}) into the class: {tgt_class}"
                    )

                    new_field = ""
                    new_methods = ""
                    f_caps = f_name[0].upper() + f_name[1:]

                    # mappedBy must be the name of the inverse property
                    # In CSV: UserStep,N:1,User,user,true -> so the inverse field is "user"!
                    mapped_by_prop = "user"
                    if tgt_class.lower() != "user":
                        mapped_by_prop = tgt_class.lower() + tgt_class[1:]

                    # --- CASE A: 1:N Composition ---
                    if r_type == "COMPOSITION_1:N":
                        # FIX PROTECTION: We strictly isolate only the first character when converting to lowercase!
                        first_char_lower = tgt_class[0].lower()
                        remaining_chars = tgt_class[1:]
                        mapped_by_prop = first_char_lower + remaining_chars

                        new_field = f'    @Composition\n    @OneToMany(mappedBy = "{mapped_by_prop}")\n    private List<{src_class}> {f_name};\n\n'

                        new_methods = f"    public List<{src_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
                        new_methods += f"    public void set{f_caps}(List<{src_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

                        # Inject the collection List import at the top of the java metadata layer safely
                        if "import java.util.List;" not in java_tgt_content:
                            package_end_idx = java_tgt_content.find(";")
                            if package_end_idx != -1:
                                java_tgt_content = (
                                    java_tgt_content[: package_end_idx + 1]
                                    + "\nimport java.util.List;"
                                    + java_tgt_content[package_end_idx + 1 :]
                                )

                    # --- CASE B: 1:1 Composition ---
                    elif r_type == "COMPOSITION_1:1":
                        # CRITICAL JPA FIX: The parent entity defines @Composition and @JoinColumn.
                        # It holds the foreign key column (e.g. PROFILE_ID) inside its database table structure.
                        sql_fk_col = f"{f_name.upper()}_ID"
                        new_field = f'@Composition\n    @JoinColumn(name = "{sql_fk_col}")\n    @OneToOne(fetch = FetchType.LAZY)\n    private {src_class} {f_name};\n\n'
                        new_methods = f"    public {src_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n    public void set{f_caps}({src_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

                        # Inverse mapping setup: Inject the bidirectional mappedBy reference into the child class (src_class)
                        src_file_path = os.path.join(
                            PROIECT_PATH,
                            "src",
                            "main",
                            "java",
                            company_path,
                            project_name,
                            "entity",
                            f"{src_class}.java",
                        )
                        if os.path.exists(src_file_path):
                            java_src_content = open(
                                src_file_path, "r", encoding="utf-8"
                            ).read()
                            inv_field_name = name.lower() + name[1:]

                            if (
                                f"private {name} {inv_field_name};"
                                not in java_src_content
                            ):
                                print(
                                    f" 🔗 Infiltrating inverse 1:1 mappedBy link into the child composition class: {src_class}"
                                )
                                inv_field = f'    @OneToOne(fetch = FetchType.LAZY, mappedBy = "{f_name}")\n    private {name} {inv_field_name};\n\n'
                                inv_caps = inv_field_name.upper() + inv_field_name[1:]
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
                                    if (
                                        "import jakarta.persistence.OneToOne;"
                                        not in java_src_content
                                    ):
                                        java_src_content = java_src_content.replace(
                                            f"package {COMPANY}.{project_name}.entity;",
                                            f"package {COMPANY}.{project_name}.entity;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.FetchType;",
                                        )
                                    with open(
                                        src_file_path, "w", encoding="utf-8"
                                    ) as f:
                                        f.write(java_src_content)

                    # Inject dynamic Jmix @Composition import into the package header
                    if (
                        "import io.jmix.core.metamodel.annotation.Composition;"
                        not in java_tgt_content
                    ):
                        java_tgt_content = java_tgt_content.replace(
                            f"package {COMPANY}.{project_name}.entity;",
                            f"package {COMPANY}.{project_name}.entity;\nimport io.jmix.core.metamodel.annotation.Composition;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.JoinColumn;\nimport jakarta.persistence.FetchType;",
                        )

                    # PERFORMING MANUAL FIELD INSERTION:
                    if "    public UUID getId()" in java_tgt_content:
                        old_anchor = "    public UUID getId()"
                        replacement = "    " + new_field + "    public UUID getId()"
                        java_tgt_content = java_tgt_content.replace(
                            old_anchor, replacement
                        )

                    elif "    public final UUID getId()" in java_tgt_content:
                        old_anchor = "    public final UUID getId()"
                        replacement = (
                            "    " + new_field + "    public final UUID getId()"
                        )
                        java_tgt_content = java_tgt_content.replace(
                            old_anchor, replacement
                        )

                    # Inject clean methods right before the LAST curly brace in the Java file
                    last_brace_index = java_tgt_content.rfind("}")
                    if last_brace_index != -1:
                        java_tgt_content = (
                            java_tgt_content[:last_brace_index]
                            + "\n"
                            + new_methods
                            + java_tgt_content[last_brace_index:]
                        )

                    # Save the cleaned file back to disk
                    with open(tgt_file_path, "w", encoding="utf-8") as f:
                        f.write(java_tgt_content)


# Function for generate liquibase files changelog from cvs
def gen_liquibase_changelog_from_csv(name, fields_list, traits):
    timestamp_id = datetime.now().strftime("%Y%m%d%H%M%S")
    table_name = name.upper()

    # 1. Map CSV data types to SQL data types recognized by Liquibase
    def map_type(java_type):
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

    # 2. Generate infrastructure columns (Traits) based on traits.csv
    xml_traits_columns = '            <column name="ID" type="UUID">\n'
    xml_traits_columns += f'                <constraints nullable="false" primaryKey="true" primaryKeyName="PK_{table_name}"/>\n'
    xml_traits_columns += "            </column>\n"

    if traits["versioned"]:
        xml_traits_columns += '            <column name="VERSION" type="INT">\n                <constraints nullable="false" />\n            </column>\n'
    if traits["audit_of_creation"]:
        xml_traits_columns += (
            '            <column name="CREATED_BY" type="VARCHAR(255)" />\n'
        )
        xml_traits_columns += '            <column name="CREATED_DATE" type="timestamp with time zone" />\n'
    if traits["audit_of_modification"]:
        xml_traits_columns += (
            '            <column name="LAST_MODIFIED_BY" type="VARCHAR(255)" />\n'
        )
        xml_traits_columns += '            <column name="LAST_MODIFIED_DATE" type="timestamp with time zone" />\n'
    if traits["soft_delete"]:
        xml_traits_columns += (
            '            <column name="DELETED_BY" type="VARCHAR(255)" />\n'
        )
        xml_traits_columns += '            <column name="DELETED_DATE" type="timestamp with time zone" />\n'

    # 3. Generate business columns and collect unique index structure
    xml_business_columns = ""
    xml_indexes = ""

    for field in fields_list:
        sql_col_name = field["name"].upper()
        sql_type = map_type(field["type"])

        # Column-level constraints (e.g., nullable)
        constraints = ""
        if field["mandatory"]:
            constraints = '                <constraints nullable="false" />\n'

        if constraints:
            xml_business_columns += f'            <column name="{sql_col_name}" type="{sql_type}">\n{constraints}            </column>\n'
        else:
            xml_business_columns += (
                f'            <column name="{sql_col_name}" type="{sql_type}" />\n'
            )

        # If the field in CSV is marked as UNIQUE, generate a separate <createIndex> element
        # (Just like EclipseLink generates separately based on @Index)
        if field["unique"]:
            index_name = f"IDX_{table_name}_UNQ_{sql_col_name}"
            xml_indexes += f"""
    <changeSet id="{timestamp_id}-idx-{field["name"].lower()}" author="{project_name}">
        <createIndex tableName="{table_name}" indexName="{index_name}" unique="true">
            <column name="{sql_col_name}"/>
        </createIndex>
    </changeSet>"""

    # 4. Assemble the XML structure with Jmix/Liquibase official namespaces
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

    # 5. Save the file on disk in a chronological subfolder structure
    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%m")
    target_dir = (
        PROIECT_PATH
        + f"/src/main/resources/{company_path}/{project_name}/liquibase/changelog/{current_year}/{current_month}"
    )
    os.makedirs(target_dir, exist_ok=True)

    filename = f"{target_dir}/{timestamp_id}-01_base-{name.lower()}.xml"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f" -> Generated Liquibase XML with Constraints & Indexes: {filename}")


# Function to read relation from csv and return the relations
def get_relations_from_csv(csv_path, target_entity_name):
    """Read relations.csv and return only the relationships where the current entity is the source."""
    relations_list = []
    if not os.path.exists(csv_path):
        return relations_list

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["source_entity"].strip().lower() == target_entity_name.lower():
                relations_list.append(
                    {
                        "type": row["relation_type"].strip(),
                        "target": row["target_entity"].strip(),
                        "field": row["field_name"].strip(),
                        "mandatory": row["mandatory"].strip().lower() == "true",
                    }
                )
    return relations_list


# Function to generate Liquibase relationships
def gen_liquibase_relations_changelog(name, relations_list):
    if not relations_list:
        return

    timestamp_id = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )  # Generate a timestamp string in YYYYMMDDHHMMSS format
    src_table = name.upper()  # Convert the input 'name' to uppercase

    xml_fk_content = (
        ""  # Initialize an empty string to store the XML content for foreign keys
    )
    for rel in relations_list:  # Iterate through the list of relationships
        tgt_table = rel["target"].upper()  # Convert the target table name to uppercase
        # EXCEPTION FOR JMIX: If the target is the "USER" class, the actual SQL table is USER_
        if tgt_table == "USER":
            tgt_table = "USER_"  # Adjust the table name to "USER_"
        if src_table == "USER":
            src_table = "USER_"  # Adjust the table name to "USER_"
        # === CASE 1: N:1 Relationship (ManyToOne) ===
        if rel["type"] == "N:1":  # If the relationship type is N:1
            f_name = rel["field"].upper()
            col_name = f"{f_name}_ID"
            fk_name = f"FK_{src_table}_ON_{f_name}"
            nullable_val = (
                "false" if rel["mandatory"] else "true"
            )  # Set the nullable value based on whether the field is mandatory

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

        # === CASE 2: 1:1 Relationship (OneToOne) ===
        # Add a UUID column + Foreign Key + a UNIQUE constraint to ensure the 1-to-1 link
        elif rel["type"] == "1:1":
            f_name = rel["field"].upper()
            col_name = f"{f_name}_ID"
            fk_name = f"FK_{src_table}_ON_{f_name}"
            nullable_val = "false" if rel["mandatory"] else "true"

            xml_fk_content += f"""
    <changeSet id="{timestamp_id}-add-11-{rel["field"].lower()}" author="{project_name}">
        <addColumn tableName="{src_table}">
            <column name="{col_name}" type="UUID">
                <constraints nullable="{nullable_val}"/>
            </column>
        </addColumn>
        <!-- Guarantee uniqueness at the SQL level for 1:1 by creating a UNIQUE Index-->
        <createIndex tableName="{src_table}" indexName="IDX_{src_table}_UNQ_{col_name}" unique="true">
            <column name="{col_name}"/>
        </createIndex>
        <addForeignKeyConstraint baseTableName="{src_table}"
                                  baseColumnNames="{col_name}"
                                  constraintName="{fk_name}"
                                  referencedTableName="{tgt_table}"
                                  referencedColumnNames="ID"/>
    </changeSet>"""

        # === CASE 3: N:N Relationship (ManyToMany) ===
        # DO NOT add columns in existing tables, but create a completely new linking table
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
    os.makedirs(target_dir, exist_ok=True)

    filename = f"{target_dir}/{timestamp_id}_02_relations_{name.lower()}.xml"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f" -> Generated Liquibase Relations XML: {filename}")


# Function to generate the list-view screen
def gen_list_view_from_csv(name, fields_list, relations_list=[]):
    lower_name = name.lower()  # Convert the input 'name' to lowercase

    # 1. Generate the simple columns from entities.csv
    xml_columns = ""
    for field in fields_list:
        f_name = field["name"]  # Get the field name from the 'fields_list'
        xml_columns += f'                <column property="{f_name}"/>\n'  # Add a <column> element with the field name as the property

    # 2. Dynamically generate the Fetch Plan and columns for relationships
    xml_fetch_plan_properties = (
        ""  # Initialize an empty string to store the Fetch Plan block.
    )
    for rel in relations_list:
        if rel["type"] == "N:1" or rel["type"] == "1:1":
            f_name = rel["field"]  # ex: step, user

            # Tell the Fetch Plan to load the relationship property with its basic attributes (_base)
            xml_fetch_plan_properties += (
                f'                <property name="{f_name}" fetchPlan="_base"/>\n'
            )

            # Add the column to the table using the dot notation (property.instanceNameField)
            # In Jmix, if is directly set property="step", it will automatically call the field marked with @InstanceName from that entity!
            xml_columns += f'                <column property="{f_name}"/>\n'

    # Construct the Fetch Plan block only if relationships are defined
    xml_fetch_plan_block = ""
    # Check if the xml_fetch_plan_properties dictionary is not empty.
    if xml_fetch_plan_properties:
        xml_fetch_plan_block = f"""            <fetchPlan extends="_base">
{xml_fetch_plan_properties}            </fetchPlan>"""
    else:
        xml_fetch_plan_block = '            <fetchPlan extends="_base"/>'

    # 3. XML FlowUI Structure for a Fully Functional List
    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<view xmlns="http://jmix.io/schema/flowui/view"
	  xmlns:c="http://jmix.io/schema/flowui/jpql-condition"
      title="msg://{lower_name}ListView.title"
      focusComponent="{lower_name}sDataGrid">
    <data readOnly="true">
        <collection id="{lower_name}sDc"
        			class="{COMPANY}.{project_name}.entity.{name}">
{xml_fetch_plan_block}
            <loader id="{lower_name}sDl" readOnly="true">
                <query>
                	<![CDATA[select e from {name} e]]>
                </query>
            </loader>
        </collection>
    </data>
    <facets>
        <dataLoadCoordinator auto="true"/>
        <urlQueryParameters>
            <genericFilter component="genericFilter"/>
            <pagination component="pagination"/>
        </urlQueryParameters>
    </facets>
    <actions>
        <action id="selectAction" type="lookup_select"/>
        <action id="discardAction" type="lookup_discard"/>
    </actions>
    <layout>
    	<genericFilter id="genericFilter"
                       dataLoader="{lower_name}sDl">
                   <properties include=".*"/>
        </genericFilter>
        <hbox id="buttonsPanel" classNames="buttons-panel">
        	<startSlot>
            	<button id="createBtn" action="{lower_name}sDataGrid.createAction"/>
             	<button id="editBtn" action="{lower_name}sDataGrid.editAction"/>
              	<button id="removeBtn" action="{lower_name}sDataGrid.removeAction"/>
            </startSlot>
            <endSlot>
                <simplePagination id="pagination" dataLoader="{lower_name}sDl"/>
                <gridColumnVisibility dataGrid="{lower_name}sDataGrid" icon="COG" themeNames="icon"/>
            </endSlot>
        </hbox>
        <dataGrid id="{lower_name}sDataGrid"
        		  width="100%" minHeight="20em"
           		  dataContainer="{lower_name}sDc"
               	  columnReorderingAllowed="true"
                  multiSortOnShiftClickOnly="true">
            <actions>
                <action id="createAction" type="list_create"/>
                <action id="editAction" type="list_edit"/>
                <action id="removeAction" type="list_remove"/>
            </actions>
            <columns resizable="true">
{xml_columns}            </columns>
        </dataGrid>
        <hbox id="lookupActions" visible="false">
            <button id="selectButton" action="selectAction"/>
            <button id="discardButton" action="discardAction"/>
        </hbox>
    </layout>
</view>
"""

    # 4. Java Controller Structure for the list-view
    java_content = f"""package {COMPANY}.{project_name}.view.{lower_name};

import {COMPANY}.{project_name}.entity.{name};
import {COMPANY}.{project_name}.view.main.MainView;
import com.vaadin.flow.router.Route;
import io.jmix.flowui.view.*;

@Route(value = "{lower_name}s", layout = MainView.class)
@ViewController("{name}.list")
@ViewDescriptor("{lower_name}-list-view.xml")
@LookupComponent("{lower_name}sDataGrid")
@DialogMode(width = "64em", height = "48em")
public class {name}ListView extends StandardListView<{name}> {{
}}
"""

    # Writing to Disk
    view_dir = f"{PROIECT_PATH}/src/main/resources/{company_path}/{project_name}/view/{lower_name}"
    java_dir = (
        f"{PROIECT_PATH}/src/main/java/{company_path}/{project_name}/view/{lower_name}"
    )
    os.makedirs(view_dir, exist_ok=True)
    os.makedirs(java_dir, exist_ok=True)

    with open(f"{view_dir}/{lower_name}-list-view.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
    with open(f"{java_dir}/{name}ListView.java", "w", encoding="utf-8") as f:
        f.write(java_content)
    print(f" 🖥️ Successfully generated List View for: {name}")


# Function to generate the detail-view screen
def gen_detail_view_from_csv(name, fields_list, relations_list=[]):
    print(f" 🖥️ Starting FlowUI Detail View architecture for entity: '{name}'")
    lower_name = name.lower()

    # 1. Generate the form components dynamically
    xml_form_components = ""
    for field in fields_list:
        f_name = field["name"]
        f_type = field["type"].lower()

        if f_type in ["boolean", "bool"]:
            xml_form_components += (
                f'            <checkbox id="{f_name}Field" property="{f_name}"/>\n'
            )
        elif f_type in ["date", "localdate", "datetime", "localdatetime"]:
            xml_form_components += (
                f'            <datePicker id="{f_name}Field" property="{f_name}"/>\n'
            )
        else:
            xml_form_components += (
                f'            <textField id="{f_name}Field" property="{f_name}"/>\n'
            )

    # 2. Add the intelligent entityComboBox component for N:1 relationships
    xml_relation_data_containers = ""
    for rel in relations_list:
        if rel["type"] == "N:1" or rel["type"] == "1:1":
            f_name = rel["field"]  # ex: step, user
            tgt_class = rel["target"]  # ex: Step, User_
            tgt_lower = tgt_class.lower()

            # Build a dynamic CollectionContainer to load data from the target table
            xml_relation_data_containers += f'        <collection id="{tgt_lower}sDc" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
            xml_relation_data_containers += '            <fetchPlan extends="_base"/>\n'
            xml_relation_data_containers += (
                f'            <loader id="{tgt_lower}sDl">\n'
            )
            xml_relation_data_containers += "                <query>\n"
            xml_relation_data_containers += (
                f"                   <![CDATA[select e from {tgt_class} e]]>\n"
            )
            xml_relation_data_containers += "                </query>\n"
            xml_relation_data_containers += "            </loader>\n"
            xml_relation_data_containers += "        </collection>\n"

            # Add the entityCombobox component connected to the itemsContainer
            xml_form_components += f'            <entityComboBox id="{f_name}Field" property="{f_name}" itemsContainer="{tgt_lower}sDc">\n'
            xml_form_components += "                <actions>\n"
            xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
            xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
            xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
            xml_form_components += "                </actions>\n"
            xml_form_components += "            </entityComboBox>\n"

    # 2. XML FlowUI Structure for detail-view
    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<view xmlns="http://jmix.io/schema/flowui/view"
      title="msg://{lower_name}DetailView.title"
      focusComponent="form">
    <data>
    	<instance id="{lower_name}Dc"
                  class="{COMPANY}.{project_name}.entity.{name}">
            <fetchPlan extends="_base"/>
            <loader id="{lower_name}Dl"/>
        </instance>
{xml_relation_data_containers}    </data>
    <facets>
        <dataLoadCoordinator auto="true"/>
    </facets>
    <actions>
        <action id="saveAction" type="detail_saveClose"/>
        <action id="closeAction" type="detail_close"/>
    </actions>
    <layout classNames="fluid-layout" width="100%">
        <formLayout id="form" dataContainer="{lower_name}Dc">
{xml_form_components}        </formLayout>
        <hbox id="detailActions">
            <button id="saveAndCloseBtn" action="saveAction"/>
            <button id="closeBtn" action="closeAction"/>
        </hbox>
    </layout>
</view>
"""

    # 3. Java Controller Structure for detail-view
    java_content = f"""package {COMPANY}.{project_name}.view.{lower_name};

import {COMPANY}.{project_name}.entity.{name};
import {COMPANY}.{project_name}.view.main.MainView;
import com.vaadin.flow.router.Route;
import io.jmix.flowui.view.*;

@Route(value = "{lower_name}s/:id", layout = MainView.class)
@ViewController("{name}.detail")
@ViewDescriptor("{lower_name}-detail-view.xml")
@EditedEntityContainer("{lower_name}Dc")
public class {name}DetailView extends StandardDetailView<{name}> {{
}}
"""

    view_dir = f"{PROIECT_PATH}/src/main/resources/{company_path}/{project_name}/view/{lower_name}"
    java_dir = (
        f"{PROIECT_PATH}/src/main/java/{company_path}/{project_name}/view/{lower_name}"
    )
    os.makedirs(view_dir, exist_ok=True)
    os.makedirs(java_dir, exist_ok=True)

    with open(f"{view_dir}/{lower_name}-detail-view.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
    with open(f"{java_dir}/{name}DetailView.java", "w", encoding="utf-8") as f:
        f.write(java_content)
    print(f" 🖥️ Detail View successfully generated for: {name}")

    # ============================================================ #
    # AUTOMATIC INJECT UI TARGET FOR 1:N COMPOSITION RELATIONSHIPS #
    # ============================================================ #
    for rel in relations_list:
        if rel["type"] == "COMPOSITION_1:N":
            tgt_class = rel["target"]  # ex: User
            tgt_lower = tgt_class.lower()
            f_name = rel["field"]  # ex: steps
            src_class = name  # Re-introduce the variable for parsing entities.csv

            # Path to the parent entity's detailed XML file
            tgt_xml_path = (
                PROIECT_PATH
                + f"/src/main/resources/{company_path}/{project_name}/view/{tgt_lower}/{tgt_lower}-detail-view.xml"
            )

            if os.path.exists(tgt_xml_path):
                xml_tgt_content = open(tgt_xml_path, "r", encoding="utf-8").read()

                # Check if the composition table has already been injected
                if f'id="{f_name}DataGrid"' not in xml_tgt_content:
                    print(
                        f" 🖥️ Dynamic injecting @Composition UI in: {tgt_class} Detail View"
                    )

                    # 1. Prepare the nested property container
                    property_container = f'            <collection id="{f_name}Dc" property="{f_name}"/>\n'

                    # Find the area where the parent instance closes and inject before closing
                    if f'id="{tgt_lower}Dc"' in xml_tgt_content:
                        xml_tgt_content = xml_tgt_content.replace(
                            "</instance>", f"{property_container}        </instance>"
                        )

                    # 2. DYNAMIC COLUMN READING: Collect child properties directly from entities.csv
                    child_fields = get_entities_from_csv("entities.csv", src_class)
                    xml_composition_columns = ""

                    if child_fields:
                        for c_field in child_fields:
                            xml_composition_columns += f'                <column property="{c_field["name"]}"/>\n'
                    else:
                        # Fallback safety if CSV is empty or inaccessible
                        xml_composition_columns = (
                            '                <column property="notFound"/>\n'
                        )

                    # 3. Assemble the <dataGrid> with all dynamically read columns
                    composition_grid = (
                        f'        <h3 text="msg://{tgt_lower}DetailView.{f_name}"/>\n'
                    )
                    composition_grid += f'        <hbox id="{f_name}ButtonsPanel" classNames="buttons-panel">\n'
                    composition_grid += f'            <button id="{f_name}CreateBtn" action="{f_name}DataGrid.create"/>\n'
                    composition_grid += f'            <button id="{f_name}EditBtn" action="{f_name}DataGrid.edit"/>\n'
                    composition_grid += f'            <button id="{f_name}RemoveBtn" action="{f_name}DataGrid.remove"/>\n'
                    composition_grid += "        </hbox>\n"
                    composition_grid += f'        <dataGrid id="{f_name}DataGrid" width="100%" minHeight="15em" dataContainer="{f_name}Dc">\n'
                    composition_grid += "            <actions>\n"
                    composition_grid += (
                        '                <action id="create" type="list_create"/>\n'
                    )
                    composition_grid += (
                        '                <action id="edit" type="list_edit"/>\n'
                    )
                    composition_grid += (
                        '                <action id="remove" type="list_remove"/>\n'
                    )
                    composition_grid += "            </actions>\n"
                    composition_grid += "            <columns>\n"
                    composition_grid += (
                        f"{xml_composition_columns}"  # Inject the dynamic block
                    )
                    composition_grid += "            </columns>\n"
                    composition_grid += "        </dataGrid>\n"

                    # Inject the table directly into the layout, immediately below the main form
                    if "</formLayout>" in xml_tgt_content:
                        xml_tgt_content = xml_tgt_content.replace(
                            "</formLayout>", f"</formLayout>\n{composition_grid}"
                        )

                    # Save the modified XML file back to disk
                    with open(tgt_xml_path, "w", encoding="utf-8") as f:
                        f.write(xml_tgt_content)


# Function to call local ollama to translate text from English to target language
def ask_ollama_translation(text_to_translate, target_language_name):
    """
    Call the local translategemma:4b model via the native Ollama API
    to obtain a clean and raw technical translation.
    """
    # Construct an ultra-strict prompt to prevent the model from providing explanations
    prompt = (
        f"Translate the following software UI label from English into {target_language_name}. "
        f"Return ONLY the translated string, without quotes, explanations, or introductory text. "
        f"Label: {text_to_translate}"
    )

    try:
        connection = http.client.HTTPConnection("localhost", 11434, timeout=10)
        payload = json.dumps(
            {"model": "translategemma:4b", "prompt": prompt, "stream": False}
        )
        headers = {"Content-Type": "application/json"}

        connection.request("POST", "/api/generate", payload, headers)
        response = connection.getresponse()

        if response.status == 200:
            data = json.loads(response.read().decode("utf-8"))
            translated_text = data.get("response", "").strip()
            # Fallback for cleaning residual text
            translated_text = translated_text.replace('"', "").replace("'", "")
            return translated_text if translated_text else text_to_translate
    except Exception as e:
        print(f"[-] Ollama translation warning: {e}. Falling back to English.")

    return text_to_translate


# Function to generate messages in all configured languages using Ollama dynamically
def update_messages_entity(project_dir, base_package, entity_name, traits_list):
    """
    Parametric localizer engine. Corrects string-boolean evaluation from traits.csv,
    injects side menu keys for menu.xml, and stabilizes Ollama text translation responses.
    """
    n = entity_name.strip()
    print(
        f"Generating dynamic parametric localization messages for exact entity {n}..."
    )

    app_properties_path = project_dir + "/src/main/resources/application.properties"
    available_locales = ["en"]

    if os.path.exists(app_properties_path):
        with open(app_properties_path, "r", encoding="utf-8") as f:
            for line in f:
                if "jmix.core.available-locales" in line:
                    match = re.search(r"jmix\.core\.available-locales\s*=\s*(.*)", line)
                    if match:
                        available_locales = [
                            loc.strip()
                            for loc in match.group(1).split(",")
                            if loc.strip()
                        ]

    package_path_slashes = base_package.replace(".", "/")
    base_path = project_dir + f"/src/main/resources/{package_path_slashes}"

    # Read traits config from traits.csv dynamically to fix string-to-boolean evaluation bug
    entity_traits = {
        "versioned": False,
        "audit_of_creation": False,
        "audit_of_modification": False,
        "soft_delete": False,
    }
    traits_csv_path = project_dir + "/traits.csv"
    if os.path.exists(traits_csv_path):
        with open(traits_csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("entity_name", "").strip() == n:
                    # Explicit string evaluation check to fix the boolean override issue
                    entity_traits["versioned"] = (
                        row.get("versioned", "").strip().lower() == "true"
                    )
                    entity_traits["audit_of_creation"] = (
                        row.get("audit_of_creation", "").strip().lower() == "true"
                    )
                    entity_traits["audit_of_modification"] = (
                        row.get("audit_of_modification", "").strip().lower() == "true"
                    )
                    entity_traits["soft_delete"] = (
                        row.get("soft_delete", "").strip().lower() == "true"
                    )

    # Human readable text conversions
    spaced_title = "".join([" " + c if c.isupper() else c for c in n]).strip().lower()
    readable_title_en = spaced_title.capitalize()
    plural_title_en = (
        readable_title_en
        if readable_title_en.endswith("s")
        else f"{readable_title_en}s"
    )

    for locale in available_locales:
        if locale == "en":
            target_path = base_path + "/messages_en.properties"
            lang_name = "English"
            primary_iso = "en"
        else:
            target_path = base_path + f"/messages_{locale}.properties"
            iso_lang_names = {
                "ar": "Arabic",
                "ckb": "Central Kurdish",
                "de": "German",
                "el": "Greek",
                "es": "Spanish",
                "fr": "French",
                "it": "Italian",
                "nl": "Dutch",
                "pt": "Brazilian Portuguese",
                "ro": "Romanian",
                "ru": "Russian",
                "tr": "Turkish",
                "zh": "Simplified Chinese",
            }
            primary_iso = locale.split("_")[0].lower()
            lang_name = iso_lang_names.get(primary_iso, locale)

        target_lines = []
        target_lines.append(f"{base_package}.entity/{n}={n}")
        target_lines.append(f"{base_package}.entity/{n}.id=Id")

        # --- DYNAMIC TRAITS LOCALIZATION (FIXED STRINGS EVALUATION) ---
        if entity_traits["versioned"]:
            v_text = "Version" if locale == "en" else "Versiune"
            target_lines.append(f"{base_package}.entity/{n}.version={v_text}")

        if entity_traits["audit_of_creation"]:
            cb = "Created by" if locale == "en" else "Creat de"
            cd = "Created date" if locale == "en" else "Data creării"
            target_lines.append(f"{base_package}.entity/{n}.createdBy={cb}")
            target_lines.append(f"{base_package}.entity/{n}.createdDate={cd}")

        if entity_traits["audit_of_modification"]:
            mb = "Last modified by" if locale == "en" else "Modificat de"
            md = "Last modified date" if locale == "en" else "Data modificării"
            target_lines.append(f"{base_package}.entity/{n}.lastModifiedBy={mb}")
            target_lines.append(f"{base_package}.entity/{n}.lastModifiedDate={md}")

        if entity_traits["soft_delete"]:
            db = "Deleted by" if locale == "en" else "Șters de"
            dd = "Deleted date" if locale == "en" else "Data ștergerii"
            target_lines.append(f"{base_package}.entity/{n}.deletedBy={db}")
            target_lines.append(f"{base_package}.entity/{n}.deletedDate={dd}")

        # --- PROCESS FIELDS AND RELATIONSHIPS ---
        for trait in traits_list:
            spaced_name = (
                "".join([" " + c if c.isupper() else c for c in trait]).strip().lower()
            )
            readable_en = spaced_name.capitalize()

            if locale == "en":
                # Write English without calling Ollama to prevent model distortions
                target_lines.append(f"{base_package}.entity/{n}.{trait}={readable_en}")
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.{trait}Field={readable_en}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.{trait}Column={readable_en}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.dataGrid.{trait}={readable_en}"
                )
            else:
                traducere_lang = ask_ollama_translation(readable_en, lang_name)

                target_lines.append(
                    f"{base_package}.entity/{n}.{trait}={traducere_lang}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.{trait}Field={traducere_lang}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.{trait}Column={traducere_lang}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.dataGrid.{trait}={traducere_lang}"
                )

        # --- VIEW TITLES AND SIDEBAR MENUS CONFIGURATION (FIXED FOR menu.xml) ---
        if locale == "en":
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}ListView.title={plural_title_en}"
            )
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.title={readable_title_en} Details"
            )
            # Menu item injection matching menu.xml layout rules
            target_lines.append(f"{base_package}/menu.{n}.list={plural_title_en}")
        else:
            traducere_title_list = ask_ollama_translation(plural_title_en, lang_name)
            if not traducere_title_list or len(traducere_title_list) > 50:
                traducere_title_list = (
                    f"Lista {spaced_title}" if primary_iso == "ro" else plural_title_en
                )

            traducere_title_detail = ask_ollama_translation(
                readable_title_en, lang_name
            )
            if not traducere_title_detail or len(traducere_title_detail) > 50:
                traducere_title_detail = (
                    f"Detalii {spaced_title}"
                    if primary_iso == "ro"
                    else f"{readable_title_en} Details"
                )

            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}ListView.title={traducere_title_list}"
            )
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.title={traducere_title_detail}"
            )
            # Localized menu title mapping for sidebar link stability
            target_lines.append(f"{base_package}/menu.{n}.list={traducere_title_list}")

        # 2. GENERATE AND TRANSLATE RELATIONSHIP LABELS (relations.csv)
        for rel in relations_list:
            f_name = rel["field"]

            # Separate camelCase with spaces for relationships
            spaced_name = (
                "".join([" " + c if c.isupper() else c for c in f_name]).strip().lower()
            )
            readable_en = spaced_name.capitalize()
            target_lines.append(
                f"{COMPANY}.{project_name}.entity/{n}.{f_name}={readable_en}"
            )

            translate_label_relation = ask_ollama_translation(readable_en, lang_name)
            target_lines.append(
                f"{COMPANY}.{project_name}.entity/{n}.{f_name}={translate_label_relation}"
            )

        # We are parsing the entity name (e.g., UserStep -> User step)
        spaced_title = (
            "".join([" " + c if c.isupper() else c for c in n]).strip().lower()
        )
        readable_title_en = spaced_title.capitalize()  # Now is "User step"

        # 2.1 DEDICATED TRANSLATIONS FOR COMPOSITION TITLES IN PARENT UI
        for rel in relations_list:
            if rel["type"] == "COMPOSITION_1:N":
                tgt_lower = rel["target"].lower()  # ex: user
                f_name = rel["field"]  # ex: steps

                # Generate beautiful English names (e.g., steps -> Steps)
                readable_title_en = f_name.capitalize()
                target_lines.append(
                    f"{COMPANY}.{project_name}.view.{tgt_lower}/{tgt_lower}DetailView.{f_name}={readable_title_en}"
                )

                translate_label_composition = ask_ollama_translation(
                    readable_title_en, lang_name
                )

                target_lines.append(
                    f"{COMPANY}.{project_name}.view.{tgt_lower}/{tgt_lower}DetailView.{f_name}={translate_label_composition}"
                )

        # --- INTERNAL LINE WRITER WITH STRICT EQUALITY PREFIX MATCHING ---
        def append_unique(file_path, lines_to_add):
            existing_content = ""
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            with open(file_path, "a", encoding="utf-8") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")

                header_written = False
                for line in lines_to_add:
                    if "=" not in line:
                        continue
                    key = line.split("=")[0].strip()

                    # Exact string layout matching to protect against collisions
                    if f"{key}=" not in existing_content:
                        if not header_written:
                            f.write(
                                f"\n# Automated localization properties bundle layout for entity: {n}\n"
                            )
                            header_written = True
                        f.write(line + "\n")

        # Execute safe isolated appends
        append_unique(target_path, target_lines)
        if locale == "en":
            append_unique(base_path + "/messages.properties", target_lines)

    print(
        f"✨ Parametric localization layout for entity '{n}' successfully compiled across available locales!"
    )


# Function for update the menu
def update_menu(n):
    print("Updating menu.xml for " + n + "...")
    menu_path = (
        PROIECT_PATH + f"/src/main/resources/{company_path}/{project_name}/menu.xml"
    )

    # Check and inform if not exist the menu.xml file in the path
    if not os.path.exists(menu_path):
        print(f"⚠️ I not found the file menu.xml in the path {menu_path}!")
        return

    # Generate the exact menu line in the Jmix Studio format
    menu_item = f'    <item view="{n}.list" title="msg://{COMPANY}.{project_name}.view.{n.lower()}/{n.lower()}ListView.title"/>\n'

    with open(menu_path, "r", encoding="utf-8") as f:
        content = f.read()

    # For safety: check if the screen is already in the menu
    if ('view="' + n + '.list"') in content:
        print("ℹ️ View " + n + ".list allready exist in menu.")
        return

    # Insert the exact item right before the closing tag of the main menu
    if "</menu>" in content:
        new_content = content.replace("</menu>", menu_item + "</menu>")
        with open(menu_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Menu injected successfully into menu.xml!")
    else:
        print("⚠️ Invalid structure for menu.xml (missing closing </menu> tag)!")


# ==============================================================================
# SUB-SISTEM COMMANDE INIT (Independent CLI - like cuba-cli)
# ==============================================================================

# Universal mapping dictionary from user input to official Jmix translation add-ons
JMIX_TRANSLATIONS_MAP = {
    "ar": "ar",
    "ckb": "ckb",
    "de": "de",
    "el": "el",
    "es": "es",
    "fr": "fr",
    "fr_fr": "fr",
    "it": "it",
    "nl": "nl",
    "pt": "pt-br",
    "pt_BR": "pt-br",
    "ro": "ro",
    "ro_RO": "ro",
    "ro_MD": "ro",
    "ru": "ru",
    "tr": "tr",
    "zh": "zh-cn",
    "zh_CN": "zh-cn",
}


# Function to initializes a new Jmix project
def cmd_init_project(project_name, target_group, lang_input="en"):
    """
    Initializes a new Jmix project by cloning the official starter template,
    automatically calculating the base package, injecting localization add-ons,
    and handling structural directory refactoring.
    """
    # Automatically calculate base package (e.g., com.florin.onboarding)
    base_package = (
        f"{target_group.strip().strip('.')}.{project_name.strip().strip('.')}"
    )
    repo_url = "https://github.com/jmix-framework/jmix-ai-template"
    current_dir = os.getcwd()
    target_dir = os.path.join(current_dir, project_name)

    # Keep the exact casing for file names and properties (e.g., ro_RO, ro_MD)
    lang_suffix = lang_input.strip()
    lang_key_for_map = lang_suffix.lower()

    print(f"\n[*] Initializing New Jmix Project: '{project_name}'")
    print(f"[*] Group ID:                 {target_group}")
    print(f"[*] Generated Base Package:   {base_package}")
    print(f"[*] Requested Locale:         {lang_suffix}")
    print("-" * 60)

    if os.path.exists(target_dir):
        print(
            f"[-] Critical Error: Folder '{project_name}' already exists in this directory."
        )
        sys.exit(1)

    print("[*] Step 1: Downloading official Jmix starter template...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, project_name], check=True
        )
    except Exception as e:
        print(f"[-] Critical Error executing Git clone: {e}")
        sys.exit(1)

    # Remove template git history for a clean slate repository
    shutil.rmtree(os.path.join(target_dir, ".git"), ignore_errors=True)
    print("[+] Git template history cleared successfully.")

    # Define old package paths (Jmix template typos) vs new packages
    old_package_dots = "io.jmix.tempate"
    old_package_slashes = "io/jmix/tempate"

    new_package_slashes = os.path.join(*base_package.split("."))
    new_package_property_slashes = base_package.replace(".", "/")

    # Define project layer matrix for physical refactoring
    paths_to_move = [
        (
            os.path.join(target_dir, "src", "main", "java"),
            old_package_slashes,
            new_package_slashes,
        ),
        (
            os.path.join(target_dir, "src", "test", "java"),
            old_package_slashes,
            new_package_slashes,
        ),
        (
            os.path.join(target_dir, "src", "main", "resources"),
            old_package_slashes,
            new_package_slashes,
        ),
    ]

    print("[*] Step 2: Refactoring structural Java source layers and XML resources...")
    for base_root, old_rel, new_rel in paths_to_move:
        src_dir = os.path.join(base_root, old_rel)
        dst_dir = os.path.join(base_root, new_rel)

        if os.path.exists(src_dir):
            os.makedirs(dst_dir, exist_ok=True)
            for item in os.listdir(src_dir):
                shutil.move(os.path.join(src_dir, item), os.path.join(dst_dir, item))
            # Clean up empty parent directories left behind (io/jmix/tempate hierarchy)
            shutil.rmtree(os.path.join(base_root, "io"), ignore_errors=True)

    print(
        "[*] Step 3: Injecting metadata and localization configuration dependencies..."
    )

    build_gradle_path = os.path.join(target_dir, "build.gradle")
    app_properties_path = os.path.join(
        target_dir, "src", "main", "resources", "application.properties"
    )

    # --- DEPENDENCY INJECTION IN BUILD.GRADLE ---
    if os.path.exists(build_gradle_path):
        with open(build_gradle_path, "r", encoding="utf-8") as f:
            gradle_content = f.read()

        # Update group metadata
        gradle_content = re.sub(
            r"group\s*=\s*['\"].*?['\"]", f"group = '{target_group}'", gradle_content
        )

        # Inject translation add-on if the locale is not default English
        if lang_key_for_map != "en" and lang_key_for_map in JMIX_TRANSLATIONS_MAP:
            addon_suffix = JMIX_TRANSLATIONS_MAP[lang_key_for_map]
            addon_dependency = f"\n    implementation 'io.jmix.translations:jmix-translations-{addon_suffix}'"

            if "dependencies {" in gradle_content:
                gradle_content = gradle_content.replace(
                    "dependencies {",
                    f"dependencies {{{addon_dependency} // Automatically configured via Jmix CLI",
                )
                print(
                    f"[+] Injected localization add-on dependency: jmix-translations-{addon_suffix}"
                )

        with open(build_gradle_path, "w", encoding="utf-8") as f:
            f.write(gradle_content)

    # --- AVAILABLE LOCALES CONFIGURATION IN APPLICATION.PROPERTIES ---
    if os.path.exists(app_properties_path):
        with open(app_properties_path, "r", encoding="utf-8") as f:
            prop_content = f.read()

        if "jmix.core.available-locales" in prop_content:
            if lang_key_for_map != "en":
                # Dynamically append the exact requested locale string (e.g., en,ro_RO)
                prop_content = re.sub(
                    r"jmix\.core\.available-locales\s*=\s*(.*)",
                    f"jmix.core.available-locales = \\1,{lang_suffix}",
                    prop_content,
                )
                print(f"[+] Updated active core locales property: en,{lang_suffix}")
        else:
            locales_line = "\njmix.core.available-locales = en"
            if lang_key_for_map != "en":
                locales_line += f",{lang_suffix}"
            prop_content += locales_line

        with open(app_properties_path, "w", encoding="utf-8") as f:
            f.write(prop_content)

    # --- INITIALIZATION OF DYNAMIC PROJECT MESSAGES FILE WITH FALLBACK COPY ---
    if lang_key_for_map != "en":
        msg_dir = os.path.join(
            target_dir, "src", "main", "resources", new_package_slashes
        )
        os.makedirs(msg_dir, exist_ok=True)

        # The exact filename present in the official Jmix template repository
        template_eng_msg_path = os.path.join(msg_dir, "messages_en.properties")

        # Standard Spring Boot fallback properties file path
        base_fallback_msg_path = os.path.join(msg_dir, "messages.properties")

        # Target bilingual file requested by user (e.g., messages_ro_RO.properties)
        custom_messages_path = os.path.join(
            msg_dir, f"messages_{lang_suffix}.properties"
        )

        # 1. Create the standard messages.properties if it doesn't exist yet as a fallback copy
        if os.path.exists(template_eng_msg_path) and not os.path.exists(
            base_fallback_msg_path
        ):
            shutil.copy2(template_eng_msg_path, base_fallback_msg_path)
            print("[+] Generated standard base fallback file: messages.properties")

        # 2. Duplicate the English template content straight into your localized twin bundle
        if not os.path.exists(custom_messages_path):
            if os.path.exists(template_eng_msg_path):
                # Copy the entire clean Jmix translation structure
                shutil.copy2(template_eng_msg_path, custom_messages_path)

                # Add a traceable header metadata comment at the first line of the properties file
                with open(custom_messages_path, "r+", encoding="utf-8") as f:
                    content = f.read()
                    f.seek(0, 0)
                    f.write(
                        f"# Automatically initialized as a bilingual twin for: {lang_suffix}\n"
                        + content
                    )

                print(
                    f"[+] Created localized bundle twin with English base: messages_{lang_suffix}.properties"
                )
            else:
                # Absolute safety scythe fallback execution string path block
                with open(custom_messages_path, "w", encoding="utf-8") as f:
                    f.write(
                        f"# Custom localization translations properties file for: {lang_suffix}\n"
                    )
                print(
                    f"[+] Initialized empty bundle (messages_en.properties was missing): messages_{lang_suffix}.properties"
                )

    # Global text search & replace refactoring execution loop
    files_to_update = [os.path.join(target_dir, "settings.gradle"), app_properties_path]
    for base_root, _, new_rel in paths_to_move:
        scan_root = os.path.join(base_root, new_rel)
        if os.path.exists(scan_root):
            for root, _, files in os.walk(scan_root):
                for file in files:
                    if file.endswith((".java", ".xml", ".properties")):
                        files_to_update.append(os.path.join(root, file))

    for file_path in files_to_update:
        if file_path == build_gradle_path:
            continue  # already processed above granularly
        if not os.path.exists(file_path):
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "settings.gradle" in file_path:
            content = re.sub(
                r"rootProject\.name\s*=\s*['\"].*?['\"]",
                f"rootProject.name = '{project_name}'",
                content,
            )

        # Replace dot and slash variations across configs, java sources, changelogs, and views
        content = content.replace(old_package_dots, base_package)
        content = content.replace(old_package_slashes, new_package_property_slashes)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    # Enforce native Gradle Wrapper execution permissions
    gradlew_path = os.path.join(target_dir, "gradlew")
    if os.path.exists(gradlew_path):
        os.chmod(gradlew_path, 0o755)

    print("\n" + "=" * 60)
    print(f"[+] SUCCESS: Jmix project '{project_name}' successfully initialized!")
    print(f"[+] Target core locale: {lang_suffix}")
    print(f"[+] Run command: cd {project_name} && ./gradlew bootRun")
    print("=" * 60 + "\n")


# Function to diplay the help
def print_cli_help():
    """Displays CLI command user manual documentation."""
    print("\n🚀 JMIX CLI - UNIFIED COMMAND HELP")
    print("-" * 50)
    print("Initialize a new clean standard Jmix template:")
    print("  python jmix-cli.py init <project_name> <target_group> [locale]")
    print("  -> Example: python jmix-cli.py init onboarding com.florin ro_RO")
    print("\nGenerate layers from CSV schema (existing engine):")
    print("  Run without parameters inside a valid Jmix directory hierarchy")
    print("  to process traits.csv, entities.csv, and relations.csv schemas.")
    print("-" * 50 + "\n")


# Function to inject in existing User class
def inject_relations_into_existing_user(relations_list):
    user_java_path = (
        PROIECT_PATH + f"/src/main/java/{company_path}/{project_name}/entity/User.java"
    )

    if os.path.exists(user_java_path):
        content = open(user_java_path, "r", encoding="utf-8").read()
        modified = False

        for rel in relations_list:
            # Ignore inverse composition relationships (1:N) in this SQL step,
            # as they were automatically injected when the child entity (e.g., UserStep) was run
            if rel["type"] != "N:1":
                continue

            f_name = rel["field"]  # ex: department
            tgt_class = rel["target"]  # ex: Department

            # Prevent property duplication
            if f"private {tgt_class} {f_name};" not in content:
                print(f"   -> Injectin property @ManyToOne '{f_name}' in User.java")

                # Build the annotations and the Java field
                sql_col = f"{f_name.upper()}_ID"

                # Add @NotNull annotation if the relationship is marked as required in CSV
                validation_anno = ""
                if rel["mandatory"]:
                    validation_anno = "    @NotNull\n"
                    if "import jakarta.validation.constraints.NotNull;" not in content:
                        content = content.replace(
                            "public class User",
                            "import jakarta.validation.constraints.NotNull;\npublic class User",
                        )

                new_field = f'    @JoinColumn(name = "{sql_col}")\n{validation_anno}    @ManyToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'

                # Add specific getter and setter methods
                f_caps = (
                    f_name.upper() + f_name[1:]
                    if len(f_name) == 1
                    else f_name[0].upper() + f_name[1:]
                )
                new_methods = f"    public {tgt_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
                new_methods += f"    public void set{f_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

                # Inject the field and methods right before the LAST closing brace of the User.java file
                last_brace = content.rfind("}")
                if last_brace != -1:
                    content = (
                        content[:last_brace]
                        + new_field
                        + new_methods
                        + content[last_brace:]
                    )
                    modified = True

        if modified:
            with open(user_java_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("✨ [Java] User.java has been updated with the new relationships!")


# Function to inject into user-list-view.xml
def inject_list_ui_into_existing_user(relations_list):
    # Determine paths using the standard Jmix architecture layout
    xml_path = (
        PROIECT_PATH
        + f"/src/main/resources/{company_path}/{project_name}/view/user/user-list-view.xml"
    )

    if os.path.exists(xml_path):
        xml_content = open(xml_path, "r", encoding="utf-8").read()
        modified = False

        for rel in relations_list:
            if rel["type"] != "N:1":
                continue

            f_name = rel["field"]  # e.g., department

            # 1. Inject the property into the fetchPlan if it exists and is missing
            if (
                f'name="{f_name}"' not in xml_content
                and '<fetchPlan extends="_base">' in xml_content
            ):
                print(f"   -> Injecting fetchPlan property for '{f_name}'")
                fp_prop = (
                    f'                <property name="{f_name}" fetchPlan="_base"/>\n'
                )
                xml_content = xml_content.replace(
                    '<fetchPlan extends="_base">',
                    f'<fetchPlan extends="_base">\n{fp_prop}',
                )
                modified = True

            # 2. Inject the column inside the dataGrid <columns> tag
            if (
                f'property="{f_name}"' not in xml_content
                and "</columns>" in xml_content
            ):
                print(f"   -> Injecting UI column for '{f_name}'")
                ui_column = f'    <column property="{f_name}"/>\n'
                xml_content = xml_content.replace(
                    "</columns>", f"{ui_column}            </columns>"
                )
                modified = True

        if modified:
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_content)
            print("✨ [UI-List] user-list-view.xml successfully updated dynamically!")


def inject_detail_ui_into_existing_user(relations_list):
    xml_path = (
        PROIECT_PATH
        + f"/src/main/resources/{company_path}/{project_name}/view/user/user-detail-view.xml"
    )

    if os.path.exists(xml_path):
        xml_content = open(xml_path, "r", encoding="utf-8").read()

        accumulated_containers = ""
        accumulated_components = ""
        modified = False

        for rel in relations_list:
            # Clean and normalize the type string to bypass any trailing whitespaces or casing bugs
            rel_type = rel["type"].strip().upper()
            if rel_type != "N:1":
                continue

            f_name = rel["field"].strip()
            tgt_class = rel["target"].strip()
            tgt_lower = tgt_class.lower()
            container_id = f"{tgt_lower}sDc"

            # 1. Build the data collection block safely if it does not exist yet
            if (
                f'id="{container_id}"' not in xml_content
                and f'id="{container_id}"' not in accumulated_containers
            ):
                print(f"   -> Preparing data collection container for '{tgt_class}'")
                c_block = f'        <collection id="{container_id}" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
                c_block += '            <fetchPlan extends="_base"/>\n'
                c_block += f'            <loader id="{tgt_lower}sDl">\n'
                c_block += "                <query>\n"
                c_block += (
                    f"                    <![CDATA[select e from {tgt_class} e]]>\n"
                )
                c_block += "                </query>\n"
                c_block += "            </loader>\n"
                c_block += "        </collection>\n"
                accumulated_containers += c_block
                modified = True

            # 2. Build the visual combo component block safely if it does not exist yet
            component_id = f"{f_name}Field"
            if (
                f'id="{component_id}"' not in xml_content
                and f'id="{component_id}"' not in accumulated_components
            ):
                print(f"   -> Preparing entityComboBox component for field '{f_name}'")
                ui_block = f'            <entityComboBox id="{component_id}" property="{f_name}" itemsContainer="{container_id}"/>\n'
                accumulated_components += ui_block
                modified = True

        if modified:
            # Inject data containers right before the closing tag of the data block
            if accumulated_containers and "</data>" in xml_content:
                xml_content = xml_content.replace(
                    "</data>", f"{accumulated_containers}    </data>"
                )

            # Inject form components right before the closing tag of the formLayout block
            if accumulated_components and "</formLayout>" in xml_content:
                xml_content = xml_content.replace(
                    "</formLayout>", f"{accumulated_components}        </formLayout>"
                )

            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_content)
            print(
                "✨ [UI-Detail] user-detail-view.xml successfully updated with fields!"
            )


# Function to generate Roles from roles.csv file
def gen_jmix_resource_roles_from_csv():
    """
    Parses roles.csv and aggregates permissions by role code to generate
    strongly-typed Jmix 2.x ResourceRole interfaces with View, Menu, Entity,
    and EntityAttribute policies automatically.
    """
    roles_file = "roles.csv"
    if not os.path.exists(roles_file):
        print(f"[-] Error: {roles_file} configuration file not found.")
        sys.exit(1)

    # 1. Group rows by their unique role code to build a single file per role
    roles_data = {}
    with open(roles_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_code = row["code"].strip()
            if r_code not in roles_data:
                roles_data[r_code] = {
                    "name": row["name"].strip(),
                    "code": r_code,
                    "policies": [],
                }
            roles_data[r_code]["policies"].append(row)

    # 2. Iterate through each unique role and generate its interface definition
    for r_code, r_info in roles_data.items():
        role_name = r_info["name"]

        # Avoid duplicate "RoleRole" text structure in file mapping names
        raw_class_name = "".join([part.capitalize() for part in r_code.split("-")])
        if raw_class_name.endswith("Role"):
            class_name = raw_class_name
        else:
            class_name = raw_class_name + "Role"

        print(f"[*] Compiling Jmix ResourceRole: '{role_name}' -> {class_name}.java")

        # Jmix 2.x native security framework annotations imports tracking
        java_imports = {
            "import io.jmix.security.model.SecurityScope;",
            "import io.jmix.security.role.annotation.ResourceRole;",
            "import io.jmix.security.role.annotation.EntityPolicy;",
            "import io.jmix.security.model.EntityPolicyAction;",
            "import io.jmix.security.role.annotation.EntityAttributePolicy;",
            "import io.jmix.security.model.EntityAttributePolicyAction;",
            "import io.jmix.securityflowui.role.annotation.ViewPolicy;",
            "import io.jmix.securityflowui.role.annotation.MenuPolicy;",
        }

        java_policies_body = ""

        # 3. Process every individual entity policy row inside this specific role
        for policy in r_info["policies"]:
            ent_name = policy["entity_name"].strip()

            # Inject dynamic domain entity import path directly into the collection structure
            java_imports.add(f"import {COMPANY}.{project_name}.entity.{ent_name};")

            # --- VIEW & MENU POLICIES SECTION ---
            view_ids = []
            menu_ids = []

            if policy["ui_list"].strip().lower() == "true":
                view_ids.append(f'"{ent_name}.list"')
                menu_ids.append(f'"{ent_name}.list"')

            if policy["ui_detail"].strip().lower() == "true":
                view_ids.append(f'"{ent_name}.detail"')

            view_policy_annotation = ""
            if view_ids:
                ids_str = ", ".join(view_ids)
                view_policy_annotation = f"    @ViewPolicy(viewIds = {{{ids_str}}})\n"

            menu_policy_annotation = ""
            if menu_ids:
                m_ids_str = ", ".join(menu_ids)
                menu_policy_annotation = f"    @MenuPolicy(menuIds = {{{m_ids_str}}})\n"

            # --- CRUD ENTITY POLICIES SECTION ---
            crud_actions = []
            if policy["create"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.CREATE")
            if policy["read"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.READ")
            if policy["update"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.UPDATE")
            if policy["delete"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.DELETE")

            entity_policy_annotation = ""
            if crud_actions:
                actions_str = ", ".join(crud_actions)
                entity_policy_annotation = f"    @EntityPolicy(entityClass = {ent_name}.class, actions = {{{actions_str}}})\n"

            # --- ENTITY ATTRIBUTE POLICIES SECTION ---
            # Automatically grants access to all attributes using the wildcard "*" format tracker.
            attr_action = "EntityAttributePolicyAction.VIEW"
            if (
                "EntityPolicyAction.CREATE" in crud_actions
                or "EntityPolicyAction.UPDATE" in crud_actions
            ):
                attr_action = "EntityAttributePolicyAction.MODIFY"

            attribute_policy_annotation = f'    @EntityAttributePolicy(entityClass = {ent_name}.class, attributes = "*", action = {attr_action})\n'

            # Combine all four strategic annotations into a single cleanly formatted method block signature
            # Strictly formatting the method name via precise camelCase index conversion
            # e.g., "UserStep" -> "user" + "Step" + "Policies" -> "userStepPolicies"
            method_name = ent_name[0].lower() + ent_name[1:] + "Policies"
            java_policies_body += f"{view_policy_annotation}{menu_policy_annotation}{entity_policy_annotation}{attribute_policy_annotation}    void {method_name}();\n\n"

        # 4. Synthesize final clean Java blueprint template
        imports_block = "\n".join(sorted(list(java_imports)))

        java_content = f"""package {COMPANY}.{project_name}.security;

{imports_block}

@ResourceRole(name = "{role_name}", code = "{r_code}", scope = SecurityScope.UI)
public interface {class_name} {{

{java_policies_body}}}
"""

        # 5. Safe IO file writing process into correct Jmix structural folder
        target_dir = os.path.join(
            PROIECT_PATH, "src", "main", "java", company_path, project_name, "security"
        )
        os.makedirs(target_dir, exist_ok=True)

        file_path = os.path.join(target_dir, f"{class_name}.java")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(java_content)

    print(
        "✨ [Security] All parametric resource roles with attribute policies generated successfully!"
    )


def get_sorted_entities_by_dependency():
    """
    Analyzes entities.csv and relations.csv to sort entities topologically.
    Implements a safe cycle-detecting mechanism that handles self-referencing
    entities (like Task depending on Task) without hitting RecursionError.
    """
    if not os.path.exists("entities.csv"):
        return []

    # 1. Collect all unique entity names from entities.csv
    all_entities = set()
    with open("entities.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["entity_name"].strip()
            if name:
                all_entities.add(name)

    # 2. Build dependency tracker (who needs to be created before whom)
    dependencies = {ent: set() for ent in all_entities}

    if os.path.exists("relations.csv"):
        with open("relations.csv", mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = row["source_entity"].strip()
                tgt = row["target_entity"].strip()
                r_type = row["relation_type"].strip().upper()

                # CRITICAL SECURITY FIX: Ignore self-referencing entities (e.g., Task to Task)
                if src == tgt:
                    continue

                if src in dependencies and tgt in all_entities:
                    if r_type in ["N:1", "1:1"] or "1:N" in r_type:
                        dependencies[src].add(tgt)

    # 3. Topological Sort with Cycle & Loop Protection
    sorted_entities = []
    visiting = set()
    visited = set()

    def visit(entity):
        if entity in visiting:
            # Cycle detected (e.g., A -> B -> A). Break to avoid infinite loops
            return
        if entity in visited:
            return

        visiting.add(entity)

        # Process dependencies first, filtering out any accidental self-loops
        for dep in dependencies.get(entity, []):
            if dep != entity:
                visit(dep)

        visiting.remove(entity)
        visited.add(entity)
        sorted_entities.append(entity)

    # Process all parsed entities systematically in alphabetical order for determinism
    for entity in sorted(list(all_entities)):
        if entity not in visited:
            visit(entity)

    # Jmix system entities tracking fallback
    if "User" not in all_entities and os.path.exists("relations.csv"):
        # If User is used as a relation target but not defined in entities, add it
        sorted_entities.append("User")

    return sorted_entities


if __name__ == "__main__":
    # -----------------------------------------------------
    # 1. Project Initialization & Help Command Interception
    # -----------------------------------------------------
    if len(sys.argv) != 1 and sys.argv[1].lower() == "init":
        if len(sys.argv) == 2 or len(sys.argv) == 3:
            print("[-] Error: Missing required arguments.")
            print_cli_help()
            sys.exit(1)

        p_name = sys.argv[2]
        t_group = sys.argv[3]

        if len(sys.argv) >= 5:
            requested_lang = sys.argv[4]
        else:
            requested_lang = "en"

        cmd_init_project(p_name, t_group, requested_lang)
        sys.exit(0)

    elif len(sys.argv) != 1 and sys.argv[1].lower() in ["help", "--help", "-h"]:
        print_cli_help()
        sys.exit(0)

    # -----------------------------------------------------
    # 2. Main Execution Engine & Workspace Validation
    # -----------------------------------------------------
    print(f"[*] Run Jmix CLI engine generation on the current project: '{PROJECT}'...")

    if not PROJECT:
        print("[-] No valid Jmix project detected in this folder.")
        print_cli_help()
        sys.exit(1)

    if len(sys.argv) == 1:
        print("Usage: python3 jmix-cli.py [entity|ui-list|ui-detail|security] [Name]")
        sys.exit(1)

    action = sys.argv[1].lower()  # Ex: entity, ui-list, ui-detail, security

    # ======================================================================
    # GLOBAL ORCHESTRATION COMMANDS (Requires no individual Entity Name)
    # ======================================================================
    if action == "security":
        gen_jmix_resource_roles_from_csv()
        sys.exit(0)

    elif action == "gen-entities":
        print("[*] Launching automatic sequential entity generation engine...")
        ordered_list = get_sorted_entities_by_dependency()
        print(f"[*] Calculated generation sequence: {ordered_list}")

        for ent in ordered_list:
            if ent == "User":
                print(
                    "👤 System User detected in batch queue. Skipping base table creation..."
                )
                relations_list = get_relations_from_csv("relations.csv", "User")
                if relations_list:
                    gen_liquibase_relations_changelog("User", relations_list)
                    inject_relations_into_existing_user(relations_list)

                    # Ensure User translation runs safely via our parametric function
                    update_messages_entity(
                        project_dir=".",
                        base_package=COMPANY + "." + PROJECT,
                        entity_name="User",
                        traits_list=[],
                    )
            else:
                print(f"▶️ Automating Entity generation for: {ent}")
                traits = get_traits_from_csv("traits.csv", ent)
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)

                if fields_list:
                    gen_entity_mechanic_from_csv(
                        ent, fields_list, traits, relations_list
                    )
                    gen_liquibase_changelog_from_csv(ent, fields_list, traits)
                    if relations_list:
                        gen_liquibase_relations_changelog(ent, relations_list)

                    # DYNAMIC TRAITS COLLECTION: Parse field names from entities.csv for update_messages_entity
                    computed_traits_list = []
                    if os.path.exists("entities.csv"):
                        with open("entities.csv", mode="r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if row["entity_name"].strip() == ent.strip():
                                    computed_traits_list.append(
                                        row["field_name"].strip()
                                    )

                    if not computed_traits_list:
                        computed_traits_list = ["name"]

                    # TRIGGER MESSAGES: Generate parametric bilingv messages inside the orchestration loop!
                    update_messages_entity(
                        project_dir=".",
                        base_package=COMPANY + "." + PROJECT,
                        entity_name=ent,
                        traits_list=computed_traits_list,
                    )

                    # FIX: Trigger messages translation for EVERY entity automatically in the loop!
                    update_messages_entity(
                        project_dir=".",
                        base_package=COMPANY + "." + PROJECT,
                        entity_name=ent,
                        traits_list=computed_traits_list,
                    )
        sys.exit(0)

    elif action == "gen-ui":
        print("[*] Launching automatic global FlowUI generation engine...")
        ordered_list = get_sorted_entities_by_dependency()

        for ent in ordered_list:
            print(f"📺 Generating UI layouts (List & Detail) for: {ent}")
            if ent == "User":
                relations_list = get_relations_from_csv("relations.csv", "User")
                inject_list_ui_into_existing_user(relations_list)
                inject_detail_ui_into_existing_user(relations_list)
            else:
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)
                if fields_list:
                    gen_list_view_from_csv(ent, fields_list, relations_list)
                    gen_detail_view_from_csv(ent, fields_list, relations_list)
                    update_menu(ent)
        sys.exit(0)

    elif action == "build-all":
        print("\n" + "=" * 70)
        print("[⚡] TRIGGERING FULL ARCHITECTURE BUILD-ALL INDUSTRIAL SEQUENCE...")
        print("=" * 70)

        # 1. Resolve and calculate the deterministic dependency graph tree sequence
        ordered_list = get_sorted_entities_by_dependency()
        print(f"[*] Calculated execution flow pipeline: {ordered_list}\n")

        # ======================================================================
        # PHASE 1: SEQUENTIAL ENTITY & LIQUIBASE SCRIPTER SCATTERING
        # ======================================================================
        print("[⚡] PHASE 1: Scaffolding Data Models and Database Changelogs...")
        for ent in ordered_list:
            if ent == "User":
                print(
                    "👤 System User discovered in pipeline. Triggering surgical relationship infiltration..."
                )
                relations_list = get_relations_from_csv("relations.csv", "User")
                if relations_list:
                    gen_liquibase_relations_changelog("User", relations_list)
                    inject_relations_into_existing_user(relations_list)
                    update_messages_entity(".", COMPANY + "." + PROJECT, "User", [])
            else:
                print(f"   ▶️ Building Domain Model: {ent}")
                traits = get_traits_from_csv("traits.csv", ent)
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)

                if fields_list:
                    gen_entity_mechanic_from_csv(
                        ent, fields_list, traits, relations_list
                    )
                    gen_liquibase_changelog_from_csv(ent, fields_list, traits)
                    if relations_list:
                        gen_liquibase_relations_changelog(ent, relations_list)

                    # Calculate entity specific traits array properties from entities.csv layout
                    computed_traits_list = []
                    if os.path.exists("entities.csv"):
                        with open("entities.csv", mode="r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if row["entity_name"].strip() == ent.strip():
                                    computed_traits_list.append(
                                        row["field_name"].strip()
                                    )
                    if not computed_traits_list:
                        computed_traits_list = ["name"]

                    # Inject bilingv localization assets dynamically
                    update_messages_entity(
                        ".", COMPANY + "." + PROJECT, ent, computed_traits_list
                    )

        # ======================================================================
        # PHASE 2: AUTOMATED FLOWUI STRUCTURAL VIEW ARCHITECTURING
        # ======================================================================
        print(
            "\n[⚡] PHASE 2: Architecturing FlowUI Screen Descriptors & Controllers..."
        )
        for ent in ordered_list:
            print(f"   📺 Compiling Layout XML and Java Views for: {ent}")
            if ent == "User":
                relations_list = get_relations_from_csv("relations.csv", "User")
                if relations_list:
                    inject_list_ui_into_existing_user(relations_list)
                    inject_detail_ui_into_existing_user(relations_list)
            else:
                # Dynamically fetch ONLY the clean, specific rows for the current entity
                # This guarantees the dictionary contains the correct keys ('field_name', etc.)
                current_fields = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)

                if current_fields:
                    gen_list_view_from_csv(ent, current_fields, relations_list)
                    # Passing current_fields instead of the corrupted global fields_list variable
                    gen_detail_view_from_csv(ent, current_fields, relations_list)
                    update_menu(ent)

        # ======================================================================
        # PHASE 3: PARAMETRIC CONTEXT ACCESS SECURITY ROLE Blueprints
        # ======================================================================
        print(
            "\n[⚡] PHASE 3: Compiling Access Control Security Roles Interface blueprinter..."
        )
        gen_jmix_resource_roles_from_csv()

        print("\n" + "=" * 70)
        print("[⚡] SUCCESS: Project scaffolding built perfectly from CSV maps!")
        print("=" * 70 + "\n")
        sys.exit(0)

    # ======================================================================
    # ENTITY SPECIFIC OPERATIONS (Requires exact Entity Name argument)
    # ======================================================================
    if len(sys.argv) == 2:
        print("[-] Error: Missing required Entity Name parameter.")
        print("Usage: python3 jmix-cli.py [entity|ui-list|ui-detail] [Name]")
        sys.exit(1)

    name = sys.argv[2]  # Ex: Department, UserStep, User

    if action == "entity":
        # Verify if the current entity is the Jmix system user
        if name == "User":
            print("👤 [System User] Triggering relational infiltration...")
            relations_list = get_relations_from_csv("relations.csv", "User")

            if relations_list:
                gen_liquibase_relations_changelog("User", relations_list)
                inject_relations_into_existing_user(relations_list)
                update_messages_entity(
                    project_dir=".",
                    base_package=COMPANY + "." + PROJECT,
                    entity_name="User",
                    traits_list=[],
                )
            else:
                print(
                    "   -> No relationships were configured for the User in relations.csv."
                )
        else:
            # Fetch data from the normalized files in the CSV files
            traits = get_traits_from_csv("traits.csv", name)
            fields_list = get_entities_from_csv("entities.csv", name)
            relations_list = get_relations_from_csv("relations.csv", name)

            if not fields_list:
                print(f" ⚠ No fields found for the entity '{name}' in entities.csv")
                sys.exit(1)

            print(f"Generating Entity {name} from CSV architecture...")
            gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list)

            # PARAMETRIC EXTRACTION: We read only the fields of this entity from entities.csv
            computed_traits_list = []
            if os.path.exists("entities.csv"):
                with open("entities.csv", mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Strict condition: if the row belongs to the current entity (e.g., Step)
                        if row["entity_name"].strip() == name.strip():
                            computed_traits_list.append(row["field_name"].strip())

            # If for some reason the list is empty, we put a safety fallback
            if not computed_traits_list:
                computed_traits_list = ["name"]

            # NOW CALLING THE FUNCTION, PASSING THE ACTUAL LIST CALCULATED FROM CSV!
            update_messages_entity(
                project_dir=".",
                base_package=COMPANY + "." + PROJECT,
                entity_name=name,
                traits_list=computed_traits_list,
            )
            gen_liquibase_changelog_from_csv(name, fields_list, traits)
            if relations_list:
                gen_liquibase_relations_changelog(name, relations_list)

    elif action == "ui-list":
        if name == "User":
            print("[*] Triggering FlowUI List View infiltration for system User...")
            relations_list = get_relations_from_csv("relations.csv", "User")
            inject_list_ui_into_existing_user(relations_list)
        else:
            fields_list = get_entities_from_csv("entities.csv", name)
            relations_list = get_relations_from_csv("relations.csv", name)
            if not fields_list:
                print(
                    f" ⚠️ Error: Fields for entity '{name}' do not exist in entities.csv"
                )
                sys.exit(1)
            gen_list_view_from_csv(name, fields_list, relations_list)
            update_menu(name)

    elif action == "ui-detail":
        if name == "User":
            print("[*] Triggering FlowUI Detail View infiltration for system User...")
            relations_list = get_relations_from_csv("relations.csv", "User")
            inject_detail_ui_into_existing_user(relations_list)
        else:
            fields_list = get_entities_from_csv("entities.csv", name)
            relations_list = get_relations_from_csv("relations.csv", name)
            if not fields_list:
                print(f" ⚠️ Error: Fields for '{name}' do not exist in entities.csv")
                sys.exit(1)
            gen_detail_view_from_csv(name, fields_list, relations_list)

    else:
        print(
            f" ⚠️ Unknown action: '{action}'. Use entity, ui-list, ui-detail or security."
        )
        sys.exit(1)
