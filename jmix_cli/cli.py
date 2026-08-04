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
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from jmix_cli.exceptions import JmixCliError, ConfigurationError, GenerationError, UserInputError
from jmix_cli.utils import get_logger
from jmix_cli.utils import COMPANY, PROIECT_PATH, PROJECT, company_path, inject_import_if_missing, project_name, update_checkbox_required_state_property, validate_csv_path
from jmix_cli.entity import (
    _inject_composition_into_parent,
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
    inject_nn_grid_into_inverse_entity,
    inject_nn_datagrid_into_source_entity,
)
from jmix_cli.security import gen_jmix_resource_roles_from_csv
from jmix_cli.i18n import update_messages_entity
from jmix_cli.user import inject_relations_into_existing_user
from jmix_cli.migrate import migrate_entity, migrate_all_entities

logger = get_logger("jmix_cli.cli")


def _read_project_name(settings_path: Path) -> str | None:
    if not settings_path.exists():
        return None
    text = settings_path.read_text(encoding="utf-8")
    m = re.search(r"""rootProject\.name\s*=\s*(['"])(.*?)\1""", text)
    return m.group(2) if m else None


def _read_company_name(build_path: Path) -> str | None:
    if not build_path.exists():
        return None
    text = build_path.read_text(encoding="utf-8")
    m = re.search(r"""group\s*=\s*(['"])(.*?)\1""", text)
    return m.group(2) if m else None


DRY_RUN_SERVER_PORT = "0"


def _ensure_dry_run_server_port(properties_path: Path) -> None:
    if not properties_path.exists():
        return
    content = properties_path.read_text(encoding="utf-8")
    if "server.port=" in content:
        content = re.sub(r"server\.port\s*=\s*.*", f"server.port={DRY_RUN_SERVER_PORT}", content)
    else:
        content += f"\nserver.port={DRY_RUN_SERVER_PORT}\n"
    properties_path.write_text(content, encoding="utf-8")


def _copy_project_to_temp() -> Path:
    src = Path.cwd()
    temp_dir = Path(tempfile.mkdtemp(prefix="jmix-dry-run-"))
    logger.info(f"[dry-run] Creating temporary project at: {temp_dir}")

    dirs_to_copy = ["gradle"]
    files_to_copy = [
        "build.gradle",
        "settings.gradle",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "entities.csv",
        "relations.csv",
        "traits.csv",
        "roles.csv",
    ]

    for d in dirs_to_copy:
        s = src / d
        if s.exists():
            shutil.copytree(s, temp_dir / d)

    for f in files_to_copy:
        s = src / f
        if s.exists():
            shutil.copy2(s, temp_dir / f)

    src_dir = src / "src"
    temp_src = temp_dir / "src"
    if src_dir.exists():
        shutil.copytree(src_dir, temp_src)

        resources = temp_src / "main" / "resources"
        if resources.exists():
            for changelog_dir in resources.rglob("*/liquibase/changelog"):
                if not changelog_dir.is_dir():
                    continue
                for path in list(changelog_dir.iterdir()):
                    if path.is_file() and path.name != "010-init-user.xml":
                        path.unlink()
                    elif path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)

    props = temp_dir / "src" / "main" / "resources" / "application.properties"
    _ensure_dry_run_server_port(props)

    readme = temp_dir / "README-dry-run.txt"
    readme.write_text(
        f"Dry-run output for project: {_read_project_name(temp_dir / 'settings.gradle')}\n"
        f"Generated by jmix-cli --dry-run\n\n"
        f"To run:\n"
        f"  cd {temp_dir}\n"
        f"  chmod +x gradlew\n"
        f"  ./gradlew bootRun\n\n"
        f"Note: server.port={DRY_RUN_SERVER_PORT} was set, so Tomcat will pick a random free port.\n"
        f"Look for 'Application started at http://localhost:XXXX' in the bootRun log.\n"
        f"To use a fixed port, edit src/main/resources/application.properties and set server.port=<desired_port>.\n",
        encoding="utf-8",
    )
    return temp_dir


def _patch_globals_for_dry_run(temp_dir: Path) -> None:
    import jmix_cli.utils as utils
    import jmix_cli.entity as entity
    import jmix_cli.views as views
    import jmix_cli.liquibase as liquibase
    import jmix_cli.security as security
    import jmix_cli.user as user
    import jmix_cli.i18n as i18n

    company = _read_company_name(temp_dir / "build.gradle") or ""
    project = _read_project_name(temp_dir / "settings.gradle") or ""
    project_name = project.lower()
    company_path = company.replace(".", "/") if company else ""

    new_values = {
        "PROIECT_PATH": temp_dir,
        "PROJECT": project,
        "project_name": project_name,
        "COMPANY": company,
        "company_path": company_path,
    }

    for mod in [utils, entity, views, liquibase, security, user, i18n]:
        for name, value in new_values.items():
            if hasattr(mod, name):
                setattr(mod, name, value)

    for name, value in new_values.items():
        if name in globals():
            globals()[name] = value


