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

from jmix_cli.core.csv import validate_csv_path
from jmix_cli.exceptions import InvalidCsvError


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


def _build_imports_and_fields(fields_list: list[dict[str, Any]], traits: dict[str, Any]) -> tuple[str, str, str, str, set[str]]:
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

        java_business_fields += f"{instance_name_annotation}{validation_annotation}    @Column({column_props})\n    private {f_type} {f_name}{' = false' if f_type.lower() == 'boolean' and field.get('mandatory') else ''};\n\n"

        f_caps = f_name[0].upper() + f_name[1:]
        java_business_methods += f"    public {f_type} get{f_caps}() {{\n        return {f_name};\n    }}\n\n    public void set{f_caps}({f_type} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

    return java_traits_fields, java_traits_methods, java_business_fields, java_business_methods, dinamic_imports
