# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations

from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})

class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0005_rename_get_case_attachment_by_name'),
    ]

    operations = [
        migrator.get_migration('get_case_by_external_id.sql'),
    ]