def _print_dry_run_summary(temp_dir: Path, original_dir: Path) -> None:
    java_files = list(temp_dir.rglob("*.java"))
    xml_files = list(temp_dir.rglob("*.xml"))
    props_files = list(temp_dir.rglob("*.properties"))

    logger.info("=" * 70)
    logger.info("[dry-run] Generation completed successfully!")
    logger.info("=" * 70)
    logger.info(f"  Dry-run output directory: {temp_dir}")
    logger.info(f"  Generated Java files:     {len(java_files)}")
    logger.info(f"  Generated XML files:      {len(xml_files)}")
    logger.info(f"  Generated properties:     {len(props_files)}")
    logger.info("\n  To inspect differences:")
    logger.info("    meld {original_dir} {temp_dir}")
    logger.info("\n  To run the application:")
    logger.info(f"    cd {temp_dir} && ./gradlew bootRun")
    logger.info("    Look for 'Application started at http://localhost:XXXX' in the bootRun log.")
    logger.info("    To use a fixed port, set server.port=<desired_port> in src/main/resources/application.properties.")
    logger.info("=" * 70 + "\n")


def _dry_run_enabled() -> bool:
    return "--dry-run" in sys.argv


def _finish_dry_run(temp_dir: Path | None, original_dir: Path | None = None) -> None:
    if temp_dir is not None and original_dir is not None:
        _print_dry_run_summary(temp_dir, original_dir)
    elif temp_dir is not None:
        _print_dry_run_summary(temp_dir, temp_dir)


def _handle_error(error: Exception) -> None:
    """Centralized error handler: log and exit with code 1."""
    if isinstance(error, UserInputError):
        logger.error(f"[-] {error}")
    elif isinstance(error, ConfigurationError):
        logger.error(f"[-] Configuration error: {error}")
    elif isinstance(error, GenerationError):
        logger.error(f"[-] Generation error: {error}")
    elif isinstance(error, JmixCliError):
        logger.error(f"[-] {error}")
    else:
        logger.error(f"[-] Unexpected error: {error}")
    sys.exit(1)

def _generate_single_entity(name: str) -> None:
    inject_audit_dependencies()
    if name == "User":
        logger.info("👤 [System User] Triggering relational infiltration...")
        relations_list = get_relations_from_csv("relations.csv", "User")
        if relations_list:
            gen_liquibase_relations_changelog("User", relations_list)
            inject_relations_into_existing_user(name, relations_list)
            from jmix_cli.utils import replace_entity_messages
            from jmix_cli.i18n import ask_ollama_translation
            resources_path = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name
            messages_files = list(resources_path.glob("messages*.properties"))
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
            for messages_file in messages_files:
                stem = messages_file.stem
                lang_code = "en" if stem == "messages" else stem.split("_", 1)[1] if "_" in stem else stem
                primary_iso = lang_code.split("_")[0].lower()
                lang_name = iso_lang_names.get(primary_iso, primary_iso)
                relation_lines = []
                for rel in relations_list:
                    f_name = rel["field"]
                    spaced_name = (
                        "".join([" " + c if c.isupper() else c for c in f_name]).strip().lower()
                    )
                    readable_en = spaced_name.capitalize()
                    if lang_code == "en":
                        label = readable_en
                    else:
                        label = ask_ollama_translation(readable_en, lang_name)
                        if not label or len(label) > 50:
                            label = readable_en
                    relation_lines.append(f"{COMPANY}.{project_name}.entity/User.{f_name}={label}")
                existing_lines = messages_file.read_text(encoding="utf-8").splitlines() if messages_file.exists() else []
                user_lines = [line for line in existing_lines if line.startswith(f"{COMPANY}.{project_name}.entity/User.")]
                non_user_lines = [line for line in existing_lines if not line.startswith(f"{COMPANY}.{project_name}.entity/User.")]
                combined_user_lines = list(dict.fromkeys(user_lines + relation_lines))
                new_content = "\n".join(non_user_lines[:len(non_user_lines) - len(user_lines)] + combined_user_lines) + "\n"
                messages_file.write_text(new_content, encoding="utf-8")
        else:
            logger.info("   -> No relationships were configured for the User in relations.csv.")
    else:
        traits = get_traits_from_csv("traits.csv", name)
        fields_list = get_entities_from_csv("entities.csv", name)
        relations_list = get_relations_from_csv("relations.csv", name)
        if not fields_list:
            raise UserInputError(f"No fields found for the entity '{name}' in entities.csv")
        
        # Check if entity already exists
        from jmix_cli.entity import has_existing_entity_and_changelog
        entity_exists = has_existing_entity_and_changelog(name)
        
        if entity_exists:
            # Entity exists - just update Java file and run migrate for new fields
            logger.info(f"Entity {name} exists. Updating Java class and checking for incremental migrations...")
            gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list)
            # Run migrate to add new columns only
            from jmix_cli.migrate import migrate_entity
            migrate_entity(name, mode="quiet")  # quiet = no prompts, just check
        else:
            # New entity - generate everything
            logger.info(f"Generating Entity {name} from CSV architecture...")
            gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list)
        
        computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(Path("entities.csv").open(encoding="utf-8")) if row["entity_name"].strip() == name.strip()]
        if not computed_traits_list:
            computed_traits_list = ["name"]
        update_messages_entity(
            project_dir=".",
            base_package=COMPANY + "." + project_name,
            entity_name=name,
            traits_list=computed_traits_list,
            relations_list=relations_list,
        )
        # Only generate changelog if entity is new
        if not entity_exists:
            gen_liquibase_changelog_from_csv(name, fields_list, traits)
        if relations_list:
            # Check if relations changelog exists
            from jmix_cli.migrate import get_existing_columns_from_changelogs
            # For relations, we need to check if FK columns exist
            migrate_entity(name, mode="quiet")  # handles relations too


