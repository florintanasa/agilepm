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
import sys
from datetime import datetime
from pathlib import Path

from jmix_cli.core.project import COMPANY, PROIECT_PATH, PROJECT, project_name
from jmix_cli.core.logger import get_logger
from jmix_cli.exceptions import JmixCliError, ConfigurationError, GenerationError, UserInputError
from jmix_cli.cli.dry_run import (
    _dry_run_enabled,
    _finish_dry_run,
    _handle_error,
    _patch_globals_for_dry_run,
    _copy_project_to_temp,
    _finalize_composition_relationships,
    update_checkbox_required_state_property,
)
from jmix_cli.cli.commands.entity import generate_single_entity, generate_all_entities
from jmix_cli.cli.commands.migrate import run_migrate, run_migrate_all
from jmix_cli.cli.commands.security import run_security
from jmix_cli.cli.commands.ui import (
    generate_single_list_view,
    generate_single_detail_view,
    generate_all_list_views,
    generate_all_detail_views,
)
from jmix_cli.cli.commands.build import run_build_all
from jmix_cli.cli.dry_run import inject_audit_dependencies
from jmix_cli.entity.relations.base import get_relations_from_csv
from jmix_cli.entity.generator import _inject_composition_into_parent, get_sorted_entities_by_dependency

logger = get_logger("jmix_cli.cli.main")


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
    dry_run_temp_dir = None
    original_dir = Path.cwd()

    try:
        if dry_run and len(sys.argv) > 1 and sys.argv[1].lower() == "init":
            raise UserInputError("--dry-run nu este suportat pentru 'init'.")

        if dry_run and len(sys.argv) > 1 and sys.argv[1].lower() in ("migrate", "migrate-all"):
            raise UserInputError("--dry-run nu este suportat pentru 'migrate' sau 'migrate-all'.")

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
            from jmix_cli.cli.commands.init import cmd_init_project
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
            import os
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
            run_security()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "entity-all":
            inject_audit_dependencies()
            generate_all_entities()
            logger.info("\n[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
            ordered_list = get_sorted_entities_by_dependency()
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
            generate_all_list_views()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "ui-detail-all":
            generate_all_detail_views()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        elif action == "build-all":
            run_build_all(dry_run=dry_run)
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        if action == "migrate-all":
            logger.info("[*] Running incremental DB migrations for all entities...")
            mode = "force" if "--force" in sys.argv else "prompt"
            run_migrate_all(mode)
            logger.info("[⚡] PHASE 1.6: Injecting COMPOSITION_1:N relationships into parent entities...")
            ordered_list = get_sorted_entities_by_dependency()
            for ent in ordered_list:
                relations_list = get_relations_from_csv("relations.csv", ent)
                composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
                if composition_rels:
                    _inject_composition_into_parent(ent, composition_rels)
            _finalize_composition_relationships()
            update_checkbox_required_state_property()
            _finish_dry_run(dry_run_temp_dir, original_dir)
            return

        if len(sys.argv) == 2:
            raise UserInputError("Missing required Entity Name parameter.")

        name = sys.argv[2]

        if action == "migrate":
            mode = "force" if "--force" in sys.argv else "prompt"
            run_migrate(name, mode)

        elif action == "entity":
            generate_single_entity(name)

        elif action == "ui-list":
            if name == "User":
                logger.info("[*] Triggering FlowUI List View infiltration for system User...")
                relations_list = get_relations_from_csv("relations.csv", "User")
                generate_single_list_view(name)
            else:
                generate_single_list_view(name)

        elif action == "ui-detail":
            if name == "User":
                logger.info("[*] Triggering FlowUI Detail View infiltration for system User...")
                relations_list = get_relations_from_csv("relations.csv", "User")
                generate_single_detail_view(name)
            else:
                generate_single_detail_view(name)

        else:
            raise UserInputError(f"Unknown action: '{action}'. Use entity, ui-list, ui-detail or security.")

        _finish_dry_run(dry_run_temp_dir, original_dir)
    except JmixCliError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)
