# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import analytic_account
from . import project_project_stage
from . import project_task_recurrence
# `project_task_stage_personal` has to be loaded before `project`
from . import project_task_stage_personal
from . import project
from . import res_config_settings
from . import res_partner
from . import digest