def _finalize_composition_relationships() -> None:
    logger.info("\n[⚡] PHASE 1.5: Finalizing Composition relationships...")
    relations_path = Path("relations.csv")
    if not relations_path.exists():
        return
    validate_csv_path("relations.csv", ["source_entity", "relation_type", "target_entity", "field_name", "mandatory"])
    with relations_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_type = row["relation_type"].strip()
            if r_type != "COMPOSITION_1:1":
                continue
            src_class = row["source_entity"].strip()
            tgt_class = row["target_entity"].strip()
            f_name = row["field_name"].strip()
            src_file_path = Path("src") / "main" / "java" / company_path / project_name / "entity" / f"{src_class}.java"
            tgt_file_path = Path("src") / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
            if not src_file_path.exists() or not tgt_file_path.exists():
                continue
            src_content = src_file_path.read_text(encoding="utf-8")
            if f"private {tgt_class} {f_name};" not in src_content:
                logger.info(f" 🔗 Finalizing @Composition 1:1 in {src_class}")
                sql_fk_col = f"{f_name.upper()}_ID"
                mandatory_val = row.get("mandatory", "false").strip().lower() == "true"
                join_col_attr = f'@JoinColumn(name = "{sql_fk_col}", nullable = false)' if mandatory_val else f'@JoinColumn(name = "{sql_fk_col}")'
                not_null_anno = "    @NotNull\n" if mandatory_val else ""
                comp_field = f'    @Composition\n    @OnDelete(DeletePolicy.CASCADE)\n    {join_col_attr}\n{not_null_anno}    @OneToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
                comp_caps = f_name[0].upper() + f_name[1:]
                comp_methods = f"    public {tgt_class} get{comp_caps}() {{\n        return {f_name};\n    }}\n\n"
                comp_methods += f"    public void set{comp_caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
                src_content = inject_import_if_missing(src_content, "io.jmix.core.metamodel.annotation.Composition")
                src_content = inject_import_if_missing(src_content, "io.jmix.core.entity.annotation.OnDelete")
                src_content = inject_import_if_missing(src_content, "io.jmix.core.DeletePolicy")
                src_content = inject_import_if_missing(src_content, "jakarta.persistence.OneToOne")
                src_content = inject_import_if_missing(src_content, "jakarta.persistence.JoinColumn")
                src_content = inject_import_if_missing(src_content, "jakarta.persistence.FetchType")
                if mandatory_val:
                    src_content = inject_import_if_missing(src_content, "jakarta.validation.constraints.NotNull")
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
                src_file_path.write_text(src_content, encoding="utf-8")

            tgt_content = tgt_file_path.read_text(encoding="utf-8")
            inv_field_name = src_class[0].lower() + src_class[1:]
            if f"private {src_class} {inv_field_name};" not in tgt_content:
                logger.info(f" 🔗 Finalizing inverse 1:1 in {tgt_class}")
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
                tgt_file_path.write_text(tgt_content, encoding="utf-8")

            stable_fk_id = f"{src_class.lower()}-add-fk-{f_name}"
            fk_changelog = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
    objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
    <changeSet id="{stable_fk_id}" author="{project_name}">
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
            fk_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "liquibase" / "changelog" / current_year / current_month
            fk_dir.mkdir(parents=True, exist_ok=True)
            existing_fk = list(fk_dir.glob(f"*-03-fk-{src_class.lower()}.xml"))
            if existing_fk:
                logger.info(f" 🔗 FK constraint changelog already exists for {src_class}, skipping")
            else:
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                fk_file = fk_dir / f"{timestamp}-03-fk-{src_class.lower()}.xml"
                fk_file.write_text(fk_changelog, encoding="utf-8")
                logger.info(f" 🔗 Added FK constraint changelog: {fk_file}")
    logger.info("\n✅ Entity generation completed!")


def _update_menu(n: str) -> None:
    logger.info("Updating menu.xml for " + n + "...")
    menu_path = (
        PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "menu.xml"
    )
    if not menu_path.exists():
        logger.warning(f"⚠️ I not found the file menu.xml in the path {menu_path}!")
        return
    menu_item = f'    <item view="{n}.list" title="msg://{COMPANY}.{project_name}.view.{n.lower()}/{n.lower()}ListView.title"/>\n'
    content = menu_path.read_text(encoding="utf-8")
    if ('view="' + n + '.list"') in content:
        logger.info("ℹ️ View " + n + ".list allready exist in menu.")
        return
    if "</menu>" in content:
        new_content = content.replace("</menu>", menu_item + "</menu>")
        menu_path.write_text(new_content, encoding="utf-8")
        logger.info("Menu injected successfully into menu.xml!")
    else:
        logger.warning("⚠️ Invalid structure for menu.xml (missing closing </menu> tag)!")


