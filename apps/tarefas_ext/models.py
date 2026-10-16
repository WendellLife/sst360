"""Espelho somente leitura das tabelas do sistema Razach Tarefas Internas.

Cada sistema continua no seu módulo e no seu banco. O SST360 só lê, pela conexão "tarefas"
(TAREFAS_DATABASE_URL), os clientes, contatos, projetos, tarefas e turmas para mostrar na área comercial.
Os models são unmanaged: o SST360 nunca cria, altera ou migra essas tabelas.
"""
from django.db import models


class SomenteLeitura(models.Model):
    class Meta:
        abstract = True
        managed = False

    def save(self, *args, **kwargs):
        raise PermissionError("Os dados do sistema Tarefas são somente leitura no SST360.")

    def delete(self, *args, **kwargs):
        raise PermissionError("Os dados do sistema Tarefas são somente leitura no SST360.")


class Pessoa(SomenteLeitura):
    nome = models.CharField(max_length=120)
    iniciais = models.CharField(max_length=3, blank=True)
    papel = models.CharField(max_length=120, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta(SomenteLeitura.Meta):
        db_table = "equipe_pessoa"

    def __str__(self):
        return self.nome


class Cliente(SomenteLeitura):
    nome = models.CharField(max_length=160)
    cnpj = models.CharField(max_length=14)
    email = models.CharField(max_length=254, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField()

    class Meta(SomenteLeitura.Meta):
        db_table = "clientes_cliente"
        ordering = ["nome", "id"]

    def __str__(self):
        return self.nome

    @property
    def codigo(self):
        return f"CL-{self.pk:03d}" if self.pk else ""


class Contato(SomenteLeitura):
    cliente = models.ForeignKey(Cliente, on_delete=models.DO_NOTHING, db_constraint=False, related_name="contatos")
    nome = models.CharField(max_length=120)
    cargo = models.CharField(max_length=80, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.CharField(max_length=254, blank=True)
    principal = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta(SomenteLeitura.Meta):
        db_table = "clientes_contato"
        ordering = ["-principal", "ordem", "id"]


class Projeto(SomenteLeitura):
    TIPOS = {"ead_presencial": "EAD e presencial", "presencial": "Presencial", "interno": "Interno"}

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20)
    curso = models.BooleanField(default=True)
    etapa_atual = models.CharField(max_length=120, blank=True)
    em_risco = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    cliente = models.ForeignKey(Cliente, null=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="projetos")

    class Meta(SomenteLeitura.Meta):
        db_table = "projetos_projeto"

    def __str__(self):
        return self.nome

    @property
    def tipo_rotulo(self):
        return self.TIPOS.get(self.tipo, self.tipo)


class Tarefa(SomenteLeitura):
    ETAPAS = {"fazer": "A fazer", "andamento": "Em andamento", "revisao": "Em revisão", "feito": "Concluída"}

    numero = models.PositiveIntegerField(null=True)
    titulo = models.CharField(max_length=160)
    etapa = models.CharField(max_length=20)
    prioridade = models.CharField(max_length=10)
    prazo = models.DateField(null=True)
    criada_em = models.DateTimeField()
    concluida_em = models.DateTimeField(null=True)
    cliente = models.ForeignKey(Cliente, null=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="tarefas")
    projeto = models.ForeignKey(Projeto, null=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="tarefas")
    responsavel = models.ForeignKey(Pessoa, null=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="tarefas")

    class Meta(SomenteLeitura.Meta):
        db_table = "tarefas_tarefa"

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"

    @property
    def codigo(self):
        return f"RZ-{self.numero:03d}" if self.numero else ""

    @property
    def etapa_rotulo(self):
        return self.ETAPAS.get(self.etapa, self.etapa)

    @property
    def aberta(self):
        return self.etapa != "feito"


class Turma(SomenteLeitura):
    ESTADOS = {"confirmada": "Confirmada", "agendando": "Agendando", "prevista": "Prevista", "realizada": "Realizada", "cancelada": "Cancelada"}
    TIPOS = {"pratica": "Prática", "presencial": "Presencial"}

    data = models.DateField()
    tipo = models.CharField(max_length=20)
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    pessoas = models.PositiveSmallIntegerField()
    estado = models.CharField(max_length=20)
    local = models.CharField(max_length=120, blank=True)
    cliente = models.ForeignKey(Cliente, null=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="turmas")
    projeto = models.ForeignKey(Projeto, null=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="turmas")

    class Meta(SomenteLeitura.Meta):
        db_table = "agenda_turma"
        ordering = ["data", "hora_inicio"]

    @property
    def estado_rotulo(self):
        return self.ESTADOS.get(self.estado, self.estado)

    @property
    def tipo_rotulo(self):
        return self.TIPOS.get(self.tipo, self.tipo)
