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

from jmix_cli.core.project import COMPANY, PROIECT_PATH, PROJECT, company_path, project_name
from jmix_cli.core.files import write_file
from jmix_cli.core.logger import get_logger
from jmix_cli.exceptions import ConfigurationError, GenerationError, UserInputError
from jmix_cli.core.constants import JMIX_TRANSLATIONS_MAP

logger = get_logger("jmix_cli.cli.main")


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

    if True:
        msg_dir = target_dir / "src" / "main" / "resources" / new_package_slashes
        msg_dir.mkdir(parents=True, exist_ok=True)
        local_templates = Path(".templates")
        templates_dir = local_templates if local_templates.exists() else target_dir / ".templates"
        base_fallback_msg_path = msg_dir / "messages.properties"
        custom_messages_path = msg_dir / f"messages_{lang_suffix}.properties"
        eng_template_path = templates_dir / "messages_en.properties"
        base_template_path = templates_dir / "messages.properties"
        lang_template_path = templates_dir / f"messages_{lang_suffix}.properties"

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

        if lang_suffix != "en" and eng_template_path.exists():
            en_in_project = msg_dir / "messages_en.properties"
            if not en_in_project.exists():
                shutil.copy2(eng_template_path, en_in_project)
                logger.info("[+] Copied English locale bundle: messages_en.properties")

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
