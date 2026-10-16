"""Textos padrão da régua. Tudo é editável no painel (Campanhas > Modelos e conteúdo do mês)."""

# Tema e conteúdo útil de cada mês: a mensagem mensal leva algo que o leitor aproveita,
# não só "lembre de nós". Valores de multa: CLT art. 201, Portaria MTE 1.131/2025.
CONTEUDO_DO_MES = {
    1: ("Calendário de SST do ano",
        "Janeiro é o mês de listar o que vence no ano: revisão do PGR (a cada 2 anos, ou 3 com sistema de gestão certificado), "
        "relatório analítico do PCMSO, reciclagens de NR-10, NR-35 e brigada, e o mandato da CIPA. Quem organiza o calendário agora "
        "evita contratar às pressas no meio do ano."),
    2: ("eSocial SST sem pendências",
        "Os eventos de SST do eSocial (S-2210 acidentes, S-2220 exames e S-2240 condições do ambiente) alimentam o PPP eletrônico e o FAP. "
        "Informação atrasada ou divergente vira passivo trabalhista e previdenciário. Vale conferir se o que foi enviado bate com o PGR e o PCMSO."),
    3: ("Riscos psicossociais no PGR",
        "Desde 26/05/2026 o NR-01 exige que os riscos psicossociais (sobrecarga, metas, assédio, jornada) estejam no inventário de riscos do PGR, "
        "com plano de ação. A fiscalização já cobra. Empresas sem avaliação ficam expostas a autuação de R$ 693,11 a R$ 6.935,56 por item."),
    4: ("Abril Verde: prevenção de acidentes",
        "Abril é o mês da campanha de prevenção de acidentes de trabalho, com 28 de abril dedicado às vítimas. Bom momento para revisar o "
        "plano de ação do PGR, os EPIs e os treinamentos obrigatórios, e para mostrar à equipe o que mudou desde o último acidente ou quase acidente."),
    5: ("CIPA e SIPAT",
        "A CIPA tem mandato de um ano e precisa de eleição, posse e treinamento no prazo do NR-05. A SIPAT também é anual. "
        "Planejar com antecedência evita processo eleitoral irregular, que costuma aparecer em fiscalização e reclamação trabalhista."),
    6: ("Ergonomia (NR-17)",
        "O NR-17 pede avaliação ergonômica preliminar dos postos de trabalho e, quando necessário, a análise ergonômica completa. "
        "Lesões por esforço repetitivo e dores lombares estão entre as maiores causas de afastamento, e cada afastamento pesa no FAP."),
    7: ("Treinamentos do segundo semestre",
        "Metade do ano é hora de conferir as reciclagens que vencem até dezembro (NR-10, NR-35, NR-33, NR-12, brigada). "
        "Trabalhador com treinamento vencido não pode executar a atividade, e a empresa responde se houver acidente."),
    8: ("LTCAT, PPP e aposentadoria especial",
        "O LTCAT sustenta o PPP e a contribuição para aposentadoria especial. Laudo desatualizado ou ausente gera autuação previdenciária "
        "e risco de cobrança retroativa. Mudou processo, máquina ou layout? O laudo precisa acompanhar."),
    9: ("FAP do próximo ano",
        "O FAP multiplica a alíquota do RAT entre 0,5 e 2,0, conforme os acidentes e afastamentos dos últimos anos. "
        "Quando o valor do próximo ano é divulgado, há prazo curto para contestar erros. Uma revisão bem feita pode reduzir o custo na folha."),
    10: ("Planejamento e orçamento de SST",
         "Outubro é quando se fecha o orçamento do ano seguinte. Incluir a gestão de SST no planejamento evita contratar com pressa "
         "e permite comparar propostas com calma, olhando escopo, equipe técnica e resultados."),
    11: ("Contestação do FAP e fechamento do ano",
         "Fim de ano é a janela para conferir o FAP divulgado, contestar o que estiver errado e fechar as pendências do plano de ação "
         "antes das férias coletivas. Pendência que entra no ano seguinte costuma virar multa."),
    12: ("O que vence no próximo ano",
         "Dezembro é a hora de olhar para frente: documentos, exames periódicos, treinamentos e contratos que vencem no próximo ano. "
         "Quem sabe as datas consegue negociar melhor, inclusive o contrato de SST."),
}

