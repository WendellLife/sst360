from django import forms

from apps.accounts.models import TipoUsuario

from .models import Venda


class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = ["empresa", "gestao", "data", "servico", "descricao", "quantidade", "valor_unitario",
                  "cobranca", "status", "vendedor", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
            "valor_unitario": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendedor"].queryset = self.fields["vendedor"].queryset.filter(tipo=TipoUsuario.INTERNO)
        self.fields["gestao"].required = False
        if empresa is not None:
            self.fields["empresa"].initial = empresa.pk
            self.fields["empresa"].widget = forms.HiddenInput()
            self.fields["gestao"].queryset = empresa.gestoes.all()
        else:
            self.fields["gestao"].queryset = self.fields["gestao"].queryset.select_related("empresa")

    def clean(self):
        dados = super().clean()
        gestao, empresa = dados.get("gestao"), dados.get("empresa")
        if gestao and empresa and gestao.empresa_id != empresa.pk:
            self.add_error("gestao", "Esta gestão é de outra empresa.")
        return dados
