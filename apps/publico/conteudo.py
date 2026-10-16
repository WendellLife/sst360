# -*- coding: utf-8 -*-
"""Conteudo editorial do site publico e do diagnostico.

Fica em Python (e nao no banco) porque e texto de marca: muda por revisao, nao
no dia a dia. As chaves sao ASCII; os textos exibidos levam a acentuacao
correta do portugues.
"""

# Linhas de servico do portfolio, na ordem da apresentacao comercial.
SERVICOS = [
    {
        "numero": "01",
        "titulo": "Documentos e programas",
        "desc": "PGR, PCMSO, LTCAT, AEP, AET, laudos de insalubridade e periculosidade, PCA, PPR, "
                "POPs e pareceres técnicos.",
        "itens": ["PGR", "PCMSO", "LTCAT", "AEP / AET", "LI / LP", "PCA / PPR"],
    },
    {
        "numero": "02",
        "titulo": "Gestão ativa personalizada",
        "desc": "Acompanhamento semanal, quinzenal ou mensal: plano de ação, auditorias, inspeções, "
                "reuniões de segurança e indicadores.",
        "itens": ["Semanal", "Quinzenal", "Mensal"],
    },
    {
        "numero": "03",
        "titulo": "Riscos psicossociais (NR-01)",
        "desc": "Identificação, avaliação e plano de ação para fatores psicossociais, integrados ao "
                "GRO e ao inventário de riscos do PGR.",
        "itens": ["Diagnóstico", "Inventário", "Plano de ação"],
    },
    {
        "numero": "04",
        "titulo": "Treinamentos",
        "desc": "CIPA, brigada de incêndio, plano de abandono, primeiros socorros, GHS, integração, "
                "NRs e treinamentos comportamentais. Presencial, on-line ou in company.",
        "itens": ["CIPA", "Brigada", "NR-35", "NR-10", "NR-33"],
    },
    {
        "numero": "05",
        "titulo": "Saúde ocupacional integrada",
        "desc": "Clínica própria: ASOs, audiometria, espirometria, acuidade, ECG, EEG, laboratoriais "
                "e campanhas de saúde in loco, ligados ao PGR e ao PCMSO.",
        "itens": ["ASO", "Exames complementares", "Campanhas"],
    },
    {
        "numero": "06",
        "titulo": "Gestão do eSocial",
        "desc": "Eventos de SST S-2210, S-2220 e S-2240 com rastreabilidade e integração com PGR, "
                "PCMSO e LTCAT.",
        "itens": ["S-2210", "S-2220", "S-2240"],
    },
    {
        "numero": "07",
        "titulo": "Redução do FAP",
        "desc": "Gestão de afastamentos, controle de incidentes, revisão de NTEP e adequação "
                "documental para reduzir contribuições e passivos.",
        "itens": ["Afastamentos", "NTEP", "Contestação"],
    },
    {
        "numero": "08",
        "titulo": "Assistência jurídica e pericial",
        "desc": "Assistência técnica em perícias de engenharia e médicas, pareceres de defesa, "
                "contraprovas e estudos de nexo causal.",
        "itens": ["Perícia de engenharia", "Perícia médica", "Pareceres"],
    },
]

DIFERENCIAIS = [
    "Equipe multidisciplinar: engenharia, medicina, ergonomia e jurídico",
    "Gestão ativa e contínua",
    "Integração documental total",
    "Estratégias financeiras: FAP e passivos",
    "Suporte jurídico e pericial",
    "Clínica própria",
    "Sistema organizado e rastreável",
    "Comunicação direta com a equipe técnica",
]

DORES = [
    "Documentações desatualizadas ou desconectadas da realidade",
    "Falta de gestão contínua dos riscos e dos planos de ação",
    "Dificuldade em auditorias e certificações",
    "Falhas de envio no eSocial",
    "Passivos trabalhistas relacionados à SST",
    "Afastamentos e acidentes com impacto em custo e produtividade",
    "Falta de indicadores e de rastreabilidade",
    "Perícias trabalhistas sem assistência técnica",
]

