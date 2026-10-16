"""Regras da régua de relacionamento.

Todo mês cada lead que ainda não é cliente recebe uma mensagem. A etapa depende da distância
até o mês de renovação do contrato de SST que ele tem hoje:

    3 meses antes -> R90 · 2 meses -> R60 · 1 mês -> R30 · no mês -> R0 · demais meses -> MENSAL

O e-mail sai sozinho (comando regua_mensal ou botão no painel). O WhatsApp fica numa fila: o
vendedor abre a mensagem pronta e envia do próprio WhatsApp, sem risco de bloqueio do número.
"""
import re
from datetime import date, datetime
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.crm.models import MESES, Atividade, Estagio, Lead, TipoAtividade

from .conteudo import CONTEUDO_DO_MES, MODELOS
from .models import MESES_NOMES, Campanha, Canal, Envio, Etapa, Modelo, StatusEnvio

DISTANCIA_ETAPA = {0: Etapa.R0, 1: Etapa.R30, 2: Etapa.R60, 3: Etapa.R90}
NOME_MES = dict(MESES)


class _Seguro(dict):
    """Campo desconhecido no texto fica como está, em vez de quebrar o envio."""

    def __missing__(self, chave):
        return "{" + chave + "}"


# ---------------------------------------------------------------- público e etapa
def publico():
    """Leads que ainda não são clientes e não pediram para sair (inclui os perdidos: renovaram com outro)."""
    return (
        Lead.objects.filter(empresa__isnull=True, descadastrado_em__isnull=True)
        .exclude(estagio=Estagio.GANHO)
        .select_related("responsavel")
    )


def distancia_meses(renovacao_mes: int, mes: int) -> int:
    return (renovacao_mes - mes) % 12


def etapa_do_lead(lead, ano: int, mes: int) -> str:
    if not lead.renovacao_mes:
        return Etapa.MENSAL
    return DISTANCIA_ETAPA.get(distancia_meses(lead.renovacao_mes, mes), Etapa.MENSAL)


def proxima_renovacao(lead, hoje: date | None = None) -> date | None:
    if not lead.renovacao_mes:
        return None
    hoje = hoje or timezone.localdate()
    ano = hoje.year if lead.renovacao_mes >= hoje.month else hoje.year + 1
    return date(ano, lead.renovacao_mes, 1)


def renovacoes_proximas(hoje: date | None = None, meses: int = 3):
    """Leads do público com renovação neste mês ou nos próximos `meses`, da mais próxima para a mais distante."""
    hoje = hoje or timezone.localdate()
    linhas = []
    for lead in publico().filter(renovacao_mes__isnull=False):
        d = distancia_meses(lead.renovacao_mes, hoje.month)
        if d <= meses:
            linhas.append({"lead": lead, "distancia": d, "etapa": DISTANCIA_ETAPA.get(d, Etapa.MENSAL),
                           "renovacao": proxima_renovacao(lead, hoje)})
    linhas.sort(key=lambda x: (x["distancia"], str(x["lead"])))
    return linhas


def pode_receber(lead, canal: str) -> bool:
    if lead.descadastrado_em:
        return False
    if canal == Canal.EMAIL:
        return bool(lead.aceita_email and lead.contato_email)
    return bool(lead.aceita_whatsapp and telefone_whatsapp(lead.contato_telefone))


def telefone_whatsapp(telefone: str) -> str:
    """'(11) 91234-5678' -> '5511912345678'. Vazio se não parecer um celular/fixo brasileiro."""
    d = re.sub(r"\D", "", telefone or "")
    if d.startswith("0"):
        d = d.lstrip("0")
    if len(d) in (10, 11):
        d = "55" + d
    return d if len(d) in (12, 13) and d.startswith("55") else ""


# ---------------------------------------------------------------- campanha e modelos
def garantir_modelos():
    for etapa, (assunto, email, whatsapp) in MODELOS.items():
        Modelo.objects.get_or_create(etapa=etapa, defaults={"assunto": assunto, "email": email, "whatsapp": whatsapp})
    return {m.etapa: m for m in Modelo.objects.all()}


