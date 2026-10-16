from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from apps.accounts.mixins import ComercialMixin, TecnicoMixin

from .fap import NIVEIS, economia_meta, panorama
from .forms import (
    FichaFapForm,
    AcaoPlanoForm,
    DocumentoForm,
    GestaoForm,
    ImportacaoPlanoForm,
    PrazoForm,
    RegistroForm,
    TreinamentoForm,
)
from .importacao import PlanilhaInvalida, aplicar_importacao, converter_valor, ler_planilha, planilha_modelo
from .models import (
    FichaFap,
    AcaoPlano,
    Documento,
    EtapaMetodo,
    Gestao,
    ImportacaoPlano,
    Prazo,
    StatusAcao,
    StatusDocumento,
    StatusPrazo,
    StatusTreinamento,
    TipoRegistro,
    Treinamento,
)
from .services import (
    gerar_prazo_cat,
    gerar_prazos_contrato,
    indicadores_gestao,
    resumo_plano,
    sincronizar_documento,
    sincronizar_treinamento,
)


class GestaoListView(TecnicoMixin, ListView):
    model = Gestao
    template_name = "gestao/lista.html"
    extra_context = {"secao": "gestao"}
    context_object_name = "gestoes"
    paginate_by = 25

    def get_queryset(self):
        qs = Gestao.objects.select_related("empresa", "responsavel")
        busca = self.request.GET.get("q", "").strip()
        etapa = self.request.GET.get("etapa", "").strip()
        if busca:
            qs = qs.filter(
                Q(codigo__icontains=busca)
                | Q(empresa__razao_social__icontains=busca)
                | Q(empresa__nome_fantasia__icontains=busca)
            )
        if etapa:
            qs = qs.filter(etapa=etapa)
        if self.request.GET.get("todas") != "1":
            qs = qs.filter(encerrado_em__isnull=True)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["etapa_atual"] = self.request.GET.get("etapa", "")
        contexto["etapas"] = EtapaMetodo.choices
        contexto["linhas"] = [
            {"gestao": gestao, "ind": indicadores_gestao(gestao)} for gestao in contexto["gestoes"]
        ]
        return contexto


class GestaoDetailView(TecnicoMixin, DetailView):
    model = Gestao
    template_name = "gestao/detalhe.html"
    extra_context = {"secao": "gestao"}
    context_object_name = "gestao"

    def get_queryset(self):
        return Gestao.objects.select_related("empresa", "responsavel")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        gestao = self.object
        contexto["registros"] = gestao.registros.select_related("registrado_por")[:40]
        contexto["prazos"] = gestao.prazos.select_related("responsavel").order_by("status", "data_fim")
        contexto["documentos"] = gestao.documentos.exclude(status=StatusDocumento.SUBSTITUIDO)
        contexto["treinamentos"] = gestao.treinamentos.exclude(status=StatusTreinamento.CANCELADO)
        contexto["acoes"] = gestao.acoes.all()
        contexto["resumo_plano"] = resumo_plano(gestao)
        contexto["status_acao"] = StatusAcao.choices
        contexto["ind"] = indicadores_gestao(gestao)
        contexto["etapas"] = [
            {"valor": valor, "rotulo": rotulo, "numero": EtapaMetodo.numero(valor)}
            for valor, rotulo in EtapaMetodo.choices
        ]
        contexto["form_registro"] = kwargs.get("form_registro") or RegistroForm()
        contexto["form_prazo"] = kwargs.get("form_prazo") or PrazoForm()
        contexto["form_documento"] = kwargs.get("form_documento") or DocumentoForm()
        contexto["form_treinamento"] = kwargs.get("form_treinamento") or TreinamentoForm()
        contexto["form_acao"] = kwargs.get("form_acao") or AcaoPlanoForm()
        contexto.update(contexto_fap(gestao, self.request.GET.get("fap")))
        return contexto


class GestaoCreateView(TecnicoMixin, CreateView):
    model = Gestao
    form_class = GestaoForm
    template_name = "gestao/form.html"
    extra_context = {"secao": "gestao"}

    def get_initial(self):
        inicial = super().get_initial()
        if self.request.GET.get("empresa"):
            inicial["empresa"] = self.request.GET["empresa"]
        inicial["responsavel"] = self.request.user.pk
        return inicial

    def form_valid(self, form):
        resposta = super().form_valid(form)
        criados = gerar_prazos_contrato(self.object, responsavel=self.request.user)
        if criados:
            messages.info(self.request, f"{len(criados)} compromisso(s) do contrato gerado(s) na agenda.")
        messages.success(self.request, f"Gestão {self.object.codigo} cadastrada.")
        return resposta