# As 12 etapas do metodo. "fase" agrupa as etapas na pagina publica.
ETAPAS_METODO = [
    {"numero": 1, "fase": "Estruturação", "titulo": "Diagnóstico técnico inicial",
     "desc": "Levantamento de documentos, riscos, exames, treinamentos e envios ao eSocial. "
             "Fotografia da situação atual, com as lacunas por norma.",
     "entrega": "Relatório de diagnóstico com lacunas priorizadas."},
    {"numero": 2, "fase": "Estruturação", "titulo": "Mapeamento de riscos",
     "desc": "Visita técnica por setor e GHE: riscos físicos, químicos, biológicos, ergonômicos, "
             "de acidente e psicossociais.",
     "entrega": "Inventário de riscos do GRO."},
    {"numero": 3, "fase": "Estruturação", "titulo": "Ajuste documental",
     "desc": "PGR, PCMSO, LTCAT, laudos e AEP coerentes entre si e com a operação real.",
     "entrega": "Documentos emitidos, com responsável técnico e validade."},
    {"numero": 4, "fase": "Estruturação", "titulo": "Plano de ação",
     "desc": "Cada risco com medida de controle, responsável, prazo e prioridade.",
     "entrega": "Plano de ação no portal, item a item."},
    {"numero": 5, "fase": "Operação", "titulo": "Gestão ativa",
     "desc": "Visitas e monitoramento no modelo contratado: semanal, quinzenal ou mensal.",
     "entrega": "Registro de cada visita na linha do tempo."},
    {"numero": 6, "fase": "Operação", "titulo": "Treinamentos",
     "desc": "Cronograma de treinamentos obrigatórios e comportamentais, com controle de reciclagem.",
     "entrega": "Lista de presença, certificados e próximas reciclagens."},
    {"numero": 7, "fase": "Operação", "titulo": "Gestão de exames e saúde",
     "desc": "ASOs e exames complementares conforme o PCMSO, com clínica própria.",
     "entrega": "Exames em dia e relatório analítico anual."},
    {"numero": 8, "fase": "Operação", "titulo": "eSocial integrado",
     "desc": "S-2210, S-2220 e S-2240 enviados no prazo e coerentes com os documentos.",
     "entrega": "Eventos conferidos, sem inconsistências."},
    {"numero": 9, "fase": "Operação", "titulo": "Indicadores e relatórios",
     "desc": "Taxa de frequência, afastamentos, ações concluídas e documentos vigentes.",
     "entrega": "Painel de desempenho de SST."},
    {"numero": 10, "fase": "Consolidação", "titulo": "Suporte jurídico e pericial",
     "desc": "Assistência técnica em perícias e pareceres para a defesa da empresa.",
     "entrega": "Dossiês técnicos e pareceres."},
    {"numero": 11, "fase": "Consolidação", "titulo": "Auditorias internas",
     "desc": "Verificação periódica do cumprimento das NRs e da eficácia das ações.",
     "entrega": "Relatório de auditoria com não conformidades."},
    {"numero": 12, "fase": "Consolidação", "titulo": "Cultura de segurança implementada",
     "desc": "SST como rotina da operação, com lideranças engajadas e indicadores estáveis.",
     "entrega": "Operação de SST que funciona sem depender de urgência."},
]

COMO_FUNCIONA = [
    {
        "numero": "01",
        "titulo": "Diagnóstico gratuito",
        "desc": "Dezesseis perguntas, cerca de quatro minutos. Resultado com o nível de exposição, os serviços indicados "
                "e retorno da equipe técnica com prazo definido.",
    },
    {
        "numero": "02",
        "titulo": "Visita e proposta",
        "desc": "Visita técnica, leitura dos documentos atuais e proposta com o modelo de "
                "acompanhamento adequado ao porte e ao grau de risco.",
    },
    {
        "numero": "03",
        "titulo": "Gestão no portal",
        "desc": "Documentos, plano de ação, treinamentos, visitas e prazos no portal do cliente, "
                "com data e responsável.",
    },
]

