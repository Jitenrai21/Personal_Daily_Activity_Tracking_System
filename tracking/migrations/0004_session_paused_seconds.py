from django.db import migrations, models


def ensure_paused_seconds_column(apps, schema_editor):
    Session = apps.get_model("tracking", "Session")
    table_name = Session._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if "paused_seconds" not in columns:
        schema_editor.execute(
            f'ALTER TABLE "{table_name}" ADD COLUMN "paused_seconds" integer NOT NULL DEFAULT 0'
        )
    else:
        schema_editor.execute(
            f'UPDATE "{table_name}" SET "paused_seconds" = 0 WHERE "paused_seconds" IS NULL'
        )


class Migration(migrations.Migration):
    dependencies = [
        ("tracking", "0003_alter_session_options_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(ensure_paused_seconds_column, migrations.RunPython.noop)],
            state_operations=[
                migrations.AddField(
                    model_name="session",
                    name="paused_seconds",
                    field=models.PositiveIntegerField(default=0),
                ),
            ],
        ),
    ]
