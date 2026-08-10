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

from jmix_cli.migrate.engine import migrate_entity, migrate_all_entities
from jmix_cli.migrate.diff import (
    detect_changed_fields,
    detect_dropped_columns,
    detect_field_metadata_changes,
    detect_missing_columns,
    detect_missing_relations,
    detect_relation_metadata_changes,
    get_table_name,
    map_type_to_sql,
)
from jmix_cli.migrate.changelog import (
    gen_add_column_changelog,
    gen_drop_column_changelog,
    gen_modify_column_changelog,
    gen_rename_column_changelog,
)
from jmix_cli.migrate.java import (
    _add_import_after,
    _append_index_entry,
    _remove_fields_from_java,
    _remove_index_entry,
    _update_java_for_metadata_changes,
    inject_new_fields_into_existing_entity,
)
from jmix_cli.migrate.adapters import (
    DatabaseAdapter,
    HSQLDBAdapter,
    PostgreSQLAdapter,
    get_existing_columns_from_changelogs,
    get_executed_changelog_ids,
)

__all__ = [
    "migrate_entity",
    "migrate_all_entities",
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
    "HSQLDBAdapter",
    "PostgreSQLAdapter",
    "get_existing_columns_from_changelogs",
    "get_executed_changelog_ids",
]
