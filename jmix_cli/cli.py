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

import csv
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jmix_cli.utils import COMPANY, PROIECT_PATH, PROJECT, company_path, project_name
from jmix_cli.entity import (
    get_entities_from_csv,
    get_relations_from_csv,
    get_sorted_entities_by_dependency,
    get_traits_from_csv,
    gen_entity_mechanic_from_csv,
)
from jmix_cli.liquibase import gen_liquibase_relations_changelog
from jmix_cli.liquibase import gen_liquibase_changelog_from_csv
from jmix_cli.views import (
    gen_detail_view_from_csv,
    gen_list_view_from_csv,
    inject_detail_ui_into_existing_user,
    inject_list_ui_into_existing_user,
)
from jmix_cli.security import gen_jmix_resource_roles_from_csv
from jmix_cli.i18n import update_messages_entity
from jmix_cli.user import inject_relations_into_existing_user


def _generate_single_entity(name: str) -> None:
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
                relations_list=relations_list,
            )
        else:
            print("   -> No relationships were configured for the User in relations.csv.")
    else:
        traits = get_traits_from_csv("traits.csv", name)
        fields_list = get_entities_from_csv("entities.csv", name)
        relations_list = get_relations_from_csv("relations.csv", name)
        if not fields_list:
            print(f" ⚠ No fields found for the entity '{name}' in entities.csv")
            sys.exit(1)
        print(f"Generating Entity {name} from CSV architecture...")
        gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list)
        computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(open("entities.csv")) if row["entity_name"].strip() == name.strip()]
        if not computed_traits_list:
            computed_traits_list = ["name"]
        update_messages_entity(
            project_dir=".",
            base_package=COMPANY + "." + PROJECT,
            entity_name=name,
            traits_list=computed_traits_list,
            relations_list=relations_list,
        )
        gen_liquibase_changelog_from_csv(name, fields_list, traits)
        if relations_list:
            gen_liquibase_relations_changelog(name, relations_list)


