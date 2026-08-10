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

import functools

from jmix_cli.core.config import get_ollama_config, get_ollama_endpoint, get_ollama_model
from jmix_cli.core.constants import ISO_LANG_NAMES, JMIX_TRANSLATIONS_MAP
from jmix_cli.core.csv import validate_csv_path
from jmix_cli.core.files import (
    append_unique,
    ensure_dir,
    replace_entity_messages,
    update_checkbox_required_state_property,
    write_file,
)
from jmix_cli.core.java import inject_import_if_missing, to_camel_case_lower
from jmix_cli.core.logger import get_logger
from jmix_cli.core.project import (
    COMPANY,
    PROIECT_PATH,
    PROJECT,
    company_path,
    get_company_name,
    get_project_name,
    project_name,
)
from jmix_cli.i18n import ask_ollama_translation, update_messages_entity
from jmix_cli.entity import (
    get_entities_from_csv,
    get_traits_from_csv,
    get_relations_from_csv,
    get_sorted_entities_by_dependency,
    has_existing_entity_and_changelog,
    gen_entity_mechanic_from_csv,
    _inject_composition_into_parent,
)
from jmix_cli.views import (
    gen_list_view_from_csv,
    gen_detail_view_from_csv,
    inject_composition_ui_into_parent,
    inject_list_ui_into_existing_user,
    inject_detail_ui_into_existing_user,
    inject_nn_grid_into_inverse_entity,
    inject_nn_datagrid_into_source_entity,
)
from jmix_cli.liquibase import (
    gen_liquibase_changelog_from_csv,
    gen_liquibase_relations_changelog,
    map_type,
)
from jmix_cli.security import gen_jmix_resource_roles_from_csv
from jmix_cli.user import inject_relations_into_existing_user


def _get_migrate_module():
    import jmix_cli.migrate as _migrate
    return _migrate


def _lazy_class(name):
    def _wrapper(*args, **kwargs):
        mod = _get_migrate_module()
        real_cls = getattr(mod, name)
        return real_cls(*args, **kwargs)
    _wrapper.__name__ = name
    _wrapper.__qualname__ = name
    return _wrapper


def _lazy_func(name):
    def _wrapper(*args, **kwargs):
        mod = _get_migrate_module()
        real_fn = getattr(mod, name)
        return real_fn(*args, **kwargs)
    _wrapper.__name__ = name
    _wrapper.__qualname__ = name
    return _wrapper


migrate_entity = _lazy_func("migrate_entity")
migrate_all_entities = _lazy_func("migrate_all_entities")
HSQLDBAdapter = _lazy_class("HSQLDBAdapter")
get_existing_columns_from_changelogs = _lazy_func("get_existing_columns_from_changelogs")
detect_changed_fields = _lazy_func("detect_changed_fields")
detect_dropped_columns = _lazy_func("detect_dropped_columns")
detect_field_metadata_changes = _lazy_func("detect_field_metadata_changes")
detect_missing_columns = _lazy_func("detect_missing_columns")
detect_missing_relations = _lazy_func("detect_missing_relations")
detect_relation_metadata_changes = _lazy_func("detect_relation_metadata_changes")
get_table_name = _lazy_func("get_table_name")
map_type_to_sql = _lazy_func("map_type_to_sql")
gen_add_column_changelog = _lazy_func("gen_add_column_changelog")
gen_drop_column_changelog = _lazy_func("gen_drop_column_changelog")
gen_modify_column_changelog = _lazy_func("gen_modify_column_changelog")
gen_rename_column_changelog = _lazy_func("gen_rename_column_changelog")
_add_import_after = _lazy_func("_add_import_after")
_append_index_entry = _lazy_func("_append_index_entry")
_remove_fields_from_java = _lazy_func("_remove_fields_from_java")
_remove_index_entry = _lazy_func("_remove_index_entry")
_update_java_for_metadata_changes = _lazy_func("_update_java_for_metadata_changes")
inject_new_fields_into_existing_entity = _lazy_func("inject_new_fields_into_existing_entity")
DatabaseAdapter = _lazy_class("DatabaseAdapter")
PostgreSQLAdapter = _lazy_class("PostgreSQLAdapter")
get_executed_changelog_ids = _lazy_func("get_executed_changelog_ids")


__all__ = [
    "get_logger",
    "get_project_name",
    "get_company_name",
    "PROIECT_PATH",
    "PROJECT",
    "project_name",
    "COMPANY",
    "company_path",
    "to_camel_case_lower",
    "inject_import_if_missing",
    "validate_csv_path",
    "ensure_dir",
    "write_file",
    "replace_entity_messages",
    "append_unique",
    "update_checkbox_required_state_property",
    "ISO_LANG_NAMES",
    "JMIX_TRANSLATIONS_MAP",
    "get_ollama_config",
    "get_ollama_endpoint",
    "get_ollama_model",
    "ask_ollama_translation",
    "update_messages_entity",
    "get_entities_from_csv",
    "get_traits_from_csv",
    "get_relations_from_csv",
    "get_sorted_entities_by_dependency",
    "has_existing_entity_and_changelog",
    "gen_entity_mechanic_from_csv",
    "_inject_composition_into_parent",
    "gen_list_view_from_csv",
    "gen_detail_view_from_csv",
    "inject_composition_ui_into_parent",
    "inject_list_ui_into_existing_user",
    "inject_detail_ui_into_existing_user",
    "inject_nn_grid_into_inverse_entity",
    "inject_nn_datagrid_into_source_entity",
    "gen_liquibase_changelog_from_csv",
    "gen_liquibase_relations_changelog",
    "map_type",
    "gen_jmix_resource_roles_from_csv",
    "inject_relations_into_existing_user",
    "migrate_entity",
    "migrate_all_entities",
    "HSQLDBAdapter",
    "get_existing_columns_from_changelogs",
    "detect_changed_fields",
    "detect_dropped_columns",
    "detect_field_metadata_changes",
    "detect_missing_columns",
    "detect_missing_relations",
    "detect_relation_metadata_changes",
    "get_table_name",
    "map_type_to_sql",
    "gen_add_column_changelog",
    "gen_drop_column_changelog",
    "gen_modify_column_changelog",
    "gen_rename_column_changelog",
    "_add_import_after",
    "_append_index_entry",
    "_remove_fields_from_java",
    "_remove_index_entry",
    "_update_java_for_metadata_changes",
    "inject_new_fields_into_existing_entity",
    "DatabaseAdapter",
    "PostgreSQLAdapter",
    "get_executed_changelog_ids",
]
