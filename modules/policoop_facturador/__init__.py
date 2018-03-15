#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .producto_consumo import ProductoConsumo
from .product import Template, Product
from .wizard_ventas import CrearVentasStart, CrearVentas, CrearVentasExito
from .registro_venta import RegistroVenta, RegistroVentaConsumo, RegistroFacturacion, RegistroControl
from .invoice import Invoice
from .resumen import ResumenCreacion
from .autorizar_fe import AutorizarFeStart, AutorizarFe
from .cuenta_corriente_tarifa import CuentaCorrienteTarifa
from .wizard_nc import notacreditoStart, notacreditoExito, notacredito
from .pagar_facturas import PagarFacturasStart, PagarFacturasExito, PagarFacturas


def register():
    Pool.register(
        ProductoConsumo,
        Template,
        Product,
        CrearVentasStart,
        CrearVentasExito,
        RegistroVenta,
        RegistroVentaConsumo,
        RegistroFacturacion,
        Invoice,
        ResumenCreacion,
        RegistroControl,
        AutorizarFeStart,
        CuentaCorrienteTarifa,
        notacreditoStart,
        notacreditoExito,
        PagarFacturasStart,
        PagarFacturasExito,
        module='sigcoop_wizard_ventas', type_='model')

    Pool.register(
        CrearVentas,
        AutorizarFe,
        notacredito,
        PagarFacturas,
        module='sigcoop_wizard_ventas', type_='wizard')