# Diagnostico: cada opcao e (rotulo, pontos de exposicao, servicos indicados).
# Pontos medem o risco de autuacao e de passivo; os servicos usam os codigos de
# apps.gestao.models.Servico e montam a recomendacao do resultado e do lead.
# "bloco" agrupa as perguntas na tela.
DOC, GES, TRE, SAU, ESO, FAP, PER, PSI = "DOC", "GES", "TRE", "SAU", "ESO", "FAP", "PER", "PSI"

PERGUNTAS_QUIZ = [
    # ---------------------------------------------------------- perfil
    {
        "chave": "trabalhadores", "bloco": "Perfil da empresa",
        "texto": "Quantos trabalhadores a empresa tem, somando todas as unidades?",
        "opcoes": [
            ("Até 19", 1, []),
            ("De 20 a 99", 2, []),
            ("De 100 a 499", 3, [GES]),
            ("500 ou mais", 3, [GES]),
        ],
    },
    {
        "chave": "operacao", "bloco": "Perfil da empresa",
        "texto": "Qual é a atividade principal?",
        "ajuda": "Define o grau de risco (NR-04) e os documentos obrigatórios.",
        "opcoes": [
            ("Escritório / administrativo", 0, []),
            ("Comércio ou serviços", 1, []),
            ("Indústria, logística ou armazenagem", 2, [DOC, TRE]),
            ("Construção, saúde, química ou outra atividade de alto risco", 3, [DOC, TRE]),
        ],
    },
    {
        "chave": "unidades", "bloco": "Perfil da empresa",
        "texto": "Em quantos endereços (unidades, lojas, obras) a empresa opera?",
        "opcoes": [
            ("Um", 0, []),
            ("De 2 a 5", 1, [GES]),
            ("Mais de 5", 2, [GES]),
        ],
    },
    {
        "chave": "gestao_atual", "bloco": "Perfil da empresa",
        "texto": "Quem cuida da saúde e segurança do trabalho hoje?",
        "opcoes": [
            ("Equipe interna (SESMT ou técnico próprio)", 0, []),
            ("Consultoria externa, e queremos melhorar ou trocar", 1, [GES]),
            ("Alguém do RH ou administrativo, sem dedicação", 2, [GES]),
            ("Ninguém de forma contínua", 3, [GES]),
        ],
    },
    # ------------------------------------------------------ documentos
    {
        "chave": "pgr", "bloco": "Documentos e programas",
        "texto": "O PGR (inventário de riscos e plano de ação) foi revisado nos últimos 2 anos?",
        "opcoes": [
            ("Sim, está atualizado", 0, []),
            ("Não sei informar", 2, [DOC]),
            ("Não, ou a empresa não tem PGR", 3, [DOC]),
        ],
    },
    {
        "chave": "psicossocial", "bloco": "Documentos e programas",
        "texto": "Os riscos psicossociais já fazem parte do inventário de riscos (NR-01)?",
        "ajuda": "Sobrecarga, assédio, metas, clima e liderança passaram a integrar o GRO.",
        "opcoes": [
            ("Sim, já foram avaliados", 0, []),
            ("Em andamento", 1, [PSI]),
            ("Não sei informar", 2, [PSI]),
            ("Ainda não", 3, [PSI]),
        ],
    },
    {
        "chave": "ltcat", "bloco": "Documentos e programas",
        "texto": "LTCAT e laudos de insalubridade e periculosidade estão atualizados?",
        "opcoes": [
            ("Sim, coerentes com a operação atual", 0, []),
            ("Existem, mas estão desatualizados", 2, [DOC]),
            ("Não temos", 3, [DOC]),
            ("Não sei informar", 2, [DOC]),
        ],
    },
    {
        "chave": "ergonomia", "bloco": "Documentos e programas",
        "texto": "A empresa tem análise ergonômica (AEP ou AET)?",
        "opcoes": [
            ("Sim", 0, []),
            ("Não sei informar", 1, [DOC]),
            ("Não", 2, [DOC]),
        ],
    },
    # ---------------------------------------------------------- saude
    {
        "chave": "exames", "bloco": "Saúde ocupacional",
        "texto": "O PCMSO e os exames ocupacionais (ASO admissional, periódico, demissional) estão em dia?",
        "opcoes": [
            ("Sim, todos", 0, []),
            ("Parcialmente", 1, [SAU]),
            ("Não sei informar", 2, [SAU]),
            ("Não", 3, [SAU]),
        ],
    },
    {
        "chave": "clinica", "bloco": "Saúde ocupacional",
        "texto": "Como os exames são feitos hoje?",
        "opcoes": [
            ("Clínica contratada, integrada ao PCMSO", 0, []),
            ("Várias clínicas, sem controle centralizado", 1, [SAU]),
            ("Sem clínica definida", 2, [SAU]),
        ],
    },
    {
        "chave": "afastamentos", "bloco": "Saúde ocupacional",
        "texto": "Nos últimos 12 meses, houve afastamentos pelo INSS?",
        "ajuda": "Afastamentos pesam no FAP, que multiplica a alíquota do RAT.",
        "opcoes": [
            ("Nenhum", 0, []),
            ("Poucos casos", 1, [FAP]),
            ("Vários casos", 2, [FAP, SAU]),
            ("Não sei informar", 1, [FAP]),
        ],
    },
    # -------------------------------------------------------- esocial
    {
        "chave": "esocial", "bloco": "eSocial",
        "texto": "Os eventos de SST do eSocial (S-2210, S-2220, S-2240) são enviados no prazo?",
        "opcoes": [
            ("Sim, sem pendências", 0, []),
            ("Com atrasos ou rejeições", 2, [ESO]),
            ("Não sei informar", 2, [ESO]),
            ("Não são enviados", 3, [ESO]),
        ],
    },
    # --------------------------------------------------- treinamentos
    {
        "chave": "treinamentos", "bloco": "Treinamentos",
        "texto": "Os treinamentos obrigatórios das NRs (NR-35, NR-10, NR-12, NR-33...) estão em dia?",
        "opcoes": [
            ("Sim, com controle de reciclagem", 0, []),
            ("Alguns vencidos", 2, [TRE]),
            ("Não sei informar", 2, [TRE]),
            ("Não são realizados", 3, [TRE]),
        ],
    },
    {
        "chave": "cipa_brigada", "bloco": "Treinamentos",
        "texto": "A CIPA (ou o designado) e a brigada de incêndio estão constituídas e treinadas?",
        "opcoes": [
            ("Sim, as duas", 0, []),
            ("Só uma delas", 1, [TRE]),
            ("Nenhuma", 2, [TRE]),
            ("Não sei informar", 1, [TRE]),
        ],
    },
    # ------------------------------------------------------- historico
    {
        "chave": "ocorrencias", "bloco": "Histórico",
        "texto": "Nos últimos 12 meses, a empresa teve algum destes eventos?",
        "opcoes": [
            ("Fiscalização ou notificação", 3, [DOC, GES]),
            ("Ação trabalhista ou perícia", 3, [PER]),
            ("Acidente com afastamento", 3, [GES, ESO]),
            ("Nenhum deles", 0, []),
        ],
    },
    {
        "chave": "prioridade", "bloco": "Histórico",
        "texto": "O que é mais urgente para a empresa agora?",
        "opcoes": [
            ("Regularizar documentos e programas", 0, [DOC]),
            ("Avaliar os riscos psicossociais (NR-01)", 0, [PSI]),
            ("Organizar exames e saúde ocupacional", 0, [SAU]),
            ("Treinar as equipes", 0, [TRE]),
            ("Reduzir o FAP e os afastamentos", 0, [FAP]),
            ("Defesa em ação trabalhista ou perícia", 0, [PER]),
        ],
    },
]