def _finalize_composition_relationships() -> None:
    print("\n[⚡] PHASE 2.5: Finalizing Composition relationships...")
    if not os.path.exists("relations.csv"):
        return
    with open("relations.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_type = row["relation_type"].strip()
            if r_type != "COMPOSITION_1:1":
                continue
            src_class = row["source_entity"].strip()
            tgt_class = row["target_entity"].strip()
            f_name = row["field_name"].strip()
            src_file_path = f"src/main/java/{company_path}/{project_name}/entity/{src_class}.java"
            tgt_file_path = f"src/main/java/{company_path}/{project_name}/entity/{tgt_class}.java"
            if not os.path.exists(src_file_path) or not os.path.exists(tgt_file_path):
                continue
            with open(src_file_path, "r", encoding="utf-8") as sf:
                src_content = sf.read()
            if f"private {tgt_class} {f_name};" not in src_content:
                print(f" 🔗 Finalizing @Composition 1:1 in {src_class}")
                sql_fk_col = f"{f_name.upper()}_ID"
                comp_field = f'    @Composition\n    @JoinColumn(name = "{sql_fk_col}")\n    @OneToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
                comp_caps = f_name[0].upper() + f_name[1:]
                comp_methods = f"    public {tgt_class} get{comp_caps}() {{\n        return {f_name};\n    }}\n\n"
                comp_methods += f"    public void set{comp_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
                src_content = inject_import_if_missing(src_content, "io.jmix.core.metamodel.annotation.Composition")
                src_content = inject_import_if_missing(src_content, "jakarta.persistence.OneToOne")
                src_content = inject_import_if_missing(src_content, "jakarta.persistence.JoinColumn")
                src_content = inject_import_if_missing(src_content, "jakarta.persistence.FetchType")
                if "    public UUID getId()" in src_content:
                    src_content = src_content.replace(
                        "    public UUID getId()",
                        f"{comp_field}    public UUID getId()",
                    )
                last_brace = src_content.rfind("}")
                if last_brace != -1:
                    src_content = (
                        src_content[:last_brace]
                        + "\n"
                        + comp_methods
                        + src_content[last_brace:]
                    )
                with open(src_file_path, "w", encoding="utf-8") as sf:
                    sf.write(src_content)

            with open(tgt_file_path, "r", encoding="utf-8") as tf:
                tgt_content = tf.read()
            inv_field_name = src_class[0].lower() + src_class[1:]
            if f"private {src_class} {inv_field_name};" not in tgt_content:
                print(f" 🔗 Finalizing inverse 1:1 in {tgt_class}")
                inv_field = f'    @OneToOne(fetch = FetchType.LAZY, mappedBy = "{f_name}")\n    private {src_class} {inv_field_name};\n\n'
                inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
                inv_methods = f"    public {src_class} get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
                inv_methods += f"    public void set{inv_caps}({src_class} {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
                tgt_content = inject_import_if_missing(tgt_content, "jakarta.persistence.OneToOne")
                tgt_content = inject_import_if_missing(tgt_content, "jakarta.persistence.FetchType")
                if "    public UUID getId()" in tgt_content:
                    tgt_content = tgt_content.replace(
                        "    public UUID getId()",
                        f"{inv_field}    public UUID getId()",
                    )
                last_brace = tgt_content.rfind("}")
                if last_brace != -1:
                    tgt_content = (
                        tgt_content[:last_brace]
                        + "\n"
                        + inv_methods
                        + tgt_content[last_brace:]
                    )
                with open(tgt_file_path, "w", encoding="utf-8") as tf:
                    tf.write(tgt_content)

            timestamp_id_fk = datetime.now().strftime("%Y%m%d%H%M%S")
            fk_changelog = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
    objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
    <changeSet id="{timestamp_id_fk}-add-fk-{f_name}" author="{project_name}">
        <addForeignKeyConstraint baseTableName="{src_class.upper()}"
                                  baseColumnNames="{f_name.upper()}_ID"
                                  constraintName="FK_{src_class.upper()}_ON_{f_name}"
                                  referencedTableName="{tgt_class.upper()}"
                                  referencedColumnNames="ID"/>
    </changeSet>
</databaseChangeLog>
"""
            current_year = datetime.now().strftime("%Y")
            current_month = datetime.now().strftime("%m")
            fk_dir = f"src/main/resources/{company_path}/{project_name}/liquibase/changelog/{current_year}/{current_month}"
            os.makedirs(fk_dir, exist_ok=True)
            fk_file = f"{fk_dir}/{timestamp_id_fk}-03-fk-{src_class.lower()}.xml"
            with open(fk_file, "w", encoding="utf-8") as fk_f:
                fk_f.write(fk_changelog)
            print(f" 🔗 Added FK constraint changelog: {fk_file}")
    print("\n✅ Entity generation completed!")


def _update_menu(n: str) -> None:
    print("Updating menu.xml for " + n + "...")
    menu_path = (
        PROIECT_PATH + f"/src/main/resources/{company_path}/{project_name}/menu.xml"
    )
    if not os.path.exists(menu_path):
        print(f"⚠️ I not found the file menu.xml in the path {menu_path}!")
        return
    menu_item = f'    <item view="{n}.list" title="msg://{COMPANY}.{project_name}.view.{n.lower()}/{n.lower()}ListView.title"/>\n'
    with open(menu_path, "r", encoding="utf-8") as f:
        content = f.read()
    if ('view="' + n + '.list"') in content:
        print("ℹ️ View " + n + ".list allready exist in menu.")
        return
    if "</menu>" in content:
        new_content = content.replace("</menu>", menu_item + "</menu>")
        with open(menu_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Menu injected successfully into menu.xml!")
    else:
        print("⚠️ Invalid structure for menu.xml (missing closing </menu> tag)!")


def cmd_init_project(project_name: str, target_group: str, lang_input: str = "en") -> None:
    base_package = f"{target_group.strip().strip('.')}.{project_name.strip().strip('.')}"
    repo_url = "https://github.com/florintanasa/jmix-ai-template"
    current_dir = os.getcwd()
    target_dir = os.path.join(current_dir, project_name)
    lang_suffix = lang_input.strip()
    lang_key_for_map = lang_suffix

    print(f"\n[*] Initializing New Jmix Project: '{project_name}'")
    print(f"[*] Group ID:                 {target_group}")
    print(f"[*] Generated Base Package:   {base_package}")
    print(f"[*] Requested Locale:         {lang_suffix}")
    print("-" * 60)

    if os.path.exists(target_dir):
        print(f"[-] Critical Error: Folder '{project_name}' already exists in this directory.")
        sys.exit(1)

    print("[*] Step 1: Downloading Jmix starter template...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "-b", "v2.8.2", repo_url, project_name],
            check=True,
        )
    except Exception as e:
        print(f"[-] Critical Error executing Git clone: {e}")
        sys.exit(1)

    shutil.rmtree(os.path.join(target_dir, ".git"), ignore_errors=True)
    print("[+] Git template history cleared successfully.")

    old_package_dots = "io.jmix.tempate"
    old_package_slashes = "io/jmix/tempate"
    new_package_slashes = os.path.join(*base_package.split("."))
    new_package_property_slashes = base_package.replace(".", "/")

    paths_to_move = [
        (os.path.join(target_dir, "src", "main", "java"), old_package_slashes, new_package_slashes),
        (os.path.join(target_dir, "src", "test", "java"), old_package_slashes, new_package_slashes),
        (os.path.join(target_dir, "src", "main", "resources"), old_package_slashes, new_package_slashes),
    ]

    print("[*] Step 2: Refactoring structural Java source layers and XML resources...")
    for base_root, old_rel, new_rel in paths_to_move:
        src_dir = os.path.join(base_root, old_rel)
        dst_dir = os.path.join(base_root, new_rel)
        if os.path.exists(src_dir):
            os.makedirs(dst_dir, exist_ok=True)
            for item in os.listdir(src_dir):
                shutil.move(os.path.join(src_dir, item), os.path.join(dst_dir, item))
            shutil.rmtree(os.path.join(base_root, "io"), ignore_errors=True)

    print("[*] Step 3: Injecting metadata and localization configuration dependencies...")
    build_gradle_path = os.path.join(target_dir, "build.gradle")
    app_properties_path = os.path.join(target_dir, "src", "main", "resources", "application.properties")

    JMIX_TRANSLATIONS_MAP = {
        "ar": "ar", "ckb": "ckb", "de": "de", "el": "el", "es": "es", "fr": "fr",
        "fr_fr": "fr", "it": "it", "nl": "nl", "pt": "pt-br", "pt_BR": "pt-br",
        "ro": "ro", "ro_RO": "ro", "ro_MD": "ro", "ru": "ru", "tr": "tr", "zh": "zh-cn", "zh_CN": "zh-cn",
    }

    if os.path.exists(build_gradle_path):
        with open(build_gradle_path, "r", encoding="utf-8") as f:
            gradle_content = f.read()
        gradle_content = gradle_content.replace(
            r"group\s*=\s*['\"].*?['\"]", f"group = '{target_group}'"
        )
        if lang_key_for_map != "en" and lang_key_for_map in JMIX_TRANSLATIONS_MAP:
            addon_suffix = JMIX_TRANSLATIONS_MAP[lang_key_for_map]
            addon_dependency = f"\n    implementation 'io.jmix.translations:jmix-translations-{addon_suffix}'"
            if "dependencies {" in gradle_content:
                gradle_content = gradle_content.replace(
                    "dependencies {",
                    f"dependencies {{{addon_dependency} // Automatically configured via Jmix CLI",
                )
                print(f"[+] Injected localization add-on dependency: jmix-translations-{addon_suffix}")
        with open(build_gradle_path, "w", encoding="utf-8") as f:
            f.write(gradle_content)

    if os.path.exists(app_properties_path):
        with open(app_properties_path, "r", encoding="utf-8") as f:
            prop_content = f.read()
        if "jmix.core.available-locales" in prop_content:
            if lang_key_for_map != "en":
                prop_content = prop_content.replace(
                    r"jmix\.core\.available-locales\s*=\s*(.*)",
                    f"jmix.core.available-locales = \\1,{lang_suffix}",
                )
                print(f"[+] Updated active core locales property: en,{lang_suffix}")
        else:
            locales_line = "\njmix.core.available-locales = en"
            if lang_key_for_map != "en":
                locales_line += f",{lang_suffix}"
            prop_content += locales_line
        with open(app_properties_path, "w", encoding="utf-8") as f:
            f.write(prop_content)

    if lang_key_for_map != "en":
        msg_dir = os.path.join(target_dir, "src", "main", "resources", new_package_slashes)
        os.makedirs(msg_dir, exist_ok=True)
        template_eng_msg_path = os.path.join(msg_dir, "messages_en.properties")
        base_fallback_msg_path = os.path.join(msg_dir, "messages.properties")
        custom_messages_path = os.path.join(msg_dir, f"messages_{lang_suffix}.properties")
        if os.path.exists(template_eng_msg_path) and not os.path.exists(base_fallback_msg_path):
            shutil.copy2(template_eng_msg_path, base_fallback_msg_path)
            print("[+] Generated standard base fallback file: messages.properties")
        if not os.path.exists(custom_messages_path):
            if os.path.exists(template_eng_msg_path):
                shutil.copy2(template_eng_msg_path, custom_messages_path)
                with open(custom_messages_path, "r+", encoding="utf-8") as f:
                    content = f.read()
                    f.seek(0, 0)
                    f.write(
                        f"# Automatically initialized as a bilingual twin for: {lang_suffix}\n"
                        + content
                    )
                print(f"[+] Created localized bundle twin with English base: messages_{lang_suffix}.properties")
            else:
                with open(custom_messages_path, "w", encoding="utf-8") as f:
                    f.write(f"# Custom localization translations properties file for: {lang_suffix}\n")
                print(f"[+] Initialized empty bundle (messages_en.properties was missing): messages_{lang_suffix}.properties")

    files_to_update = [os.path.join(target_dir, "settings.gradle"), app_properties_path]
    for base_root, _, new_rel in paths_to_move:
        scan_root = os.path.join(base_root, new_rel)
        if os.path.exists(scan_root):
            for root, _, files in os.walk(scan_root):
                for file in files:
                    if file.endswith((".java", ".xml", ".properties")):
                        files_to_update.append(os.path.join(root, file))

    for file_path in files_to_update:
        if file_path == build_gradle_path or not os.path.exists(file_path):
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "settings.gradle" in file_path:
            content = content.replace(
                r"rootProject\.name\s*=\s*['\"].*?['\"]",
                f"rootProject.name = '{project_name}'",
            )
        content = content.replace(old_package_dots, base_package)
        content = content.replace(old_package_slashes, new_package_property_slashes)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    gradlew_path = os.path.join(target_dir, "gradlew")
    if os.path.exists(gradlew_path):
        os.chmod(gradlew_path, 0o755)

    print("[*] Step 3: Initializing a fresh Git repository...")
    try:
        subprocess.run(["git", "init"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=target_dir, check=True)
        print("✅ Project initialized successfully with a fresh Git history!")
    except subprocess.CalledProcessError:
        print("Warning: Template was cloned, but failed to initialize fresh Git repository automatically.")

    print("\n" + "=" * 60)
    print(f"[+] SUCCESS: Jmix project '{project_name}' successfully initialized!")
    print(f"[+] Target core locale: {lang_suffix}")
    print(f"[+] Run command: cd {project_name} && ./gradlew bootRun")
    print("=" * 60 + "\n")


def print_cli_help() -> None:
    print("\n🚀 JMIX CLI - UNIFIED COMMAND HELP")
    print("-" * 50)
    print("Initialize a new clean standard Jmix template:")
    print("  python jmix-cli.py init <project_name> <target_group> [locale]")
    print("  -> Example: python jmix-cli.py init onboarding com.florin ro_RO")
    print("\nGenerate layers from CSV schema (existing engine):")
    print("  Run without parameters inside a valid Jmix directory hierarchy")
    print("  to process traits.csv, entities.csv, and relations.csv schemas.")
    print("-" * 50 + "\n")


def main() -> None:
    if len(sys.argv) != 1 and sys.argv[1].lower() == "init":
        if len(sys.argv) == 2 or len(sys.argv) == 3:
            print("[-] Error: Missing required arguments.")
            print_cli_help()
            sys.exit(1)
        p_name = sys.argv[2]
        t_group = sys.argv[3]
        requested_lang = sys.argv[4] if len(sys.argv) >= 5 else "en"
        cmd_init_project(p_name, t_group, requested_lang)
        sys.exit(0)

    elif len(sys.argv) != 1 and sys.argv[1].lower() in ["help", "--help", "-h"]:
        print_cli_help()
        sys.exit(0)

    print(f"[*] Run Jmix CLI engine generation on the current project: '{PROJECT}'...")

    if not PROJECT:
        print("[-] No valid Jmix project detected in this folder.")
        print_cli_help()
        sys.exit(1)

    if len(sys.argv) == 1:
        print("=" * 70)
        print("JMIX CLI - Command Reference")
        print("=" * 70)
        print("Available commands:")
        print("  python3 jmix-cli.py entity-all   - Generate ALL entities + liquibase")
        print("  python3 jmix-cli.py entity <Name> - Generate single entity")
        print("  python3 jmix-cli.py security      - Generate security roles")
        print("  python3 jmix-cli.py ui-list-all   - Generate ALL list views")
        print("  python3 jmix-cli.py ui-list <Name> - Generate single list view")
        print("  python3 jmix-cli.py ui-detail-all - Generate ALL detail views")
        print("  python3 jmix-cli.py ui-detail <Name> - Generate single detail view")
        print("  python3 jmix-cli.py build-all     - Full generation (all phases)")
        print("=" * 70)
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "security":
        gen_jmix_resource_roles_from_csv()
        sys.exit(0)

    elif action == "entity-all":
        print("[*] Launching ENTITY-ONLY generation for ALL entities...")
        ordered_list = get_sorted_entities_by_dependency()
        print(f"[*] Calculated generation sequence: {ordered_list}")
        for ent in ordered_list:
            if ent == "User":
                relations_list = get_relations_from_csv("relations.csv", "User")
                if relations_list:
                    gen_liquibase_relations_changelog("User", relations_list)
                    inject_relations_into_existing_user(relations_list)
                    update_messages_entity(
                        project_dir=".",
                        base_package=COMPANY + "." + PROJECT,
                        entity_name="User",
                        traits_list=[],
                        relations_list=relations_list,
                    )
            else:
                traits = get_traits_from_csv("traits.csv", ent)
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)
                if fields_list:
                    gen_entity_mechanic_from_csv(ent, fields_list, traits, relations_list)
                    gen_liquibase_changelog_from_csv(ent, fields_list, traits)
                    if relations_list:
                        gen_liquibase_relations_changelog(ent, relations_list)
                    computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(open("entities.csv")) if row["entity_name"].strip() == ent.strip()]
                    if not computed_traits_list:
                        computed_traits_list = ["name"]
                    update_messages_entity(
                        ".", COMPANY + "." + PROJECT, ent, computed_traits_list, relations_list
                    )
        _finalize_composition_relationships()
        sys.exit(0)

    elif action == "ui-list-all":
        print("[*] Launching UI-LIST generation for ALL entities...")
        ordered_list = get_sorted_entities_by_dependency()
        for ent in ordered_list:
            fields_list = get_entities_from_csv("entities.csv", ent)
            relations_list = get_relations_from_csv("relations.csv", ent)
            if fields_list:
                gen_list_view_from_csv(ent, fields_list, relations_list)
        print("\n✅ UI List views generation completed!")
        sys.exit(0)

    elif action == "ui-detail-all":
        print("[*] Launching UI-DETAIL generation for ALL entities...")
        ordered_list = get_sorted_entities_by_dependency()
        for ent in ordered_list:
            fields_list = get_entities_from_csv("entities.csv", ent)
            relations_list = get_relations_from_csv("relations.csv", ent)
            if fields_list:
                gen_detail_view_from_csv(ent, fields_list, relations_list)
        print("\n✅ UI Detail views generation completed!")
        sys.exit(0)

    elif action == "build-all":
        print("\n" + "=" * 70)
        print("[⚡] TRIGGERING FULL ARCHITECTURE BUILD-ALL INDUSTRIAL SEQUENCE...")
        print("=" * 70)
        ordered_list = get_sorted_entities_by_dependency()
        print(f"[*] Calculated execution flow pipeline: {ordered_list}\n")

        print("[⚡] PHASE 1: Scaffolding Data Models and Database Changelogs...")
        for ent in ordered_list:
            if ent == "User":
                print("👤 System User discovered in pipeline. Triggering surgical relationship infiltration...")
                relations_list = get_relations_from_csv("relations.csv", "User")
                if relations_list:
                    gen_liquibase_relations_changelog("User", relations_list)
                    inject_relations_into_existing_user(relations_list)
                    update_messages_entity(".", COMPANY + "." + PROJECT, "User", [], relations_list)
            else:
                print(f"   ▶️ Building Domain Model: {ent}")
                traits = get_traits_from_csv("traits.csv", ent)
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)
                if fields_list:
                    gen_entity_mechanic_from_csv(ent, fields_list, traits, relations_list)
                    gen_liquibase_changelog_from_csv(ent, fields_list, traits)
                    if relations_list:
                        gen_liquibase_relations_changelog(ent, relations_list)
                    computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(open("entities.csv")) if row["entity_name"].strip() == ent.strip()]
                    if not computed_traits_list:
                        computed_traits_list = ["name"]
                    update_messages_entity(".", COMPANY + "." + PROJECT, ent, computed_traits_list, relations_list)

        _finalize_composition_relationships()

        print("\n[⚡] PHASE 2: Architecturing FlowUI Screen Descriptors & Controllers...")
        for ent in ordered_list:
            print(f"   📺 Compiling Layout XML and Java Views for: {ent}")
            if ent == "User":
                relations_list = get_relations_from_csv("relations.csv", "User")
                if relations_list:
                    inject_list_ui_into_existing_user(relations_list)
                    inject_detail_ui_into_existing_user(relations_list)
            else:
                current_fields = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)
                if current_fields:
                    gen_list_view_from_csv(ent, current_fields, relations_list)
                    gen_detail_view_from_csv(ent, current_fields, relations_list)
                    _update_menu(ent)

        print("\n[⚡] PHASE 3: Compiling Access Control Security Roles Interface blueprinter...")
        gen_jmix_resource_roles_from_csv()

        print("\n" + "=" * 70)
        print("[⚡] SUCCESS: Project scaffolding built perfectly from CSV maps!")
        print("=" * 70 + "\n")
        sys.exit(0)

    if len(sys.argv) == 2:
        print("[-] Error: Missing required Entity Name parameter.")
        print("Usage: python3 jmix-cli.py [entity|ui-list|ui-detail] [Name]")
        sys.exit(1)

    name = sys.argv[2]

    if action == "entity":
        _generate_single_entity(name)

    elif action == "ui-list":
        if name == "User":
            print("[*] Triggering FlowUI List View infiltration for system User...")
            relations_list = get_relations_from_csv("relations.csv", "User")
            inject_list_ui_into_existing_user(relations_list)
        else:
            fields_list = get_entities_from_csv("entities.csv", name)
            relations_list = get_relations_from_csv("relations.csv", name)
            if not fields_list:
                print(f" ⚠️ Error: Fields for entity '{name}' do not exist in entities.csv")
                sys.exit(1)
            gen_list_view_from_csv(name, fields_list, relations_list)
            _update_menu(name)

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
        print(f" ⚠️ Unknown action: '{action}'. Use entity, ui-list, ui-detail or security.")
        sys.exit(1)


if __name__ == "__main__":
    main()
