import os
from typing import Any

from jmix_cli.utils import COMPANY, PROIECT_PATH, company_path, inject_import_if_missing, project_name


def inject_relations_into_existing_user(relations_list: list[dict[str, Any]]) -> None:
    user_java_path = (
        PROIECT_PATH + f"/src/main/java/{company_path}/{project_name}/entity/User.java"
    )
    if not os.path.exists(user_java_path):
        return
    content = open(user_java_path, "r", encoding="utf-8").read()
    modified = False
    for rel in relations_list:
        if rel["type"] != "N:1":
            continue
        f_name = rel["field"]
        tgt_class = rel["target"]
        if f"private {tgt_class} {f_name};" not in content:
            print(f"   -> Injectin property @ManyToOne '{f_name}' in User.java")
            sql_col = f"{f_name.upper()}_ID"
            validation_anno = ""
            if rel["mandatory"]:
                validation_anno = "    @NotNull\n"
                if "import jakarta.validation.constraints.NotNull;" not in content:
                    content = content.replace(
                        "public class User",
                        "import jakarta.validation.constraints.NotNull;\npublic class User",
                    )
            new_field = f'    @JoinColumn(name = "{sql_col}")\n{validation_anno}    @ManyToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
            f_caps = f_name[0].upper() + f_name[1:] if len(f_name) > 1 else f_name.upper()
            new_methods = f"    public {tgt_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
            new_methods += f"    public void set{f_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
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