class GestaoUpdateView(TecnicoMixin, UpdateView):
    model = Gestao
    form_class = GestaoForm
    template_name = "gestao/form.html"
    extra_context = {"secao": "gestao"}

    def form_valid(self, form):
        resposta = super().form_valid(form)
        gerar_prazos_contrato(self.object, responsavel=self.request.user)
        messages.success(self.request, "Gestão atualizada.")
        return resposta


class EtapaView(TecnicoMixin, View):
    """Avanca (ou recua) a etapa do metodo e registra na linha do tempo."""

    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        nova = request.POST.get("etapa")
        if nova in dict(EtapaMetodo.choices) and nova != gestao.etapa:
            gestao.etapa = nova
            gestao.save(update_fields=["etapa", "atualizado_em"])
            gestao.registros.create(
                tipo=TipoRegistro.OUTRO,
                titulo=f"Etapa {gestao.etapa} · {gestao.get_etapa_display()}",
                descricao="Avanço no método de implantação.",
                registrado_por=request.user,
            )
            messages.success(request, f"Gestão na etapa {gestao.etapa} · {gestao.get_etapa_display()}.")
        return redirect(gestao.get_absolute_url())


class _GestaoSubCreate(TecnicoMixin, View):
    """Base para cadastros feitos dentro da pagina da gestao."""

    form_class = None
    mensagem = "Registro adicionado."

    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        form = self.form_class(request.POST, request.FILES or None)
        if form.is_valid():
            objeto = form.save(commit=False)
            objeto.gestao = gestao
            self.antes_de_salvar(objeto, request)
            objeto.save()
            self.depois_de_salvar(objeto, request)
            messages.success(request, self.mensagem)
        else:
            erros = "; ".join(
                f"{form.fields[campo].label if campo in form.fields else campo}: {' '.join(lista)}"
                for campo, lista in form.errors.items()
            )
            messages.error(request, f"Não foi possível salvar. {erros}")
        return redirect(gestao.get_absolute_url())

    def antes_de_salvar(self, objeto, request):
        return None

    def depois_de_salvar(self, objeto, request):
        return None


class RegistroCreateView(_GestaoSubCreate):
    form_class = RegistroForm
    mensagem = "Registro incluído na linha do tempo."

    def antes_de_salvar(self, objeto, request):
        objeto.registrado_por = request.user

    def depois_de_salvar(self, objeto, request):
        if objeto.tipo == TipoRegistro.OCORRENCIA:
            prazo = gerar_prazo_cat(objeto.gestao, objeto.data, objeto.pk, responsavel=request.user)
            messages.warning(
                request,
                f"Acidente registrado: prazo da CAT (S-2210) criado para {prazo.data_fim:%d/%m/%Y}.",
            )


class PrazoCreateView(_GestaoSubCreate):
    form_class = PrazoForm
    mensagem = "Prazo cadastrado."


class DocumentoCreateView(_GestaoSubCreate):
    form_class = DocumentoForm
    mensagem = "Documento incluído."

    def antes_de_salvar(self, objeto, request):
        objeto.enviado_por = request.user

    def depois_de_salvar(self, objeto, request):
        prazo = sincronizar_documento(objeto, responsavel=request.user)
        if prazo:
            messages.info(request, f"Revisão de {objeto.sigla} agendada para {prazo.data_fim:%d/%m/%Y}.")


class TreinamentoCreateView(_GestaoSubCreate):
    form_class = TreinamentoForm
    mensagem = "Treinamento registrado."

    def depois_de_salvar(self, objeto, request):
        prazo = sincronizar_treinamento(objeto, responsavel=request.user)
        if prazo:
            messages.info(request, f"{prazo.titulo}: {prazo.data_fim:%d/%m/%Y}.")


class AcaoCreateView(_GestaoSubCreate):
    form_class = AcaoPlanoForm
    mensagem = "Ação incluída no plano."


