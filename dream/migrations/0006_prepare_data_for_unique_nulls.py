from django.db import migrations

def set_empty_strings_to_null(apps, schema_editor):
    """
    查找用户记录中email或phone_number为空字符串的字段，并将其设置为NULL，
    以满足即将应用的UNIQUE约束（在MySQL中，多个NULL值是允许的，但多个空字符串''是不允许的）。
    """
    User = apps.get_model('dream', 'User')
    db_alias = schema_editor.connection.alias

    # 将空的email更新为NULL
    User.objects.using(db_alias).filter(email='').update(email=None)

    # 将空的phone_number更新为NULL
    User.objects.using(db_alias).filter(phone_number='').update(phone_number=None)

class Migration(migrations.Migration):

    dependencies = [
        ('dream', '0005_alter_tag_unique_together_remove_tag_created_by'),
    ]

    operations = [
        # 运行Python函数来修复数据，第二个参数是反向操作（此处不需要）
        migrations.RunPython(set_empty_strings_to_null, migrations.RunPython.noop),
    ] 