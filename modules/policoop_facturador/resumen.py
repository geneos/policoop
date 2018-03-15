#-*- coding: utf-8 -*-
from trytond.model import ModelView, ModelSQL, fields
import datetime

__all__ = ['ResumenCreacion']

class ResumenCreacion(ModelSQL, ModelView):
    u"Resumen de creación de facturas"
    __name__ = "sigcoop_wizard_ventas.resumen_creacion"

    fecha_comienzo = fields.DateTime(u"Fecha de comienzo")
    cantidad_ventas_creadas = fields.Integer(u"Número de ventas creadas")
    cantidad_facturas_creadas = fields.Integer(u"Número de facturas creadas")
    finalizado = fields.Boolean(u"Finalizado")


    @classmethod
    def default_cantidad_ventas_creadas(cls):
        return 0

    @classmethod
    def default_cantidad_facturas_creadas(cls):
        return 0

    @classmethod
    def default_fecha_comienzo(cls):
        return datetime.datetime.now()

    @classmethod
    def default_finalizado(cls):
        return False
