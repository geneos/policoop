#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.model import ModelView, ModelSQL, fields
from decimal import Decimal

from celery.contrib import rdb

__all__ = ['Template','Product']
__metaclass__ = PoolMeta

TIPO_CARGO = [('fijo', 'Fijo'), ('variable', 'Variable')]
TIPO_PRODUCTO = [('otros', 'Otros'), ('cargos', 'Cargos'), ('varios', 'Varios')]

class Template(ModelSQL, ModelView):
    "Product Template"
    __name__ = "product.template"

    aplica_iva = fields.Boolean('Aplicar iva')
    aplica_ap = fields.Boolean('Aplicar alumbrado publico')
    aplica_iibb = fields.Boolean('Aplicar ingresos brutos')
    tipo_cargo = fields.Selection(TIPO_CARGO, 'Tipo cargo')
    tipo_producto = fields.Selection(TIPO_PRODUCTO, 'Tipo Producto')
    calcular_por_dia = fields.Boolean('Calcular precio por dia')
    suma_aportes = fields.Boolean('Suma Aportes (solo asociados)')
    forzar_unit_price = fields.Boolean('Forzar Precio Unitario (no toma en cuenta las listas de precios)')
 

class Product:
    __name__ = 'product.product'

    @classmethod
    def get_sale_price(cls, products, quantity=0):
        #rdb.set_trace()
        ret = super(Product, cls).get_sale_price(products, quantity)
        for p in products:
            if not p.suma_aportes:
                if (p.forzar_unit_price is None) or (not p.forzar_unit_price):
                    if p.calcular_por_dia:
                        dias_lectura = Transaction().context.get('dias_lectura')
                        if (dias_lectura):
                            ret[p.id] = ((ret[p.id] / 30) * dias_lectura).quantize(Decimal(str(10.00 ** -4)))
                    elif Transaction().context.get('recargo_fuera_de_termino'):
                        ret[p.id] = Transaction().context.get('recargo_fuera_de_termino')

        return ret
