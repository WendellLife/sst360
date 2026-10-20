from base64 import b64decode

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from apps.accounts.mixins import ComercialMixin

from . import regua
from .models import Campanha, Canal, Envio, Etapa, Modelo, StatusEnvio

PIXEL = b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


def _campanha_do_pedido(request) -> Campanha:
    """Campanha do mês pedido (?mes=AAAA-MM).

    Num GET nada é criado além do mês corrente e dos vizinhos que a navegação do painel oferece
    (idempotente e limitado); qualquer outro mês inexistente cai no mês corrente. Só o POST cria
    campanhas de meses distantes.
    """
    chave = request.GET.get("mes") or request.POST.get("mes") or ""
    try:
        ano, mes = (int(x) for x in chave.split("-"))
        if 1 <= mes <= 12 and 2020 <= ano <= 2100:
            if request.method == "POST" or Campanha.objects.filter(ano=ano, mes=mes).exists():
                return regua.garantir_campanha(ano, mes)
            hoje = timezone.localdate()
            if abs((ano - hoje.year) * 12 + mes - hoje.month) <= 1:
                return regua.garantir_campanha(ano, mes)
    except ValueError:
        pass
    return regua.campanha_atual()


def _vizinho(c: Campanha, passo: int) -> str:
    mes, ano = c.mes + passo, c.ano
    if mes < 1:
        mes, ano = 12, ano - 1
    if mes > 12:
        mes, ano = 1, ano + 1
    return f"{ano}-{mes:02d}"


