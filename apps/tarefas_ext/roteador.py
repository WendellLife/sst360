"""Leituras do app tarefas_ext vão para a conexão "tarefas"; nada é escrito nem migrado lá."""

ALIAS = "tarefas"
APP = "tarefas_ext"


class RoteadorTarefas:
    def db_for_read(self, model, **hints):
        return ALIAS if model._meta.app_label == APP else None

    def db_for_write(self, model, **hints):
        return ALIAS if model._meta.app_label == APP else None

    def allow_relation(self, obj1, obj2, **hints):
        apps = {obj1._meta.app_label, obj2._meta.app_label}
        if APP in apps:
            return apps == {APP}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == APP or db == ALIAS:
            return False
        return None
