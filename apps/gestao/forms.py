from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.core.arquivos import validar_planilha

from .models import AcaoPlano, Documento, FichaFap, Gestao, Prazo, Registro, Servico, Treinamento


def _data(**extra):
    return forms.DateInput(attrs={"type": "date", **extra}, format="%Y-%m-%d")


class GestaoForm(forms.ModelForm):
    servicos = forms.MultipleChoiceField(
        label="Serviços contratados",
        choices=Servico.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Gestao
        fields = [
            "empresa", "etapa", "modelo", "servicos", "inicio", "responsavel",
            "responsavel_tecnico", "medico_coordenador", "certificacao_sgsst",
            "fap_atual", "fap_meta", "valor_mensal", "encerrado_em", "observacoes",
        ]
        widgets = {
            "inicio": _data(),
            "encerrado_em": _data(),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import TipoUsuario

        self.fields["responsavel"].queryset = self.fields["responsavel"].queryset.filter(
            tipo=TipoUsuario.INTERNO
        )


class RegistroForm(forms.ModelForm):
    class Meta:
        model = Registro
        fields = ["data", "tipo", "titulo", "descricao", "visivel_cliente"]
        widgets = {"data": _data(), "descricao": forms.Textarea(attrs={"rows": 3})}


class PrazoForm(forms.ModelForm):
    class Meta:
        model = Prazo
        fields = ["titulo", "base_legal", "tipo", "data_inicio", "data_fim", "responsavel", "observacoes"]
        widgets = {
            "data_inicio": _data(),
            "data_fim": _data(),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "titulo", "status", "emitido_em", "valido_ate",
                  "responsavel_tecnico", "arquivo", "visivel_cliente"]
        widgets = {"emitido_em": _data(), "valido_ate": _data()}


class TreinamentoForm(forms.ModelForm):
    class Meta:
        model = Treinamento
        fields = ["tipo", "titulo", "modalidade", "status", "previsto_para", "realizado_em",
                  "carga_horaria", "participantes", "valido_ate", "visivel_cliente"]
        widgets = {"previsto_para": _data(), "realizado_em": _data(), "valido_ate": _data()}


class AcaoPlanoForm(forms.ModelForm):
    class Meta:
        model = AcaoPlano
        fields = ["descricao", "risco", "setor", "prioridade", "responsavel_empresa",
                  "prazo", "status", "custo_estimado", "visivel_cliente"]
        widgets = {"prazo": _data()}


class ImportacaoPlanoForm(forms.Form):
    """Upload da planilha do plano de acao."""

    POLITICAS = [
        ("atualizar", "Atualizar as ações já cadastradas"),
        ("ignorar", "Manter como está e importar só as novas"),
        ("duplicar", "Importar tudo como novo (pode duplicar)"),
    ]

    arquivo = forms.FileField(
        label="Planilha (.xlsx ou .csv)",
        help_text="A primeira linha deve ser o cabeçalho.",
    )
    politica = forms.ChoiceField(
        label="Ação já cadastrada (mesma ação no mesmo setor)", choices=POLITICAS, initial="atualizar"
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Arquivo muito grande (limite de 10 MB).")
        try:
            validar_planilha(arquivo)
        except ValidationError:
            raise forms.ValidationError("Envie um arquivo .xlsx ou .csv válido.")
        return arquivo


class FichaFapForm(forms.ModelForm):
    class Meta:
        model = FichaFap
        fields = ["vigencia", "grau_rat", "percentil_gravidade", "percentil_frequencia", "percentil_custo",
                  "bloqueio", "fap_oficial", "folha_mensal", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 2}),
            "percentil_gravidade": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "percentil_frequencia": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "percentil_custo": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "fap_oficial": forms.NumberInput(attrs={"step": "0.0001", "min": "0.5", "max": "2"}),
            "folha_mensal": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "vigencia": forms.NumberInput(attrs={"min": "2010", "max": "2100"}),
        }

    def clean(self):
        dados = super().clean()
        for campo in ("percentil_gravidade", "percentil_frequencia", "percentil_custo"):
            valor = dados.get(campo)
            if valor is not None and not 0 <= valor <= 100:
                self.add_error(campo, "Use um valor de 0 a 100.")
        fap = dados.get("fap_oficial")
        if fap is not None and not Decimal("0.5") <= fap <= Decimal("2"):
            self.add_error("fap_oficial", "O FAP vai de 0,5000 a 2,0000.")
        percentis = [dados.get(c) for c in ("percentil_gravidade", "percentil_frequencia", "percentil_custo")]
        if fap is None and any(p is None for p in percentis):
            raise forms.ValidationError("Informe os três percentis do FAPWeb ou o FAP oficial.")
        return dados
