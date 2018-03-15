#-*- coding: utf-8 -*-
from trytond.model import ModelView, ModelSQL, fields

class RegistroVenta(ModelSQL, ModelView):
    "Registro Venta"
    __name__ = "sigcoop_wizard_ventas.registro_venta"

    periodo = fields.Many2One('sigcoop_periodo.periodo', 'Periodo')
    #categoria = fields.Many2One('product.price_list', 'Categoria')
    servicio = fields.Many2One('product.category', 'Servicio')
    fecha_vencimiento_1 = fields.Date('1er Fecha de Vencimiento')
    fecha_vencimiento_2 = fields.Date('2da Fecha de Vencimiento')
    ruta = fields.Integer('Ruta')
    fecha_emision_factura = fields.Date('Fecha emision factura')
    consumos = fields.Many2Many('sigcoop_wizard_ventas.registro_venta_consumo', 'registro_id', 'consumo_id', 'Consumos')
    numerocesp = fields.Many2One('account.cesp', 'C.E.S.P.')

class RegistroVentaConsumo(ModelSQL):
    "Registro Venta - Consumo"
    __name__ = "sigcoop_wizard_ventas.registro_venta_consumo"
    registro_id = fields.Many2One('sigcoop_wizard_ventas.registro_venta', 'Registro Venta')
    consumo_id = fields.Many2One('sigcoop_consumos.consumo', 'Consumo')

class RegistroFacturacion(ModelSQL, ModelView):
    "Registro Facturacion"
    __name__ = "sigcoop_wizard_ventas.registro_facturacion"

    suministro = fields.Many2One('sigcoop_suministro.suministro', 'Suministro',readonly=True)
    ruta = fields.Integer('Ruta')
    periodo = fields.Many2One('sigcoop_periodo.periodo', 'Periodo', readonly=True)
    operador = fields.Many2One('res.user', 'Operador', readonly=True)
    estado = fields.Char('Estado', readonly=True)
    codigo = fields.Char('Codigo', readonly=True)
    mensaje = fields.Text('Mensaje', readonly=True)


class RegistroControl(ModelSQL, ModelView):
    "Registro Control"
    __name__ = "sigcoop_wizard_ventas.registro_control"

    controlid = fields.Char('Control ID', readonly=True)
    estado = fields.Boolean('Estado', readonly=True)
    totalreg = fields.Integer('Total Registros', readonly=True)
    posicion = fields.Integer('Posicion', readonly=True)
