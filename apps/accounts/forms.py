"""Gestão de usuários: cadastro e acesso por módulo, feitos pela administração do sistema."""
from django import forms
from django.contrib.auth import get_user_model, password_validation

from .models import TipoUsuario

User = get_user_model()


class UsuarioForm(forms.ModelForm):
    senha = forms.CharField(
        label="Senha", required=False, strip=False, widget=forms.PasswordInput(render_value=False),
        help_text="No cadastro é obrigatória. Na edição, deixe vazio para manter a senha atual.",
    )

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "email", "username", "cargo", "telefone",
            "tipo", "empresa", "acesso_comercial", "acesso_tecnico", "acesso_admin", "is_active",
        ]
        labels = {
            "first_name": "Nome", "last_name": "Sobrenome", "email": "E-mail", "username": "Usuário",
            "is_active": "Acesso ativo",
        }
        help_texts = {
            "username": "Usado para entrar, junto com o e-mail. Letras, números e @ . + - _",
            "empresa": "Só para cliente do portal: a empresa que ele acompanha.",
            "is_active": "Desmarcado, a pessoa não entra mais (o histórico fica).",
        }

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.novo = self.instance.pk is None
        if self.novo:
            self.fields["senha"].required = True
            self.fields["senha"].help_text = "Mínimo de 8 caracteres. A pessoa pode trocar depois em Minha conta."

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um usuário com esse e-mail.")
        return email

    def clean(self):
        dados = super().clean()
        tipo = dados.get("tipo")
        if tipo == TipoUsuario.CLIENTE:
            if not dados.get("empresa"):
                self.add_error("empresa", "Cliente do portal precisa de uma empresa vinculada.")
            dados["acesso_comercial"] = dados["acesso_tecnico"] = dados["acesso_admin"] = False
        elif tipo == TipoUsuario.INTERNO:
            dados["empresa"] = None
            if not (dados.get("acesso_comercial") or dados.get("acesso_tecnico") or dados.get("acesso_admin")):
                self.add_error("acesso_comercial", "Marque ao menos um módulo para a equipe interna.")
        # Quem edita não tira o próprio acesso à administração nem se desativa por engano.
        if self.editor and self.instance.pk == self.editor.pk:
            if not dados.get("acesso_admin") and not self.editor.is_superuser:
                self.add_error("acesso_admin", "Você não pode tirar o seu próprio acesso à administração.")
            if not dados.get("is_active"):
                self.add_error("is_active", "Você não pode desativar o seu próprio usuário.")
        senha = dados.get("senha")
        if senha:
            try:
                password_validation.validate_password(senha, self.instance)
            except forms.ValidationError as erro:
                self.add_error("senha", erro)
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get("senha"):
            usuario.set_password(self.cleaned_data["senha"])
        if commit:
            usuario.save()
        return usuario