# Etapa -> (assunto, e-mail, WhatsApp). Campos: {contato} {empresa} {mes_renovacao} {fornecedor}
# {tema} {conteudo} {link_proposta} {remetente} {mes}
MODELOS = {
    "MEN": (
        "{tema} · Universo FX · Life Laboral",
        "Olá, {contato}.\n\n"
        "Todo mês separamos um assunto de SST que costuma pesar no caixa e na fiscalização. O deste mês: {tema}.\n\n"
        "{conteudo}\n\n"
        "Se quiser, fazemos uma leitura rápida da situação da {empresa} sobre esse ponto, sem compromisso.\n\n"
        "Abraço,\n{remetente}",
        "Olá, {contato}! Aqui é {remetente}, da Universo FX · Life Laboral. "
        "Assunto de SST do mês: *{tema}*.\n\n{conteudo}\n\n"
        "Se fizer sentido para a {empresa}, posso mandar uma leitura rápida: {link_proposta}\n\n"
        "(Se não quiser receber estas mensagens, é só responder SAIR.)",
    ),
    "R90": (
        "{empresa}: a renovação de SST de {mes_renovacao} está chegando",
        "Olá, {contato}.\n\n"
        "Pelo que conversamos, o contrato de SST da {empresa} renova em {mes_renovacao}. "
        "Faltam cerca de três meses, o prazo ideal para comparar propostas com calma.\n\n"
        "Gostaríamos de participar da cotação. Montamos a proposta a partir do que a empresa tem hoje "
        "(PGR, PCMSO, LTCAT, treinamentos e eSocial), sem custo.\n\n"
        "Assunto do mês, para aproveitar: {tema}. {conteudo}\n\n"
        "Abraço,\n{remetente}",
        "Olá, {contato}! Aqui é {remetente}, da Universo FX · Life Laboral. "
        "O contrato de SST da {empresa} renova em *{mes_renovacao}*, certo? Faltam uns três meses, "
        "e gostaríamos de participar da cotação. Posso preparar uma proposta sem custo? {link_proposta}\n\n"
        "(Se não quiser receber estas mensagens, é só responder SAIR.)",
    ),
    "R60": (
        "Cotação de SST da {empresa}: podemos enviar a proposta?",
        "Olá, {contato}.\n\n"
        "A renovação do contrato de SST da {empresa} é em {mes_renovacao}, daqui a dois meses. "
        "Para a comparação ser justa, sugerimos receber nossa proposta agora, com tempo de analisar escopo e equipe técnica.\n\n"
        "É só confirmar pelo botão abaixo que o comercial entra em contato para entender o cenário.\n\n"
        "Abraço,\n{remetente}",
        "{contato}, a renovação de SST da {empresa} é em *{mes_renovacao}*, daqui a dois meses. "
        "Podemos enviar nossa proposta para entrar na comparação? Confirma por aqui: {link_proposta}\n\n"
        "(Se não quiser receber estas mensagens, é só responder SAIR.)",
    ),
    "R30": (
        "Última chamada: proposta de SST para a {empresa} antes de {mes_renovacao}",
        "Olá, {contato}.\n\n"
        "O contrato de SST da {empresa} renova no mês que vem. Se a cotação ainda está aberta, "
        "queremos estar nela: enviamos a proposta em poucos dias, com o escopo completo e o valor fechado.\n\n"
        "Confirme pelo botão abaixo e falamos ainda esta semana.\n\n"
        "Abraço,\n{remetente}",
        "{contato}, o contrato de SST da {empresa} renova no mês que vem (*{mes_renovacao}*). "
        "Se a cotação ainda estiver aberta, mandamos a proposta em poucos dias. Confirma aqui: {link_proposta}\n\n"
        "(Se não quiser receber estas mensagens, é só responder SAIR.)",
    ),
    "R0": (
        "{empresa}: ainda dá tempo de comparar a proposta de SST",
        "Olá, {contato}.\n\n"
        "Este é o mês da renovação do contrato de SST da {empresa}. Se a decisão ainda não foi tomada, "
        "conseguimos apresentar uma proposta rápida para comparação.\n\n"
        "E se já renovou, tudo bem: seguimos mandando o assunto de SST do mês e voltamos a falar perto da próxima renovação.\n\n"
        "Abraço,\n{remetente}",
        "{contato}, este é o mês da renovação de SST da {empresa}. Se ainda estiverem decidindo, "
        "mandamos uma proposta rápida para comparar: {link_proposta}\n\n"
        "(Se não quiser receber estas mensagens, é só responder SAIR.)",
    ),
}
