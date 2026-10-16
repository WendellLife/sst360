import uuid

from django.db import migrations, models


def gerar_tokens(apps, schema_editor):
    Lead = apps.get_model("crm", "Lead")
    for lead in Lead.objects.all().only("pk"):
        Lead.objects.filter(pk=lead.pk).update(token=uuid.uuid4())


MESES = [(1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"), (5, "Maio"), (6, "Junho"),
         (7, "Julho"), (8, "Agosto"), (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro")]


class Migration(migrations.Migration):

    dependencies = [("crm", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="lead", name="renovacao_mes",
            field=models.PositiveSmallIntegerField(
                "mês de renovação do contrato atual", choices=MESES, null=True, blank=True,
                help_text="Quando vence o contrato de SST que a empresa tem hoje. A régua acelera 3, 2 e 1 mês antes."),
        ),
        migrations.AddField(model_name="lead", name="fornecedor_atual",
                            field=models.CharField("fornecedor atual de SST", max_length=150, blank=True)),
        migrations.AddField(model_name="lead", name="aceita_email",
                            field=models.BooleanField("aceita e-mail com conteúdo e ofertas", default=True)),
        migrations.AddField(model_name="lead", name="aceita_whatsapp",
                            field=models.BooleanField("aceita mensagem no WhatsApp", default=True)),
        migrations.AddField(model_name="lead", name="descadastrado_em",
                            field=models.DateTimeField("pediu para não receber em", null=True, blank=True)),
        migrations.AddField(model_name="lead", name="cotacao_pedida_em",
                            field=models.DateTimeField("pediu para participar da cotação em", null=True, blank=True)),
        # token: entra nulo, cada lead recebe o seu, depois vira único
        migrations.AddField(model_name="lead", name="token",
                            field=models.UUIDField("token dos links públicos", null=True, editable=False)),
        migrations.RunPython(gerar_tokens, migrations.RunPython.noop),
        migrations.AlterField(model_name="lead", name="token",
                              field=models.UUIDField("token dos links públicos", default=uuid.uuid4, unique=True, editable=False)),
    ]
