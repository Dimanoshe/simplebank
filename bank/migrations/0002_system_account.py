from django.db import migrations


def create_system_account(apps, schema_editor):
    Account = apps.get_model('bank', 'Account')
    Account.objects.create(number='0000000000')


class Migration(migrations.Migration):
    dependencies = [('bank', '0001_initial')]

    operations = [migrations.RunPython(create_system_account, migrations.RunPython.noop)]
