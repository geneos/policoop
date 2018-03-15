#-*- coding: utf-8 -*-
from trytond.model import ModelView, ModelSQL, fields

__all__ = ['ProductoConsumo']

class ProductoConsumo(ModelSQL, ModelView):
    "Producto Consumo"
    __name__ = "sigcoop_wizard_ventas.producto_consumo"

    producto_id = fields.Many2One('product.product', 'Producto')
    tarifa_id = fields.Many2One('product.price_list', 'Tarifa')
    concepto = fields.Many2One('sigcoop_conceptos_consumos.concepto', 'Concepto')
    servicio = fields.Many2One('product.category', 'Servicio')
    cantidad_fija = fields.Boolean('Cantidad fija?')
    cantidad = fields.Integer('Cantidad')