class CampanhasView(ComercialMixin, TemplateView):
    template_name = "campanhas/painel.html"
    extra_context = {"secao": "campanhas"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        c = _campanha_do_pedido(self.request)
        modelos = regua.garantir_modelos()
        envios = list(c.envios.select_related("lead", "lead__responsavel", "campanha").order_by("lead__razao_social"))
        fila = [e for e in envios if e.canal == Canal.WHATSAPP]
        for e in fila:
            e.texto = regua.mensagem(e, modelos)["whatsapp"]
        hoje = timezone.localdate()
        atual = (c.ano, c.mes) == (hoje.year, hoje.month)
        pendentes_wpp = {e.lead_id: e for e in fila if e.status == StatusEnvio.PENDENTE}
        renovacoes = regua.renovacoes_proximas(hoje) if atual else []
        for r in renovacoes:
            r["envio_wpp"] = pendentes_wpp.get(r["lead"].pk)
        contexto.update(
            campanha=c, atual=atual, anterior=_vizinho(c, -1), proximo=_vizinho(c, 1), resumo=regua.resumo(c),
            fila=sorted(fila, key=lambda e: (e.status != StatusEnvio.PENDENTE, e.etapa == Etapa.MENSAL, str(e.lead))),
            emails=[e for e in envios if e.canal == Canal.EMAIL], renovacoes=renovacoes,
            gerada=bool(c.envios_gerados_em),
        )
        return contexto


class GerarEnviosView(ComercialMixin, View):
    def post(self, request):
        c = _campanha_do_pedido(request)
        n = regua.gerar_envios(c)
        messages.success(request, f"Envios de {c.rotulo} gerados: {n[Canal.EMAIL]} e-mail(s) e {n[Canal.WHATSAPP]} WhatsApp novos.")
        return redirect(f"{reverse('campanhas:painel')}?mes={c.chave}")


class EnviarEmailsView(ComercialMixin, View):
    def post(self, request):
        c = _campanha_do_pedido(request)
        if not c.envios_gerados_em:
            regua.gerar_envios(c)
        t = regua.enviar_emails(c, request.user)
        if t["falhas"]:
            messages.error(request, f"{t['enviados']} e-mail(s) enviado(s) e {t['falhas']} com falha. Confira o servidor de e-mail em .env.")
        else:
            messages.success(request, f"{t['enviados']} e-mail(s) enviado(s)." + (f" {t['pulados']} pulado(s) por descadastro." if t["pulados"] else ""))
        return redirect(f"{reverse('campanhas:painel')}?mes={c.chave}#emails")


class ConteudoView(ComercialMixin, View):
    def post(self, request):
        c = _campanha_do_pedido(request)
        tema, conteudo = request.POST.get("tema", "").strip(), request.POST.get("conteudo", "").strip()
        if not tema or not conteudo:
            messages.error(request, "Informe o tema e o conteúdo do mês.")
        else:
            c.tema, c.conteudo = tema[:150], conteudo
            c.save(update_fields=["tema", "conteudo", "atualizado_em"])
            messages.success(request, f"Conteúdo de {c.rotulo} salvo. Os envios ainda não feitos já usam o texto novo.")
        return redirect(f"{reverse('campanhas:painel')}?mes={c.chave}#conteudo")


class WhatsappView(ComercialMixin, View):
    """Marca o envio como feito e abre o WhatsApp com a mensagem pronta."""

    def post(self, request, pk):
        envio = get_object_or_404(Envio.objects.select_related("lead", "campanha"), pk=pk, canal=Canal.WHATSAPP)
        link = regua.link_whatsapp(envio)
        regua.marcar_whatsapp_enviado(envio, request.user)
        return redirect(link)

    def get(self, request, pk):
        # GET não grava nada (prefetch e robôs); quem chega por link antigo volta ao painel.
        envio = get_object_or_404(Envio.objects.select_related("campanha"), pk=pk, canal=Canal.WHATSAPP)
        return redirect(f"{reverse('campanhas:painel')}?mes={envio.campanha.chave}#whatsapp")


class PularEnvioView(ComercialMixin, View):
    def post(self, request, pk):
        envio = get_object_or_404(Envio, pk=pk)
        if envio.status == StatusEnvio.PENDENTE:
            envio.status = StatusEnvio.PULADO
            envio.save(update_fields=["status", "atualizado_em"])
        return redirect(f"{reverse('campanhas:painel')}?mes={envio.campanha.chave}#whatsapp")


class PreviaEmailView(ComercialMixin, View):
    def get(self, request, pk):
        envio = get_object_or_404(Envio.objects.select_related("lead", "campanha"), pk=pk)
        msg = regua._email(envio, regua.garantir_modelos())
        return HttpResponse(msg.alternatives[0][0])


class ModelosView(ComercialMixin, View):
    template_name = "campanhas/modelos.html"

    def contexto(self, request):
        modelos = regua.garantir_modelos()
        c = regua.campanha_atual()
        exemplo = regua.publico().exclude(contato_email="").first() or regua.publico().first()
        itens = []
        for etapa, rotulo in Etapa.choices:
            m = modelos[etapa]
            previa = None
            if exemplo:
                ctx = regua.contexto(exemplo, c)
                if not exemplo.renovacao_mes:
                    ctx["mes_renovacao"] = "março"
                previa = {"assunto": regua.preencher(m.assunto, ctx), "email": regua.preencher(m.email, ctx),
                          "whatsapp": regua.preencher(m.whatsapp, ctx)}
            itens.append({"etapa": etapa, "rotulo": rotulo, "cor": Etapa.cor(etapa), "modelo": m, "previa": previa})
        return {"secao": "campanhas", "itens": itens, "exemplo": exemplo, "campanha": c,
                "campos": ["contato", "empresa", "mes_renovacao", "fornecedor", "tema", "conteudo", "mes", "remetente", "link_proposta"]}

    def get(self, request):
        return render(request, self.template_name, self.contexto(request))

    def post(self, request):
        m = get_object_or_404(Modelo, etapa=request.POST.get("etapa"))
        assunto, email, whatsapp = (request.POST.get(k, "").strip() for k in ("assunto", "email", "whatsapp"))
        if not (assunto and email and whatsapp):
            messages.error(request, "Assunto, e-mail e WhatsApp são obrigatórios.")
        elif "{link_proposta}" not in whatsapp:
            messages.error(request, "A mensagem do WhatsApp precisa ter {link_proposta}, que é por onde o lead pede a cotação.")
        else:
            m.assunto, m.email, m.whatsapp = assunto[:200], email, whatsapp
            m.save()
            messages.success(request, f"Modelo “{m.get_etapa_display()}” salvo.")
        return redirect(reverse("campanhas:modelos") + f"#etapa-{m.etapa}")


# ---------------------------------------------------------------- páginas públicas (sem login)
def _envio_ou_lead(token):
    envio = Envio.objects.select_related("lead", "campanha").filter(token=token).first()
    if envio:
        return envio, envio.lead
    from apps.crm.models import Lead

    return None, get_object_or_404(Lead, token=token)


class PropostaView(View):
    """Link “quero participar da cotação”. GET mostra a confirmação (robôs de e-mail só fazem GET); POST registra."""

    template_name = "campanhas/publico_proposta.html"

    def get(self, request, token):
        envio, lead = _envio_ou_lead(token)
        if envio:
            regua.registrar_clique(envio)
        return render(request, self.template_name, {"lead": lead, "confirmado": False, "token": token})

    def post(self, request, token):
        envio, lead = _envio_ou_lead(token)
        regua.registrar_pedido_cotacao(lead, envio)
        return render(request, self.template_name, {"lead": lead, "confirmado": True, "token": token})


@method_decorator(csrf_exempt, name="dispatch")
class DescadastrarView(View):
    """Descadastro. Aceita o POST de um clique dos provedores de e-mail (List-Unsubscribe-Post)."""

    template_name = "campanhas/publico_descadastro.html"

    def get(self, request, token):
        _, lead = _envio_ou_lead(token)
        return render(request, self.template_name, {"lead": lead, "feito": bool(lead.descadastrado_em), "token": token})

    def post(self, request, token):
        envio, lead = _envio_ou_lead(token)
        if not lead.descadastrado_em:
            regua.descadastrar(lead, envio)
        return render(request, self.template_name, {"lead": lead, "feito": True, "token": token})


class PixelView(View):
    def get(self, request, token):
        envio = Envio.objects.filter(token=token).first()
        if envio and not envio.aberto_em:
            envio.aberto_em = timezone.now()
            envio.save(update_fields=["aberto_em", "atualizado_em"])
        resposta = HttpResponse(PIXEL, content_type="image/gif")
        resposta["Cache-Control"] = "no-store"
        return resposta