def contexto_fap(gestao, editar=None):
    """Fichas do FAP com o cálculo, a vigente, a próxima e o formulário."""
    ano = timezone.localdate().year
    fichas = list(gestao.fichas_fap.all())
    for ficha in fichas:
        ficha.c = ficha.calculo
    vigente = next((f for f in fichas if f.vigencia <= ano), None)
    proxima = next((f for f in fichas if f.vigencia > ano), None)
    destaque = vigente or proxima
    edicao = next((f for f in fichas if str(f.vigencia) == str(editar)), None) if editar else None
    base = fichas[0] if fichas else None
    inicial = {
        "vigencia": ano + 1 if vigente and not proxima else ano,
        "grau_rat": base.grau_rat if base else None,
        "folha_mensal": base.folha_mensal if base else None,
    }
    economia = None
    if destaque and destaque.c.fap is not None:
        economia = economia_meta(destaque.c, gestao.fap_meta, destaque.folha_mensal)
    def posicao(valor):
        return None if valor is None else round(float((valor - Decimal("0.5")) / Decimal("1.5") * 100), 1)
    return {
        "fichas_fap": fichas, "fap_destaque": destaque, "fap_proxima": proxima if vigente else None,
        "fap_vigente": vigente, "fap_economia_meta": economia,
        "fap_pos": posicao(destaque.c.fap) if destaque else None, "fap_pos_meta": posicao(gestao.fap_meta),
        "fap_edicao": edicao,
        "form_fap": FichaFapForm(instance=edicao) if edicao else FichaFapForm(initial=inicial),
    }


def sincronizar_fap_gestao(gestao):
    """Leva o FAP da vigência atual para o campo 'FAP vigente' da gestão."""
    ano = timezone.localdate().year
    vigente = gestao.fichas_fap.filter(vigencia__lte=ano).first()
    if vigente and vigente.calculo.fap is not None and gestao.fap_atual != vigente.calculo.fap:
        gestao.fap_atual = vigente.calculo.fap
        gestao.save(update_fields=["fap_atual", "atualizado_em"])


class FichaFapSalvarView(TecnicoMixin, View):
    """Cria ou atualiza a ficha do FAP de uma vigência (uma por ano)."""

    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        existente = gestao.fichas_fap.filter(vigencia=request.POST.get("vigencia") or 0).first()
        form = FichaFapForm(request.POST, instance=existente)
        if form.is_valid():
            ficha = form.save(commit=False)
            ficha.gestao = gestao
            ficha.save()
            sincronizar_fap_gestao(gestao)
            c = ficha.calculo
            messages.success(
                request,
                f"FAP {ficha.vigencia} {'atualizado' if existente else 'registrado'}: {c.fap:.4f}".replace(".", ",")
                + f" · {c.nivel['rotulo']}" + (f" · RAT ajustado {c.rat_ajustado:.2f}%".replace(".", ",") if c.rat_ajustado is not None else ""),
            )
        else:
            erros = "; ".join(
                f"{form.fields[campo].label if campo in form.fields else 'FAP'}: {' '.join(lista)}"
                for campo, lista in form.errors.items()
            )
            messages.error(request, f"FAP não salvo. {erros}")
        return redirect(gestao.get_absolute_url() + "#fap")


class FichaFapExcluirView(TecnicoMixin, View):
    def post(self, request, pk):
        ficha = get_object_or_404(FichaFap, pk=pk)
        gestao = ficha.gestao
        ficha.delete()
        sincronizar_fap_gestao(gestao)
        messages.success(request, f"Ficha do FAP {ficha.vigencia} removida.")
        return redirect(gestao.get_absolute_url() + "#fap")


class AcaoEventoView(TecnicoMixin, View):
    """Registra um passo de uma acao do plano e atualiza o status."""

    def post(self, request, pk):
        acao = get_object_or_404(AcaoPlano, pk=pk)
        descricao = (request.POST.get("descricao") or "").strip()
        status = request.POST.get("status") or acao.status
        custo = (request.POST.get("custo_estimado") or "").strip()

        if descricao:
            acao.eventos.create(descricao=descricao[:250], registrado_por=request.user)
        campos = []
        if status in dict(StatusAcao.choices) and status != acao.status:
            acao.status = status
            campos.append("status")
            if status in StatusAcao.encerrados() and not acao.concluida_em:
                acao.concluida_em = timezone.localdate()
                campos.append("concluida_em")
        if custo:
            try:
                acao.custo_estimado = converter_valor(custo)
                campos.append("custo_estimado")
            except ValueError:
                messages.error(request, f"Valor inválido: {custo}")
        if campos:
            acao.save(update_fields=[*campos, "atualizado_em"])
        if descricao or campos:
            messages.success(request, "Ação do plano atualizada.")
        destino = request.POST.get("next") or acao.gestao.get_absolute_url()
        return redirect(destino)