TOTAL_PERGUNTAS = len(PERGUNTAS_QUIZ)
PONTUACAO_MAXIMA = sum(max(opcao[1] for opcao in pergunta["opcoes"]) for pergunta in PERGUNTAS_QUIZ)
BLOCOS_QUIZ = list(dict.fromkeys(pergunta["bloco"] for pergunta in PERGUNTAS_QUIZ))

# Por que cada servico aparece no resultado, na voz do manual: o que, para que.
MOTIVO_SERVICO = {
    DOC: "PGR, PCMSO, LTCAT, laudos e AEP coerentes entre si e com a operação real.",
    GES: "Acompanhamento contínuo, com plano de ação, inspeções e indicadores no portal.",
    TRE: "Cronograma de treinamentos das NRs, CIPA e brigada, com controle de reciclagem.",
    SAU: "ASOs e exames complementares com clínica própria, integrados ao PCMSO.",
    ESO: "Eventos S-2210, S-2220 e S-2240 no prazo e coerentes com os documentos.",
    FAP: "Gestão de afastamentos, revisão de NTEP e contestação do FAP.",
    PER: "Assistência técnica em perícias, pareceres e estudos de nexo causal.",
    PSI: "Avaliação de riscos psicossociais integrada ao GRO e ao inventário do PGR.",
}

