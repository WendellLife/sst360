"""Leituras do app tarefas_ext vão para a conexão "tarefas"; nada é escrito nem migrado lá."""

from .models import MENSAGEM_SOMENTE_LEITURA, escrita_liberada

ALIAS = "tarefas"
APP = "tarefas_ext"


class RoteadorTarefas:
    def db_for_read(self, model, **hints):
        return ALIAS if model._meta.app_label == APP else None

    def db_for_write(self, model, **hints):
        if model._meta.app_label != APP:
            return None
        if not escrita_liberada():
            # nunca devolve o alias tarefas (nem cai no banco do SST360): escrever aqui é erro de programação
            raise PermissionError(MENSAGEM_SOMENTE_LEITURA)
        return ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        apps = {obj1._meta.app_label, obj2._meta.app_label}
        if APP in apps:
            return apps == {APP}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == APP or db == ALIAS:
            return False
        return None