class GerarPrazosView(TecnicoMixin, View):
    """Recalcula compromissos do contrato, revisoes e reciclagens."""

    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        antes = gestao.prazos.count()
        gerar_prazos_contrato(gestao, responsavel=request.user)
        for documento in gestao.documentos.all():
            sincronizar_documento(documento, responsavel=request.user)
        for treinamento in gestao.treinamentos.all():
            sincronizar_treinamento(treinamento, responsavel=request.user)
        novos = gestao.prazos.count() - antes
        if novos > 0:
            messages.success(request, f"{novos} prazo(s) novo(s) na agenda.")
        else:
            messages.info(request, "Agenda conferida: nenhum prazo novo.")
        return redirect(gestao.get_absolute_url())


class PrazoConcluirView(TecnicoMixin, View):
    def post(self, request, pk):
        prazo = get_object_or_404(Prazo, pk=pk)
        prazo.status = StatusPrazo.CUMPRIDO
        prazo.concluido_em = timezone.localdate()
        prazo.save(update_fields=["status", "concluido_em", "atualizado_em"])
        if request.headers.get("HX-Request"):
            return render(request, "gestao/partials/linha_prazo.html", {"prazo": prazo})
        messages.success(request, "Prazo marcado como cumprido.")
        return redirect(request.POST.get("next") or prazo.gestao.get_absolute_url())


class AgendaPrazosView(TecnicoMixin, ListView):
    template_name = "gestao/agenda.html"
    extra_context = {"secao": "prazos"}
    context_object_name = "prazos"
    paginate_by = 50

    def get_queryset(self):
        qs = Prazo.objects.select_related("gestao", "gestao__empresa", "responsavel")
        status = self.request.GET.get("status", StatusPrazo.PENDENTE)
        tipo = self.request.GET.get("tipo", "")
        if status:
            qs = qs.filter(status=status)
        if tipo:
            qs = qs.filter(tipo=tipo)
        if self.request.GET.get("meus") == "1":
            qs = qs.filter(responsavel=self.request.user)
        return qs.order_by("data_fim")

    def get_context_data(self, **kwargs):
        from .models import TipoPrazo

        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        contexto["hoje"] = hoje
        contexto["limite_alerta"] = hoje + timedelta(days=settings.PRAZO_ALERTA_DIAS)
        contexto["status_atual"] = self.request.GET.get("status", StatusPrazo.PENDENTE)
        contexto["tipo_atual"] = self.request.GET.get("tipo", "")
        contexto["status_opcoes"] = StatusPrazo.choices
        contexto["tipo_opcoes"] = TipoPrazo.choices
        return contexto