# ---------------------------------------------------------------- riscos e multas
# Valores de referência 2026. Multas das NRs (CLT, art. 201): Portaria MTE nº 1.131/2025,
# por item descumprido, com o valor máximo na reincidência ou embaraço à fiscalização.
# Multas previdenciárias: Portaria Interministerial MPS/MF nº 13/2026.
SEG_MIN, SEG_MAX = 693.11, 6935.56      # segurança do trabalho, por infração
MED_MIN, MED_MAX = 415.87, 4160.89      # medicina do trabalho, por infração
CAT_MIN, CAT_MAX = 1621.00, 8475.55     # Lei 8.213/1991, art. 22 (limites do salário de contribuição)
LTCAT_FIXA = 34997.79                   # RPS, art. 283, II
RPS_MIN, RPS_MAX = 3499.80, 349978.53   # RPS: infração sem penalidade específica, conforme a gravidade

FONTE_MULTAS = (
    "Valores de referência 2026: Portaria MTE nº 1.131/2025 (multas das NRs, CLT art. 201) e "
    "Portaria Interministerial MPS/MF nº 13/2026 (multas previdenciárias). Cada item descumprido "
    "pode gerar um auto de infração; na reincidência ou embaraço à fiscalização vale o valor máximo. "
    "Estimativa sem considerar número de trabalhadores, condenações judiciais ou custos de afastamento. "
    "Não constitui parecer jurídico."
)

