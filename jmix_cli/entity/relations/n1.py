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

from jmix_cli.core.java import inject_import_if_missing
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name


def build_n1_fields(rel: dict[str, str]) -> tuple[str, str, set[str]]:
    f_name = rel["field"]
    tgt_class = rel["target"]
    sql_col = f"{f_name.upper()}_ID"
    validation_anno = ""
    dinamic_imports: set[str] = set()
    if rel["mandatory"]:
        validation_anno = "    @NotNull\n"
        dinamic_imports.add("import jakarta.validation.constraints.NotNull;")
    join_col = f'@JoinColumn(name = "{sql_col}", nullable = false)' if rel["mandatory"] else f'@JoinColumn(name = "{sql_col}")'
    field = f'    {join_col}\n{validation_anno}    @ManyToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
    caps = f_name[0].upper() + f_name[1:] if len(f_name) > 1 else f_name.upper()
    methods = f"    public {tgt_class} get{caps}() {{\n        return {f_name};\n    }}\n\n"
    methods += f"    public void set{caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
    dinamic_imports.add("import jakarta.persistence.ManyToOne;")
    dinamic_imports.add("import jakarta.persistence.JoinColumn;")
    dinamic_imports.add("import jakarta.persistence.FetchType;")
    return field, methods, dinamic_imports
