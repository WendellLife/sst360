# Roadmap SST360

## MVP

- [x] Empresas com CNAE, grau de risco e trabalhadores
- [x] Gestão de SST com método de 12 etapas
- [x] Documentos técnicos com revisão calculada pela norma
- [x] Treinamentos com reciclagem
- [x] Plano de ação do PGR, com importação por planilha
- [x] Agenda de prazos, vencimentos e prazo da CAT a partir de acidente
- [x] Portal do cliente (plano, documentos, treinamentos, visitas, conversa)
- [x] Site público, diagnóstico de exposição e funil de captação
- [x] Identidade visual Razach

## Próximos

- Exames ocupacionais (ASO) por trabalhador, ligados ao PCMSO
- Cadastro de trabalhadores, funções e GHE
- Questionário psicossocial aplicado pelo portal, com relatório
- Eventos do eSocial (S-2210, S-2220, S-2240) com status de envio
- Indicadores: taxa de frequência e gravidade, afastamentos, FAP
- Testes automatizados do domínio de SST

## Dívidas técnicas

- Migrar `EMAIL_*`/`get_connection()` para `MAILERS` antes do Django 2028 (hoje só emite `RemovedInDjango2028Warning`). Arquivos afetados: `apps/campanhas/regua.py` (`get_connection`, linha ~192), `apps/notificacoes/services.py` (`get_connection`, ~141), `apps/accounts/codigos.py` (`send_mail`) e `config/settings.py` (linhas 195-206, `EMAIL_*`).