# gravidade: "alta" ou "media". minimo/maximo em reais (None quando o risco não é multa).
RISCOS = {
    "PGR": {
        "correcao": "Elaborar ou revisar o PGR: inventário de riscos por setor e plano de ação com prazo e responsável.",
        "titulo": "PGR ausente ou desatualizado", "norma": "NR-01 · GRO", "gravidade": "alta", "servico": DOC,
        "minimo": SEG_MIN, "maximo": SEG_MAX, "unidade": "por item da NR-01 descumprido",
        "impacto": "É a base do gerenciamento de riscos. Sem ele, PCMSO, LTCAT e eSocial ficam sem sustentação "
                   "técnica e cada lacuna do inventário vira um item autuável.",
    },
    "PSI": {
        "correcao": "Avaliar os fatores psicossociais e incluir no inventário do PGR, com plano de ação.",
        "titulo": "Riscos psicossociais fora do inventário", "norma": "NR-01 · obrigatório desde 26/05/2026",
        "gravidade": "alta", "servico": PSI, "minimo": SEG_MIN, "maximo": SEG_MAX, "unidade": "por item descumprido",
        "impacto": "Sobrecarga, metas e assédio sem avaliação nem plano de ação. Além da autuação, sustentam "
                   "afastamentos por saúde mental e ações trabalhistas por assédio.",
    },
    "LTCAT": {
        "correcao": "Emitir ou atualizar o LTCAT com as avaliações ambientais atuais.",
        "titulo": "LTCAT ausente ou desatualizado", "norma": "RPS, art. 283, II", "gravidade": "alta", "servico": DOC,
        "minimo": LTCAT_FIXA, "maximo": LTCAT_FIXA, "unidade": "multa fixa",
        "impacto": "Sem LTCAT, PPP e S-2240 ficam sem base técnica. Insalubridade (10% a 40% do salário mínimo) "
                   "e periculosidade (30% do salário) podem ser cobradas com retroativo em ação trabalhista.",
    },
    "ERGO": {
        "correcao": "Fazer a AEP dos postos de trabalho e a AET onde houver risco ergonômico relevante.",
        "titulo": "Sem análise ergonômica", "norma": "NR-17 · AEP / AET", "gravidade": "media", "servico": DOC,
        "minimo": MED_MIN, "maximo": SEG_MAX, "unidade": "por item da NR-17 descumprido",
        "impacto": "Lesões osteomusculares estão entre as principais causas de afastamento e de nexo técnico "
                   "previdenciário, que eleva o FAP da empresa.",
    },
    "PCMSO": {
        "correcao": "Atualizar o PCMSO e regularizar os ASOs vencidos ou faltantes.",
        "titulo": "PCMSO e ASOs fora do prazo", "norma": "NR-07", "gravidade": "alta", "servico": SAU,
        "minimo": MED_MIN, "maximo": MED_MAX, "unidade": "por item da NR-07 descumprido",
        "impacto": "Sem ASO admissional, periódico ou demissional, a empresa perde a prova de aptidão do "
                   "trabalhador numa ação trabalhista ou num pedido de nexo de doença ocupacional.",
    },
    "EXAMES": {
        "correcao": "Centralizar os exames numa clínica integrada ao PCMSO, com controle de vencimentos.",
        "titulo": "Exames sem controle centralizado", "norma": "NR-07 · eSocial S-2220", "gravidade": "media",
        "servico": SAU, "minimo": MED_MIN, "maximo": MED_MAX, "unidade": "por item da NR-07 descumprido",
        "impacto": "Várias clínicas sem integração geram ASO vencido sem aviso e divergência entre o PCMSO "
                   "e o que é enviado ao eSocial.",
    },
    "ESOCIAL": {
        "correcao": "Conferir e retificar os eventos S-2220 e S-2240 com base no LTCAT e no PCMSO.",
        "titulo": "Eventos de SST do eSocial com falhas", "norma": "S-2220 · S-2240 · PPP eletrônico",
        "gravidade": "alta", "servico": ESO, "minimo": RPS_MIN, "maximo": RPS_MAX, "unidade": "conforme a gravidade",
        "impacto": "O S-2240 é o PPP eletrônico do trabalhador. Informação ausente ou incoerente com o LTCAT é "
                   "infração previdenciária e base para pedidos de aposentadoria especial.",
    },
    "CAT": {
        "correcao": "Implantar rotina de envio da CAT (S-2210) até o 1º dia útil após o acidente.",
        "titulo": "CAT não comunicada no prazo", "norma": "Lei 8.213/1991, art. 22 · S-2210", "gravidade": "alta",
        "servico": ESO, "minimo": CAT_MIN, "maximo": CAT_MAX, "unidade": "por comunicação",
        "impacto": "Acidente sem CAT até o 1º dia útil seguinte gera multa por ocorrência, que sobe na reincidência.",
    },
    "TREIN": {
        "correcao": "Montar o cronograma de treinamentos das NRs e reciclar os vencidos.",
        "titulo": "Treinamentos obrigatórios vencidos", "norma": "NR-35 · NR-10 · NR-12 · NR-33", "gravidade": "alta",
        "servico": TRE, "minimo": SEG_MIN, "maximo": SEG_MAX, "unidade": "por item descumprido",
        "impacto": "Em acidente com trabalhador sem treinamento válido, o INSS pode cobrar da empresa os "
                   "benefícios pagos (ação regressiva, Lei 8.213/1991, art. 120).",
    },
    "CIPA": {
        "correcao": "Constituir e treinar a CIPA (ou designado) e a brigada de incêndio.",
        "titulo": "CIPA ou brigada não constituídas", "norma": "NR-05 · NR-23", "gravidade": "media", "servico": TRE,
        "minimo": SEG_MIN, "maximo": SEG_MAX, "unidade": "por item descumprido",
        "impacto": "A brigada também é exigência do Corpo de Bombeiros e pode travar a renovação do AVCB, "
                   "conforme a instrução técnica do estado.",
    },
    "FAP": {
        "correcao": "Analisar afastamentos e NTEP e contestar o FAP quando houver erro.",
        "titulo": "Afastamentos elevam o FAP", "norma": "Decreto 3.048/1999, art. 202-A", "gravidade": "media",
        "servico": FAP, "minimo": None, "maximo": None, "unidade": "",
        "impacto": "O FAP multiplica a alíquota RAT (1%, 2% ou 3% da folha) por um fator de 0,5 a 2,0. "
                   "Com RAT de 3% e FAP 2,0, a empresa recolhe 6% da folha de pagamento.",
    },
    "FISCAL": {
        "correcao": "Responder às notificações abertas e corrigir os itens autuados antes de nova fiscalização.",
        "titulo": "Empresa já notificada pela fiscalização", "norma": "CLT, art. 201 · reincidência",
        "gravidade": "alta", "servico": GES, "minimo": None, "maximo": None, "unidade": "",
        "impacto": "Na reincidência ou embaraço à fiscalização, cada item autuado vai ao valor máximo: "
                   "R$ 6.935,56 em segurança e R$ 4.160,89 em medicina do trabalho.",
    },
    "PERICIA": {
        "correcao": "Indicar assistente técnico e preparar a defesa técnica da perícia.",
        "titulo": "Ação trabalhista sem assistência técnica", "norma": "Perícia judicial", "gravidade": "alta",
        "servico": PER, "minimo": None, "maximo": None, "unidade": "",
        "impacto": "Sem assistente técnico, o laudo do perito define sozinho insalubridade, periculosidade ou "
                   "nexo causal da doença, e a condenação costuma vir com retroativo.",
    },
    "ACIDENTE": {
        "correcao": "Investigar o acidente, registrar as medidas de controle e revisar o PGR.",
        "titulo": "Acidente com afastamento no histórico", "norma": "Lei 8.213/1991, art. 120 · CLT, art. 161",
        "gravidade": "alta", "servico": GES, "minimo": None, "maximo": None, "unidade": "",
        "impacto": "Além da CAT, abre espaço para ação regressiva do INSS, indenização por dano moral e material "
                   "e interdição do setor pela fiscalização.",
    },
    "SEMGESTAO": {
        "correcao": "Definir um responsável técnico e uma agenda de acompanhamento contínuo.",
        "titulo": "Ninguém responde pela SST de forma contínua", "norma": "Gestão de SST", "gravidade": "media",
        "servico": GES, "minimo": None, "maximo": None, "unidade": "",
        "impacto": "Revisões, reciclagens e exames vencem sem aviso. Cada vencimento é um item autuável e "
                   "uma prova a menos na defesa da empresa.",
    },
}

