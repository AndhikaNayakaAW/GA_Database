# Generated by Django 5.1.3 on 2024-12-06 07:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("yellow", "0002_worker"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="worker",
            name="id",
        ),
        migrations.DeleteModel(
            name="User",
        ),
        migrations.DeleteModel(
            name="Worker",
        ),
    ]