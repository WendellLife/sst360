# SST360

Sistema de **gestão de saúde e segurança do trabalho (SST)** com portal do
cliente e módulo de **captação de clientes**. Operado por Universo FX · Life
Laboral.

A equipe técnica acompanha várias empresas pelo painel interno. Cada cliente
entra num portal próprio e vê só a gestão da sua empresa: documentos, plano de
ação, treinamentos, visitas e prazos.

Derivado do RJ360 (mesma base: CRM, diagnóstico público, portal, relacionamento,
login por código e alertas por e-mail), com o domínio trocado de recuperação
judicial para SST.

## Módulos

**Painel interno**

- Empresas com CNAE, grau de risco (NR-04) e número de trabalhadores.
- **Gestão de SST** por empresa: modelo de acompanhamento (semanal, quinzenal,
  mensal), serviços contratados, responsável técnico, médico coordenador, FAP
  vigente e meta, valor mensal.
- **Método de 12 etapas** (diagnóstico → cultura de segurança), com trilha visual.
- **Documentos técnicos** (PGR, PCMSO, LTCAT, AEP/AET, LI/LP, PCA, PPR,
  psicossocial…): a data de revisão é calculada pela periodicidade da norma
  (PGR 2 anos, 3 com certificação em SGSST) e vira prazo na agenda.
- **Treinamentos** (CIPA, brigada, NR-10/11/12/18/33/35…) com reciclagem
  calculada e turmas planejadas.
- **Plano de ação do PGR** por tipo de risco (inclusive psicossocial), com
  prioridade, responsável na empresa, prazo, custo e andamentos; importação por
  planilha (.xlsx/.csv) com prévia antes de gravar.
- **Agenda de prazos** (normativos, eSocial, contratuais) e tela de
  **Vencimentos** consolidada. Registro de acidente gera o prazo da CAT (S-2210).
- Linha do tempo de visitas, inspeções, auditorias, entregas e envios ao eSocial.

**Portal do cliente** — próximo passo, trilha do método, indicadores, plano de
ação item a item, programas e laudos para baixar, envio de documentos pedidos,
treinamentos, visitas e conversa com a equipe.

**Captação** — site público com serviços, NR-01 (riscos psicossociais) e método;
diagnóstico gratuito de 8 perguntas com nível de exposição; funil de leads com
situação em SST e serviço de interesse.

## Stack

Python 3.11+ · Django 5.2 · PostgreSQL (SQLite em desenvolvimento) · templates
Django + HTMX · WhiteNoise. Identidade visual: a mesma interface do Razach Tarefas Internas (design system
Razach com o tema soft): Archivo e Montserrat servidas pelo próprio servidor,
ícones Lucide locais, barra lateral e barra superior em vidro, cantos
arredondados, status em pastel e temas claro e escuro (escolha guardada no
navegador). Arquivos do design system em `static/razach/` (copiados sem
alteração); a ponte das telas do SST360 para esse visual fica em
`static/css/sst360-razach.css`. Busca global no cabeçalho (`/busca/`, atalho `/`).

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Linux/macOS: cp
```

Banco: `docker compose up -d` (Postgres na porta 5433) ou, sem Docker, no `.env`:
`DATABASE_URL=sqlite:///db.sqlite3`.

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

O `seed_demo` cria três clientes com gestões em etapas diferentes, leads e
diagnósticos. Senha `sst360demo`:

| usuário      | perfil         | vê                               |
|--------------|----------------|----------------------------------|
| `analista`   | equipe interna | tudo (também é admin)            |
| `engenheiro` | equipe interna | tudo                             |
| `cliente`    | portal         | só a Metalúrgica Exemplo         |

- Site público: http://localhost:8000/
- Painel: http://localhost:8000/painel/
- Portal: http://localhost:8000/portal/

## Alertas por e-mail

```bash
python manage.py alertar_prazos
```

Resumo diário por responsável (atrasados, vencem hoje, a vencer). Sem SMTP no
`.env`, as mensagens saem no terminal.

## Login por código (portal)

O cliente entra com e-mail ou celular e recebe um código de 6 dígitos (hash,
10 minutos, uso único, limite de tentativas). Canal em `CANAL_CODIGO_ACESSO`.

## Permissões por módulo

Cada pessoa da equipe interna tem um ou mais módulos, marcados em **Usuários e acessos**
(`/conta/usuarios/`, só para quem tem o módulo Administração):

- **Comercial:** Painel, Indicadores, Funil, Diagnósticos, Leads, Vendas, Campanhas, FAP dos clientes
  e Sistema Tarefas.
- **Técnico:** Gestões de SST, Prazos, Vencimentos, documentos, treinamentos e relacionamento.
- **Administração:** cadastra pessoas e define o acesso de cada uma.

Empresas e a busca abrem para qualquer módulo. O menu só mostra o que a pessoa pode abrir; quem tenta
abrir outra área volta para a própria página inicial com um aviso. Superusuário enxerga tudo. Clientes
do portal entram com código e não têm módulo. A equipe entra com o nome de usuário ou com o e-mail.

## Sistema Tarefas (leitura)

O SST360 e o Razach Tarefas Internas continuam separados, cada um com o seu banco. O SST360 lê do
Tarefas (nunca grava) clientes, contatos, projetos, tarefas e turmas e mostra na área comercial:

- `/comercial/tarefas/`: clientes do Tarefas cruzados pelo CNPJ com empresas e leads do SST360,
  tarefas em aberto e atrasadas, próximas turmas, e o botão **Criar lead** para quem ainda não tem
  cadastro aqui;
- cartão **No sistema Tarefas** no detalhe da empresa e do lead.

Configuração (de preferência com um usuário do banco só com permissão de leitura):

```
TAREFAS_DATABASE_URL=postgres://leitura:senha@servidor:5432/razach_tarefas
TAREFAS_URL=https://tarefas.seu-dominio.com.br
```

Sem `TAREFAS_DATABASE_URL`, a tela explica como ligar. O SST360 não migra nem altera as tabelas do Tarefas.
