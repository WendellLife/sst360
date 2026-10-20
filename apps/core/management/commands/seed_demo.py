"""Popula o banco com dados ficticios de SST para demonstracao e testes manuais.

Idempotente: rodar de novo nao duplica nada.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import TipoUsuario
from apps.core.management import travas
from apps.crm.models import (
    Atividade,
    Estagio,
    Lead,
    OrigemLead,
    ServicoInteresse,
    SituacaoSST,
    TipoAtividade,
    Urgencia as UrgenciaLead,
)
from apps.empresas.models import Contato, Empresa, Porte, SituacaoEmpresa
from apps.gestao.models import (
    AcaoPlano,
    Documento,
    EtapaMetodo,
    Gestao,
    Modalidade,
    ModeloAcompanhamento,
    Prioridade,
    Servico,
    StatusAcao,
    StatusDocumento,
    StatusTreinamento,
    TipoDocumento,
    TipoRegistro,
    TipoRisco,
    TipoTreinamento,
    Treinamento,
)
from apps.gestao.services import gerar_prazos_contrato, sincronizar_documento, sincronizar_treinamento
from apps.publico.models import Diagnostico, Urgencia
from apps.relacionamento.models import (
    DocumentoSolicitado,
    Mensagem,
    Reuniao,
    StatusDocumento as StatusPedido,
    StatusReuniao,
    TipoReuniao,
)

User = get_user_model()


def meses_atras(hoje, meses: int, dias: int = 0):
    return hoje - timedelta(days=round(meses * 30.44) + dias)


class Command(BaseCommand):
    help = "Cria dados de demonstracao (equipe, clientes, gestoes de SST, leads e diagnosticos)."

    def add_arguments(self, parser):
        parser.add_argument("--senha", default=None, help="Senha dos usuarios criados (padrão de demonstração: sst360demo).")
        parser.add_argument(
            "--permitir-producao", action="store_true",
            help="Permite rodar com DEBUG=False; exige também --senha.",
        )

    def handle(self, *args, **options):
        travas.exigir_para_seed(options["senha"] is not None, options["permitir_producao"])
        self.senha = options["senha"] or "sst360demo"
        self.hoje = timezone.localdate()

        analista = self._usuario(
            "analista", "Rita", "Lorenzo", "analista@exemplo.com.br", TipoUsuario.INTERNO, staff=True
        )
        engenheiro = self._usuario(
            "engenheiro", "Paulo", "Andrade", "engenharia@exemplo.com.br", TipoUsuario.INTERNO
        )

        metalurgica = self._empresa(
            "04.252.011/0001-10", "Metalúrgica Exemplo Indústria e Comércio Ltda", "Metalúrgica Exemplo",
            Porte.MEDIA, "Fabricação de estruturas metálicas", "25.11-0", 3, 180, "Campinas", analista,
        )
        supermercado = self._empresa(
            "11.222.333/0001-81", "Rede Bom Preço Supermercados Ltda", "Bom Preço Supermercados",
            Porte.GRANDE, "Comércio varejista de alimentos", "47.11-3", 2, 420, "Jundiaí", analista,
        )
        construtora = self._empresa(
            "45.997.418/0001-53", "Construtora Horizonte Ltda", "Construtora Horizonte",
            Porte.EPP, "Construção de edifícios", "41.20-4", 4, 95, "Sorocaba", engenheiro,
        )
        self._contato(metalurgica, "Carlos Menezes", "Diretor industrial", "diretor@exemplo.com.br")
        self._contato(supermercado, "Juliana Prado", "Gerente de RH", "rh@bompreco.com.br")
        self._contato(construtora, "Marcos Vieira", "Sócio-diretor", "marcos@horizonte.com.br")

        cliente = self._usuario(
            "cliente", "Carlos", "Menezes", "diretor@exemplo.com.br", TipoUsuario.CLIENTE, empresa=metalurgica
        )

        g1 = self._gestao_metalurgica(metalurgica, analista, engenheiro)
        self._gestao_supermercado(supermercado, analista)
        self._gestao_construtora(construtora, engenheiro)
        self._relacionamento(g1, analista, cliente)
        # compromissos de contrato ja vencidos na demo contam como entregues
        from apps.gestao.models import Prazo, StatusPrazo, TipoPrazo
        for prazo in Prazo.objects.filter(tipo=TipoPrazo.CONTRATUAL, status=StatusPrazo.PENDENTE,
                                          data_fim__lt=self.hoje, gestao__etapa__gte="03"):
            prazo.status = StatusPrazo.CUMPRIDO
            prazo.concluido_em = prazo.data_fim
            prazo.save(update_fields=["status", "concluido_em"])
        self._leads(analista, engenheiro)
        self._diagnosticos()
        self._vendas(metalurgica, supermercado, construtora, analista, engenheiro)
        self._campanhas()
        self._fap(metalurgica, supermercado, construtora)

        self.stdout.write(self.style.SUCCESS("Dados de demonstração prontos."))
        self.stdout.write(f"  Painel interno: analista / {self.senha}")
        self.stdout.write(f"  Portal do cliente: cliente / {self.senha}")

    def _fap(self, metalurgica, supermercado, construtora):
        """Fichas do FAP: a metalúrgica sai do malus, o supermercado tem bônus e a construtora tem bloqueio."""
        from apps.gestao.models import BloqueioFap, FichaFap, GrauRat
        from apps.gestao.views import sincronizar_fap_gestao

        ano = self.hoje.year
        fichas = [
            (metalurgica, ano - 1, GrauRat.GRAVE, "78", "70", "66", "", None, "756000", "Período-base com dois afastamentos longos por LER/DORT."),
            (metalurgica, ano, GrauRat.GRAVE, "72", "62.8", "60.8", "", None, "756000", ""),
            (metalurgica, ano + 1, GrauRat.GRAVE, "49", "44", "40", "", None, "780000", "Divulgado no FAPWeb em setembro. Efeito da gestão de afastamentos."),
            (supermercado, ano, GrauRat.MEDIO, "42", "38", "35", "", None, "1092000", ""),
            (construtora, ano, GrauRat.GRAVE, "30", "25", "28", BloqueioFap.MORTE_INVALIDEZ, None, "361000", "Bonificação bloqueada por acidente fatal em obra no período-base."),
        ]
        for empresa, vigencia, grau, g, f, c, bloqueio, oficial, folha, obs in fichas:
            gestao = empresa.gestoes.filter(encerrado_em__isnull=True).first()
            if not gestao:
                continue
            FichaFap.objects.update_or_create(
                gestao=gestao, vigencia=vigencia,
                defaults={"grau_rat": grau, "percentil_gravidade": Decimal(g), "percentil_frequencia": Decimal(f),
                          "percentil_custo": Decimal(c), "bloqueio": bloqueio, "fap_oficial": oficial,
                          "folha_mensal": Decimal(folha), "observacoes": obs},
            )
            sincronizar_fap_gestao(gestao)

    def _vendas(self, metalurgica, supermercado, construtora, analista, engenheiro):
        """Vendas manuais de servicos: avulsos, aditivos e recorrentes."""
        from decimal import Decimal

        from apps.vendas.models import Cobranca, StatusVenda, Venda

        h = self.hoje
        itens = [
            (metalurgica, 40, "GES", "Gestão ativa de SST · contrato mensal", 1, "6800.00", Cobranca.MENSAL, StatusVenda.RECEBIDA, analista),
            (metalurgica, 18, "TRE", "Treinamento NR-12 para operadores de prensa", 22, "180.00", Cobranca.UNICA, StatusVenda.RECEBIDA, engenheiro),
            (metalurgica, 6, "TRE", "Reciclagem NR-35 · trabalho em altura", 14, "160.00", Cobranca.UNICA, StatusVenda.FATURADA, engenheiro),
            (metalurgica, 2, "PSI", "Avaliação de riscos psicossociais (NR-01)", 1, "7400.00", Cobranca.UNICA, StatusVenda.FECHADA, analista),
            (supermercado, 25, "SAU", "PCMSO e exames ocupacionais · 6 lojas", 1, "4200.00", Cobranca.MENSAL, StatusVenda.RECEBIDA, analista),
            (supermercado, 9, "ESO", "Gestão do eSocial SST (S-2210, S-2220, S-2240)", 1, "1900.00", Cobranca.MENSAL, StatusVenda.FATURADA, analista),
            (supermercado, 4, "TRE", "Formação da brigada de incêndio", 30, "120.00", Cobranca.UNICA, StatusVenda.FECHADA, engenheiro),
            (construtora, 12, "DOC", "PGR e LTCAT para nova obra", 1, "5600.00", Cobranca.UNICA, StatusVenda.RECEBIDA, engenheiro),
            (construtora, 3, "FAP", "Revisão e contestação do FAP", 1, "3800.00", Cobranca.UNICA, StatusVenda.FECHADA, analista),
            (construtora, 7, "PER", "Assistência técnica em perícia trabalhista", 1, "4500.00", Cobranca.UNICA, StatusVenda.CANCELADA, engenheiro),
        ]
        # histórico: mensalidades recebidas e avulsos espalhados pelos últimos 11 meses
        avulsos = {
            10: (metalurgica, "DOC", "Revisão do PGR e LTCAT", "5200.00", engenheiro),
            8: (supermercado, "TRE", "Treinamento NR-10 para manutenção", "3400.00", engenheiro),
            7: (construtora, "TRE", "Reciclagem NR-18 da obra Centro", "2900.00", engenheiro),
            5: (metalurgica, "FAP", "Análise do FAP e do NTEP", "4600.00", analista),
            4: (supermercado, "PSI", "Mapeamento de riscos psicossociais", "6800.00", analista),
            3: (construtora, "DOC", "PCMAT e PGR da obra Jardins", "4100.00", engenheiro),
            2: (metalurgica, "PER", "Assistência técnica em perícia", "3900.00", analista),
        }
        for meses in range(11, 1, -1):
            ano, mes = h.year, h.month - meses
            while mes <= 0:
                mes, ano = mes + 12, ano - 1
            dia = date(ano, mes, 10)
            itens.append((metalurgica, (h - dia).days, "GES", f"Gestão ativa de SST · {dia:%m/%Y}", 1, "6800.00", Cobranca.MENSAL, StatusVenda.RECEBIDA, analista))
            if meses <= 8:
                itens.append((supermercado, (h - dia).days + 2, "SAU", f"PCMSO e exames ocupacionais · {dia:%m/%Y}", 1, "4200.00", Cobranca.MENSAL, StatusVenda.RECEBIDA, analista))
            if meses in avulsos:
                emp, serv, desc, val, vend = avulsos[meses]
                itens.append((emp, (h - dia).days - 5, serv, desc, 1, val, Cobranca.UNICA, StatusVenda.RECEBIDA, vend))
        for empresa, dias, servico, descricao, qtd, valor, cobranca, status, vendedor in itens:
            Venda.objects.update_or_create(
                empresa=empresa, descricao=descricao,
                defaults={
                    "gestao": empresa.gestoes.filter(encerrado_em__isnull=True).first(),
                    "data": h - timedelta(days=dias), "servico": servico, "quantidade": qtd,
                    "valor_unitario": Decimal(valor), "cobranca": cobranca, "status": status, "vendedor": vendedor,
                },
            )

    def _campanhas(self):
        """Régua de relacionamento: renovação dos leads relativa a hoje, histórico do mês passado e do atual."""
        from django.utils import timezone as tz

        from apps.campanhas import regua
        from apps.campanhas.models import Canal, StatusEnvio
        from apps.crm.models import Lead

        def mes_mais(n):
            return (self.hoje.month - 1 + n) % 12 + 1

        dados = {
            "Transportadora Rota Sul Ltda": (1, "SegurMed Consultoria", "Carla Nunes", "carla.nunes@rotasul.exemplo.com.br", "(19) 99812-3344"),
            "Hospital Santa Clara": (2, "Clínica Ocupar", "Dr. Marcelo Reis", "marcelo.reis@santaclara.exemplo.com.br", "(19) 99734-5521"),
            "Plásticos Vale Verde": (3, "Prevenir SST", "Juliana Costa", "juliana@valeverde.exemplo.com.br", "(19) 99611-2087"),
            "Logística Expressa Brasil": (0, "Ocupacional Prime", "Renato Alves", "renato.alves@expressabr.exemplo.com.br", "(11) 98877-6655"),
            "Escola Novo Saber": (None, "", "Patrícia Lima", "secretaria@novosaber.exemplo.com.br", "(19) 99555-1200"),
            "Indústria de Alimentos Sabor & Cia": (5, "SegurMed Consultoria", "Fernando Dias", "fernando.dias@saborecia.exemplo.com.br", "(19) 99444-9087"),
            "Metalúrgica Aço Forte": (1, "Prevenir SST", "Rogério Prado", "rogerio@acoforte.exemplo.com.br", "(19) 99321-4455"),
        }
        for nome, (meses, fornecedor, contato, email, telefone) in dados.items():
            Lead.objects.filter(razao_social=nome).update(
                renovacao_mes=mes_mais(meses) if meses is not None else None, fornecedor_atual=fornecedor,
                contato_nome=contato, contato_email=email, contato_telefone=telefone,
                aceita_email=True, aceita_whatsapp=True, descadastrado_em=None,
            )
        regua.garantir_modelos()
        if regua.campanha_atual().envios.exists():
            return
        # mês passado: tudo enviado, parte aberta
        ano, mes = (self.hoje.year, self.hoje.month - 1) if self.hoje.month > 1 else (self.hoje.year - 1, 12)
        anterior = regua.garantir_campanha(ano, mes)
        regua.gerar_envios(anterior)
        quando = tz.now() - timedelta(days=self.hoje.day + 20)
        for i, envio in enumerate(anterior.envios.all()):
            envio.status, envio.enviado_em = StatusEnvio.ENVIADO, quando
            if envio.canal == Canal.EMAIL and i % 2 == 0:
                envio.aberto_em = quando + timedelta(hours=3)
            envio.save()
        anterior.emails_enviados_em = quando
        anterior.save()
        # mês atual: envios gerados, alguns já feitos, um pedido de cotação
        atual = regua.campanha_atual()
        regua.gerar_envios(atual)
        agora = tz.now()
        for i, envio in enumerate(atual.envios.filter(canal=Canal.EMAIL).order_by("lead__razao_social")[:4]):
            envio.status, envio.enviado_em = StatusEnvio.ENVIADO, agora - timedelta(hours=30)
            envio.aberto_em = agora - timedelta(hours=26) if i % 2 == 0 else None
            envio.save()
        rota = atual.envios.filter(lead__razao_social="Transportadora Rota Sul Ltda", canal=Canal.EMAIL).first()
        if rota:
            rota.status, rota.enviado_em = StatusEnvio.ENVIADO, agora - timedelta(hours=30)
            rota.aberto_em, rota.clicado_em = agora - timedelta(hours=26), agora - timedelta(hours=25)
            rota.save()
            lead = rota.lead
            lead.cotacao_pedida_em = agora - timedelta(hours=25)
            lead.save(update_fields=["cotacao_pedida_em"])
            Atividade.objects.create(lead=lead, tipo=TipoAtividade.NOTA, titulo="Pediu para participar da cotação",
                                     descricao=f"Confirmou pelo e-mail da campanha de {atual.rotulo}.", autor=None)
        wpp = atual.envios.filter(canal=Canal.WHATSAPP, lead__razao_social="Hospital Santa Clara").first()
        if wpp:
            wpp.status, wpp.enviado_em = StatusEnvio.ENVIADO, agora - timedelta(hours=5)
            wpp.save()

    # ------------------------------------------------------------- basicos

    def _usuario(self, username, nome, sobrenome, email, tipo, staff=False, empresa=None):
        usuario, criado = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": nome, "last_name": sobrenome, "email": email,
                "tipo": tipo, "is_staff": staff, "is_superuser": staff, "empresa": empresa,
                # Analista: comercial e administração. Engenheiro: técnico (gestões de SST). Cliente: só o portal.
                "acesso_comercial": tipo == TipoUsuario.INTERNO and username != "engenheiro",
                "acesso_tecnico": tipo == TipoUsuario.INTERNO,
                "acesso_admin": staff,
            },
        )
        if criado:
            usuario.set_password(self.senha)
            usuario.save()
        return usuario

    def _empresa(self, cnpj, razao, fantasia, porte, atividade, cnae, grau, trabalhadores, cidade, responsavel):
        empresa, _ = Empresa.objects.get_or_create(
            cnpj=cnpj,
            defaults={
                "razao_social": razao, "nome_fantasia": fantasia, "porte": porte,
                "atividade": atividade, "cnae": cnae, "grau_risco": grau,
                "num_trabalhadores": trabalhadores, "situacao": SituacaoEmpresa.CLIENTE,
                "cidade": cidade, "uf": "SP", "responsavel": responsavel,
                "inicio_contrato": self.hoje - timedelta(days=240),
            },
        )
        return empresa

    def _contato(self, empresa, nome, cargo, email):
        Contato.objects.get_or_create(
            empresa=empresa, nome=nome, defaults={"cargo": cargo, "email": email, "principal": True}
        )

    def _documentos(self, gestao, itens, usuario):
        if gestao.documentos.exists():
            return
        for tipo, emitido, status, rt in itens:
            documento = Documento.objects.create(
                gestao=gestao, tipo=tipo, status=status, emitido_em=emitido,
                responsavel_tecnico=rt, enviado_por=usuario,
            )
            sincronizar_documento(documento, responsavel=usuario)

    def _treinamentos(self, gestao, itens, usuario):
        if gestao.treinamentos.exists():
            return
        for tipo, status, data, participantes, horas in itens:
            treinamento = Treinamento.objects.create(
                gestao=gestao, tipo=tipo, status=status,
                realizado_em=data if status == StatusTreinamento.REALIZADO else None,
                previsto_para=data if status == StatusTreinamento.PLANEJADO else None,
                participantes=participantes, carga_horaria=horas, modalidade=Modalidade.IN_COMPANY,
            )
            if treinamento.status == StatusTreinamento.REALIZADO:
                from apps.gestao.services import calcular_validade_treinamento

                treinamento.valido_ate = calcular_validade_treinamento(treinamento)
                treinamento.save(update_fields=["valido_ate"])
            sincronizar_treinamento(treinamento, responsavel=usuario)

    def _acoes(self, gestao, itens):
        if gestao.acoes.exists():
            return []
        criadas = []
        for descricao, risco, setor, prioridade, prazo_dias, status, responsavel in itens:
            criadas.append(AcaoPlano.objects.create(
                gestao=gestao, descricao=descricao, risco=risco, setor=setor, prioridade=prioridade,
                prazo=self.hoje + timedelta(days=prazo_dias), status=status,
                responsavel_empresa=responsavel,
                concluida_em=self.hoje - timedelta(days=10) if status in StatusAcao.encerrados() else None,
            ))
        return criadas

    def _registros(self, gestao, itens, usuario):
        if gestao.registros.exists():
            return
        for dias, tipo, titulo, descricao in itens:
            gestao.registros.create(
                data=self.hoje - timedelta(days=dias), tipo=tipo, titulo=titulo,
                descricao=descricao, registrado_por=usuario,
            )

    # ------------------------------------------------------------- gestoes

    def _gestao_metalurgica(self, empresa, analista, engenheiro):
        gestao, criada = Gestao.objects.get_or_create(
            empresa=empresa,
            defaults={
                "etapa": EtapaMetodo.TREINAMENTOS, "modelo": ModeloAcompanhamento.QUINZENAL,
                "servicos": [Servico.DOCUMENTOS, Servico.GESTAO_ATIVA, Servico.TREINAMENTOS,
                             Servico.SAUDE, Servico.ESOCIAL, Servico.PSICOSSOCIAL, Servico.FAP],
                "inicio": self.hoje - timedelta(days=240), "responsavel": analista,
                "responsavel_tecnico": "Eng. Paulo Andrade · CREA-SP 506.112.334",
                "medico_coordenador": "Dra. Helena Costa · CRM-SP 98.765",
                "fap_atual": Decimal("1.3420"), "fap_meta": Decimal("0.9500"),
                "valor_mensal": Decimal("6800.00"),
            },
        )
        if criada:
            gerar_prazos_contrato(gestao, responsavel=analista)

        rt = "Eng. Paulo Andrade"
        self._documentos(gestao, [
            (TipoDocumento.PGR, meses_atras(self.hoje, 22, 18), StatusDocumento.VIGENTE, rt),
            (TipoDocumento.PCMSO, meses_atras(self.hoje, 7), StatusDocumento.VIGENTE, "Dra. Helena Costa"),
            (TipoDocumento.LTCAT, meses_atras(self.hoje, 7), StatusDocumento.VIGENTE, rt),
            (TipoDocumento.AET, meses_atras(self.hoje, 5), StatusDocumento.VIGENTE, "Ft. Marina Lopes"),
            (TipoDocumento.LI, meses_atras(self.hoje, 7), StatusDocumento.VIGENTE, rt),
            (TipoDocumento.PCA, meses_atras(self.hoje, 14), StatusDocumento.VIGENTE, rt),
            (TipoDocumento.PSICOSSOCIAL, None, StatusDocumento.ELABORACAO, "Psic. Ana Ribeiro"),
        ], engenheiro)

        self._treinamentos(gestao, [
            (TipoTreinamento.NR35, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 23), 14, 8),
            (TipoTreinamento.NR12, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 4), 32, 8),
            (TipoTreinamento.CIPA, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 6), 8, 20),
            (TipoTreinamento.BRIGADA, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 13), 12, 16),
            (TipoTreinamento.INTEGRACAO, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 1), 9, 4),
            (TipoTreinamento.ABANDONO, StatusTreinamento.PLANEJADO, self.hoje + timedelta(days=18), 180, 2),
            (TipoTreinamento.NR11, StatusTreinamento.PLANEJADO, self.hoje + timedelta(days=34), 6, 16),
        ], engenheiro)

        acoes = self._acoes(gestao, [
            ("Instalar proteção fixa na prensa excêntrica PE-03", TipoRisco.ACIDENTE, "Estamparia",
             Prioridade.ALTA, -6, StatusAcao.EM_ANDAMENTO, "Sr. Roberto (manutenção)"),
            ("Enclausurar o compressor e medir o ruído após a obra", TipoRisco.FISICO, "Utilidades",
             Prioridade.ALTA, 25, StatusAcao.AGUARDANDO, "Carlos Menezes"),
            ("Substituir protetor auricular por modelo com NRRsf adequado", TipoRisco.FISICO, "Estamparia",
             Prioridade.MEDIA, -20, StatusAcao.VERIFICADA, "Almoxarifado"),
            ("Exaustão localizada na cabine de solda", TipoRisco.QUIMICO, "Solda",
             Prioridade.ALTA, 45, StatusAcao.NAO_INICIADA, "Carlos Menezes"),
            ("Ajustar altura das bancadas de montagem (AET)", TipoRisco.ERGONOMICO, "Montagem",
             Prioridade.MEDIA, 15, StatusAcao.EM_ANDAMENTO, "Sr. Roberto (manutenção)"),
            ("Rodízio de tarefas na linha de embalagem", TipoRisco.ERGONOMICO, "Expedição",
             Prioridade.BAIXA, 60, StatusAcao.NAO_INICIADA, "Supervisão de produção"),
            ("Aplicar questionário de fatores psicossociais", TipoRisco.PSICOSSOCIAL, "Todos os setores",
             Prioridade.MEDIA, 20, StatusAcao.EM_ANDAMENTO, "RH"),
            ("Canal de escuta e procedimento contra assédio", TipoRisco.PSICOSSOCIAL, "Todos os setores",
             Prioridade.MEDIA, 50, StatusAcao.NAO_INICIADA, "RH"),
            ("Sinalizar rotas de fuga e pontos de encontro", TipoRisco.ACIDENTE, "Fábrica",
             Prioridade.MEDIA, -30, StatusAcao.CONCLUIDA, "Brigada"),
            ("Atualizar fichas de EPI com assinatura digital", TipoRisco.GESTAO, "Almoxarifado",
             Prioridade.BAIXA, -12, StatusAcao.CONCLUIDA, "Almoxarifado"),
            ("Linha de vida no telhado do galpão 2", TipoRisco.ACIDENTE, "Manutenção predial",
             Prioridade.ALTA, 30, StatusAcao.EM_ANDAMENTO, "Carlos Menezes"),
        ])
        if acoes:
            acoes[0].eventos.create(data=self.hoje - timedelta(days=21), descricao="Projeto da proteção aprovado pela manutenção.", registrado_por=engenheiro)
            acoes[0].eventos.create(data=self.hoje - timedelta(days=4), descricao="Fornecedor atrasou a chapa perfurada; nova previsão em 10 dias.", registrado_por=engenheiro)
            acoes[1].eventos.create(data=self.hoje - timedelta(days=9), descricao="Orçamento do enclausuramento enviado para aprovação da diretoria.", registrado_por=analista)
            acoes[2].eventos.create(data=self.hoje - timedelta(days=30), descricao="Novo protetor entregue a 46 trabalhadores.", registrado_por=engenheiro)
            acoes[2].eventos.create(data=self.hoje - timedelta(days=10), descricao="Audiometrias de controle sem novos desencadeamentos.", registrado_por=engenheiro)
            acoes[4].eventos.create(data=self.hoje - timedelta(days=6), descricao="4 de 9 bancadas ajustadas.", registrado_por=engenheiro)
            acoes[6].eventos.create(data=self.hoje - timedelta(days=3), descricao="Questionário aplicado em 112 de 180 trabalhadores.", registrado_por=analista)

        self._registros(gestao, [
            (238, TipoRegistro.VISITA, "Visita técnica inicial", "Levantamento documental e visita a todos os setores."),
            (210, TipoRegistro.DOCUMENTO, "Relatório de diagnóstico entregue", "34 lacunas identificadas, 9 de prioridade alta."),
            (180, TipoRegistro.ESOCIAL, "S-2240 retificado para 180 trabalhadores", "Agentes nocivos alinhados ao LTCAT."),
            (150, TipoRegistro.DOCUMENTO, "PCMSO e LTCAT emitidos", ""),
            (120, TipoRegistro.TREINAMENTO, "NR-12 para operadores de prensa", "32 participantes, 8h."),
            (60, TipoRegistro.AUDITORIA, "Auditoria interna NR-12", "Duas prensas sem proteção fixa; ação aberta no plano."),
            (21, TipoRegistro.INSPECAO, "Inspeção quinzenal · solda e estamparia", "Uso de EPI adequado; exaustão da cabine 2 inoperante."),
            (7, TipoRegistro.REUNIAO, "Reunião de segurança com a CIPA", "Pauta: SIPAT, ações atrasadas e psicossocial."),
        ], engenheiro)
        return gestao

    def _gestao_supermercado(self, empresa, analista):
        gestao, criada = Gestao.objects.get_or_create(
            empresa=empresa,
            defaults={
                "etapa": EtapaMetodo.PLANO, "modelo": ModeloAcompanhamento.MENSAL,
                "servicos": [Servico.DOCUMENTOS, Servico.GESTAO_ATIVA, Servico.PSICOSSOCIAL, Servico.ESOCIAL],
                "inicio": self.hoje - timedelta(days=75), "responsavel": analista,
                "responsavel_tecnico": "Eng. Paulo Andrade", "medico_coordenador": "Dra. Helena Costa",
                "valor_mensal": Decimal("9400.00"),
            },
        )
        if criada:
            gerar_prazos_contrato(gestao, responsavel=analista)
        self._documentos(gestao, [
            (TipoDocumento.PGR, self.hoje - timedelta(days=20), StatusDocumento.VIGENTE, "Eng. Paulo Andrade"),
            (TipoDocumento.PCMSO, meses_atras(self.hoje, 13), StatusDocumento.VIGENTE, "Dra. Helena Costa"),
            (TipoDocumento.AEP, self.hoje - timedelta(days=20), StatusDocumento.VIGENTE, "Ft. Marina Lopes"),
        ], analista)
        self._treinamentos(gestao, [
            (TipoTreinamento.CIPA, StatusTreinamento.PLANEJADO, self.hoje + timedelta(days=9), 10, 20),
            (TipoTreinamento.BRIGADA, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 12, 5), 22, 16),
        ], analista)
        self._acoes(gestao, [
            ("Câmara fria: alarme interno e abertura por dentro", TipoRisco.ACIDENTE, "Açougue", Prioridade.ALTA, 10, StatusAcao.EM_ANDAMENTO, "Manutenção"),
            ("Luvas de malha de aço para desossa", TipoRisco.ACIDENTE, "Açougue", Prioridade.ALTA, 5, StatusAcao.CONCLUIDA, "Compras"),
            ("Pausas e rodízio nos caixas", TipoRisco.ERGONOMICO, "Frente de caixa", Prioridade.MEDIA, 40, StatusAcao.NAO_INICIADA, "Gerência de loja"),
            ("Avaliar metas e jornada aos fins de semana", TipoRisco.PSICOSSOCIAL, "Lojas", Prioridade.MEDIA, 70, StatusAcao.NAO_INICIADA, "RH"),
        ])
        self._registros(gestao, [
            (74, TipoRegistro.VISITA, "Visita técnica inicial às 4 lojas", ""),
            (20, TipoRegistro.DOCUMENTO, "PGR e AEP emitidos", "Inventário com 4 GHEs e plano de ação inicial."),
        ], analista)

    def _gestao_construtora(self, empresa, engenheiro):
        gestao, criada = Gestao.objects.get_or_create(
            empresa=empresa,
            defaults={
                "etapa": EtapaMetodo.DIAGNOSTICO, "modelo": ModeloAcompanhamento.SEMANAL,
                "servicos": [Servico.DOCUMENTOS, Servico.GESTAO_ATIVA, Servico.TREINAMENTOS, Servico.PERICIAL],
                "inicio": self.hoje - timedelta(days=12), "responsavel": engenheiro,
                "responsavel_tecnico": "Eng. Paulo Andrade", "valor_mensal": Decimal("5200.00"),
            },
        )
        if criada:
            gerar_prazos_contrato(gestao, responsavel=engenheiro)
        self._documentos(gestao, [
            (TipoDocumento.PGR, meses_atras(self.hoje, 26), StatusDocumento.VIGENTE, "Fornecedor anterior"),
        ], engenheiro)
        self._treinamentos(gestao, [
            (TipoTreinamento.NR35, StatusTreinamento.REALIZADO, meses_atras(self.hoje, 25), 18, 8),
            (TipoTreinamento.NR18, StatusTreinamento.PLANEJADO, self.hoje + timedelta(days=6), 40, 6),
        ], engenheiro)
        self._registros(gestao, [
            (11, TipoRegistro.VISITA, "Visita ao canteiro · Ed. Jardins", "PGR do fornecedor anterior vencido; NR-35 com reciclagem vencida."),
        ], engenheiro)

    # ------------------------------------------------------ relacionamento

    def _relacionamento(self, gestao, analista, cliente):
        agora = timezone.now()
        if not gestao.solicitacoes.exists():
            DocumentoSolicitado.objects.create(
                gestao=gestao, titulo="Lista de trabalhadores por função e setor",
                motivo="Atualização dos GHEs no inventário de riscos.", prazo=self.hoje + timedelta(days=5),
                solicitado_por=analista,
            )
            DocumentoSolicitado.objects.create(
                gestao=gestao, titulo="Fichas de EPI do último trimestre",
                motivo="Auditoria interna de EPI.", prazo=self.hoje - timedelta(days=2),
                solicitado_por=analista,
            )
            DocumentoSolicitado.objects.create(
                gestao=gestao, titulo="Ordens de serviço assinadas",
                motivo="NR-01, item 1.4.1.", status=StatusPedido.VALIDADO, enviado_em=agora - timedelta(days=40),
                solicitado_por=analista,
            )
        if not gestao.reunioes.exists():
            def quando(dias, hora):
                return timezone.make_aware(datetime.combine(self.hoje + timedelta(days=dias), time(hora, 0)))

            Reuniao.objects.create(
                gestao=gestao, tipo=TipoReuniao.VISITA, titulo="Inspeção quinzenal · solda e estamparia",
                quando=quando(4, 9), duracao_minutos=180, local="Fábrica · Campinas",
                participantes="Eng. Paulo Andrade, Sr. Roberto", pauta="Conferir proteção da PE-03 e exaustão da cabine 2.",
            )
            Reuniao.objects.create(
                gestao=gestao, tipo=TipoReuniao.ONLINE, titulo="Resultado do questionário psicossocial",
                quando=quando(16, 14), duracao_minutos=60, local="Google Meet",
                participantes="RH e diretoria", pauta="Primeira leitura dos fatores psicossociais.",
            )
            Reuniao.objects.create(
                gestao=gestao, tipo=TipoReuniao.REUNIAO, titulo="Reunião mensal de segurança",
                quando=quando(-7, 10), status=StatusReuniao.REALIZADA, local="Sala de reuniões",
                ata="Prazo da PE-03 renegociado. SIPAT confirmada para o próximo mês.",
            )
        if not gestao.mensagens.exists():
            Mensagem.objects.create(gestao=gestao, autor=analista,
                                    texto="Carlos, a reciclagem de NR-35 vence no próximo mês. Já reservei turma para dia 20.")
            Mensagem.objects.create(gestao=gestao, autor=cliente,
                                    texto="Perfeito. São 14 pessoas, vou confirmar a lista com a supervisão.")
            Mensagem.objects.create(gestao=gestao, autor=analista,
                                    texto="Combinado. Aproveite e envie a lista de trabalhadores por função que pedimos em Documentos.")

    # ------------------------------------------------------------- captacao

    def _leads(self, analista, engenheiro):
        # Mesmo CNPJ do cliente de exemplo do sistema Tarefas: mostra o cruzamento na área comercial.
        CNPJ_LEADS = {"Hospital Santa Clara": "30.561.892/0001-60"}
        dados = [
            ("Transportadora Rota Sul Ltda", Estagio.NOVO, SituacaoSST.DOCS_VENCIDOS, ServicoInteresse.GESTAO_ATIVA, 210, 3, "4500", OrigemLead.PARCEIRO, 2),
            ("Hospital Santa Clara", Estagio.CONTATO, SituacaoSST.NOTIFICADA, ServicoInteresse.PSICOSSOCIAL, 640, 3, "12000", OrigemLead.SITE, -1),
            ("Plásticos Vale Verde", Estagio.DIAGNOSTICO, SituacaoSST.FORNECEDOR, ServicoInteresse.DOCUMENTOS, 130, 3, "3800", OrigemLead.INDICACAO, 3),
            ("Logística Expressa Brasil", Estagio.PROPOSTA, SituacaoSST.PASSIVO, ServicoInteresse.PERICIAL, 300, 3, "7600", OrigemLead.EVENTO, 5),
            ("Escola Novo Saber", Estagio.NEGOCIACAO, SituacaoSST.SEM_GESTAO, ServicoInteresse.TREINAMENTOS, 85, 2, "2100", OrigemLead.ATIVA, 1),
            ("Indústria de Alimentos Sabor & Cia", Estagio.PROPOSTA, SituacaoSST.EM_DIA, ServicoInteresse.FAP, 520, 3, "8900", OrigemLead.CARTEIRA, -3),
            ("Cerâmica Paulista", Estagio.GANHO, SituacaoSST.SEM_GESTAO, ServicoInteresse.GESTAO_ATIVA, 160, 3, "5200", OrigemLead.INDICACAO, 0),
            ("Rede Farma Mais", Estagio.GANHO, SituacaoSST.DOCS_VENCIDOS, ServicoInteresse.DOCUMENTOS, 240, 2, "3600", OrigemLead.SITE, 0),
            ("Metalúrgica Aço Forte", Estagio.PERDIDO, SituacaoSST.EM_DIA, ServicoInteresse.FAP, 310, 3, "4800", OrigemLead.ATIVA, 0),
        ]
        for nome, estagio, situacao, servico, trabalhadores, grau, valor, origem, dias in dados:
            if Lead.objects.filter(razao_social=nome).exists():
                continue
            lead = Lead.objects.create(
                cnpj=CNPJ_LEADS.get(nome, ""),
                razao_social=nome, estagio=estagio, situacao_sst=situacao, servico_interesse=servico,
                num_trabalhadores=trabalhadores, grau_risco=grau, valor_estimado=Decimal(valor),
                origem=origem, responsavel=analista if dias % 2 else engenheiro,
                proximo_contato=self.hoje + timedelta(days=dias), cidade="Campinas", uf="SP",
                contato_nome="Responsável de RH", urgencia=UrgenciaLead.MEDIA,
            )
            Atividade.objects.create(
                lead=lead, tipo=TipoAtividade.LIGACAO, titulo="Primeiro contato",
                descricao="Apresentação da gestão integrada de SST.", autor=lead.responsavel,
                data=self.hoje - timedelta(days=6),
            )

    def _diagnosticos(self):
        if Diagnostico.objects.exists():
            return
        from apps.publico.conteudo import PERGUNTAS_QUIZ, riscos_da_resposta

        def respostas(escolhas):
            itens = []
            for pergunta, indice in zip(PERGUNTAS_QUIZ, escolhas):
                rotulo, pontos, servicos = pergunta["opcoes"][indice]
                itens.append({"chave": pergunta["chave"], "pergunta": pergunta["texto"],
                              "resposta": rotulo, "pontos": pontos, "servicos": list(servicos),
                              "riscos": riscos_da_resposta(pergunta["chave"], indice)})
            return itens

        casos = [
            ("Fernanda Alves", "Cerâmica Bela Vista", "(19) 99876-1234", "fernanda@belavista.com.br",
             timedelta(hours=3), [2, 2, 1, 2, 1, 3, 1, 2, 1, 1, 2, 1, 1, 1, 0, 1]),
            ("Ricardo Nunes", "Escritório Nunes Contabilidade", "", "ricardo@nunes.com.br",
             timedelta(days=1), [0, 0, 0, 2, 0, 2, 3, 0, 0, 0, 0, 0, 0, 0, 3, 1]),
            ("Marcelo Tavares", "Transportes Ligeiro", "(11) 98765-4321", "",
             timedelta(minutes=50), [2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 2, 4]),
        ]
        for nome, empresa, telefone, email, ha, escolhas in casos:
            itens = respostas(escolhas)
            pontos = sum(item["pontos"] for item in itens)
            diagnostico = Diagnostico.objects.create(
                nome=nome, empresa=empresa, telefone=telefone, email=email,
                contato_em=timezone.now() - ha, respostas=itens, pontuacao=pontos,
                urgencia=Urgencia.da_pontuacao(pontos),
            )
            Diagnostico.objects.filter(pk=diagnostico.pk).update(criado_em=timezone.now() - ha)