def garantir_campanha(ano: int, mes: int) -> Campanha:
    tema, conteudo = CONTEUDO_DO_MES[mes]
    campanha, _ = Campanha.objects.get_or_create(ano=ano, mes=mes, defaults={"tema": tema, "conteudo": conteudo})
    return campanha


def campanha_atual(hoje: date | None = None) -> Campanha:
    hoje = hoje or timezone.localdate()
    return garantir_campanha(hoje.year, hoje.month)


# ---------------------------------------------------------------- textos
def url_absoluta(caminho: str) -> str:
    return settings.SITE_URL.rstrip("/") + caminho


def contexto(lead, campanha: Campanha, envio: Envio | None = None) -> dict:
    nome = (lead.contato_nome or "").strip().split(" ")[0] or "tudo bem"
    remetente = lead.responsavel.get_full_name() if lead.responsavel and lead.responsavel.get_full_name() else "Equipe Universo FX · Life Laboral"
    token = envio.token if envio else lead.token
    return {
        "contato": nome,
        "empresa": str(lead),
        "mes_renovacao": NOME_MES.get(lead.renovacao_mes, "").lower() or "o mês da renovação",
        "fornecedor": lead.fornecedor_atual or "o fornecedor atual",
        "tema": campanha.tema,
        "conteudo": campanha.conteudo,
        "mes": MESES_NOMES[campanha.mes - 1],
        "remetente": remetente,
        "link_proposta": url_absoluta(reverse("campanhas:proposta", args=[token])),
    }


def preencher(texto: str, ctx: dict) -> str:
    return (texto or "").format_map(_Seguro(ctx))


def mensagem(envio: Envio, modelos: dict | None = None) -> dict:
    modelos = modelos or garantir_modelos()
    modelo = modelos[envio.etapa]
    ctx = contexto(envio.lead, envio.campanha, envio)
    return {
        "assunto": preencher(modelo.assunto, ctx),
        "email": preencher(modelo.email, ctx),
        "whatsapp": preencher(modelo.whatsapp, ctx),
        "ctx": ctx,
    }


def link_whatsapp(envio: Envio, modelos: dict | None = None) -> str:
    texto = mensagem(envio, modelos)["whatsapp"]
    return f"https://wa.me/{telefone_whatsapp(envio.lead.contato_telefone)}?text={quote(texto)}"


# ---------------------------------------------------------------- geração e envio
def gerar_envios(campanha: Campanha) -> dict:
    """Cria os envios pendentes do mês para cada lead e canal permitido. Pode rodar de novo sem duplicar."""
    criados = {Canal.EMAIL: 0, Canal.WHATSAPP: 0}
    for lead in publico():
        etapa = etapa_do_lead(lead, campanha.ano, campanha.mes)
        for canal in (Canal.EMAIL, Canal.WHATSAPP):
            if not pode_receber(lead, canal):
                continue
            _, novo = Envio.objects.get_or_create(campanha=campanha, lead=lead, canal=canal, defaults={"etapa": etapa})
            criados[canal] += int(novo)
    campanha.envios_gerados_em = timezone.now()
    campanha.save(update_fields=["envios_gerados_em", "atualizado_em"])
    return criados