def inject_audit_dependencies() -> None:
    build_gradle_path = Path("build.gradle")
    if build_gradle_path.exists():
        traits_path = Path("traits.csv")
        if traits_path.exists():
            audit_needed = False
            with traits_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (
                        row.get("audit_of_creation", "").strip().lower() == "true"
                        or row.get("audit_of_modification", "").strip().lower() == "true"
                    ):
                        audit_needed = True
                        break

            if audit_needed:
                content = build_gradle_path.read_text(encoding="utf-8")
                has_starter = "jmix-audit-starter" in content
                has_flowui = "jmix-audit-flowui-starter" in content
                if not has_starter or not has_flowui:
                    lines_to_add = []
                    if not has_starter:
                        lines_to_add.append("    implementation 'io.jmix.audit:jmix-audit-starter' // Automatically configured via Jmix CLI")
                    if not has_flowui:
                        lines_to_add.append("    implementation 'io.jmix.audit:jmix-audit-flowui-starter' // Automatically configured via Jmix CLI")
                    if lines_to_add and "dependencies {" in content:
                        insertion = "\n".join([""] + lines_to_add) + "\n"
                        content = content.replace("dependencies {", f"dependencies {{{insertion}", 1)
                        build_gradle_path.write_text(content, encoding="utf-8")
                        logger.info("[+] Injected Jmix Audit dependencies into build.gradle")

    changelog_path = Path("src/main/resources") / company_path / project_name / "liquibase" / "changelog.xml"
    if changelog_path.exists():
        changelog_content = changelog_path.read_text(encoding="utf-8")
        if "/io/jmix/audit/liquibase/changelog.xml" not in changelog_content:
            insert_marker = f'    <includeAll path="/{company_path}/{project_name}/liquibase/changelog"/>'
            if insert_marker in changelog_content:
                audit_include = '    <include file="/io/jmix/audit/liquibase/changelog.xml"/>\n'
                changelog_content = changelog_content.replace(insert_marker, f"{audit_include}{insert_marker}")
                changelog_path.write_text(changelog_content, encoding="utf-8")
                logger.info("[+] Injected Jmix Audit changelog into liquibase/changelog.xml")


