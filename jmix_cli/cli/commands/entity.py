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

from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file
from jmix_cli.core.logger import get_logger
from jmix_cli.core.csv import validate_csv_path
from jmix_cli.exceptions import UserInputError, ConfigurationError
from jmix_cli.entity import (
    get_entities_from_csv,
    get_relations_from_csv,
    get_sorted_entities_by_dependency,
    get_traits_from_csv,
    gen_entity_mechanic_from_csv,
    has_existing_entity_and_changelog,
)
from jmix_cli.liquibase import gen_liquibase_changelog_from_csv, gen_liquibase_relations_changelog
from jmix_cli.i18n import update_messages_entity
from jmix_cli.migrate import migrate_entity
from jmix_cli.user import inject_relations_into_existing_user

logger = get_logger("jmix_cli.cli.commands.entity")


def _get_inverse_composition_relations(entity_name: str) -> list[dict[str, Any]]:
    relations_csv_path = Path("relations.csv")
    inverse_rels: list[dict[str, Any]] = []
    if not relations_csv_path.exists():
        return inverse_rels
    with relations_csv_path.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["target_entity"].strip().lower() == entity_name.lower():
                r_type = row["relation_type"].strip().upper()
                if r_type == "COMPOSITION_1:1" or r_type == "COMPOSITION_1:N":
                    src_class = row["source_entity"].strip()
                    inv_field_name = src_class[0].lower() + src_class[1:]
                    inverse_rels.append({
                        "type": row["relation_type"].strip(),
                        "target": src_class,
                        "field": inv_field_name,
                        "mandatory": row["mandatory"].strip().lower() == "true",
                    })
    return inverse_rels


def _update_menu(n: str) -> None:
    logger.info("Updating menu.xml for " + n + "...")
    menu_path = (
        PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "menu.xml"
    )
    if not menu_path.exists():
        logger.warning(f"⚠️ I not found the file menu.xml in the path {menu_path}!")
        return
    content = menu_path.read_text(encoding="utf-8")
    if ('view="' + n + '.list"') in content:
        logger.info("ℹ️ View " + n + ".list allready exist in menu.")
        return
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "</menu>":
            menu_item = '        <item view="' + n + '.list" title="msg://' + COMPANY + '.' + project_name + '.view.' + n.lower() + '/' + n.lower() + 'ListView.title"/>'
            lines.insert(i, menu_item)
            menu_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            logger.info("Menu injected successfully into menu.xml!")
            return
    logger.warning("⚠️ Invalid structure for menu.xml (missing closing </menu> tag)!")


def generate_single_entity(name: str) -> None:
    if name == "User":
        logger.info("👤 [System User] Triggering relational infiltration...")
        relations_list = get_relations_from_csv("relations.csv", "User")
        if relations_list:
            gen_liquibase_relations_changelog("User", relations_list)
            inject_relations_into_existing_user(name, relations_list)
            from jmix_cli.i18n import ask_ollama_translation
            resources_path = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name
            messages_files = list(resources_path.glob("messages*.properties"))
            from jmix_cli.core.constants import ISO_LANG_NAMES
            for messages_file in messages_files:
                stem = messages_file.stem
                lang_code = "en" if stem == "messages" else stem.split("_", 1)[1] if "_" in stem else stem
                primary_iso = lang_code.split("_")[0].lower()
                lang_name = ISO_LANG_NAMES.get(primary_iso, primary_iso)
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

        entity_exists = has_existing_entity_and_changelog(name)

        if entity_exists:
            logger.info(f"Entity {name} exists. Updating Java class and checking for incremental migrations...")
            gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list)
            migrate_entity(name, mode="quiet")
        else:
            logger.info(f"Generating Entity {name} from CSV architecture...")
            gen_entity_mechanic_from_csv(name, fields_list, traits, relations_list)
            gen_liquibase_changelog_from_csv(name, fields_list, traits)
            if relations_list:
                gen_liquibase_relations_changelog(name, relations_list)

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
        _update_menu(name)


def generate_all_entities() -> None:
    from jmix_cli.cli.dry_run import inject_audit_dependencies, _finalize_composition_relationships, _patch_globals_for_dry_run, _copy_project_to_temp
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
                inverse_user_rels = _get_inverse_composition_relations("User")
                relations_list = relations_list + inverse_user_rels
                from jmix_cli.i18n import ask_ollama_translation
                resources_path = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name
                messages_files = list(resources_path.glob("messages*.properties"))
                from jmix_cli.core.constants import ISO_LANG_NAMES
                for messages_file in messages_files:
                    stem = messages_file.stem
                    lang_code = "en" if stem == "messages" else stem.split("_", 1)[1] if "_" in stem else stem
                    primary_iso = lang_code.split("_")[0].lower()
                    lang_name = ISO_LANG_NAMES.get(primary_iso, primary_iso)
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
            _update_menu("User")
            computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(Path("entities.csv").open(encoding="utf-8")) if row["entity_name"].strip() == "User".strip()]
            if not computed_traits_list:
                computed_traits_list = ["name"]
            update_messages_entity(
                ".", COMPANY + "." + project_name, "User", computed_traits_list, []
            )
        else:
            traits = get_traits_from_csv("traits.csv", ent)
            fields_list = get_entities_from_csv("entities.csv", ent)
            relations_list = get_relations_from_csv("relations.csv", ent)
            inverse_rels = _get_inverse_composition_relations(ent)
            relations_list_for_messages = relations_list + inverse_rels
            if not fields_list:
                raise UserInputError(f"No fields found for the entity '{ent}' in entities.csv")

            entity_exists = has_existing_entity_and_changelog(ent)

            if entity_exists:
                logger.info(f"Entity {ent} exists. Updating Java class and checking for incremental migrations...")
                gen_entity_mechanic_from_csv(ent, fields_list, traits, relations_list)
                migrate_entity(ent, mode="quiet")
            else:
                logger.info(f"Generating Entity {ent} from CSV architecture...")
                gen_entity_mechanic_from_csv(ent, fields_list, traits, relations_list)
                gen_liquibase_changelog_from_csv(ent, fields_list, traits)

            if relations_list:
                gen_liquibase_relations_changelog(ent, relations_list)

            computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(Path("entities.csv").open(encoding="utf-8")) if row["entity_name"].strip() == ent.strip()]
            if not computed_traits_list:
                computed_traits_list = ["name"]
            update_messages_entity(
                project_dir=".",
                base_package=COMPANY + "." + project_name,
                entity_name=ent,
                traits_list=computed_traits_list,
                relations_list=relations_list_for_messages,
            )
            _update_menu(ent)
    from jmix_cli.cli.dry_run import _finalize_composition_relationships
    logger.info("\n[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
    for ent in ordered_list:
        relations_list = get_relations_from_csv("relations.csv", ent)
        composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
        if composition_rels:
            from jmix_cli.entity import _inject_composition_into_parent
            _inject_composition_into_parent(ent, composition_rels)
    _finalize_composition_relationships()