def _email(envio: Envio, modelos: dict) -> EmailMultiAlternatives:
    m = mensagem(envio, modelos)
    link_sair = url_absoluta(reverse("campanhas:descadastrar", args=[envio.token]))
    pixel = url_absoluta(reverse("campanhas:pixel", args=[envio.token]))
    paragrafos = [p.strip() for p in m["email"].split("\n\n") if p.strip()]
    contexto_html = {"paragrafos": paragrafos, "link_proposta": m["ctx"]["link_proposta"], "link_sair": link_sair,
                     "pixel": pixel, "assunto": m["assunto"], "etapa": envio.etapa}
    texto = m["email"] + f"\n\nQuero participar da cotação: {m['ctx']['link_proposta']}\n\nNão quer mais receber? {link_sair}"
    msg = EmailMultiAlternatives(m["assunto"], texto, settings.DEFAULT_FROM_EMAIL, [envio.lead.contato_email],
                                 headers={"List-Unsubscribe": f"<{link_sair}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})
    msg.attach_alternative(render_to_string("campanhas/email.html", contexto_html), "text/html")
    return msg


def enviar_emails(campanha: Campanha, usuario=None) -> dict:
    """Envia os e-mails pendentes da campanha. Falha de um não interrompe os outros."""
    modelos = garantir_modelos()
    total = {"enviados": 0, "falhas": 0, "pulados": 0}
    conexao = get_connection()
    for envio in campanha.envios.filter(canal=Canal.EMAIL, status=StatusEnvio.PENDENTE).select_related("lead", "lead__responsavel", "campanha"):
        if not pode_receber(envio.lead, Canal.EMAIL):
            envio.status = StatusEnvio.PULADO
            envio.save(update_fields=["status", "atualizado_em"])
            total["pulados"] += 1
            continue
        try:
            conexao.send_messages([_email(envio, modelos)])
        except Exception as erro:  # noqa: BLE001 - registra e segue para o próximo
            envio.status, envio.erro = StatusEnvio.FALHOU, str(erro)[:300]
            envio.save(update_fields=["status", "erro", "atualizado_em"])
            total["falhas"] += 1
            continue
        envio.status, envio.enviado_em, envio.enviado_por, envio.erro = StatusEnvio.ENVIADO, timezone.now(), usuario, ""
        envio.save(update_fields=["status", "enviado_em", "enviado_por", "erro", "atualizado_em"])
        Atividade.objects.create(lead=envio.lead, tipo=TipoAtividade.EMAIL, titulo=f"E-mail da campanha de {campanha.rotulo}",
                                 descricao=f"{envio.get_etapa_display()} · {mensagem(envio, modelos)['assunto']}", autor=usuario)
        total["enviados"] += 1
    campanha.emails_enviados_em = timezone.now()
    campanha.save(update_fields=["emails_enviados_em", "atualizado_em"])
    return total


def marcar_whatsapp_enviado(envio: Envio, usuario=None):
    if envio.status == StatusEnvio.ENVIADO:
        return
    envio.status, envio.enviado_em, envio.enviado_por = StatusEnvio.ENVIADO, timezone.now(), usuario
    envio.save(update_fields=["status", "enviado_em", "enviado_por", "atualizado_em"])
    Atividade.objects.create(lead=envio.lead, tipo=TipoAtividade.WHATSAPP, titulo=f"WhatsApp da campanha de {envio.campanha.rotulo}",
                             descricao=envio.get_etapa_display(), autor=usuario)


# ---------------------------------------------------------------- respostas do lead
def registrar_clique(envio: Envio):
    if not envio.clicado_em:
        envio.clicado_em = timezone.now()
        envio.aberto_em = envio.aberto_em or envio.clicado_em
        envio.save(update_fields=["clicado_em", "aberto_em", "atualizado_em"])


def registrar_pedido_cotacao(lead, envio: Envio | None = None) -> bool:
    """O lead confirmou que quer participar da cotação. Vai para o funil e o responsável é avisado."""
    if envio:
        registrar_clique(envio)
    if lead.cotacao_pedida_em and (timezone.now() - lead.cotacao_pedida_em).days < 1:
        return False  # clique repetido no mesmo dia
    lead.cotacao_pedida_em = timezone.now()
    lead.proximo_contato = timezone.localdate()
    if lead.estagio in (Estagio.NOVO, Estagio.CONTATO, Estagio.PERDIDO):
        lead.estagio = Estagio.DIAGNOSTICO
    lead.save(update_fields=["cotacao_pedida_em", "proximo_contato", "estagio", "atualizado_em"])
    origem = f"{envio.get_canal_display()} da campanha de {envio.campanha.rotulo}" if envio else "link da campanha"
    Atividade.objects.create(lead=lead, tipo=TipoAtividade.NOTA, titulo="Pediu para participar da cotação",
                             descricao=f"Confirmou pelo {origem}. Renovação: {NOME_MES.get(lead.renovacao_mes, 'não informada')}.")
    _avisar_responsavel(lead, origem)
    return True


def _avisar_responsavel(lead, origem: str):
    destino = lead.responsavel.email if lead.responsavel and lead.responsavel.email else None
    if not destino:
        return
    corpo = (f"{lead} pediu para participar da cotação de SST ({origem}).\n\n"
             f"Contato: {lead.contato_nome} · {lead.contato_telefone} · {lead.contato_email}\n"
             f"Renovação: {NOME_MES.get(lead.renovacao_mes, 'não informada')} · fornecedor atual: {lead.fornecedor_atual or 'não informado'}\n\n"
             f"Abrir o lead: {url_absoluta(lead.get_absolute_url())}")
    try:
        EmailMultiAlternatives(f"Pedido de cotação: {lead}", corpo, settings.DEFAULT_FROM_EMAIL, [destino]).send()
    except Exception:  # noqa: BLE001 - o aviso não pode impedir o registro do pedido
        pass


def descadastrar(lead, envio: Envio | None = None):
    lead.descadastrado_em = timezone.now()
    lead.aceita_email = False
    lead.aceita_whatsapp = False
    lead.save(update_fields=["descadastrado_em", "aceita_email", "aceita_whatsapp", "atualizado_em"])
    Envio.objects.filter(lead=lead, status=StatusEnvio.PENDENTE).update(status=StatusEnvio.PULADO)
    Atividade.objects.create(lead=lead, tipo=TipoAtividade.NOTA, titulo="Pediu para não receber as campanhas",
                             descricao="Descadastrado pelo link da mensagem. Não entra mais nos envios.")


# ---------------------------------------------------------------- números do mês
def resumo(campanha: Campanha) -> dict:
    envios = list(campanha.envios.all())
    emails = [e for e in envios if e.canal == Canal.EMAIL]
    zaps = [e for e in envios if e.canal == Canal.WHATSAPP]
    enviados = [e for e in emails if e.status == StatusEnvio.ENVIADO]
    inicio = timezone.make_aware(datetime(campanha.ano, campanha.mes, 1))
    fim = timezone.make_aware(datetime(campanha.ano + (campanha.mes == 12), campanha.mes % 12 + 1, 1))
    return {
        "publico": publico().count(),
        "emails": len(emails), "emails_enviados": len(enviados),
        "emails_pendentes": sum(1 for e in emails if e.status == StatusEnvio.PENDENTE),
        "emails_falhas": sum(1 for e in emails if e.status == StatusEnvio.FALHOU),
        "abertos": sum(1 for e in enviados if e.aberto_em), "cliques": sum(1 for e in envios if e.clicado_em),
        "taxa_abertura": round(sum(1 for e in enviados if e.aberto_em) / len(enviados) * 100) if enviados else 0,
        "whats": len(zaps), "whats_enviados": sum(1 for e in zaps if e.status == StatusEnvio.ENVIADO),
        "whats_pendentes": sum(1 for e in zaps if e.status == StatusEnvio.PENDENTE),
        "cotacoes": Lead.objects.filter(cotacao_pedida_em__gte=inicio, cotacao_pedida_em__lt=fim).count(),
        "descadastros": Lead.objects.filter(descadastrado_em__gte=inicio, descadastrado_em__lt=fim).count(),
        "sem_renovacao": publico().filter(renovacao_mes__isnull=True).count(),
        "sem_contato": publico().filter(Q(contato_email="") & Q(contato_telefone="")).count(),
    }