# Quais respostas apontam cada risco: chave da pergunta -> índice da opção -> riscos.
RISCOS_POR_RESPOSTA = {
    "gestao_atual": {2: ["SEMGESTAO"], 3: ["SEMGESTAO"]},
    "pgr": {1: ["PGR"], 2: ["PGR"]},
    "psicossocial": {2: ["PSI"], 3: ["PSI"]},
    "ltcat": {1: ["LTCAT"], 2: ["LTCAT"], 3: ["LTCAT"]},
    "ergonomia": {1: ["ERGO"], 2: ["ERGO"]},
    "exames": {1: ["PCMSO"], 2: ["PCMSO"], 3: ["PCMSO"]},
    "clinica": {1: ["EXAMES"], 2: ["EXAMES"]},
    "afastamentos": {1: ["FAP"], 2: ["FAP"], 3: ["FAP"]},
    "esocial": {1: ["ESOCIAL"], 2: ["ESOCIAL"], 3: ["ESOCIAL", "CAT"]},
    "treinamentos": {1: ["TREIN"], 2: ["TREIN"], 3: ["TREIN"]},
    "cipa_brigada": {1: ["CIPA"], 2: ["CIPA"], 3: ["CIPA"]},
    "ocorrencias": {0: ["FISCAL"], 1: ["PERICIA"], 2: ["ACIDENTE", "CAT"]},
}


def riscos_da_resposta(chave: str, indice: int) -> list[str]:
    return list(RISCOS_POR_RESPOSTA.get(chave, {}).get(indice, []))