def cmd_init_project(project_name: str, target_group: str, lang_input: str = "en") -> None:
    base_package = f"{target_group.strip().strip('.')}.{project_name.strip().strip('.')}"
    repo_url = "https://github.com/florintanasa/jmix-ai-template"
    current_dir = Path.cwd()
    target_dir = current_dir / project_name
    lang_suffix = lang_input.strip()
    lang_key_for_map = lang_suffix

    logger.info(f"\n[*] Initializing New Jmix Project: '{project_name}'")
    logger.info(f"[*] Group ID:                 {target_group}")
    logger.info(f"[*] Generated Base Package:   {base_package}")
    logger.info(f"[*] Requested Locale:         {lang_suffix}")
    logger.info("-" * 60)

    if target_dir.exists():
        raise UserInputError(f"Folder '{project_name}' already exists in this directory.")

    logger.info("[*] Step 1: Downloading Jmix starter template...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "-b", "v2.8.2", repo_url, project_name],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GenerationError(f"Git clone failed: {e}") from e

    shutil.rmtree(target_dir / ".git", ignore_errors=True)
    logger.info("[+] Git template history cleared successfully.")

    old_package_dots = "io.jmix.tempate"
    old_package_slashes = "io/jmix/tempate"
    new_package_slashes = Path(*base_package.split("."))
    new_package_property_slashes = base_package.replace(".", "/")

    paths_to_move = [
        (target_dir / "src" / "main" / "java", old_package_slashes, new_package_slashes),
        (target_dir / "src" / "test" / "java", old_package_slashes, new_package_slashes),
        (target_dir / "src" / "main" / "resources", old_package_slashes, new_package_slashes),
    ]

    logger.info("[*] Step 2: Refactoring structural Java source layers and XML resources...")
    for base_root, old_rel, new_rel in paths_to_move:
        src_dir = base_root / old_rel
        dst_dir = base_root / new_rel
        if src_dir.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)
            for item in src_dir.iterdir():
                shutil.move(str(item), str(dst_dir / item.name))
            shutil.rmtree(base_root / "io", ignore_errors=True)

    logger.info("[*] Step 3: Injecting metadata and localization configuration dependencies...")
    build_gradle_path = target_dir / "build.gradle"
    app_properties_path = target_dir / "src" / "main" / "resources" / "application.properties"

    JMIX_TRANSLATIONS_MAP = {
        "ar": "ar", "ckb": "ckb", "de": "de", "el": "el", "es": "es", "fr": "fr",
        "fr_fr": "fr", "it": "it", "nl": "nl", "pt": "pt-br", "pt_BR": "pt-br",
        "ro": "ro", "ro_RO": "ro", "ro_MD": "ro", "ru": "ru", "tr": "tr", "zh": "zh-cn", "zh_CN": "zh-cn",
    }

    if build_gradle_path.exists():
        gradle_content = build_gradle_path.read_text(encoding="utf-8")
        gradle_content = re.sub(
            r"group\s*=\s*['\"].*?['\"]", f"group = '{target_group}'", gradle_content
        )
        if lang_key_for_map != "en" and lang_key_for_map in JMIX_TRANSLATIONS_MAP:
            addon_suffix = JMIX_TRANSLATIONS_MAP[lang_key_for_map]
            addon_dependency = f"\n    implementation 'io.jmix.translations:jmix-translations-{addon_suffix}'"
            if "dependencies {" in gradle_content:
                gradle_content = gradle_content.replace(
                    "dependencies {",
                    f"dependencies {{{addon_dependency} // Automatically configured via Jmix CLI",
                )
                logger.info(f"[+] Injected localization add-on dependency: jmix-translations-{addon_suffix}")
        build_gradle_path.write_text(gradle_content, encoding="utf-8")

    if app_properties_path.exists():
        prop_content = app_properties_path.read_text(encoding="utf-8")
        if "jmix.core.available-locales" in prop_content:
            if lang_key_for_map != "en":
                prop_content = re.sub(
                    r"jmix\.core\.available-locales\s*=\s*(.*)",
                    f"jmix.core.available-locales = \\1,{lang_suffix}",
                    prop_content,
                )
                logger.info(f"[+] Updated active core locales property: en,{lang_suffix}")
        else:
            locales_line = "\njmix.core.available-locales = en"
            if lang_key_for_map != "en":
                locales_line += f",{lang_suffix}"
            prop_content += locales_line
        app_properties_path.write_text(prop_content, encoding="utf-8")

    if True:  # Always generate message bundles: en base fallback + localized bundles
        msg_dir = target_dir / "src" / "main" / "resources" / new_package_slashes
        msg_dir.mkdir(parents=True, exist_ok=True)
        # Prefer local .templates/ (user custom templates), fall back to the
        # template repo's .templates/ inside the freshly cloned project
        local_templates = Path(".templates")
        templates_dir = local_templates if local_templates.exists() else target_dir / ".templates"
        base_fallback_msg_path = msg_dir / "messages.properties"
        custom_messages_path = msg_dir / f"messages_{lang_suffix}.properties"
        eng_template_path = templates_dir / "messages_en.properties"
        base_template_path = templates_dir / "messages.properties"
        lang_template_path = templates_dir / f"messages_{lang_suffix}.properties"

        # Base fallback: prefer .templates/messages.properties (full Jmix template),
        # fall back to messages_en.properties, or create empty
        if base_template_path.exists():
            if not base_fallback_msg_path.exists():
                shutil.copy2(base_template_path, base_fallback_msg_path)
                logger.info("[+] Generated base fallback file from .templates/messages.properties")
        elif eng_template_path.exists():
            if not base_fallback_msg_path.exists():
                shutil.copy2(eng_template_path, base_fallback_msg_path)
                logger.info("[+] Generated standard base fallback file: messages.properties")
        else:
            if not base_fallback_msg_path.exists():
                base_fallback_msg_path.write_text(
                    f"# Base fallback localization bundle\n",
                    encoding="utf-8",
                )
                logger.info("[+] Initialized empty base fallback file: messages.properties")

        # Also copy messages_en.properties from .templates/ to project for explicit
        # English locale support (login screen, User entity messages, etc.)
        if lang_suffix != "en" and eng_template_path.exists():
            en_in_project = msg_dir / "messages_en.properties"
            if not en_in_project.exists():
                shutil.copy2(eng_template_path, en_in_project)
                logger.info("[+] Copied English locale bundle: messages_en.properties")

        # Determine source for localized bundle
        if lang_template_path.exists():
            src_template = lang_template_path
        else:
            template_suffix = JMIX_TRANSLATIONS_MAP.get(lang_key_for_map, lang_key_for_map)
            if template_suffix != lang_key_for_map:
                alt_template_path = templates_dir / f"messages_{template_suffix}.properties"
                if alt_template_path.exists():
                    src_template = alt_template_path
                elif eng_template_path.exists():
                    src_template = eng_template_path
                else:
                    src_template = None
            elif eng_template_path.exists():
                src_template = eng_template_path
            else:
                src_template = None

        if src_template and not custom_messages_path.exists():
            shutil.copy2(src_template, custom_messages_path)
            if lang_template_path.exists():
                logger.info(f"[+] Copied localized bundle from template: messages_{lang_suffix}.properties")
            else:
                logger.info(f"[+] Initialized localized bundle from English template: messages_{lang_suffix}.properties")
        elif not custom_messages_path.exists():
            custom_messages_path.write_text(
                f"# Custom localization translations properties file for: {lang_suffix}\n",
                encoding="utf-8",
            )
            logger.info(f"[+] Initialized empty bundle: messages_{lang_suffix}.properties")

    files_to_update = [target_dir / "settings.gradle", app_properties_path]
    for base_root, _, new_rel in paths_to_move:
        scan_root = base_root / new_rel
        if scan_root.exists():
            for root, _, files in os.walk(scan_root):
                for file in files:
                    if file.endswith((".java", ".xml", ".properties")):
                        files_to_update.append(Path(root) / file)

    for file_path in files_to_update:
        if file_path == build_gradle_path or not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        if "settings.gradle" in str(file_path):
            content = re.sub(
                r"rootProject\.name\s*=\s*['\"].*?['\"]",
                f"rootProject.name = '{project_name}'",
                content,
            )
        content = content.replace(old_package_dots, base_package)
        content = content.replace(old_package_slashes, new_package_property_slashes)
        # Replace generic placeholder from .templates/ message bundles
        # (com.company.project — used by the jmix-ai-template repo)
        content = content.replace("com.company.project", base_package)
        file_path.write_text(content, encoding="utf-8")

    gradlew_path = target_dir / "gradlew"
    if gradlew_path.exists():
        os.chmod(gradlew_path, 0o755)

    logger.info("[*] Step 3: Initializing a fresh Git repository...")
    try:
        subprocess.run(["git", "init"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=target_dir, check=True)
        logger.info("✅ Project initialized successfully with a fresh Git history!")
    except subprocess.CalledProcessError:
        logger.warning("Warning: Template was cloned, but failed to initialize fresh Git repository automatically.")

    logger.info("\n" + "=" * 60)
    logger.info(f"[+] SUCCESS: Jmix project '{project_name}' successfully initialized!")
    logger.info(f"[+] Target core locale: {lang_suffix}")
    logger.info(f"[+] Run command: cd {project_name} && ./gradlew bootRun")
    logger.info("=" * 60 + "\n")


def print_cli_help() -> None:
    logger.info("\n🚀 JMIX CLI - UNIFIED COMMAND HELP")
    logger.info("-" * 50)
    logger.info("Initialize a new clean standard Jmix template:")
    logger.info("  python jmix-cli.py init <project_name> <target_group> [locale]")
    logger.info("  -> Example: python jmix-cli.py init onboarding com.florin ro_RO")
    logger.info("\nGenerate layers from CSV schema (existing engine):")
    logger.info("  Run without parameters inside a valid Jmix directory hierarchy")
    logger.info("  to process traits.csv, entities.csv, and relations.csv schemas.")
    logger.info("\nDry-run mode:")
    logger.info("  Append --dry-run to any generation command to generate in a temporary directory.")
    logger.info("  Example: python jmix-cli.py build-all --dry-run")
    logger.info("\nVerbosity options:")
    logger.info("  --verbose / -v    Enable debug output")
    logger.info("  --quiet / -q      Suppress info output, show only warnings and errors")
    logger.info("-" * 50 + "\n")


def main() -> None:
    dry_run = _dry_run_enabled()
    dry_run_temp_dir: Path | None = None
    original_dir = Path.cwd()

    try:
        if dry_run and len(sys.argv) > 1 and sys.argv[1].lower() == "init":
            raise UserInputError("--dry-run nu este suportat pentru 'init'.")

        if dry_run:
            sys.argv = [arg for arg in sys.argv if arg != "--dry-run"]

        verbose = "--verbose" in sys.argv or "-v" in sys.argv
        quiet = "--quiet" in sys.argv or "-q" in sys.argv
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Verbose mode enabled.")
        elif quiet:
            logging.getLogger().setLevel(logging.WARNING)
        else:
            logging.getLogger().setLevel(logging.INFO)
        if verbose or quiet:
            sys.argv = [arg for arg in sys.argv if arg not in ("--verbose", "-v", "--quiet", "-q")]

        if len(sys.argv) != 1 and sys.argv[1].lower() == "init":
            if len(sys.argv) == 2 or len(sys.argv) == 3:
                raise UserInputError("Missing required arguments for init command.")
            p_name = sys.argv[2]
            t_group = sys.argv[3]
            requested_lang = sys.argv[4] if len(sys.argv) >= 5 else "en"
            cmd_init_project(p_name, t_group, requested_lang)
            return

        elif len(sys.argv) != 1 and sys.argv[1].lower() in ["help", "--help", "-h"]:
            print_cli_help()
            return

        logger.info(f"[*] Run Jmix CLI engine generation on the current project: '{PROJECT}'...")

        if not PROJECT:
            raise ConfigurationError("No valid Jmix project detected in this folder.")

        if dry_run:
            if len(sys.argv) == 1:
                raise UserInputError("--dry-run needs a command.")
            dry_run_temp_dir = _copy_project_to_temp()
            os.chdir(dry_run_temp_dir)
            _patch_globals_for_dry_run(dry_run_temp_dir)

        if len(sys.argv) == 1:
            logger.info("=" * 70)
            logger.info("JMIX CLI - Command Reference")
            logger.info("=" * 70)
            logger.info("Available commands:")
            logger.info("  python3 jmix-cli.py entity-all   - Generate ALL entities + liquibase")
            logger.info("  python3 jmix-cli.py entity <Name> - Generate single entity")
            logger.info("  python3 jmix-cli.py migrate <Name> - Generate incremental DB migration for entity")
            logger.info("  python3 jmix-cli.py migrate-all - Generate incremental DB migrations for all entities")
            logger.info("  python3 jmix-cli.py security      - Generate security roles")
            logger.info("  python3 jmix-cli.py ui-list-all   - Generate ALL list views")
            logger.info("  python3 jmix-cli.py ui-list <Name> - Generate single list view")
            logger.info("  python3 jmix-cli.py ui-detail-all - Generate ALL detail views")
            logger.info("  python3 jmix-cli.py ui-detail <Name> - Generate single detail view")
            logger.info("  python3 jmix-cli.py build-all     - Full generation (all phases)")
            logger.info("\nOptions:")
            logger.info("  --dry-run    Generate in a temporary project directory without modifying the current project")
            logger.info("=" * 70)
            return

        action = sys.argv[1].lower()

        if action == "security":
            gen_jmix_resource_roles_from_csv()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "entity-all":
            inject_audit_dependencies()
            logger.info("[*] Launching ENTITY-ONLY generation for ALL entities...")
            ordered_list = get_sorted_entities_by_dependency()
            logger.info(f"[*] Calculated generation sequence: {ordered_list}")
            for ent in ordered_list:
                if ent == "User":
                    relations_list = get_relations_from_csv("relations.csv", "User")
                    if relations_list:
                        gen_liquibase_relations_changelog("User", relations_list)
                        inject_relations_into_existing_user("User", relations_list)
                        from jmix_cli.utils import replace_entity_messages
                        from jmix_cli.i18n import ask_ollama_translation
                        resources_path = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name
                        messages_files = list(resources_path.glob("messages*.properties"))
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
                        for messages_file in messages_files:
                            stem = messages_file.stem
                            lang_code = "en" if stem == "messages" else stem.split("_", 1)[1] if "_" in stem else stem
                            primary_iso = lang_code.split("_")[0].lower()
                            lang_name = iso_lang_names.get(primary_iso, primary_iso)
                            relation_lines = []
                            for rel in relations_list:
                                f_name = rel["field"]
                                spaced_name = (
                                    "".join([" " + c if c.isupper() else c for c in f_name]).strip().lower()
                                )
                                readable_en = spaced_name.capitalize()
                                if lang_code == "en":
                                    label = readable_en
                                else:
                                    label = ask_ollama_translation(readable_en, lang_name)
                                    if not label or len(label) > 50:
                                        label = readable_en
                                relation_lines.append(f"{COMPANY}.{project_name}.entity/User.{f_name}={label}")
                            existing_lines = messages_file.read_text(encoding="utf-8").splitlines() if messages_file.exists() else []
                            user_lines = [line for line in existing_lines if line.startswith(f"{COMPANY}.{project_name}.entity/User.")]
                            non_user_lines = [line for line in existing_lines if not line.startswith(f"{COMPANY}.{project_name}.entity/User.")]
                            combined_user_lines = list(dict.fromkeys(user_lines + relation_lines))
                            new_content = "\n".join(non_user_lines + combined_user_lines) + "\n"
                            messages_file.write_text(new_content, encoding="utf-8")
                else:
                    traits = get_traits_from_csv("traits.csv", ent)
                    fields_list = get_entities_from_csv("entities.csv", ent)
                    relations_list = get_relations_from_csv("relations.csv", ent)
                    if fields_list:
                        gen_entity_mechanic_from_csv(ent, fields_list, traits, relations_list)
                        gen_liquibase_changelog_from_csv(ent, fields_list, traits)
                        if relations_list:
                            gen_liquibase_relations_changelog(ent, relations_list)
                        computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(Path("entities.csv").open(encoding="utf-8")) if row["entity_name"].strip() == ent.strip()]
                        if not computed_traits_list:
                            computed_traits_list = ["name"]
                        update_messages_entity(
                            ".", COMPANY + "." + project_name, ent, computed_traits_list, relations_list
                        )
            logger.info("\n[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
            for ent in ordered_list:
                relations_list = get_relations_from_csv("relations.csv", ent)
                composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
                if composition_rels:
                    _inject_composition_into_parent(ent, composition_rels)
            _finalize_composition_relationships()
            update_checkbox_required_state_property()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "ui-list-all":
            logger.info("[*] Launching UI-LIST generation for ALL entities...")
            ordered_list = get_sorted_entities_by_dependency()
            for ent in ordered_list:
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)
                if ent == "User":
                    if fields_list or relations_list:
                        inject_list_ui_into_existing_user(relations_list, fields_list)
                elif fields_list:
                    gen_list_view_from_csv(ent, fields_list, relations_list)
            logger.info("\n✅ UI List views generation completed!")
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "ui-detail-all":
            logger.info("[*] Launching UI-DETAIL generation for ALL entities...")
            ordered_list = get_sorted_entities_by_dependency()
            logger.info("[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
            for ent in ordered_list:
                relations_list = get_relations_from_csv("relations.csv", ent)
                composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
                if composition_rels:
                    _inject_composition_into_parent(ent, composition_rels)
            _finalize_composition_relationships()
            for ent in ordered_list:
                fields_list = get_entities_from_csv("entities.csv", ent)
                relations_list = get_relations_from_csv("relations.csv", ent)
                if ent == "User":
                    if fields_list or relations_list:
                        inject_detail_ui_into_existing_user(relations_list, fields_list)
                elif fields_list:
                    gen_detail_view_from_csv(ent, fields_list, relations_list)
            # Post-process N:N relations: inject dataGrid in source and inverse entities
            all_relations = []
            for ent in ordered_list:
                rels = get_relations_from_csv("relations.csv", ent)
                for rel in rels:
                    rel["source_entity"] = ent
                all_relations.extend(rels)
            inject_nn_datagrid_into_source_entity(all_relations)
            inject_nn_grid_into_inverse_entity(all_relations)
            logger.info("\n✅ UI Detail views generation completed!")
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "build-all":
            inject_audit_dependencies()
            logger.info("=" * 70)
            logger.info("[⚡] TRIGGERING FULL ARCHITECTURE BUILD-ALL INDUSTRIAL SEQUENCE...")
            logger.info("=" * 70)
            ordered_list = get_sorted_entities_by_dependency()
            logger.info(f"[*] Calculated execution flow pipeline: {ordered_list}\n")

            logger.info("[⚡] PHASE 1: Scaffolding Data Models and Database Changelogs...")
            for ent in ordered_list:
                if ent == "User":
                    logger.info("👤 System User discovered in pipeline. Triggering surgical relationship infiltration...")
                    relations_list = get_relations_from_csv("relations.csv", "User")
                    if relations_list:
                        gen_liquibase_relations_changelog("User", relations_list)
                        inject_relations_into_existing_user("User", relations_list)
                        from jmix_cli.utils import replace_entity_messages
                        from jmix_cli.i18n import ask_ollama_translation
                        resources_path = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name
                        messages_files = list(resources_path.glob("messages*.properties"))
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
                        for messages_file in messages_files:
                            stem = messages_file.stem
                            lang_code = "en" if stem == "messages" else stem.split("_", 1)[1] if "_" in stem else stem
                            primary_iso = lang_code.split("_")[0].lower()
                            lang_name = iso_lang_names.get(primary_iso, primary_iso)
                            relation_lines = []
                            for rel in relations_list:
                                f_name = rel["field"]
                                spaced_name = (
                                    "".join([" " + c if c.isupper() else c for c in f_name]).strip().lower()
                                )
                                readable_en = spaced_name.capitalize()
                                if lang_code == "en":
                                    label = readable_en
                                else:
                                    label = ask_ollama_translation(readable_en, lang_name)
                                    if not label or len(label) > 50:
                                        label = readable_en
                                relation_lines.append(f"{COMPANY}.{project_name}.entity/User.{f_name}={label}")
                            existing_lines = messages_file.read_text(encoding="utf-8").splitlines() if messages_file.exists() else []
                            user_lines = [line for line in existing_lines if line.startswith(f"{COMPANY}.{project_name}.entity/User.")]
                            non_user_lines = [line for line in existing_lines if not line.startswith(f"{COMPANY}.{project_name}.entity/User.")]
                            combined_user_lines = list(dict.fromkeys(user_lines + relation_lines))
                            new_content = "\n".join(non_user_lines + combined_user_lines) + "\n"
                            messages_file.write_text(new_content, encoding="utf-8")
                else:
                    logger.info(f"   ▶️ Building Domain Model: {ent}")
                    traits = get_traits_from_csv("traits.csv", ent)
                    fields_list = get_entities_from_csv("entities.csv", ent)
                    relations_list = get_relations_from_csv("relations.csv", ent)
                    if fields_list:
                        gen_entity_mechanic_from_csv(ent, fields_list, traits, relations_list)
                        gen_liquibase_changelog_from_csv(ent, fields_list, traits)
                        if relations_list:
                            gen_liquibase_relations_changelog(ent, relations_list)
                        computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(Path("entities.csv").open(encoding="utf-8")) if row["entity_name"].strip() == ent.strip()]
                        if not computed_traits_list:
                            computed_traits_list = ["name"]
                        update_messages_entity(".", COMPANY + "." + project_name, ent, computed_traits_list, relations_list)

            logger.info("\n[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
            for ent in ordered_list:
                relations_list = get_relations_from_csv("relations.csv", ent)
                composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
                if composition_rels:
                    _inject_composition_into_parent(ent, composition_rels)

            _finalize_composition_relationships()

            # Inject relationships into existing User entity (Jmix built-in)
            logger.info("\n[⚡] PHASE 1.7: Injecting relationships into system User entity...")
            if "User" in ordered_list:
                user_rels = get_relations_from_csv("relations.csv", "User")
                if user_rels:
                    inject_relations_into_existing_user("User", user_rels)

            logger.info("\n[⚡] PHASE 2: Architecturing FlowUI Screen Descriptors & Controllers...")
            for ent in ordered_list:
                logger.info(f"   📺 Compiling Layout XML and Java Views for: {ent}")
                if ent == "User":
                    fields_list = get_entities_from_csv("entities.csv", "User")
                    relations_list = get_relations_from_csv("relations.csv", "User")
                    if fields_list or relations_list:
                        inject_list_ui_into_existing_user(relations_list, fields_list)
                        inject_detail_ui_into_existing_user(relations_list, fields_list)
                else:
                    current_fields = get_entities_from_csv("entities.csv", ent)
                    relations_list = get_relations_from_csv("relations.csv", ent)
                    if current_fields:
                        gen_list_view_from_csv(ent, current_fields, relations_list)
                        gen_detail_view_from_csv(ent, current_fields, relations_list)
                        _update_menu(ent)

            all_relations = []
            for ent in ordered_list:
                rels = get_relations_from_csv("relations.csv", ent)
                for rel in rels:
                    rel["source_entity"] = ent
                all_relations.extend(rels)
            inject_nn_grid_into_inverse_entity(all_relations)
            inject_nn_datagrid_into_source_entity(all_relations)

            logger.info("\n[⚡] PHASE 3: Compiling Access Control Security Roles Interface blueprinter...")
            gen_jmix_resource_roles_from_csv()

            logger.info("=" * 70)
            logger.info("[⚡] SUCCESS: Project scaffolding built perfectly from CSV maps!")
            logger.info("=" * 70 + "\n")
            update_checkbox_required_state_property()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        if action == "migrate-all":
            logger.info("[*] Running incremental DB migrations for all entities...")
            mode = "force" if "--force" in sys.argv else "prompt"
            migrate_all_entities(mode)
            logger.info("[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
            ordered_list = get_sorted_entities_by_dependency()
            for ent in ordered_list:
                relations_list = get_relations_from_csv("relations.csv", ent)
                composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
                if composition_rels:
                    _inject_composition_into_parent(ent, composition_rels)
            _finalize_composition_relationships()
            update_checkbox_required_state_property()
            return

        if len(sys.argv) == 2:
            raise UserInputError("Missing required Entity Name parameter.")

        name = sys.argv[2]

        if action == "migrate":
            mode = "force" if "--force" in sys.argv else "prompt"
            migrate_entity(name, mode)

        elif action == "entity":
            _generate_single_entity(name)

        elif action == "ui-list":
            if name == "User":
                logger.info("[*] Triggering FlowUI List View infiltration for system User...")
                relations_list = get_relations_from_csv("relations.csv", "User")
                inject_list_ui_into_existing_user(relations_list)
            else:
                fields_list = get_entities_from_csv("entities.csv", name)
                relations_list = get_relations_from_csv("relations.csv", name)
                if not fields_list:
                    raise UserInputError(f"Fields for entity '{name}' do not exist in entities.csv")
                gen_list_view_from_csv(name, fields_list, relations_list)
                _update_menu(name)

        elif action == "ui-detail":
            if name == "User":
                logger.info("[*] Triggering FlowUI Detail View infiltration for system User...")
                relations_list = get_relations_from_csv("relations.csv", "User")
                inject_detail_ui_into_existing_user(relations_list)
            else:
                fields_list = get_entities_from_csv("entities.csv", name)
                relations_list = get_relations_from_csv("relations.csv", name)
                if not fields_list:
                    raise UserInputError(f"Fields for '{name}' do not exist in entities.csv")
                gen_detail_view_from_csv(name, fields_list, relations_list)

        else:
            raise UserInputError(f"Unknown action: '{action}'. Use entity, ui-list, ui-detail or security.")

        _finish_dry_run(dry_run_temp_dir, original_dir)
    except JmixCliError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)
