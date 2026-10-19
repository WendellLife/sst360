"""Arquivos enviados: nome gerado, tipos permitidos, checagem de conteúdo e download autenticado.

Nada em /media/ é servido por URL pública; os arquivos saem pelas views de apps.core.downloads.
"""
import mimetypes
import os
import posixpath
import uuid

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.utils.deconstruct import deconstructible

EXTENSOES_PERMITIDAS = (
    ".pdf", ".png", ".jpg", ".jpeg", ".webp",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".odt", ".ods", ".txt",
)
EXTENSOES_PLANILHA = (".xlsx", ".xlsm", ".csv", ".txt")

_ZIP = (b"PK\x03\x04",)
_OLE = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)
_ASSINATURAS = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    ".doc": _OLE,
    ".xls": _OLE,
    ".docx": _ZIP,
    ".xlsx": _ZIP,
    ".xlsm": _ZIP,
    ".odt": _ZIP,
    ".ods": _ZIP,
}
_TEXTO = (".csv", ".txt")


def extensao(nome: str) -> str:
    return os.path.splitext(nome or "")[1].lower()


def nome_uuid(nome_original: str) -> str:
    """Nome novo e imprevisível, mantendo só a extensão (em minúsculas)."""
    return f"{uuid.uuid4().hex}{extensao(nome_original)}"


@deconstructible
class CaminhoUuid:
    """upload_to que guarda em `<pasta>/<id da gestão>/<uuid>.<ext>`."""

    def __init__(self, pasta: str):
        self.pasta = pasta

    def __call__(self, instance, filename: str) -> str:
        return posixpath.join(self.pasta, str(instance.gestao_id), nome_uuid(filename))

    def __eq__(self, other):
        return isinstance(other, CaminhoUuid) and other.pasta == self.pasta


def validar_arquivo_enviado(arquivo, extensoes=EXTENSOES_PERMITIDAS) -> None:
    """Recusa extensão fora da lista e conteúdo que não bate com ela."""
    nome = getattr(arquivo, "name", "") or ""
    ext = extensao(nome)
    if ext not in extensoes:
        permitidas = ", ".join(e.lstrip(".") for e in extensoes)
        raise ValidationError(f"Tipo de arquivo não aceito. Envie: {permitidas}.")
    try:
        arquivo.seek(0)
        inicio = arquivo.read(4096)
        arquivo.seek(0)
    except (AttributeError, ValueError, OSError):
        return  # arquivo já gravado e fechado: nada a conferir aqui
    if isinstance(inicio, str):
        inicio = inicio.encode("utf-8", "ignore")
    if ext in _TEXTO:
        if b"\x00" in inicio:
            raise ValidationError("O conteúdo do arquivo não é texto.")
        return
    assinaturas = _ASSINATURAS.get(ext)
    if assinaturas and not inicio.startswith(assinaturas):
        raise ValidationError("O conteúdo do arquivo não confere com o tipo informado.")
    if ext == ".webp" and inicio[8:12] != b"WEBP":
        raise ValidationError("O conteúdo do arquivo não confere com o tipo informado.")


def validar_documento(arquivo) -> None:
    validar_arquivo_enviado(arquivo, EXTENSOES_PERMITIDAS)


def validar_planilha(arquivo) -> None:
    validar_arquivo_enviado(arquivo, EXTENSOES_PLANILHA)


def resposta_download(campo, nome_amigavel: str = "") -> FileResponse:
    """Entrega o arquivo como anexo, sem deixar o navegador interpretar o conteúdo."""
    if not campo:
        raise Http404("Arquivo não encontrado.")
    try:
        arquivo = campo.storage.open(campo.name, "rb")
    except (FileNotFoundError, OSError):
        raise Http404("Arquivo não encontrado.")
    base = posixpath.basename(campo.name)
    ext = extensao(base)
    nome = nome_amigavel.strip() or base
    if extensao(nome) != ext:
        nome = f"{nome}{ext}"
    tipo = mimetypes.guess_type(base)[0] if ext in EXTENSOES_PERMITIDAS + (".xlsm",) else None
    resposta = FileResponse(arquivo, as_attachment=True, filename=nome, content_type=tipo or "application/octet-stream")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta
