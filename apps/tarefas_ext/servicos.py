"""Leitura do sistema Tarefas para a área comercial do SST360.

O cruzamento com o SST360 é pelo CNPJ (só letras e dígitos, em maiúsculas: o Tarefas aceita o CNPJ
alfanumérico). Nada é gravado no Tarefas; daqui só sai a criação de um lead no SST360.
"""
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError
from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from .roteador import ALIAS

logger = logging.getLogger(__name__)


def chave_cnpj(valor) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(valor or "").upper())


def configurado() -> bool:
    return ALIAS in settings.DATABASES


def url_tarefas(caminho: str = "") -> str:
    base = (getattr(settings, "TAREFAS_URL", "") or "").rstrip("/")
    return f"{base}{caminho}" if base else ""


def status() -> dict:
    """{'ok': bool, 'motivo': str} — se a conexão existe e responde."""
    if not configurado():
        return {"ok": False, "motivo": "nao_configurado"}
    from .models import Cliente

    try:
        Cliente.objects.exists()
    except DatabaseError as erro:
        # O detalhe pode trazer host, usuário e banco: vai só para o log, a tela recebe texto genérico.
        logger.error("Falha ao consultar o sistema Tarefas: %s", erro)
        return {"ok": False, "motivo": "erro", "erro": "Não foi possível consultar o sistema Tarefas. Veja o registro do servidor."}
    return {"ok": True, "motivo": ""}


def _mapas_sst360():
    from apps.crm.models import Lead
    from apps.empresas.models import Empresa

    empresas = {chave_cnpj(e.cnpj): e for e in Empresa.objects.only("id", "razao_social", "nome_fantasia", "cnpj", "situacao")}
    leads = {}
    for lead in Lead.objects.exclude(cnpj="").only("id", "razao_social", "nome_fantasia", "cnpj", "estagio", "empresa_id"):
        leads.setdefault(chave_cnpj(lead.cnpj), lead)
    return empresas, leads


def datas_servico(cli):
    """Marca no cliente anotado: desde quando é cliente, último serviço e próximo serviço (com o que é)."""
    entrega = timezone.localdate(cli.ultima_entrega) if getattr(cli, "ultima_entrega", None) else None
    turma = getattr(cli, "ultima_turma", None)
    candidatos = [(d, o) for d, o in ((turma, "turma"), (entrega, "entrega")) if d]
    cli.ultimo_servico, cli.ultimo_servico_tipo = max(candidatos) if candidatos else (None, "")
    futuros = [(d, o) for d, o in ((getattr(cli, "proxima_turma", None), "turma"), (getattr(cli, "proximo_prazo", None), "prazo")) if d]
    cli.proximo_servico, cli.proximo_servico_tipo = min(futuros) if futuros else (None, "")
    cli.cliente_desde = timezone.localdate(cli.criado_em) if cli.criado_em else None
    return cli


def painel(hoje=None) -> dict:
    """Clientes do Tarefas com o que está em andamento e o vínculo com o SST360."""
    from .models import Cliente, Tarefa, Turma

    hoje = hoje or timezone.localdate()
    limite_turmas = hoje + timedelta(days=60)
    trinta = timezone.now() - timedelta(days=30)
    clientes = list(
        Cliente.objects.annotate(
            abertas=Count("tarefas", filter=~Q(tarefas__etapa="feito"), distinct=True),
            atrasadas=Count("tarefas", filter=~Q(tarefas__etapa="feito") & Q(tarefas__prazo__lt=hoje), distinct=True),
            concluidas_30=Count("tarefas", filter=Q(tarefas__etapa="feito", tarefas__concluida_em__gte=trinta), distinct=True),
            projetos_ativos=Count("projetos", filter=Q(projetos__ativo=True), distinct=True),
            proxima_turma=Min("turmas__data", filter=Q(turmas__data__gte=hoje) & ~Q(turmas__estado="cancelada")),
            proximo_prazo=Min("tarefas__prazo", filter=Q(tarefas__prazo__gte=hoje) & ~Q(tarefas__etapa="feito")),
            ultima_turma=Max("turmas__data", filter=Q(turmas__data__lt=hoje) & ~Q(turmas__estado="cancelada")),
            ultima_entrega=Max("tarefas__concluida_em"),
            turmas_realizadas=Count("turmas", filter=Q(turmas__data__lt=hoje) & ~Q(turmas__estado="cancelada"), distinct=True),
        ).order_by("-ativo", "nome")
    )
    principais = {}
    from .models import Contato

    for c in Contato.objects.filter(cliente_id__in=[x.pk for x in clientes]).order_by("cliente_id", "-principal", "ordem", "id"):
        principais.setdefault(c.cliente_id, c)

    for cli in clientes:
        datas_servico(cli)
    empresas, leads = _mapas_sst360()
    linhas = []
    for cli in clientes:
        k = chave_cnpj(cli.cnpj)
        empresa, lead = empresas.get(k), leads.get(k)
        if empresa:
            vinculo = "cliente"
        elif lead:
            vinculo = "lead"
        else:
            vinculo = "sem_cadastro"
        linhas.append({"cliente": cli, "contato": principais.get(cli.pk), "empresa": empresa, "lead": lead, "vinculo": vinculo})

    turmas = list(
        Turma.objects.filter(data__gte=hoje, data__lte=limite_turmas).exclude(estado="cancelada")
        .select_related("cliente", "projeto").order_by("data", "hora_inicio")[:12]
    )
    for t in turmas:
        k = chave_cnpj(t.cliente.cnpj) if t.cliente_id and t.cliente else ""
        t.empresa_sst = empresas.get(k)
        t.lead_sst = leads.get(k)

    ativos = [l for l in linhas if l["cliente"].ativo]
    return {
        "linhas": linhas,
        "turmas": turmas,
        "totais": {
            "clientes": len(ativos),
            "no_sst360": sum(1 for l in ativos if l["vinculo"] == "cliente"),
            "leads": sum(1 for l in ativos if l["vinculo"] == "lead"),
            "oportunidades": sum(1 for l in ativos if l["vinculo"] == "sem_cadastro"),
            "turmas_60": len(turmas),
            "pessoas_turmas": sum(t.pessoas for t in turmas),
            "tarefas_abertas": Tarefa.objects.filter(cliente__isnull=False).exclude(etapa="feito").count(),
        },
    }


def resumo_por_cnpj(cnpj, hoje=None):
    """O que o Tarefas tem para uma empresa ou lead do SST360. None quando não há cliente com esse CNPJ."""
    from .models import Cliente, Tarefa, Turma

    k = chave_cnpj(cnpj)
    if not k or not configurado():
        return None
    hoje = hoje or timezone.localdate()
    try:
        cliente = Cliente.objects.filter(cnpj=k).first()
        if cliente is None:
            return None
        abertas = list(
            Tarefa.objects.filter(cliente=cliente).exclude(etapa="feito").select_related("responsavel", "projeto")
            .order_by("prazo", "numero")[:6]
        )
        total_abertas = Tarefa.objects.filter(cliente=cliente).exclude(etapa="feito").count()
        atrasadas = Tarefa.objects.filter(cliente=cliente, prazo__lt=hoje).exclude(etapa="feito").count()
        turmas = list(Turma.objects.filter(cliente=cliente, data__gte=hoje).exclude(estado="cancelada").select_related("projeto")[:4])
        projetos = list(cliente.projetos.filter(ativo=True).order_by("nome")[:4])
        contato = cliente.contatos.order_by("-principal", "ordem", "id").first()
        realizados = sorted(
            [{"data": t.data, "tipo": "Turma", "titulo": f"{t.projeto or 'Turma'} · {t.pessoas} pessoas", "estado": t.estado_rotulo}
             for t in Turma.objects.filter(cliente=cliente, data__lt=hoje).exclude(estado="cancelada").select_related("projeto").order_by("-data")[:5]]
            + [{"data": timezone.localdate(t.concluida_em), "tipo": "Entrega", "titulo": f"{t.codigo} · {t.titulo}", "estado": "Concluída"}
               for t in Tarefa.objects.filter(cliente=cliente, etapa="feito", concluida_em__isnull=False).order_by("-concluida_em")[:5]],
            key=lambda x: x["data"], reverse=True,
        )[:5]
    except DatabaseError:
        return None
    for t in abertas:
        t.atrasada = bool(t.prazo and t.prazo < hoje)
    return {
        "cliente": cliente, "contato": contato, "abertas": abertas, "total_abertas": total_abertas,
        "atrasadas": atrasadas, "turmas": turmas, "projetos": projetos, "realizados": realizados,
        "cliente_desde": timezone.localdate(cliente.criado_em) if cliente.criado_em else None,
        "ultimo_servico": realizados[0]["data"] if realizados else None,
        "proximo_servico": min([d for d in [turmas[0].data if turmas else None] + [t.prazo for t in abertas if t.prazo and t.prazo >= hoje] if d], default=None),
        "url": url_tarefas(f"/clientes/?cliente={cliente.pk}"),
    }


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _observacao_tarefas(cliente, resumo):
    linhas = [f"Veio do sistema Tarefas ({cliente.codigo}). Já é atendido pela Razach em cursos, turmas ou projetos."]
    linhas.append(
        f"Cliente desde {_fmt(resumo.get('cliente_desde'))} · último serviço {_fmt(resumo.get('ultimo_servico'))}"
        f" · próximo {_fmt(resumo.get('proximo_servico'))}."
    )
    for r in resumo.get("realizados", []):
        linhas.append(f"- {_fmt(r['data'])}: {r['tipo']} · {r['titulo']}")
    for t in resumo.get("turmas", []):
        linhas.append(f"- {_fmt(t.data)}: Turma prevista · {t.projeto or 'Turma'} · {t.estado_rotulo}")
    return "\n".join(linhas)


