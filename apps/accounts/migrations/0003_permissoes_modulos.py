from django.db import migrations, models


def liberar_existentes(apps, schema_editor):
    """Quem já era da equipe interna continua vendo tudo; a administração ajusta depois."""
    User = apps.get_model("accounts", "User")
    User.objects.filter(tipo="INTERNO").update(acesso_comercial=True, acesso_tecnico=True)
    User.objects.filter(tipo="INTERNO", is_staff=True).update(acesso_admin=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="acesso_comercial",
            field=models.BooleanField(
                default=True, verbose_name="comercial",
                help_text="Painel, indicadores, funil, leads, diagnósticos, vendas, campanhas, FAP e dados do Tarefas.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="acesso_tecnico",
            field=models.BooleanField(
                default=False, verbose_name="técnico",
                help_text="Gestões de SST, prazos, vencimentos, documentos, treinamentos e relacionamento com o cliente.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="acesso_admin",
            field=models.BooleanField(
                default=False, verbose_name="administração", help_text="Cadastra pessoas e define o acesso de cada uma.",
            ),
        ),
        migrations.RunPython(liberar_existentes, migrations.RunPython.noop),
    ]
