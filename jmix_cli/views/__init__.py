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

from jmix_cli.views.list import gen_list_view_from_csv
from jmix_cli.views.detail import gen_detail_view_from_csv
from jmix_cli.views.composition import inject_composition_ui_into_parent
from jmix_cli.views.user import inject_list_ui_into_existing_user, inject_detail_ui_into_existing_user
from jmix_cli.views.nn_grid import inject_nn_grid_into_inverse_entity, inject_nn_datagrid_into_source_entity

__all__ = [
    "gen_list_view_from_csv",
    "gen_detail_view_from_csv",
    "inject_composition_ui_into_parent",
    "inject_list_ui_into_existing_user",
    "inject_detail_ui_into_existing_user",
    "inject_nn_grid_into_inverse_entity",
    "inject_nn_datagrid_into_source_entity",
]