def criar_lead(cliente_id, usuario):
    """Cria no funil um lead a partir de um cliente do Tarefas.

    Devolve (lead, criado). Se já existe empresa ou lead com o mesmo CNPJ, não cria outro: devolve o que existe
    (para empresa já cliente, devolve (None, False)).
    """
    from apps.core.validators import formatar_cnpj
    from apps.crm.models import Atividade, Lead, OrigemLead, TipoAtividade

    from .models import Cliente

    cliente = Cliente.objects.get(pk=cliente_id)
    k = chave_cnpj(cliente.cnpj)
    empresas, leads = _mapas_sst360()
    resumo = resumo_por_cnpj(cliente.cnpj) or {}
    if k in empresas:
        return None, False
    if k in leads:
        return leads[k], False
    contato = cliente.contatos.order_by("-principal", "ordem", "id").first()
    cnpj = formatar_cnpj(k) if k.isdigit() and len(k) == 14 else k
    lead = Lead.objects.create(
        razao_social=cliente.nome,
        cnpj=cnpj,
        contato_nome=getattr(contato, "nome", ""),
        contato_cargo=getattr(contato, "cargo", ""),
        contato_email=getattr(contato, "email", "") or cliente.email,
        contato_telefone=getattr(contato, "telefone", "") or cliente.telefone,
        origem=OrigemLead.CARTEIRA,
        responsavel=usuario,
        proximo_contato=timezone.localdate(),
        observacoes=_observacao_tarefas(cliente, resumo),
    )
    Atividade.objects.create(
        lead=lead, tipo=TipoAtividade.NOTA, titulo="Lead criado a partir do sistema Tarefas",
        descricao=f"Cliente {cliente.codigo} · {cliente.nome}.", autor=usuario,
    )
    return lead, True


def importar_clientes(usuario=None, incluir_inativos=False) -> dict:
    """Cria leads para todos os clientes do Tarefas que ainda não estão no SST360."""
    from .models import Cliente

    criados, ja, inativos = [], 0, 0
    for cliente in Cliente.objects.order_by("nome", "id"):
        if not cliente.ativo and not incluir_inativos:
            inativos += 1
            continue
        lead, criado = criar_lead(cliente.pk, usuario)
        if criado:
            criados.append(lead)
        else:
            ja += 1
    return {"criados": criados, "ja_existiam": ja, "inativos": inativos}