class VencimentosView(TecnicoMixin, TemplateView):
    """Documentos e treinamentos vencidos ou perto de vencer, em todos os clientes."""

    template_name = "gestao/vencimentos.html"
    extra_context = {"secao": "vencimentos"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        limite = timezone.localdate() + timedelta(days=settings.VENCIMENTO_ALERTA_DIAS)
        documentos = (
            Documento.objects.filter(
                status=StatusDocumento.VIGENTE, valido_ate__lte=limite, gestao__encerrado_em__isnull=True
            )
            .select_related("gestao", "gestao__empresa")
            .order_by("valido_ate")
        )
        treinamentos = (
            Treinamento.objects.filter(
                status=StatusTreinamento.REALIZADO, valido_ate__lte=limite, gestao__encerrado_em__isnull=True
            )
            .select_related("gestao", "gestao__empresa")
            .order_by("valido_ate")
        )
        acoes = (
            AcaoPlano.objects.filter(prazo__lte=limite, gestao__encerrado_em__isnull=True)
            .exclude(status__in=StatusAcao.encerrados())
            .select_related("gestao", "gestao__empresa")
            .order_by("prazo")
        )
        contexto.update(
            documentos=documentos,
            treinamentos=treinamentos,
            acoes=acoes,
            dias=settings.VENCIMENTO_ALERTA_DIAS,
            limite=limite,
        )
        return contexto


class ImportarPlanoView(TecnicoMixin, View):
    """Passo 1: recebe a planilha e mostra a previa para conferencia."""

    template_name = "gestao/importar_plano.html"

    def get(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        return render(
            request,
            self.template_name,
            {"gestao": gestao, "form": ImportacaoPlanoForm(), "secao": "gestao"},
        )

    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        form = ImportacaoPlanoForm(request.POST, request.FILES)
        contexto = {"gestao": gestao, "form": form, "secao": "gestao"}
        if not form.is_valid():
            return render(request, self.template_name, contexto)

        arquivo = form.cleaned_data["arquivo"]
        try:
            resultado = ler_planilha(arquivo, arquivo.name)
        except PlanilhaInvalida as erro:
            form.add_error("arquivo", str(erro))
            return render(request, self.template_name, contexto)

        arquivo.seek(0)
        importacao = ImportacaoPlano.objects.create(
            gestao=gestao,
            arquivo=arquivo,
            enviado_por=request.user,
            linhas_lidas=len(resultado.linhas),
            linhas_validas=len(resultado.validas),
        )
        contexto.update(
            {"resultado": resultado, "importacao": importacao, "politica": form.cleaned_data["politica"]}
        )
        return render(request, self.template_name, contexto)


class ConfirmarImportacaoView(TecnicoMixin, View):
    """Passo 2: rele o arquivo salvo e grava o que foi conferido."""

    def post(self, request, pk):
        importacao = get_object_or_404(ImportacaoPlano, pk=pk)
        politica = request.POST.get("politica", "atualizar")
        if politica not in {"atualizar", "ignorar", "duplicar"}:
            politica = "atualizar"
        try:
            with importacao.arquivo.open("rb") as arquivo:
                resultado = ler_planilha(arquivo, importacao.arquivo.name)
        except PlanilhaInvalida as erro:
            messages.error(request, f"Não foi possível reler a planilha: {erro}")
            return redirect(importacao.gestao.get_absolute_url())

        numeros = aplicar_importacao(importacao, resultado, politica)
        messages.success(
            request,
            f"Plano de ação atualizado: {numeros['criados']} criada(s), "
            f"{numeros['atualizados']} atualizada(s), {numeros['ignorados']} ignorada(s)"
            + (f", {numeros['com_erro']} linha(s) com erro descartada(s)." if numeros["com_erro"] else "."),
        )
        return redirect(importacao.gestao.get_absolute_url())


class ModeloPlanoView(TecnicoMixin, View):
    def get(self, request):
        resposta = HttpResponse(
            planilha_modelo(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resposta["Content-Disposition"] = 'attachment; filename="modelo-plano-de-acao.xlsx"'
        return resposta


def panorama_carteira(gestoes=None):
    """Panorama do FAP de todas as gestões ativas, ordenado pela oportunidade."""
    if gestoes is None:
        gestoes = Gestao.objects.filter(encerrado_em__isnull=True)
    gestoes = gestoes.select_related("empresa").prefetch_related("fichas_fap")
    linhas = [panorama(g, fichas=g.fichas_fap.all()) for g in gestoes]
    linhas.sort(key=lambda x: (x["vigente"] is None, -x["prioridade"]))
    return linhas


class FapCarteiraView(ComercialMixin, TemplateView):
    """FAP de cada cliente lado a lado, para a equipe usar como argumento de venda."""

    template_name = "gestao/fap_carteira.html"
    extra_context = {"secao": "fap"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        todas = panorama_carteira()
        g = self.request.GET
        nivel, q, so_oportunidade = g.get("nivel", ""), g.get("q", "").strip().lower(), g.get("oportunidade") == "1"
        linhas = todas
        if nivel == "SEM":
            linhas = [x for x in linhas if x["vigente"] is None]
        elif nivel:
            linhas = [x for x in linhas if x["c"] and x["c"].nivel and x["c"].nivel["codigo"] == nivel]
        if q:
            linhas = [x for x in linhas if q in f"{x['empresa'].razao_social} {x['empresa'].nome_fantasia} {x['gestao'].codigo}".lower()]
        if so_oportunidade:
            linhas = [x for x in linhas if not x["contratado"] and (x["potencial"] or x["vigente"] is None)]
        com = [x for x in todas if x["c"]]
        contexto.update(
            linhas=linhas, q=g.get("q", ""), nivel_atual=nivel, oportunidade=so_oportunidade,
            niveis=[(codigo, rotulo) for _, codigo, rotulo, _ in NIVEIS] + [("SEM", "Sem FAP registrado")],
            tot={
                "clientes": len(todas), "com_fap": len(com),
                "malus": sum(1 for x in com if x["c"].nivel and x["c"].nivel["codigo"] in ("MAL", "MMAX")),
                "bonus": sum(1 for x in com if x["c"].nivel and x["c"].nivel["codigo"] in ("BON", "BMAX")),
                "acrescimo": sum((x["acrescimo"] for x in com), Decimal("0")),
                "potencial": sum((x["potencial"] for x in com), Decimal("0")),
                "bloqueados": sum(1 for x in com if x["vigente"].bloqueio),
                "sem_servico": sum(1 for x in todas if not x["contratado"]),
            },
        )
        return contexto
