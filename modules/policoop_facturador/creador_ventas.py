# -*' coding: utf8 -*-

#COMPANY NAME
#Sierra: "COOPERSIVE LTDA."
#Puan: "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN"
#San Manuel: "COOPERATIVA ELECTRICA DE SMA"

import sys
import os
from trytond.pool import Pool
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
from trytond.transaction import Transaction
import datetime
import math
import psycopg2
REQUERIDO = True


conn = psycopg2.connect(host='localhost' ,dbname='arba', user='tryton',
	password='tryton')
cur = conn.cursor()


class CreadorVentas(object):
	def __init__(self, periodo, fecha_emision_factura, fecha_vencimiento_1, fecha_vencimiento_2, ruta, numerocesp, fecha_vencimiento_proxima_factura):
		self.cantidad_ventas_creadas = 0
		self.cantidad_facturas_creadas = 0
		self.periodo = periodo
		self.fecha_emision_factura = fecha_emision_factura
		self.fecha_vencimiento_1 = fecha_vencimiento_1
		self.fecha_vencimiento_2 = fecha_vencimiento_2
		self.ruta = ruta
		self.numerocesp = numerocesp
		self.fecha_vencimiento_proxima_factura = fecha_vencimiento_proxima_factura


	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''FUNCIONES GENERALES '''
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	def calcular_unit_price(self, quantity, product, price_list, customer, dias_lectura=None):
		return product.get_sale_price([product], quantity)[product.id]

	def obtener_kwh_consumidos(self, consumos):
		consumo_neto = 0
		for c in consumos:
			#RESIDENCIALES
			if c.id_suministro.lista_precios.clave == 'T1R':
				if (c.concepto.name == 'Cargo variable'):
					consumo_neto += int(c.consumo_neto)
			#RESIDENCIALES ESTACIONAL
			elif c.id_suministro.lista_precios.clave == 'T1RE':
				if (c.concepto.name == 'Cargo variable'):
					consumo_neto += int(c.consumo_neto)
			#COMERCIALES
			elif ((str(c.id_suministro.lista_precios.clave) == 'T1G') or (str(c.id_suministro.lista_precios.clave) == 'T1Gac')):
				if (c.concepto.name == 'Cargo variable'):
					consumo_neto += int(c.consumo_neto)
			#INDUSTRIALES
			elif ((str(c.id_suministro.lista_precios.clave) == 'T2BT') or (str(c.id_suministro.lista_precios.clave) == 'T3BT') or (str(c.id_suministro.lista_precios.clave) == 'T3MT') or (str(c.id_suministro.lista_precios.clave) == 'T2BTac')):
				if (c.concepto.name == 'Cargo variable Pico') | (c.concepto.name == 'Cargo variable Valle') | (c.concepto.name == 'Cargo variable Resto') | (c.concepto.name == 'Cargo variable Fuera de pico'):
					consumo_neto += int(c.consumo_neto)
			
		return consumo_neto

	def buscar(self, modelo, atributo, valor):
		search = modelo.search([atributo, '=', valor])
		if search:
			return search[0]
		else:
			return None

	def buscar_cliente(self, id_suministro):
		Suministro = Pool().get('sigcoop_suministro.suministro')
		suministro = self.buscar(Suministro, "id", id_suministro)
		if suministro is not None:
			return suministro.usuario_id
		else:
			return None

	def construir_descripcion(self):
		return "Descripcion"

	def get_subtotal_cargos(self, sale, tipo, servicio):
		"""
		Retornamos el subtotal de los cargos
		"""
		subtotal_cargos = 0
		if sale.lines:
			for line in sale.lines:
				if line.servicio == servicio:
					if line.type == 'line' and line.product.tipo_producto == tipo:
						if not line.product.sin_subsidio and not line.product.ocultar_en_impresion:
							subtotal_cargos += Decimal(line.amount).quantize(Decimal(".01"), rounding=ROUND_DOWN)
							
		return subtotal_cargos

	def get_extra_taxes(self, product, suministro_padre, party, servicio_actual, perc_iibb):
		"""
		Retornamos una lista de account.tax con los impuestos que tenemos que calcular
		dinamicamente.
		"""
			
		ret = []
		#La linea actual pertenece al suministro padre
		if suministro_padre.servicio == servicio_actual:
			#El iva se obtiene del suministro
			if product.aplica_iva:
				if suministro_padre.iva:
					ret.append(suministro_padre.iva)
				if suministro_padre.iva_no_categorizado:
					ret.append(suministro_padre.iva_no_categorizado)

				if perc_iibb!=0:
					tmp = Decimal(perc_iibb/Decimal(100))
					
					if suministro_padre.servicio.name=='Energia':
						filtro_per = [('name', '=', 'Percepcion IIBB Energia')]
					elif suministro_padre.servicio.name=='Agua':
						filtro_per = [('name', '=', 'Percepcion IIBB Agua')]
					elif suministro_padre.servicio.name=='Telefonia':
						filtro_per = [('name', '=', 'Percepcion IIBB Telefonia')]
					else:
						filtro_per = [('name', '=', 'Percepcion IIBB Internet')]

					id_imp = Pool().get('account.tax').search(filtro_per)[0]		
					id_imp.rate = Decimal(tmp).quantize(Decimal(".0001"), rounding=ROUND_DOWN)
					id_imp.save()
					ret.append(id_imp)
		else:
			Suministros = Pool().get('sigcoop_suministro.suministro')
			filtro_suministros_hijos = [
				('estado', '=', 'activo'),
				('tipo_servicio', '=', 'hijo'),
				('hijo_de_servicio', '=', suministro_padre),
			]
			suministros_hijos = Suministros.search(filtro_suministros_hijos, order=[('servicio', 'ASC')])
			for suministro_hijo in suministros_hijos:
				#La linea actual pertenece a este suministro hijo
				if suministro_hijo.servicio == servicio_actual:
					#El iva se obtiene del suministro
					if product.aplica_iva:
						if suministro_hijo.iva:
							ret.append(suministro_hijo.iva)
						if suministro_hijo.iva_no_categorizado:
							ret.append(suministro_hijo.iva_no_categorizado)

						if perc_iibb!=0:
							tmp = Decimal(perc_iibb/Decimal(100))
							if suministro_hijo.servicio.name=='Energia':
								filtro_per = [('name', '=', 'Percepcion IIBB Energia')]
							elif suministro_hijo.servicio.name=='Agua':
								filtro_per = [('name', '=', 'Percepcion IIBB Agua')]
							elif suministro_hijo.servicio.name=='Telefonia':
								filtro_per = [('name', '=', 'Percepcion IIBB Telefonia')]
							else:
								filtro_per = [('name', '=', 'Percepcion IIBB Internet')]

							id_imp = Pool().get('account.tax').search(filtro_per)[0]
							id_imp.rate = Decimal(tmp).quantize(Decimal(".0001"), rounding=ROUND_DOWN)
							id_imp.save()
							ret.append(id_imp)

	
		return ret

	def buscar_pos(self, tipo_pos, servicio):
		"""
		Buscamos el punto de venta que vamos a usar para las facturas.
		Este punto de venta deberia tener un PosSequence para cada tipo de factura (ver INVOICE_TYPE_AFIP_CODE
		en account_invoice_ar/invoice.py).
		"""

		Pos = Pool().get('account.pos')
		Company = Pool().get('company.company')
		company = Company(Transaction().context.get('company')).party.name

		if company == "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN":
			#PUAN
			if servicio == 'Energia' or servicio == 'Servicios Sociales Sepelio' or servicio == 'Cable' or servicio == 'Agua' or servicio == 'Servicios Sociales Enfermeria':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 5)])
				return pos[0]
			elif servicio == 'Telefonia' or servicio == 'Internet':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 1)])
				return pos[0]
		elif company == "COOPERATIVA ELECTRICA DE SM" or company == "COOPERATIVA ELECTRICA DE SM " or company == "COOPERATIVA ELECTRICA Y SERVICIOS ANEXOS DE SAN MANUEL LTDA":
			#SAN MANUEL
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 7)])  #7
				return pos[0]
			elif servicio == 'Agua':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 6)])  #6
				return pos[0]
			elif servicio == 'Telefonia' or servicio == 'Internet':
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 8)])  #8
				return pos[0]
		elif company == "COOPERSIVE LTDA.":
			#SIERRA
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 3)])  #3
				
				return pos[0]
			else:
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 4)])  #3
				return pos[0]
		
		elif company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
			#COLINA
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 3)])  #3
				
				return pos[0]
			else:
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 4)])  #3
				return pos[0]
		
		elif company == "Cooperativa Electrica Limitada Norberto de la Riestra":
			#RIESTRA
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 5)])  #5
				
				return pos[0]
			else:
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 6)])  #6
				return pos[0]

		elif company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
			#SAN BLAS
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 2)])  #2
				
				return pos[0]
			else:
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 3)])  #3
				return pos[0]
		elif company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
			#VILLA IRIS
			if servicio == 'Energia' or servicio == 'Agua':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 4)])  #4
				return pos[0]
			elif servicio == 'Cable' or servicio == 'Internet' or servicio == 'Sepelio':
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 8)])  #8
				return pos[0]
			elif servicio == 'Telefonia Celular':
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 7)])  #7
				return pos[0]
			
			else:
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 4)])  #4
				return pos[0]
		
		elif company == "COOPERATIVA ELECTRICA DE CHASICO LIMITADA":
			#CHASICO
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 2)])  #2
				return pos[0]
			elif servicio == 'Cable' or servicio == 'Internet':
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 5)])  #5
				return pos[0]
			elif servicio == 'Telefonia Celular':
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 6)])  #6
				return pos[0]			
			else:
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 5)])  #5
				return pos[0]

		elif company == 'COOPERATIVA DE PROVISION DE SERVICIOS PUBLICOS, VIVIENDA Y SERVICIOS SOCIALES DE COPETONAS LIMITADA':
			#COPETONAS
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 2)])  #2
				return pos[0]			
			elif servicio == 'Telefonia Celular':
				#VER POS ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 3)])  #6
				return pos[0]			
			else:
				#Sueltos (No electrodomesticos)
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 5)])  #5
				return pos[0]
		elif company == "Cooperativa ELECTRICA Ltda. de GOYENA":
			#GOYENA
			if servicio == 'Energia':
				pos = Pos.search([('pos_type', '=', 'manual'), ('number', '=', 4)])  #2
				return pos[0]			
			elif servicio == 'Agua':				
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 4)])  #6
				return pos[0]			
			elif servicio == 'Sepelio':				
				#ELECTRONICO
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 5)])  #6
				return pos[0]			
			else:
				#Sueltos (No electrodomesticos)
				pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 3)])  #5
				return pos[0]

	def asociar_invoice_leyendas(self, invoice):
		"""
		Asociamos las leyendas activas al invoice que se creo desde la factura.
		"""
		leyendas = Pool().get('sigcoop_leyendas.leyenda').search(domain=[('activa', '=', True)])
		invoice.leyendas = leyendas


	def asociar_invoice_consumo(self, invoice, consumos):
		"""
		La factura que creamos tiene que guardar referencias a los consumos
		que se usaron para crearla.
		"""
		for c in consumos:
			c.invoice = invoice
			c.save()

	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''RESUMENES  '''
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

	def get_resumen_creacion(self):
		"""
		Retornamos el resultado de lo creado por este creador
		de ventas.
		"""
		return {
		"cantidad_ventas_creadas" : self.cantidad_ventas_creadas,
		"cantidad_facturas_creadas" : self.cantidad_facturas_creadas
		}

	def actualizar_resumen_creacion(self, resumen_id):
		"""
		Actualizamos el resumen de creacion.
		"""
		resumen = Pool().get('sigcoop_wizard_ventas.resumen_creacion')(resumen_id)
		resumen.cantidad_ventas_creadas += self.cantidad_ventas_creadas
		resumen.cantidad_facturas_creadas += self.cantidad_facturas_creadas
		resumen.save()

	def actualizar_resumen_importacion(self, sale):
		if sale:
			self.cantidad_ventas_creadas += 1
			self.cantidad_facturas_creadas += len(sale.invoices)

	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''DEUDAS  '''
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
 
	def calcular_deuda_factura_actual(self, ultimoconsumo):
		"""
		Calculamos si existen deudas por el pago de la ultima factura
		"""

		#Buscar en account_statement y en deudas, para ver si se marco sin interes
		if ultimoconsumo.estado == '2': #FACTURADO - SIGCOOP ultimoconsumo.
			#Factura SIGCOOP
			StatementLine = Pool().get('account.statement.line')
			statement_line = StatementLine.search([('invoice', '=', ultimoconsumo.invoice)])
			if statement_line:
				#Solo si no clickeo "No calcula interes"
				if not statement_line[0].no_calcula_interes:
					#Calculo la deuda
					if ultimoconsumo.invoice and (ultimoconsumo.invoice.state in ('paid','anulada')): #ultimoconsumo.invoice.state == 'paid':
						Deuda = Pool().get('sigcoop_deudas.deuda')
						if "Telefonia" in ultimoconsumo.periodo.name:
							deuda = Deuda.search([('suministro_id', '=', ultimoconsumo.suministro), ('periodo', '=', ultimoconsumo.periodo), ('saldada', '=', True)])
						else:
							deuda = Deuda.search([('suministro_id', '=', ultimoconsumo.id_suministro), ('periodo', '=', ultimoconsumo.periodo), ('saldada', '=', True)])
						if deuda:
							if deuda[0].fecha_pago_factura is None:
								diaspago = 0
							else:
								#Ver si se pago con 2do Vencimiento o despues del 2do Vencimiento
								if (deuda[0].fecha_pago_factura > ultimoconsumo.invoice.vencimiento_1) and (deuda[0].fecha_pago_factura <= ultimoconsumo.invoice.vencimiento_2):
									#no va recargo
									return Decimal(0)
								else:
									montorecargo_sin_iva = 0
									diaspago = (deuda[0].fecha_pago_factura - ultimoconsumo.invoice.vencimiento_2).days
									if diaspago > 0:
										tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
										#Descontar el valor de la capitalizacion
										capital = 0
										#for line in ultimoconsumo.invoice.lines:
										#    if line.product.suma_aportes:
										#        capital += line.amount
																	
										montorecargo_sin_iva = (float(ultimoconsumo.invoice.total_amount) - float(capital)) *  (float(diaspago) * float(tasa_actual))

									return Decimal(montorecargo_sin_iva)
						
						'''
						if ultimoconsumo.invoice.get_fecha_pago() is None:
							diaspago = 0
						else:
							#Ver si se pago con 2do Vencimiento o despues del 2do Vencimiento
							if (ultimoconsumo.invoice.get_fecha_pago() > ultimoconsumo.invoice.vencimiento_1) and (ultimoconsumo.invoice.get_fecha_pago() <= ultimoconsumo.invoice.vencimiento_2):
								#montorecargo_sin_iva = ultimoconsumo.invoice.recargo_vencimiento
								#return Decimal(montorecargo_sin_iva)
								#no va recargo
								return Decimal(0)
							else:
								montorecargo_sin_iva = 0
								diaspago = (ultimoconsumo.invoice.get_fecha_pago() - ultimoconsumo.invoice.vencimiento_2).days
								if diaspago > 0:
									tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
									#Descontar el valor de la capitalizacion
									capital = 0
									#for line in ultimoconsumo.invoice.lines:
									#    if line.product.suma_aportes:
									#        capital += line.amount
																
									montorecargo_sin_iva = (float(ultimoconsumo.invoice.total_amount) - float(capital)) *  (float(diaspago) * float(tasa_actual))

								return Decimal(montorecargo_sin_iva)
						'''
		elif ultimoconsumo.estado  == '0':
			#Factura SISTEMA ANTERIOR
			Deuda = Pool().get('sigcoop_deudas.deuda')
			deuda = Deuda.search([('suministro_id', '=', ultimoconsumo.id_suministro), ('periodo', '=', ultimoconsumo.periodo), ('saldada', '=', True)])
			diaspago = 0
			if deuda:
				if not deuda[0].interes_especial:
					if (deuda[0].fecha_pago_factura > deuda[0].fecha_vencimiento_factura_vieja) and (deuda[0].fecha_pago_factura <= deuda[0].fecha_vencimiento2_factura_vieja):
						#montorecargo_sin_iva = deuda[0].recargo_vencimiento2
						#return Decimal(montorecargo_sin_iva)
						#no va recargo
						return Decimal(0)
					else:
						montorecargo_sin_iva = 0
						diaspago = (deuda[0].fecha_pago_factura - deuda[0].fecha_vencimiento2_factura_vieja).days
						if diaspago > 0:
							tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
							#Descontar el valor de la capitalizacion (no se puede)
							montorecargo_sin_iva = float(deuda[0].monto_deuda) *  (float(diaspago) * float(tasa_actual))

						return Decimal(montorecargo_sin_iva)
										
		return Decimal(0)


	def calcular_deuda_factura_actual_sin_consumos(self, suministro, periodo_facturacion):
		"""
		Calculamos si existen deudas por el pago de la ultima factura
		"""
		Invoices = Pool().get('account.invoice')
		#Ver estado de factura para filtro
		ultima_invoice = Invoices.search([('suministro', '=', suministro), ('periodo', '=', periodo_facturacion.get_periodo_anterior())], order=[('invoice_date', 'DESC')])
		StatementLine = Pool().get('account.statement.line')
		if ultima_invoice:
			statement_line = StatementLine.search([('invoice', '=', ultima_invoice[0])])
		else:
			statement_line = None

		if statement_line:
			#Solo si no clickeo "No calcula interes"
			if not statement_line[0].no_calcula_interes:
				if ultima_invoice:
					#SIGCOOP
					
					if ultima_invoice[0].state in ('paid','anulada'): #== 'paid':
						Deuda = Pool().get('sigcoop_deudas.deuda')
						deuda = Deuda.search([('suministro_id', '=', suministro), ('periodo', '=', self.periodo.get_periodo_anterior()), ('saldada', '=', True)])
						if deuda:
							if deuda[0].fecha_pago_factura is None:
								diaspago = 0
							else:
								#Ver si se pago con 2do Vencimiento o despues del 2do Vencimiento
								if (deuda[0].fecha_pago_factura > ultima_invoice[0].vencimiento_1) and (deuda[0].fecha_pago_factura <= ultima_invoice[0].vencimiento_2):
									#no va recargo
									return Decimal(0)
								else:
									montorecargo_sin_iva = 0
									diaspago = (deuda[0].fecha_pago_factura - ultima_invoice[0].vencimiento_2).days
									if diaspago > 0:
										tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
										#Descontar el valor de la capitalizacion
										capital = 0
										#for line in ultima_invoice[0].lines:
										#    if line.product.suma_aportes:
										#        capital += line.amount
																
										montorecargo_sin_iva = (float(ultima_invoice[0].total_amount) - float(capital)) *  (float(diaspago) * float(tasa_actual))

									return Decimal(montorecargo_sin_iva)
						

						'''
						if ultima_invoice[0].get_fecha_pago() is None:
							diaspago = 0
						else:
							#Ver si se pago con 2do Vencimiento o despues del 2do Vencimiento
							if (ultima_invoice[0].get_fecha_pago() > ultima_invoice[0].vencimiento_1) and (ultima_invoice[0].get_fecha_pago() <= ultima_invoice[0].vencimiento_2):
								#montorecargo_sin_iva = ultima_invoice[0].recargo_vencimiento
								#return Decimal(montorecargo_sin_iva)
								#no va recargo
								return Decimal(0)
							else:
								montorecargo_sin_iva = 0
								diaspago = (ultima_invoice[0].get_fecha_pago() - ultima_invoice[0].vencimiento_2).days
								if diaspago > 0:
									tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
									#Descontar el valor de la capitalizacion
									capital = 0
									#for line in ultima_invoice[0].lines:
									#    if line.product.suma_aportes:
									#        capital += line.amount
																
									montorecargo_sin_iva = (float(ultima_invoice[0].total_amount) - float(capital)) *  (float(diaspago) * float(tasa_actual))
								
								return Decimal(montorecargo_sin_iva)
						'''
		else:
			#SISTEMA ANTERIOR
			Deuda = Pool().get('sigcoop_deudas.deuda')
			deuda = Deuda.search([('suministro_id', '=', suministro), ('periodo', '=', self.periodo.get_periodo_anterior()), ('saldada', '=', True)])
			diaspago = 0
			if deuda:
				if not deuda[0].interes_especial:
					if (deuda[0].fecha_vencimiento_factura_vieja and deuda[0].fecha_vencimiento2_factura_vieja):
						if (deuda[0].fecha_pago_factura > deuda[0].fecha_vencimiento_factura_vieja) and (deuda[0].fecha_pago_factura <= deuda[0].fecha_vencimiento2_factura_vieja):
							#montorecargo_sin_iva = deuda[0].recargo_vencimiento2
							#return Decimal(montorecargo_sin_iva)
							#no va recargo
							return Decimal(0)
						else:
							return Decimal(0)
					else:
						montorecargo_sin_iva = 0
						diaspago = 0
						if deuda[0].fecha_vencimiento2_factura_vieja:
							diaspago = (deuda[0].fecha_pago_factura - deuda[0].fecha_vencimiento2_factura_vieja).days
						if diaspago > 0:
							tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
							#No tengo la capitalizacion para sacarla del valor
							montorecargo_sin_iva = float(deuda.monto_deuda) *  (float(diaspago) * float(tasa_actual))

						return Decimal(montorecargo_sin_iva)

		return Decimal(0)

	
	def calcular_recargo_vencimiento(self, fecha_creacion, fecha_vencimiento, invoice):
		"""
		Calculamos el recargo que se tiene que aplicar a una factura cuando se paga
		despues del primer vencimiento.
		"""
		Company = Pool().get('company.company')
		company = Company(Transaction().context.get('company')).party.name
		#Descontar el valor de la capitalizacion

		capital = 0
		#for line in invoice.lines:
		#    if line.product.suma_aportes:
		#        capital += line.amount
		
		dias = (fecha_vencimiento - fecha_creacion).days
		if dias > 0:
			tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
			if capital > 0:
				recargo = (float(invoice.total_amount) - float(capital)) *  (float(dias) * float(tasa_actual))
				recargo = Decimal(recargo).quantize(Decimal(".01"), rounding=ROUND_DOWN)
				if company == "Cooperativa Electrica Limitada Norberto de la Riestra":
					#SI ES RIESTRA REDONDEO
					i, d = divmod(recargo, 1)
					dec = int(d * 100)
					ajuste = 0

					if (not dec == 0):
						if (dec >= 1) and (dec <= 49):
							ajuste = Decimal(Decimal(-dec)/100)
						elif (dec >= 51) and (dec <= 99):
							ajuste = 100 - dec
							ajuste = Decimal(Decimal(ajuste)/100)

					recargo += Decimal(ajuste)
								
				return recargo
			else:
				recargo = float(invoice.total_amount) *  (float(dias) * float(tasa_actual))
				recargo = Decimal(recargo).quantize(Decimal(".01"), rounding=ROUND_DOWN)
				if company == "Cooperativa Electrica Limitada Norberto de la Riestra":
					#SI ES RIESTRA REDONDEO
					
					i, d = divmod(recargo, 1)
					dec = int(d * 100)
					ajuste = 0

					if (not dec == 0):
						if (dec >= 1) and (dec <= 49):
							ajuste = Decimal(Decimal(-dec)/100)
						elif (dec >= 51) and (dec <= 99):
							ajuste = 100 - dec
							ajuste = Decimal(Decimal(ajuste)/100)

					recargo += Decimal(ajuste)
				
								
				return recargo
				

		return Decimal(0)


	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''FUNCIONES QUE CREAN LINEAS'''
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	
	#Todas las otras funciones crean con esta funcion
	#Creo la columna servicio, para usar despues en el reporte
	def crear_sale_line(self, amount, product, unit_price, suministro, sequence):
		"""
		Creamos una linea de ventas de acuerdo a los parametros que recibimos.
		"""
		
		SaleLine = Pool().get('sale.line')
		new_line = SaleLine(
				product=product,
				quantity=Decimal(round(amount,2)),
				description=product.name + " - " + str(amount),
				unit=product.default_uom,
				unit_price = Decimal(unit_price),
				servicio = suministro.servicio,
				sequence = sequence,
				suministro=suministro,
				)

		return new_line


	#Lineas que dependen del consumo
	def crear_sale_lines_dependientes_consumo(self, concepto, cantidad_consumida, customer, price_list, suministro):
		"""
		Creamos las lineas de venta que dependen de la cantidad de kw/otros consumidos.
		"""	   				
		
		#Pregunto por tarifa - si es T1RS/T1RS20
		if ((price_list.clave == 'T1RS') or (price_list.clave == 'T1RS20')):
			#Esto es para Cargos Variables, no cargos fijos
			ret = []
			#NO USO ProductoConsumo para TarifaSocial
			#Lo que viene en cantidad_consumida lo uso para ver que cargo corresponde
			if cantidad_consumida <= float(100):
				#Todo al CV1
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 1')])[0]
				up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
				ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
				
			elif cantidad_consumida <= float(150):
				 #Todo al CV2
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 2')])[0]
				up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
				ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))

			elif cantidad_consumida > float(150):
				#150 al CV2
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 2')])[0]
				up = self.calcular_unit_price(150, producto, price_list, customer)
				ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
				if cantidad_consumida <= float(200):
					#Resto al CV3
					resto = cantidad_consumida - 150					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 3')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
												
				elif cantidad_consumida <= float(300):					
					#Resto al CV4
					resto = cantidad_consumida - 150
					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
				
				elif cantidad_consumida <= float(400):
					#150 al CV4
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV5
					resto = cantidad_consumida - 300
					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 5')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
					
				elif cantidad_consumida <= float(500):
					#150 al CV4
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV6
					resto = cantidad_consumida - 300
	
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 6')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))				
				
				elif cantidad_consumida <= float(700):
					#150 al CV4
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV7
					resto = cantidad_consumida - 300
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 7')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
								
				elif cantidad_consumida <= float(1400):
					#150 al CV4
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV8
					resto = cantidad_consumida - 300					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 8')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
									
				elif cantidad_consumida > float(1400):
					#150 al CV4
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV9
					resto = cantidad_consumida - 300					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 9')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))                                                        					
	
			#Agregar para cargos fijos - escalonados - Cargo Fijo T1RS				
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])

			for producto_consumo in producto_consumo_list:
				cantidad = producto_consumo.cantidad_fija and producto_consumo.cantidad or cantidad_consumida
				up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)					
				if (cantidad == 0):
					ret.append(self.crear_sale_line(1, producto_consumo.producto_id, up, suministro, 3))
				else:
					ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))
					
									
		elif ((price_list.clave == 'T4S') or (price_list.clave == 'T4S20')):
														
			#Esto es para Cargos Variables, no cargos fijos
			ret = []

			#Cargo Perdida Transformador
			if suministro.perdida_transformador:
				perdida = int(suministro.perdida_transformador.perdida)*(suministro.porcentaje_sobre_transformador/100)
			else:
				perdida = 0

			cantidad_consumida = cantidad_consumida + perdida
			
			#NO USO ProductoConsumo para TarifaSocial
			#Lo que viene en cantidad_consumida lo uso para ver que cargo corresponde
			if cantidad_consumida <= float(150):
				#Todo al CV1
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 1')])[0]
				up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
				ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
			
			elif cantidad_consumida > float(150):
				#150 al CV1
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 1')])[0]
				up = self.calcular_unit_price(150, producto, price_list, customer)
				ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
				if cantidad_consumida <= float(300):
					#Resto al CV2
					resto = cantidad_consumida - 150
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
															
				elif cantidad_consumida <= float(500):
					#150 al CV2
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV3
					resto = cantidad_consumida - 300
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 3')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
				
				elif cantidad_consumida <= float(700):
					#150 al CV2
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV4
					resto = cantidad_consumida - 300
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 4')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
									
				elif cantidad_consumida <= float(1400):
					#150 al CV2
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV5
					resto = cantidad_consumida - 300
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 5')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))

				
				elif cantidad_consumida > float(1400):
					#150 al CV2
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2')])[0]
					up = self.calcular_unit_price(150, producto, price_list, customer)
					ret.append(self.crear_sale_line(150, producto, up, suministro, 3))
				
					#Resto al CV6
					resto = cantidad_consumida - 300
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 6')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
					
			#Agregar para cargos fijos - escalonados - Cargo Fijo T4s				
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])

			for producto_consumo in producto_consumo_list:
				cantidad = producto_consumo.cantidad_fija and producto_consumo.cantidad or cantidad_consumida
				up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)					
				if (cantidad == 0):
					ret.append(self.crear_sale_line(1, producto_consumo.producto_id, up, suministro, 3))
				else:
					ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))
		
		
		#ELECTRO
		elif ((price_list.clave == 'T1RSELE600') or (price_list.clave == 'T1RSELE600E') or (price_list.clave == 'T1RSELE')):
			#Esto es para Cargos Variables, no cargos fijos
			ret = []
			#NO USO ProductoConsumo para TarifaSocial
			#Lo que viene en cantidad_consumida lo uso para ver que cargo corresponde
			if cantidad_consumida <= float(600):
				#T1RSELE
				if cantidad_consumida <= float(100):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 1')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
				elif cantidad_consumida <= float(200):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 2a')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
				elif cantidad_consumida <= float(400):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 2b - Exc')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
				elif cantidad_consumida <= float(500):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 3 - Exc')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
				elif cantidad_consumida <= float(600):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4 - Exc')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))

			elif cantidad_consumida > float(600):
				#600 al CV2
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 2a')])[0]
				up = self.calcular_unit_price(600, producto, price_list, customer)
				ret.append(self.crear_sale_line(600, producto, up, suministro, 3))
				
				if cantidad_consumida <= float(700):
					#Resto al CV2b
					resto = cantidad_consumida - 600					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 2b - Exc')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
												
				elif cantidad_consumida <= float(1050) and (price_list.clave == 'T1RSELE600'):
					resto = cantidad_consumida - 600					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 3 - Exc')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))

				elif cantidad_consumida <= float(1400):
					#Resto al CV3
					resto = cantidad_consumida - 600					
					
					if (price_list.clave == 'T1RSELE600'):
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
					elif (price_list.clave == 'T1RSELE600E'): 								
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 3 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))					

				elif cantidad_consumida > float(1400):
					
					resto = cantidad_consumida - 600

					if (price_list.clave == 'T1RSELE600'):
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4b - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
					elif (price_list.clave == 'T1RSELE600E'): 								
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T1RS 4 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
																																																																		
			#Agregar para cargos fijos - escalonados - Cargo Fijo T1RS				
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])

			for producto_consumo in producto_consumo_list:
				cantidad = producto_consumo.cantidad_fija and producto_consumo.cantidad or cantidad_consumida
				up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)					
				if (cantidad == 0):
					ret.append(self.crear_sale_line(1, producto_consumo.producto_id, up, suministro, 3))
				else:
					ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))

		elif ((price_list.clave == 'T4') or (price_list.clave == 'T420') or (price_list.clave == 'T4NR')):
			ret = []
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])
			
			for producto_consumo in producto_consumo_list:
				#CV T4
				#CPT T4
				#RES
				#ICM
				#DCM

				#Obtengo Perdida
				if suministro.perdida_transformador:
					perdida = int(suministro.perdida_transformador.perdida)*(suministro.porcentaje_sobre_transformador/100)
				else:
					perdida = 0

				up = self.calcular_unit_price(cantidad_consumida+perdida, producto_consumo.producto_id, price_list, customer)
				ret.append(self.crear_sale_line(cantidad_consumida+perdida, producto_consumo.producto_id, up, suministro, 3))

			
		#ELECTRO RURAL
		elif ((price_list.clave == 'T4SELE600') or (price_list.clave == 'T4SELE600E') or (price_list.clave == 'T4SELE')):
			#Esto es para Cargos Variables, no cargos fijos
			ret = []
			#NO USO ProductoConsumo para TarifaSocial
			#Lo que viene en cantidad_consumida lo uso para ver que cargo corresponde
			if cantidad_consumida <= float(600):
				#T1RSELE
				if cantidad_consumida <= float(500):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 1')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))
				elif cantidad_consumida <= float(600):
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2a')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))

			elif cantidad_consumida > float(600):
				#600 al CV2
				producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2a')])[0]
				up = self.calcular_unit_price(600, producto, price_list, customer)
				ret.append(self.crear_sale_line(600, producto, up, suministro, 3))
				
				if cantidad_consumida <= float(700):
					#Resto al CV2b
					resto = cantidad_consumida - 600					
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2b - Exc')])[0]
					up = self.calcular_unit_price(resto, producto, price_list, customer)
					ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
												
				elif cantidad_consumida <= float(1050) and (price_list.clave == 'T4SELE600'):
					resto = cantidad_consumida - 600
					producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 2c - Exc')])[0]
					up = self.calcular_unit_price(cantidad_consumida, producto, price_list, customer)
					ret.append(self.crear_sale_line(cantidad_consumida, producto, up, suministro, 3))

				elif cantidad_consumida <= float(1400):
					#Resto al CV3
					resto = cantidad_consumida - 600
					if (price_list.clave == 'T4SELE600'):
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 3 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
					elif (price_list.clave == 'T4SELE600E'):
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 3 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))
										
				elif cantidad_consumida > float(1400):
					
					resto = cantidad_consumida - 600														
					if (price_list.clave == 'T4SELE600'):						
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 4 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))						
					elif (price_list.clave == 'T4SELE600E'):
						producto = Pool().get('product.product').search([('name','=','Cargo Variable T4S 4 - Exc')])[0]
						up = self.calcular_unit_price(resto, producto, price_list, customer)
						ret.append(self.crear_sale_line(resto, producto, up, suministro, 3))

																																
			#Agregar para cargos fijos - escalonados - Cargo Fijo T1RS				
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])

			for producto_consumo in producto_consumo_list:
				cantidad = producto_consumo.cantidad_fija and producto_consumo.cantidad or cantidad_consumida
				up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)					
				if (cantidad == 0):
					ret.append(self.crear_sale_line(1, producto_consumo.producto_id, up, suministro, 3))
				else:
					ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))

		else:
			ret = []
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])

			for producto_consumo in producto_consumo_list:
				cantidad = producto_consumo.cantidad_fija and producto_consumo.cantidad or cantidad_consumida
				Company = Pool().get('company.company')
				company = Company(Transaction().context.get('company')).party.name
					
				if suministro.servicio.name == 'Agua' and company == "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN":
					#PUAN
					cantidad = cantidad_consumida
					if int(cantidad) > 10:
						total_variable = 0
						
						if int(cantidad) <= 15:
							#Entre 11 y 15
							extra = int(cantidad) - 10
																		
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(cantidad) < int(producto_en_pricelist.quantity):
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
										
							total_variable += up * extra
						
						elif int(cantidad) > 15 and int(cantidad) <= 25:
							#Entre 15 y 25
							#Sumo los 5 de 10-15
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 15:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 5
							#Sumo los extras entre 15 y 25
							extra = int(cantidad) - 15
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(cantidad) < int(producto_en_pricelist.quantity):
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
																												
							total_variable += up * extra

						elif int(cantidad) > 25 and int(cantidad) <= 40:
							#Sumo los 5 de 10-15
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 15:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 5
							#Sumo los 10 de 15-25
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 25:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 10
							#Sumo los extras entre 25 y 40
							extra = int(cantidad) - 25
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(cantidad) < int(producto_en_pricelist.quantity):
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
																												
							total_variable += up * extra
						elif int(cantidad) > 40 and int(cantidad) <= 60:
							#Sumo los 5 de 10-15
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 15:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 5
							#Sumo los 10 de 15-25
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 25:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 10
							#Sumo los 15 de 25-40
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 40:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 15
							#Sumo los extras entre 40 y 60
							extra = int(cantidad) - 40
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(cantidad) < int(producto_en_pricelist.quantity):
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
																												
							total_variable += up * extra
						elif int(cantidad) > 60:
							#Sumo los 5 de 10-15
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 15:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 5
							#Sumo los 10 de 15-25
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 25:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 10
							#Sumo los 15 de 25-40
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 40:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 15
							#Sumo los 20 de 40-60
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 60:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 20
							#Sumo los extras mas de 60
							extra = int(cantidad) - 60
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(cantidad) < int(producto_en_pricelist.quantity):
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
																												
							total_variable += up * extra

						
						#El precio unitario es el total variable dividido la cantidad
						up = Decimal(total_variable)/Decimal(cantidad)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						uom = producto_consumo.producto_id.default_uom
						ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))
				
				elif suministro.servicio.name == 'Agua' and company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
					#AGUA VILLA IRIS
										
					cantidad = cantidad_consumida
					if int(cantidad) > 9:
						total_variable = 0
						
						if int(cantidad) <= 18:
							#Entre 10 y 18
							extra = int(cantidad) - 9
																		
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 9:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
										
							total_variable += up * extra

							uom = producto_consumo.producto_id.default_uom
							ret.append(self.crear_sale_line(extra, producto_consumo.producto_id, up, suministro, 3))

						
						elif int(cantidad) > 18:
							#Sumo los 8 de 10-17
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 9:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							total_variable += up * 9
							
							uom = producto_consumo.producto_id.default_uom
							ret.append(self.crear_sale_line(9 , producto_consumo.producto_id, up, suministro, 3))


							#Sumo los extras mas de 17
							extra = int(cantidad) - 18
							up = 0
							for producto_en_pricelist in price_list.lines:
								#Busco el producto dentro de la pricelist
								if up == 0:
									if producto_en_pricelist.product == producto_consumo.producto_id:
										if int(producto_en_pricelist.quantity) == 18:
											up = Decimal(producto_en_pricelist.formula)
											up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
																												
							total_variable += up * extra
							
							uom = producto_consumo.producto_id.default_uom
							ret.append(self.crear_sale_line(extra, producto_consumo.producto_id, up, suministro, 3))

																												
				else: #ENERGIA
					
					#RES 206/13 y Tarifa Industrial: Por potencia fuera de pico
					#Potencia Pico, si es menor a contratada = la contratada
					#Potencia Pico, si es mayor a contratada = contratada + exceso
					#Potencia Fuera de Pico, si es menor a contratada = la contratada
					##Potencia Fuera de Pico, si es mayor a contratada = la contratada + exceso
				
																											
					if producto_consumo.concepto.potencia_pico and (producto_consumo.producto_id.name[:14] == 'Cargo Potencia'):
						if suministro.potencia_contratada_pico:
							if int(cantidad) > int(suministro.potencia_contratada_pico):
								#va la contratada
								up = self.calcular_unit_price(suministro.potencia_contratada_pico, producto_consumo.producto_id, price_list, customer)
								ret.append(self.crear_sale_line(suministro.potencia_contratada_pico, producto_consumo.producto_id, up, suministro, 3))
								#Mas el exceso
								cantidad_exceso = 0
								if suministro.lista_precios.clave == 'T2BT':
									cantidad_exceso = cantidad - suministro.potencia_contratada_pico
									cantidad_exceso = abs(cantidad_exceso)
									producto_exceso = Pool().get('product.product').search([('name','=','Recargo por Exceso de Potencia en Pico T2BT')])[0]
									#Doy de alta el Exceso
									up = self.calcular_unit_price(cantidad_exceso, producto_exceso, price_list, customer)
									ret.append(self.crear_sale_line(cantidad_exceso, producto_exceso, up, suministro, 4))
								elif suministro.lista_precios.clave == 'T3BT':
									cantidad_exceso = cantidad - suministro.potencia_contratada_pico
									cantidad_exceso = abs(cantidad_exceso)
									producto_exceso = Pool().get('product.product').search([('name','=','Recargo por Exceso de Potencia Pico T3BT')])[0]
									#Doy de alta el Exceso
									up = self.calcular_unit_price(cantidad_exceso, producto_exceso, price_list, customer)
									ret.append(self.crear_sale_line(cantidad_exceso, producto_exceso, up, suministro, 4))
								elif suministro.lista_precios.clave == 'T3MT':
									cantidad_exceso = cantidad - suministro.potencia_contratada_pico
									cantidad_exceso = abs(cantidad_exceso)
									producto_exceso = Pool().get('product.product').search([('name','=','Recargo por Exceso de Potencia Pico T3MT')])[0]
									#Doy de alta el Exceso
									up = self.calcular_unit_price(cantidad_exceso, producto_exceso, price_list, customer)
									ret.append(self.crear_sale_line(cantidad_exceso, producto_exceso, up, suministro, 4))
							else:
								#si es menor, va la potencia contratada
								up = self.calcular_unit_price(suministro.potencia_contratada_pico, producto_consumo.producto_id, price_list, customer)
								ret.append(self.crear_sale_line(suministro.potencia_contratada_pico, producto_consumo.producto_id, up, suministro, 4))
						else:
							#Va todo en Potencia Pico - entero
							up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)
							ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 4))
					
					elif producto_consumo.concepto.potencia_fuera_de_pico and producto_consumo.producto_id.name[:14] == 'Cargo Potencia':
						if suministro.potencia_contratada_fuera_pico:
							if int(cantidad) > int(suministro.potencia_contratada_fuera_pico):
								#va la contratada
								up = self.calcular_unit_price(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, price_list, customer)
								ret.append(self.crear_sale_line(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, up, suministro, 5))
								#Mas el exceso
								cantidad_exceso = 0
								if suministro.lista_precios.clave == 'T2BT':
									cantidad_exceso = cantidad - suministro.potencia_contratada_fuera_pico
									cantidad_exceso = abs(cantidad_exceso)
									producto_exceso = Pool().get('product.product').search([('name','=','Recargo por Exceso de Potencia Fuera Pico T2BT')])[0]
									#Doy de alta el Exceso
									up = self.calcular_unit_price(int(cantidad_exceso), producto_exceso, price_list, customer)
									ret.append(self.crear_sale_line(cantidad_exceso, producto_exceso, up, suministro, 5))
								elif suministro.lista_precios.clave == 'T3BT':
									cantidad_exceso = cantidad - suministro.potencia_contratada_fuera_pico
									cantidad_exceso = abs(cantidad_exceso)
									producto_exceso = Pool().get('product.product').search([('name','=','Recargo por Exceso de Potencia Resto T3BT')])[0]
									#Doy de alta el Exceso
									up = self.calcular_unit_price(cantidad_exceso, producto_exceso, price_list, customer)
									ret.append(self.crear_sale_line(cantidad_exceso, producto_exceso, up, suministro, 5))
								elif suministro.lista_precios.clave == 'T3MT':
									#rdb.set_trace()
									cantidad_exceso = cantidad - suministro.potencia_contratada_fuera_pico
									cantidad_exceso = abs(cantidad_exceso)
									producto_exceso = Pool().get('product.product').search([('name','=','Recargo por Exceso de Potencia Resto T3MT')])[0]
									#Doy de alta el Exceso
									up = self.calcular_unit_price(cantidad_exceso, producto_exceso, price_list, customer)
									ret.append(self.crear_sale_line(cantidad_exceso, producto_exceso, up, suministro, 5))
							else:
								#si es menor, va la potencia contratada
								up = self.calcular_unit_price(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, price_list, customer)
								ret.append(self.crear_sale_line(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, up, suministro, 5))
						else:
							#Va todo en Potencia Fuera de Pico - entero
							up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)
							ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 5))
										
					elif (producto_consumo.producto_id.template.name == 'RES MI 206/13 T2BT') or (producto_consumo.producto_id.template.name == 'RES MI 206/13 T3BT') or (producto_consumo.producto_id.template.name == 'RES MI 206/13 T3MT'):
						#Recorro de nuevo los productos-consumos para multiplicar por eso
						Conceptos = Pool().get('sigcoop_conceptos_consumos.concepto')
						concepto_potencia_fuera_de_pico = Conceptos.search([('potencia_fuera_de_pico', '=', True)])
						Consumos = Pool().get('sigcoop_consumos.consumo')
				
						filtro_consumo = [
									#('estado', '=', '1'), #Estado 1 es facturable.
									('periodo', '=', self.periodo),
									('id_suministro', '=', suministro),
									('concepto', '=', concepto_potencia_fuera_de_pico[0])
									]
						
						consumos_actuales = Consumos.search([filtro_consumo])
						if consumos_actuales:
							if int(consumos_actuales[0].consumo_neto) < int(suministro.potencia_contratada_fuera_pico):
								potencia_fuera_de_pico = suministro.potencia_contratada_fuera_pico
							else:
								potencia_fuera_de_pico = consumos_actuales[0].consumo_neto
						else:
							potencia_fuera_de_pico = 1

						up = potencia_fuera_de_pico * 32
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						cantidad = potencia_fuera_de_pico
						ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 6))
					
					
					elif  (producto_consumo.producto_id.name[:16] == 'DCM - T2BT - Pot') or (producto_consumo.producto_id.name[:16] == 'DCM - T3BT - Pot'):
						#Es DCM de Potencia, el consumo se maneja igual que en el caso de potencia, pero sin excesos
						if producto_consumo.concepto.potencia_pico:
							if suministro.potencia_contratada_pico:
								if int(cantidad) > int(suministro.potencia_contratada_pico):
									#va la cantidad
									up = self.calcular_unit_price(suministro.potencia_contratada_pico, producto_consumo.producto_id, price_list, customer)
									ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))
								else:
									#si es menor, va la potencia contratada
									up = self.calcular_unit_price(suministro.potencia_contratada_pico, producto_consumo.producto_id, price_list, customer)
									ret.append(self.crear_sale_line(suministro.potencia_contratada_pico, producto_consumo.producto_id, up, suministro, 4))
							else:
								#Va la cantidad
								up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)
								ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 4))
					
						elif producto_consumo.concepto.potencia_fuera_de_pico:
							if suministro.potencia_contratada_fuera_pico:
								if int(cantidad) > int(suministro.potencia_contratada_fuera_pico):
									#va la cantidad
									up = self.calcular_unit_price(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, price_list, customer)
									ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 5))
								else:
									#si es menor, va la potencia contratada
									up = self.calcular_unit_price(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, price_list, customer)
									ret.append(self.crear_sale_line(suministro.potencia_contratada_fuera_pico, producto_consumo.producto_id, up, suministro, 5))
							else:
								#Va la cantidad
								up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)
								ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 5))
					
					else:
						
						#COSENO DE FI ENTRARIA ACA (viene el numero, y el up es 0.096)
						up = self.calcular_unit_price(cantidad, producto_consumo.producto_id, price_list, customer)
						
						if company == "COOPERATIVA ELECTRICA DE SM":
							if (cantidad == 0) and ((producto_consumo.producto_id.template.name[:13] == 'Resolucion MI') or (producto_consumo.producto_id.template.name[:6] == 'RES MI') or (producto_consumo.producto_id.template.name == 'Cargo Fijo Agua') or (producto_consumo.producto_id.template.name[:10] == 'Cargo Fijo')):
								ret.append(self.crear_sale_line(1, producto_consumo.producto_id, up, suministro, 3))
							else:
								ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))
						
						else:
							if (cantidad == 0) and ((producto_consumo.producto_id.template.name[:13] == 'Resolucion MI') or (producto_consumo.producto_id.template.name[:6] == 'RES MI') or (producto_consumo.producto_id.template.name[:10] == 'Cargo Fijo')):
								ret.append(self.crear_sale_line(1, producto_consumo.producto_id, up, suministro, 3))
							else:
								ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro, 3))
						

		return ret


	 #Lineas que dependen del consumo
	def crear_sale_lines_dependientes_consumo_telefonico(self, concepto, minutos, valor, customer, suministro):
		"""
		Creamos las lineas de venta que dependen de la cantidad de minutos consumidos.
		"""

		ret = []
		ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
		producto_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('servicio', '=', suministro.servicio)])
		
		cantidad = minutos
		producto = producto_consumo[0].producto_id
 

		SaleLine = Pool().get('sale.line')
		new_line = SaleLine(
			product=producto,
			#quantity=Decimal(round(cantidad,2)),
			quantity=Decimal(1),
			description=producto.name,
			unit=producto.default_uom,
			#unit_price = Decimal(valor/minutos).quantize(Decimal(".01"), rounding=ROUND_DOWN) ,
			unit_price = Decimal(valor).quantize(Decimal(".01"), rounding=ROUND_DOWN) ,
			servicio = suministro.servicio,
		)

		ret.append(new_line)

		return ret

		'''ANTES
		producto_consumo_list = ProductoConsumo.search([('concepto', '=', concepto), ('servicio', '=', suministro.servicio)])
		for producto_consumo in producto_consumo_list:
			cantidad = minutos
			up = Decimal(valor/minutos).quantize(Decimal(".01"), rounding=ROUND_UP)
			ret.append(self.crear_sale_line(cantidad, producto_consumo.producto_id, up, suministro))

		return ret
		'''

	 #Lineas que dependen del consumo
	def crear_sale_lines_dependientes_consumo_celular(self, concepto, valor, customer, suministro):
		"""
		Creamos las lineas de venta que dependen de la cantidad de minutos consumidos.
		"""

		ret = []
		ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
		producto_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('servicio', '=', suministro.servicio)])
		
		cantidad = 1
		producto = producto_consumo[0].producto_id
 

		SaleLine = Pool().get('sale.line')
		new_line = SaleLine(
			product=producto,
			#quantity=Decimal(round(cantidad,2)),
			quantity=Decimal(1),
			description=producto.name,
			unit=producto.default_uom,
			#unit_price = Decimal(valor/minutos).quantize(Decimal(".01"), rounding=ROUND_DOWN) ,
			unit_price = Decimal(valor).quantize(Decimal(".01"), rounding=ROUND_DOWN) ,
			servicio = suministro.servicio,
		)

		ret.append(new_line)

		return ret
	

	#Todos los cargos fijos de la pricelist (FIJO +  CARGOS)
	#T1G Elijo cargo fijo segun consumo (excepcion)
	def crear_sale_lines_independientes_consumo(self, party, price_list, dias_de_consumo, consumos, suministro):
		ret = []
		#Obtenemos los productos que son cargos fijos, de la lista de precios que recibimos como parametro
		filtro_producto = lambda x: (x.product.tipo_cargo == 'fijo' and x.product.tipo_producto == 'cargos')
		productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
		for producto in productos:
			#Dos cargos fijos en el caso de T1G
			if str(price_list.clave) == 'T1G':
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				if kwh_consumidos <= 1000:
					if producto.name == 'Cargo Fijo T1GBC':
						up = self.calcular_unit_price(1, producto, price_list, party)
						ret.append(
							self.crear_sale_line(1, producto, up, suministro, 1)
						)
				if kwh_consumidos > 1000:
					if producto.name == 'Cargo Fijo T1GAC':
						up = self.calcular_unit_price(1, producto, price_list, party)
						ret.append(
							self.crear_sale_line(1, producto, up, suministro, 1)
						)
			else:
				#UN SOLO CARGO FIJO
				#Para Hijos: busco en la propia pricelist
				if suministro.servicio.name == 'Agua' or suministro.servicio.name == 'Cable' or suministro.servicio.name == 'Internet' or suministro.servicio.name == 'Servicios Sociales Enfermeria' or suministro.servicio.name == 'Servicios Sociales Sepelio' or suministro.servicio.name == 'Bomberos' or suministro.servicio.name == 'Club' or suministro.servicio.name == 'Comedor' or suministro.servicio.name == 'Unidad Sanitaria' or suministro.servicio.name == 'Sepelio':
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							up = Decimal(producto_en_pricelist.formula)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
				else:
					#Padres
					up = self.calcular_unit_price(1, producto, price_list, party)
							
			
				#Le agrego la sequence = 1 para cargos fijos
				ret.append(
					self.crear_sale_line(1, producto, up, suministro, 1)
				)
		return ret

	#Las lineas que van despues de impuestos (Fijo-Varios) - EJEMPLO: Decr. P Ejec Pcial.
	#Puede ir capitalizacion fija
	def crear_sale_lines_sin_impuestos(self, party, price_list, sale, suministro=None):
		ret = []

		
		filtro_producto = lambda x: (x.product.tipo_cargo == 'fijo' and x.product.tipo_producto == 'varios')
		productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
		for producto in productos:
			#hay que dar de alta la suscripcion si hay cuotas de capital
			#Esto no pasa en PUAN, porque la capitalizacion es variable, no fija
			'''
			if producto.suma_aportes:
				up = self.calcular_unit_price(1, producto, party, price_list)
				ret.append(self.crear_sale_line(1, producto, up, suministro))
				#Doy de alta la suscripcion (rango)
				Rango = Pool().get('sigcoop_usuario.rango')
				rango = Rango()
				rango.cantidad = up * 1 #Cantidad*UPrice
				rango.asociado = party
				rango.fecha = datetime.date.today()
				rango.save()
			else:
				#VER NOMBRES CONCEPTO PLAN PAGO (Nro de Cuota) / Servicio
				if not (producto.name == "Cuota de Plan de Pago"):
					if not (producto.suma_aportes):
						up = self.calcular_unit_price(1, producto, party, price_list)
						ret.append(self.crear_sale_line(1, producto, up, suministro))
			'''
			#PUAN: No agregar Alumbrado publico cargo fijo porque se agregga en funcion especifica
			if not (producto.name == "Cuota de Plan de Pago") and not (producto.name[:17] == 'Alumbrado Publico') and not (producto.name[:14] == 'Tasa Municipal'):
					if not (producto.suma_aportes):
						up = self.calcular_unit_price(1, producto, party, price_list)
						ret.append(self.crear_sale_line(1, producto, up, suministro, 20))

		return ret

	#Las lineas que van despues de impuestos (Variable-Varios) - EJEMPLO: Descuento Patagonico en San Blas
	#No suman aportes
	def crear_sale_lines_sin_impuestos_variables(self, party, price_list, sale, suministro=None):
		ret = []
	
		
		filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == False)
		productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
		subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			
		for producto in productos:
			up = 0
			for producto_en_pricelist in price_list.lines:
				#Busco el producto dentro de la pricelist
				if producto_en_pricelist.product == producto:
					up = float(producto_en_pricelist.formula) * float(subtotal_cargos)
					up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

					ret.append(self.crear_sale_line(1, producto, up, suministro, 18))
			
		return ret

	#VARIOS/VARIABLES/SUMA APORTES
	def crear_sale_line_retencion_capitalizacion(self, party, price_list, sale, consumos, suministro=None):
	
		ret=[]
		#Obtenemos los productos que son varios-variables y suman aportes, de la lista de precios que recibimos como parametro
		
		Company = Pool().get('company.company')
		company = Company(Transaction().context.get('company')).party.name
		
		if (company == "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN") or (company == "COOPERATIVA ELECTRICA DE SM") or (company == "COOPERATIVA ELECTRICA DE SM ") or (company == "COOPERATIVA ELECTRICA Y SERVICIOS ANEXOS DE SAN MANUEL LTDA"):
			#PUAN y SAN MANUEL
			#Producto: Capitalizacion % (deberia haber uno asi por pricelist nada mas)
			filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
			productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
			subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			for producto in productos:
				#UP especial, me trae un porcentaje, no el precio unitario: EJEMPLO 0,22 (22%)
				up = 0
				
				for producto_en_pricelist in price_list.lines:
					#Busco el producto dentro de la pricelist
					if producto_en_pricelist.product == producto:
						up = float(producto_en_pricelist.formula) * float(subtotal_cargos)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
						
				if (party.asociado):
					#CUOTA: El precio es el % del subtotal cargos
					#Doy de alta la suscripcion (rango)
					Rango = Pool().get('sigcoop_usuario.rango')
					rango = Rango()
					rango.cantidad = up
					rango.asociado = party
					rango.fecha = datetime.date.today()
					rango.save()
																						
				ret.append(self.crear_sale_line(1, producto, up, suministro, 18))
		
		elif company == "COOPERSIVE LTDA.":
			#SIERRA - SOLO ENERGIA
			#CAPITALIZACION FIJA + ADICIONAL segun KWH consumidos

			if suministro.servicio.name == 'Energia':
				filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
				productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))

				#Traer consumos
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				
				for producto in productos:
					#UP especial, me trae el basico
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							up = float(producto_en_pricelist.formula)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

					#T1R, T1RS - T1RE - T1G
					if price_list.clave == 'T1R' or price_list.clave == 'T1R10' or price_list.clave == 'T1R20' or price_list.clave == 'T1RS' or price_list.clave == 'T1RS150' or price_list.clave == 'T1R150E':
						if kwh_consumidos > 200:
							if kwh_consumidos > 400:
								up = 20
							else:
								up = 13
					elif price_list.clave == 'T1RE' or price_list.clave == 'T1RE10' or price_list.clave == 'T1RE20':
						if kwh_consumidos > 700:
							up = 34
					elif price_list.clave == 'T1G':
						if kwh_consumidos > 1000:
							up = 40

					if (party.asociado):
						#CUOTA: El precio es el % del subtotal cargos
						#Doy de alta la suscripcion (rango)
						Rango = Pool().get('sigcoop_usuario.rango')
						rango = Rango()
						rango.cantidad = up
						rango.asociado = party
						rango.fecha = datetime.date.today()
						rango.save()
																							
					ret.append(self.crear_sale_line(1, producto, up, suministro, 18))

		elif company == "Cooperativa Electrica Limitada Norberto de la Riestra":
			#RIESTRA - SOLO ENERGIA
			#CAPITALIZACION 35%

			#Producto: Capitalizacion % (deberia haber uno asi por pricelist nada mas)
			filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
			productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
			subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			for producto in productos:
				#UP especial, me trae un porcentaje, no el precio unitario: EJEMPLO 0,35 (35%)
				up = 0
				
				for producto_en_pricelist in price_list.lines:
					#Busco el producto dentro de la pricelist
					if producto_en_pricelist.product == producto:
						up = float(producto_en_pricelist.formula) * float(subtotal_cargos)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
						
				if (party.asociado):
					#CUOTA: El precio es el % del subtotal cargos
					#Doy de alta la suscripcion (rango)
					Rango = Pool().get('sigcoop_usuario.rango')
					rango = Rango()
					rango.cantidad = up
					rango.asociado = party
					rango.fecha = datetime.date.today()
					rango.save()
																						
				ret.append(self.crear_sale_line(1, producto, up, suministro, 18))

		elif company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
			#COLINA - SOLO ENERGIA
			#CAPITALIZACION %

			#Producto: Capitalizacion % (deberia haber uno asi por pricelist nada mas)
			filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
			productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
			subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			for producto in productos:
				#UP especial, me trae un porcentaje, no el precio unitario: EJEMPLO 0,35 (35%)
				up = 0
				
				for producto_en_pricelist in price_list.lines:
					#Busco el producto dentro de la pricelist
					if producto_en_pricelist.product == producto:
						if suministro.ex_tarifas == '4':
							up = float(0.16) * float(subtotal_cargos)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
						else:
							up = float(producto_en_pricelist.formula) * float(subtotal_cargos)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
							
				#if (party.asociado):
					#CUOTA: El precio es el % del subtotal cargos
					#Doy de alta la suscripcion (rango)
				#	Rango = Pool().get('sigcoop_usuario.rango')
				#	rango = Rango()
				#	rango.cantidad = up
				#	rango.asociado = party
				#	rango.fecha = datetime.date.today()
				#	rango.save()
																						
				#ret.append(self.crear_sale_line(1, producto, up, suministro, 18))

		elif company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
			#SOLO ENERGIA
			#CAPITALIZACION %
			#6% o 3%, segun area de concesion
			
			if suministro.servicio.name == 'Energia':
				#Busco producto directamente por nombre
				if suministro.area_concesion == 'san blas':
					filtro_producto_capital_variable = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True and x.product.name == 'Capitalizacion Energia - % - B. San Blas')										
					productos_variable = map(lambda x: x.product, filter(filtro_producto_capital_variable, price_list.lines))
					
				else:
					filtro_producto_capital_variable = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True and x.product.name == 'Capitalizacion Energia - % - Otros')										
					productos_variable = map(lambda x: x.product, filter(filtro_producto_capital_variable, price_list.lines))            					
				
				subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
				
				#Agrego el porcentaje
				for producto in productos_variable:
					#UP especial, me trae un porcentaje, no el precio unitario: EJEMPLO 0,35 (35%)
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							#0.06 o 0.15
							up = float(producto_en_pricelist.formula) * float(subtotal_cargos)                 							
														
					up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
					#if (party.asociado):
						#CUOTA: El precio es el % del subtotal cargos
						#Doy de alta la suscripcion (rango)
					#	Rango = Pool().get('sigcoop_usuario.rango')
					#	rango = Rango()
					#	rango.cantidad = up
					#	rango.asociado = party
					#	rango.fecha = datetime.date.today()
					#	rango.save()
																					
					#ret.append(self.crear_sale_line(1, producto, up, suministro, 18))

		
		elif company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
			#Villa Iris - SOLO ENERGIA
			#CAPITALIZACION %

			if suministro.servicio.name == 'Energia':
				filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
				productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
				
				subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			
				#Agrego el porcentaje
				for producto in productos:
					#UP especial, me trae un porcentaje, no el precio unitario: EJEMPLO 0,35 (35%)
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							#0.15
							up = float(producto_en_pricelist.formula) * float(subtotal_cargos)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
																																						
					#if (party.asociado):
						#CUOTA: El precio es el % del subtotal cargos
						#Doy de alta la suscripcion (rango)
					#	Rango = Pool().get('sigcoop_usuario.rango')
					#	rango = Rango()
					#	rango.cantidad = up
					#	rango.asociado = party
					#	rango.fecha = datetime.date.today()
					#	rango.save()
																								
					#ret.append(self.crear_sale_line(1, producto, up, suministro, 18))
		
		
		elif company == "COOPERATIVA ELECTRICA DE CHASICO LIMITADA":
			#CHASICO - SOLO ENERGIA
			#CAPITALIZACION FIJA

			if suministro.servicio.name == 'Energia':
				filtro_producto = lambda x: (x.product.tipo_cargo == 'fijo' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
				productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
											
				#Agrego el porcentaje
				for producto in productos:
					#UP especial, me trae un fijo
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							
							up = float(producto_en_pricelist.formula)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
																																						
					#if (party.asociado):
						#CUOTA: El precio es el % del subtotal cargos
						#Doy de alta la suscripcion (rango)
					#	Rango = Pool().get('sigcoop_usuario.rango')
					#	rango = Rango()
					#	rango.cantidad = up
					#	rango.asociado = party
					#	rango.fecha = datetime.date.today()
					#	rango.save()
																								
					#ret.append(self.crear_sale_line(1, producto, up, suministro, 18))
		elif company == 'COOPERATIVA DE PROVISION DE SERVICIOS PUBLICOS, VIVIENDA Y SERVICIOS SOCIALES DE COPETONAS LIMITADA':
			#COPETONAS - SOLO ENERGIA
			#CAPITALIZACION %

			if suministro.servicio.name == 'Energia':
				filtro_producto = lambda x: (x.product.tipo_cargo == 'variable' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
				productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
				
				subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			
				#Agrego el porcentaje
				for producto in productos:
					#UP especial, me trae un porcentaje, no el precio unitario: EJEMPLO 0,35 (35%)
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							#0.15
							up = float(producto_en_pricelist.formula) * float(subtotal_cargos)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
																																						
					if (party.asociado):
						#CUOTA: El precio es el % del subtotal cargos
						#Doy de alta la suscripcion (rango)
						Rango = Pool().get('sigcoop_usuario.rango')
						rango = Rango()
						rango.cantidad = up
						rango.asociado = party
						rango.fecha = datetime.date.today()
						rango.save()
																								
					ret.append(self.crear_sale_line(1, producto, up, suministro, 18))    	

		elif company == "Cooperativa ELECTRICA Ltda. de GOYENA":
			#GOYENA - SOLO ENERGIA
			#CAPITALIZACION FIJA

			if suministro.servicio.name == 'Energia':				
				filtro_producto = lambda x: (x.product.tipo_cargo == 'fijo' and x.product.tipo_producto == 'varios' and x.product.suma_aportes == True)
				productos = map(lambda x: x.product, filter(filtro_producto, price_list.lines))
											
				#Agrego el porcentaje
				for producto in productos:
					#UP especial, me trae un fijo
					up = 0
					for producto_en_pricelist in price_list.lines:
						#Busco el producto dentro de la pricelist
						if producto_en_pricelist.product == producto:
							
							up = float(producto_en_pricelist.formula)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
																																						
					if (party.asociado):
						#CUOTA: El precio es el % del subtotal cargos
						#Doy de alta la suscripcion (rango)
						Rango = Pool().get('sigcoop_usuario.rango')
						rango = Rango()
						rango.cantidad = up
						rango.asociado = party
						rango.fecha = datetime.date.today()
						rango.save()
																								
					ret.append(self.crear_sale_line(1, producto, up, suministro, 18))
																																												
		return ret

	#Agrega el Cargo Fijo cargado dentro del suministro, y el variable, que depende del consumo
	#% Harcodeados por ahora
	#Si el suministro no tiene cargado el cargo fijo, no tiene que pagar AP
	def crear_sale_line_alumbrado_publico(self, party, price_list, suministro, consumos, sale_lines, sale):
				
		ret=[]

		Company = Pool().get('company.company')
		company = Company(Transaction().context.get('company')).party.name
			
		#Si el suministro no tiene configurado el cargo fijo de AP, el variable no se calcula
		producto = suministro.impuesto_alumbrado #CARGO FIJO de ALUMBRADO
		if producto:
			up = 0
			if company == "COOPERATIVA ELECTRICA DE SM" or company == "COOPERATIVA ELECTRICA DE SM " or company == "COOPERATIVA ELECTRICA Y SERVICIOS ANEXOS DE SAN MANUEL LTDA":
				#SAN  MANUEL=TASA MUNICIPAL
				for producto_en_pricelist in price_list.lines:
					if producto_en_pricelist.product == producto:
						up = producto_en_pricelist.formula
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

				ret.append(self.crear_sale_line(1, producto, up, suministro, 19))
				#SAN MANUEL: si el consumo es mayor a 100Kwh, agrego una Tasa Adicional de 8$
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				if kwh_consumidos > 100:
					producto_tasa_municipal_adicional = Pool().get('product.product').search([('name','=','Tasa Municipal Adicional')])[0]
					for producto_en_pricelist in price_list.lines:
						if producto_en_pricelist.product == producto_tasa_municipal_adicional:
							up = producto_en_pricelist.formula
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

					ret.append(self.crear_sale_line(1, producto_tasa_municipal_adicional, up, suministro,20))
																
			elif company == "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN":
				#PUAN
				
				#HARDCODED Cargo Variable, depende del consumo
				#T1R = 0,071
				#T1G = 0,113 / 0,08 / 0,05 dependiendo de consumo cargos variables
				#T2BT/T3BT/T3MT = 0,08 / 0,05 / 0,03 dependiendo de consumo cargos variables
				#GOBIERNO = 0,08 siempre (ver check en party)
				#PUAN
				
				if party.es_gobierno:
					porcentaje_sobre_cargos_variables = 0.08
				else:
					#Obtener cargos variables segun consumo y su tarifa
					kwh_consumidos = self.obtener_kwh_consumidos(consumos)
				
					if suministro.lista_precios.clave == 'T1R':
						porcentaje_sobre_cargos_variables = 0.071
					elif (suministro.lista_precios.clave == 'T1G') or (suministro.lista_precios.clave == 'T1Gac'):
						#rdb.set_trace()
						if kwh_consumidos <= 250:
							porcentaje_sobre_cargos_variables = 0.1130
						elif ((kwh_consumidos >= 251) and (kwh_consumidos <= 700)):
							porcentaje_sobre_cargos_variables = 0.08
						elif kwh_consumidos > 700:
							porcentaje_sobre_cargos_variables = 0.05
					elif (str(suministro.lista_precios.clave) == 'T2BTac') or (str(suministro.lista_precios.clave) == 'T2BT') or (str(suministro.lista_precios.clave) == 'T3BT') or (str(suministro.lista_precios.clave) == 'T3MT'):
						if kwh_consumidos <= 250:
							porcentaje_sobre_cargos_variables = 0.08
						elif ((kwh_consumidos >= 251) and (kwh_consumidos <= 25000)):
							porcentaje_sobre_cargos_variables = 0.05
						elif kwh_consumidos > 25000:
							porcentaje_sobre_cargos_variables = 0.03

				#Multiplicar porcentaje por total cargos variables en $
				valor_ap_variable = 0
				for line in sale_lines:
					if suministro.lista_precios.clave == 'T1R':
						if str(line.product.name.encode('utf-8')) == str('Cargo Variable T1R'):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
					elif ((str(suministro.lista_precios.clave) == 'T1G') or (str(suministro.lista_precios.clave) == 'T1Gac')):
						if (str(line.product.name.encode('utf-8')) == str('Cargo Variable T1G-BC-AC')):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
					elif ((str(suministro.lista_precios.clave) == 'T2BT') or (str(suministro.lista_precios.clave) == 'T2BTac')):
						if ((str(line.product.name.encode('utf-8')) == str('Cargo Variable por Energia Demandada En Pico T2BT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable por Energia Demandada Fuera de Pico T2BT'))):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
					elif str(suministro.lista_precios.clave) == 'T3BT':
						if ((str(line.product.name.encode('utf-8')) == str('Cargo Variable Pico T3BT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Valle T3BT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Resto T3BT'))):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
						if ((str(line.product.name.encode('utf-8')) == str('Cargo Variable Pico T3BT)')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Valle T3BT')) or (str(line.product.name.encode('utf-8')) == 'Cargo Variable Resto T3BT')):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
					elif suministro.lista_precios.clave == 'T3MT':
						if ((str(line.product.name.encode('utf-8')) == str('Cargo Variable Pico T3MT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Valle T3MT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Resto T3MT'))):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
						if ((str(line.product.name.encode('utf-8')) == str('Cargo Variable Pico T3MT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Valle T3MT')) or (str(line.product.name.encode('utf-8')) == str('Cargo Variable Resto T3MT'))):
							valor_ap_variable += Decimal(line.amount)*Decimal(porcentaje_sobre_cargos_variables)
			
				valor_ap_variable = Decimal(valor_ap_variable).quantize(Decimal('.01'), rounding=ROUND_DOWN)

				#Agrego el  producto de AP Variable - Configurado con Forzar Unit Price
				producto_apvariable = Pool().get('product.product').search([('name', '=', 'Alumbrado Publico - Cargo Variable')])[0]
				ret.append(self.crear_sale_line(1, producto_apvariable, valor_ap_variable, suministro, 19))
			
			elif company == "COOPERSIVE LTDA.":
				#SIERRA - TRAIGO EL AP, PERO DESPUES LE PONGO EL UP
				up = 0
				for producto_en_pricelist in price_list.lines:
					if producto_en_pricelist.product == producto:
						up = producto_en_pricelist.formula
						#Me trae el porcentaje: T1R = 0.216 y T1G = 0.0675
						#Multiplico por el subtotal de energia
						subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
						up = float(up) * float(subtotal_cargos)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

				ret.append(self.crear_sale_line(1, producto, up, suministro, 19))
			elif company == "Cooperativa Electrica Limitada Norberto de la Riestra":
				#TRAIGO EL AP, PERO DESPUES LE PONGO EL UP
				up = 0
				for producto_en_pricelist in price_list.lines:
					if producto_en_pricelist.product == producto:
						up = producto_en_pricelist.formula
						#Me trae el porcentaje: T1R = 0.15y T1G = 0.8
						#Multiplico por el subtotal de energia
						subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
						up = float(up) * float(subtotal_cargos)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

				ret.append(self.crear_sale_line(1, producto, up, suministro, 19))

			elif company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
				#Traigo el precio de lista del producto directamente
				up = producto.list_price
				up = float(up)
				up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
				ret.append(self.crear_sale_line(1, producto, up, suministro, 19))

			elif company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
				#Villa iris
				#69$ + % segun

				if party.es_gobierno:
					porcentaje_sobre_cargos_variables = 0.08
				else:
					#Obtener cargos variables segun consumo y su tarifa
					kwh_consumidos = self.obtener_kwh_consumidos(consumos)
				
					if suministro.lista_precios.clave == 'T1R' or suministro.lista_precios.clave == 'T1RS':
						porcentaje_sobre_cargos_variables = 0.05
					elif suministro.lista_precios.clave == 'T1G':
						if kwh_consumidos <= 250:
							porcentaje_sobre_cargos_variables = 0.08
						elif ((kwh_consumidos >= 251) and (kwh_consumidos <= 700)):
							porcentaje_sobre_cargos_variables = 0.05
						elif kwh_consumidos > 700:
							porcentaje_sobre_cargos_variables = 0.03
					else:
						porcentaje_sobre_cargos_variables = 0


				#Multiplico por el subtotal de energia
				subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
				valor_ap_variable = float(subtotal_cargos)*float(porcentaje_sobre_cargos_variables)
				
				#UP: 89$ + Variable
				up = float(producto.list_price) + float(valor_ap_variable)
				up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
				ret.append(self.crear_sale_line(1, producto, up, suministro, 19))


		return ret

	#Todos los productos deben estar configurados con forzar unit price (VER)
	#Si tiene periodo trae el del periodo de facturacion actual +  los vacios
	def crear_sale_lines_conceptos_especiales(self, party, price_list, suministro, periodo_facturacion, sale_lines, sale):
		ret = []
		
		Company = Pool().get('company.company')
		company = Company(Transaction().context.get('company')).party.name
		
		if suministro.lineas_conceptos_suministro:
			for linea_concepto_suministro in suministro.lineas_conceptos_suministro:
				if linea_concepto_suministro.concepto.name != 'Adicional Ruralidad Internet':
					if linea_concepto_suministro.periodo: #tiene periodo
						if linea_concepto_suministro.periodo == periodo_facturacion:    #Es el periodo de facturacion
							if not linea_concepto_suministro.bonificacion_sobre_total_energia:
								SaleLine = Pool().get('sale.line')
								new_line = SaleLine(
									product=linea_concepto_suministro.concepto,
									quantity=1,
									description=linea_concepto_suministro.concepto.name,
									unit=linea_concepto_suministro.concepto.default_uom,
									unit_price = Decimal(linea_concepto_suministro.cantidad).quantize(Decimal(".01"), rounding=ROUND_DOWN),
									servicio = suministro.servicio,
									)

								ret.append(new_line)
							else:
								#Descuento o Recargo % sobre total energia -> busco las lineas de la venta que son de energia y cargos
								subtotal_cargos_energia = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
								
								SaleLine = Pool().get('sale.line')
								new_line = SaleLine(
									product=linea_concepto_suministro.concepto,
									quantity=1,
									description=linea_concepto_suministro.concepto.name,
									unit=linea_concepto_suministro.concepto.default_uom,
									unit_price = Decimal(Decimal(Decimal(linea_concepto_suministro.porcentaje_bonificacion_energia)*Decimal(subtotal_cargos_energia))/100).quantize(Decimal(".01"), rounding=ROUND_DOWN),
									servicio = suministro.servicio,
									)

								ret.append(new_line)

					else:
						#No tiene periodo, se incluye porque es permanente.
						if not linea_concepto_suministro.bonificacion_sobre_total_energia:
							SaleLine = Pool().get('sale.line')
							new_line = SaleLine(
								product=linea_concepto_suministro.concepto,
								quantity=1,
								description=linea_concepto_suministro.concepto.name,
								unit=linea_concepto_suministro.concepto.default_uom,
								unit_price = Decimal(linea_concepto_suministro.cantidad).quantize(Decimal(".01"), rounding=ROUND_DOWN),
								servicio = suministro.servicio,
								)

							ret.append(new_line)
						else:
							
							if (linea_concepto_suministro.concepto.name == 'Descuento Empleados - Internet') and (company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS"):
								#San Blas -> descuento del 10% para Internet-Empleados
								Servicio =  Pool().get('product.category')
								servicio_internet = Servicio.search([('name', '=', 'Internet')])[0]
								if servicio_internet:
									subtotal_cargos_internet= self.get_subtotal_cargos(sale, 'cargos', servicio_internet)

									SaleLine = Pool().get('sale.line')
									new_line = SaleLine(
										product=linea_concepto_suministro.concepto,
										quantity=1,
										description=linea_concepto_suministro.concepto.name,
										unit=linea_concepto_suministro.concepto.default_uom,
										unit_price = Decimal(Decimal(Decimal(linea_concepto_suministro.porcentaje_bonificacion_energia)*Decimal(subtotal_cargos_internet))/100).quantize(Decimal(".01"), rounding=ROUND_DOWN),
										servicio = servicio_internet,
										)

									ret.append(new_line)
							else:
								#import pudb;pu.db
								#Descuento o Recargo % sobre total energia -> busco las lineas de la venta que son de energia y cargos
								subtotal_cargos_energia = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
						
								SaleLine = Pool().get('sale.line')
								new_line = SaleLine(
									product=linea_concepto_suministro.concepto,
									quantity=1,
									description=linea_concepto_suministro.concepto.name,
									unit=linea_concepto_suministro.concepto.default_uom,
									unit_price = Decimal(Decimal(Decimal(linea_concepto_suministro.porcentaje_bonificacion_energia)*Decimal(subtotal_cargos_energia))/100).quantize(Decimal(".01"), rounding=ROUND_DOWN),
									servicio = suministro.servicio,
									)

								ret.append(new_line)

	
		return ret


	def crear_sale_lines_recargo_pago_fuera_de_termino(self, suministro, periodo_facturacion, sin_consumos=False):
		ret = []
		#import pudb;pu.db
		if not sin_consumos:
			#Busco el ultimo consumo
			ultimoconsumo = suministro.get_ultimo_consumo(periodo_facturacion)
			if ultimoconsumo is not None:
				if ultimoconsumo.estado == '2': #FACTURADO - SIGCOOP
					#Calculo la deuda de la factura actual (si la anterior fue pagada fuera de termino)
					#monto del recargo sin el iva
					deuda_factura_actual = self.calcular_deuda_factura_actual(ultimoconsumo)
					if (deuda_factura_actual > 0):
						#Creo la linea de venta con el producto Recargo por pago fuera de termino
						if suministro.servicio.name == 'Energia':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
						elif suministro.servicio.name == 'Agua':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (agua)')])[0]
						elif suministro.servicio.name == 'Telefonia':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (telefonia)')])[0]
						elif suministro.servicio.name == 'Internet':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (internet)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Sepelio':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (ambulancia)')])[0]
						else:
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
						
						#Creo la linea de venta con el producto IVA Recargo por pago fuera de termino
						if suministro.servicio.name == 'Energia':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]
						elif suministro.servicio.name == 'Agua':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (agua)')])[0]
						elif suministro.servicio.name == 'Telefonia':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (telefonia)')])[0]
						elif suministro.servicio.name == 'Internet':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (internet)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Sepelio':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (ambulancia)')])[0]
						else:
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]

						#EL IVA YA VIENE
						up = Decimal(deuda_factura_actual) / Decimal(1.21)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						up_iva = deuda_factura_actual - up
						up_iva = Decimal(up_iva).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						
						#Recargo
						ret.append(self.crear_sale_line(1, producto, up,suministro, 21))
						#Iva Recargo
						ret.append(self.crear_sale_line(1, producto_iva, up_iva,suministro, 21))

				elif ultimoconsumo.estado == '0': #NO FACTURABLE - SISTEMA ANTERIOR
					#POR ACA
					#Calculo la deuda de la factura actual (si la anterior fue pagada fuera de termino)
					#monto del recargo sin el iva
					deuda_factura_actual = self.calcular_deuda_factura_actual(ultimoconsumo)
					if (deuda_factura_actual > 0):
						#rdb.set_trace()
						print "El suministro de " + str(suministro.usuario_id.name) + " tiene deuda y se genera recargo."
						#Creo la linea de venta con el producto Recargo por pago fuera de termino
						if suministro.servicio.name == 'Energia':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
						elif suministro.servicio.name == 'Agua':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (agua)')])[0]
						elif suministro.servicio.name == 'Telefonia':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (telefonia)')])[0]
						elif suministro.servicio.name == 'Internet':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (internet)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Sepelio':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (ambulancia)')])[0]
						else:
							producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
						
						#Creo la linea de venta con el producto IVA Recargo por pago fuera de termino
						if suministro.servicio.name == 'Energia':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]
						elif suministro.servicio.name == 'Agua':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (agua)')])[0]
						elif suministro.servicio.name == 'Telefonia':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (telefonia)')])[0]
						elif suministro.servicio.name == 'Internet':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (internet)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Sepelio':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
						elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (ambulancia)')])[0]
						else:
							producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]

						#EL IVA YA VIENE
						up = Decimal(deuda_factura_actual) / Decimal(1.21)
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						up_iva = deuda_factura_actual - up
						up_iva = Decimal(up_iva).quantize(Decimal(".01"), rounding=ROUND_DOWN)
											
						#Recargo
						ret.append(self.crear_sale_line(1, producto, up,suministro, 21))
						#Iva Recargo
						ret.append(self.crear_sale_line(1, producto_iva, up_iva,suministro, 21))

				return ret
			else:
				#Es suministro con consumos, pero no tiene consumos anteriores->Telefonia
				#Lo manejo como un sin consumos
				deuda_factura_actual = self.calcular_deuda_factura_actual_sin_consumos(suministro, periodo_facturacion)
				if (deuda_factura_actual > 0):
					#Creo la linea de venta con el producto Recargo por pago fuera de termino
					if suministro.servicio.name == 'Energia':
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
					elif suministro.servicio.name == 'Agua':
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (agua)')])[0]
					elif suministro.servicio.name == 'Telefonia':
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (telefonia)')])[0]
					elif suministro.servicio.name == 'Internet':
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (internet)')])[0]
					elif suministro.servicio.name == 'Sepelio':
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
					elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (ambulancia)')])[0]
					else:
						producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
					
					#Creo la linea de venta con el producto IVA Recargo por pago fuera de termino
					if suministro.servicio.name == 'Energia':
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]
					elif suministro.servicio.name == 'Agua':
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (agua)')])[0]
					elif suministro.servicio.name == 'Telefonia':
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (telefonia)')])[0]
					elif suministro.servicio.name == 'Internet':
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (internet)')])[0]
					elif suministro.servicio.name == 'Sepelio':
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
					elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (ambulancia)')])[0]
					else:
						producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]

					#EL IVA YA VIENE
					up = Decimal(deuda_factura_actual) / Decimal(1.21)
					up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
					up_iva = deuda_factura_actual - up
					up_iva = Decimal(up_iva).quantize(Decimal(".01"), rounding=ROUND_DOWN)
										
					#Recargo
					ret.append(self.crear_sale_line(1, producto, up,suministro, 21))
					#Iva Recargo
					ret.append(self.crear_sale_line(1, producto_iva, up_iva,suministro, 21))
					
				return ret
			
		else: #SIN CONSUMOS
			#Calculo la deuda de la factura actual (si la anterior fue pagada fuera de termino)
			deuda_factura_actual = self.calcular_deuda_factura_actual_sin_consumos(suministro, periodo_facturacion)
			if (deuda_factura_actual > 0):
				#Creo la linea de venta con el producto Recargo por pago fuera de termino
				if suministro.servicio.name == 'Energia':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
				elif suministro.servicio.name == 'Agua':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (agua)')])[0]
				elif suministro.servicio.name == 'Telefonia':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (telefonia)')])[0]
				elif suministro.servicio.name == 'Internet':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (internet)')])[0]
				elif suministro.servicio.name == 'Sepelio':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
				elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (ambulancia)')])[0]
				elif suministro.servicio.name == 'Sepelio':
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
				else:
					producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
				
				#Creo la linea de venta con el producto IVA Recargo por pago fuera de termino
				if suministro.servicio.name == 'Energia':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]
				elif suministro.servicio.name == 'Agua':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (agua)')])[0]
				elif suministro.servicio.name == 'Telefonia':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (telefonia)')])[0]
				elif suministro.servicio.name == 'Internet':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (internet)')])[0]
				elif suministro.servicio.name == 'Sepelio':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
				elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (ambulancia)')])[0]
				elif suministro.servicio.name == 'Sepelio':
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
				else:
					producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]


				#EL IVA YA VIENE
				up = Decimal(deuda_factura_actual) / Decimal(1.21)
				up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
				up_iva = deuda_factura_actual - up
				up_iva = Decimal(up_iva).quantize(Decimal(".01"), rounding=ROUND_DOWN)
							
				#Recargo
				ret.append(self.crear_sale_line(1, producto, up,suministro, 21))
				#Iva Recargo
				ret.append(self.crear_sale_line(1, producto_iva, up_iva,suministro, 21))
				
			return ret

	def crear_sale_lines_multiples_recargo_por_pago_fuera_de_termino(self, suministro, sale):
		"""
		Vamos a crear una linea de venta por cada deuda en estado-> saldada: True y recargo_a_pagar: True.
		Estas son deudas que se pagaron a traves de facturas viejas, pero que tienen un recargo por los
		dias de retraso en el pago.
		Tomamos el producto Recargo por Pago Fuera de Termino (deuda).
		Por cada deuda, creamos una linea de venta. En lugar de la cantidad, indicamos el monto
		de la deuda. Asi logramos tener varias lineas de venta con un mismo producto y diferente valor.
		A su vez, seteamos recargo_a_pagar = False en las deudas procesadas.
		"""

		#Deberian ser deudas anteriores a la ultima - No tomar en cuenta el ultimo periodo
		#import pudb;pu.db
		ret = []
		deudas = Pool().get('sigcoop_deudas.deuda').search(
				[
				('suministro_id', '=', suministro),
				('saldada', '=', True),
				('recargo_a_pagar', '=', True),
				])
		if deudas:
			if suministro.servicio.name == 'Energia':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (energia)')])[0]
			elif suministro.servicio.name == 'Agua':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (agua)')])[0]
			elif suministro.servicio.name == 'Telefonia':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (telefonia)')])[0]
			elif suministro.servicio.name == 'Internet':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (internet)')])[0]
			elif suministro.servicio.name == 'Sepelio':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
			elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (ambulancia)')])[0]
			elif suministro.servicio.name == 'Sepelio':
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
			else:
				producto = Pool().get('product.product').search([('name','=','Recargo por Pago Fuera de Termino (sepelio)')])[0]
			
			#Creo la linea de venta con el producto IVA Recargo por pago fuera de termino
			if suministro.servicio.name == 'Energia':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]
			elif suministro.servicio.name == 'Agua':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (agua)')])[0]
			elif suministro.servicio.name == 'Telefonia':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (telefonia)')])[0]
			elif suministro.servicio.name == 'Internet':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (internet)')])[0]
			elif suministro.servicio.name == 'Sepelio':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
			elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (ambulancia)')])[0]
			elif suministro.servicio.name == 'Sepelio':
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (sepelio)')])[0]
			else:
				producto_iva = Pool().get('product.product').search([('name','=','IVA Recargo por Pago Fuera de Termino (energia)')])[0]

			#Chequeo si las deudas son del periodo anterior o no
			periodo_anterior = self.periodo.get_periodo_anterior()
			
			for deuda in deudas:
				if deuda.periodo != periodo_anterior:
					if not deuda.interes_especial:
						
						montorecargo_sin_iva = 0
						diaspago = 0
						if deuda.nro_factura_vieja:
							if deuda.fecha_vencimiento2_factura_vieja:
								diaspago = (deuda.fecha_pago_factura - deuda.fecha_vencimiento2_factura_vieja).days
						elif deuda.invoice_id:
							diaspago = (deuda.fecha_pago_factura - deuda.invoice_id.vencimiento_2).days
						
						if diaspago > 0:
							tasa_actual = Pool().get('sigcoop_tasas.tasa').get_valor_tasa_actual()
							#Descontar el valor de la capitalizacion (no se puede)
							montorecargo_sin_iva = float(deuda.monto_deuda) *  (float(diaspago) * float(tasa_actual))
												
							#EL IVA YA VIENE
							up = Decimal(montorecargo_sin_iva) / Decimal(1.21)
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
							up_iva = Decimal(montorecargo_sin_iva) - up
							up_iva = Decimal(up_iva).quantize(Decimal(".01"), rounding=ROUND_DOWN)

							#Recargo
							ret.append(self.crear_sale_line(1, producto,up, suministro, 22))
							#Iva Recargo
							ret.append(self.crear_sale_line(1, producto_iva, up_iva, suministro, 22))
							deuda.recargo_a_pagar = False
							deuda.sale = sale
							deuda.save()

		return ret

	'''
	def crear_sale_lines_puree(self, suministro, periodo):
		"""
		Creamos las lineas de venta para los recargos de puree.
		Asumimos que hay, como maximo, un recargo para un producto y periodo
		dados.
		"""
		ret = []
		recargos_puree = Pool().get('sigcoop_puree.recargo_puree').search(
				[('periodo', '=', periodo), ('id_suministro', '=', suministro)]
				)
		if recargos_puree:
			producto_puree = Pool().get('product.product').search([('name', '=', 'Puree')])[0]
			ret.append(self.crear_sale_line(Decimal(recargos_puree[0].recargo).quantize(Decimal(".01"), rounding=ROUND_DOWN), producto_puree, Decimal(1), suministro.servicio, 22))
		return ret
	'''

	'''
	#Actualmente comentada. Traer desde sigcoop_vencimiento_invoice
	def crear_sale_lines_moratoria(self, suministro, periodo):
		"""
		Aca creo la linea de la cuota correspondiente a una moratoria si estuviera
		"""
		ret = []

		producto = Pool().get('product.product').search([('name', '=', 'Cuota de Plan de Pago')])[0]
		producto_name_original = "Cuota de Plan de Pago"
		cuota_planes = Pool().get('sigcoop_plan_pagos_deudas.cuota_moratoria').search(
				[
				('suministro_id', '=', suministro),
				('pagada', '=', False),
				('periodo', '=', periodo),
				])
		
		if cuota_planes:

			descripcion = producto.name + " - " + str(cuota_planes[0].nro_cuota) +' / '+ str(cuota_planes[0].cantidad_cuotas)

			#Property = Pool().get('ir.property')
			#nuevo_valor = u',' + unicode(descripcion)
			#Property.set('name', 'product.template', [producto.id], nuevo_valor)

			SaleLine = Pool().get('sale.line')
			new_line = SaleLine(
					product=producto,
					quantity=Decimal('1'),
					description=descripcion,
					unit=producto.default_uom,
					unit_price=Decimal(cuota_planes[0].monto_cuota).quantize(Decimal('.01'), rounding=ROUND_DOWN),
					servicio = suministro.servicio,
					)
			ret.append(new_line)

			#nuevo_valor = u',' + unicode(producto_name_original)
			#Property.set('name', 'product.template', [producto.id], nuevo_valor)

		return ret
	'''

	#Agrego facturacion Proporcional, Si no tiene facturas anteriores
	#Ver calculo de servicios sociales, en caso de que tenga adicionales a cargo
	def crear_sale_lines_sin_consumos(self, suministro, periodo_facturacion):
		"""
		Creamos las lineas de venta para servicios sin consumos.
		"""
		
		ret = []
		#Tomar el producto por Tarifa
		#Obtenemos los productos que son cargos fijos, de la lista de precios del suministro
		filtro_producto = lambda x: (x.product.tipo_cargo == 'fijo' and x.product.tipo_producto == 'cargos')
		productos = map(lambda x: x.product, filter(filtro_producto, suministro.lista_precios.lines))
		for producto in productos:
			up = self.calcular_unit_price(1, producto, suministro.lista_precios, suministro.titular_id)
			#Pregunto por servicio y fecha de alta para facturacion proporcional
			if (str(suministro.servicio.name) == str('Internet')) | (str(suministro.servicio.name) == str('Cable')):
 
				
				Company = Pool().get('company.company')
				company = Company(Transaction().context.get('company')).party.name

				if company == "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN" or company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS" or company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
					#VARIOS
					#veo si el alta del servicio se dio en el periodo que se esta facturando o antes
					#Si se dio en el periodo de facturacion: proporcional
					#Sino, entero
					if (suministro.fecha_alta.month == periodo_facturacion.periodo) and (suministro.fecha_alta.year == periodo_facturacion.anio):
						#Es nuevo
						for producto_en_pricelist in suministro.lista_precios.lines:
							if producto_en_pricelist.product == producto:
								up = producto_en_pricelist.formula
								up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

						dias_de_servicio = 30 - int(suministro.fecha_alta.day) + 1
						porcentaje_cobro = dias_de_servicio*100/30
						up_a_cobrar = up*porcentaje_cobro/100
												
						ret.append(
							self.crear_sale_line(1, producto, up_a_cobrar, suministro, 1)
						)
					else:
						#No es nuevo, va completo
						up = 0
						for producto_en_pricelist in suministro.lista_precios.lines:
							if producto_en_pricelist.product == producto:
								up = producto_en_pricelist.formula
								up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						
						ret.append(
							self.crear_sale_line(1, producto, up, suministro, 1)
						)
				else:
					#COMPLETO
					up = 0
					for producto_en_pricelist in suministro.lista_precios.lines:
						if producto_en_pricelist.product == producto:
							up = producto_en_pricelist.formula
							up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
					
					ret.append(
						self.crear_sale_line(1, producto, up, suministro, 1)
					)
			
			elif suministro.servicio.name == 'Servicios Sociales Sepelio':
				#Agrego cargo fijo

				up = 0
			
				for producto_en_pricelist in suministro.lista_precios.lines:
					if producto_en_pricelist.product == producto:
						up = producto_en_pricelist.formula
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

				
				ret.append(
								self.crear_sale_line(1, producto, up, suministro, 1)
							)

				#Preguntar por personas a cargo adicionales si es Servicios Sociales
				Familiares = Pool().get('sigcoop_usuario.familiar')
				familiares_a_cargo = Familiares.search([('usuario_id', '=', suministro.usuario_id), ('sepelio_a_cargo','=',True)])

				if familiares_a_cargo:
					precio_por_adicional = Decimal(up/4)
					total_adicional = Decimal(precio_por_adicional * len(familiares_a_cargo))
					product_adic = Pool().get('product.product').search([('name', '=', 'Adicional Sepelio')])[0]
					ret.append(
								self.crear_sale_line(1, product_adic, total_adicional, suministro, 2)
							)

			elif suministro.servicio.name == 'Servicios Sociales Enfermeria':
				#Agrego cargo fijo
								
				up = 0
			
				for producto_en_pricelist in suministro.lista_precios.lines:
					if producto_en_pricelist.product == producto:
						up = producto_en_pricelist.formula
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)

				ret.append(
								self.crear_sale_line(1, producto, up, suministro, 1)
							)

				#Preguntar por personas a cargo adicionales si es Servicios Sociales
				Familiares = Pool().get('sigcoop_usuario.familiar')
				familiares_a_cargo = Familiares.search([('usuario_id', '=', suministro.usuario_id), ('ambulancia_a_cargo','=',True)])

				if familiares_a_cargo:
					precio_por_adicional = Decimal(up/4)
					total_adicional = Decimal(precio_por_adicional * len(familiares_a_cargo))

					product_adic = Pool().get('product.product').search([('name', '=', 'Adicional Ambulancia y Enfermeria')])[0]
					ret.append(
								self.crear_sale_line(1, product_adic, total_adicional, suministro, 2)
							)
			else:
				#SEPELIO SUELTO, BOMBERO SUELTO
				up = 0
				for producto_en_pricelist in suministro.lista_precios.lines:
					if producto_en_pricelist.product == producto:
						up = producto_en_pricelist.formula
						up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
				
				ret.append(
					self.crear_sale_line(1, producto, up, suministro, 1)
				)

		return ret


	'''
	def crear_sale_lines_credito(self, suministro, producto, up):
		"""
		Aca creo la linea de credito
		"""
		ret = []
		SaleLine = Pool().get('sale.line')
		new_line = SaleLine(
				product=producto,
				quantity=Decimal('1'),
				description=producto.name,
				unit=producto.default_uom,
				unit_price=Decimal(up).quantize(Decimal('.01'), rounding=ROUND_DOWN),
				servicio = suministro.servicio,
				)
		ret.append(new_line)
		
		return ret
	'''


	def crear_sale_line_ajuste(self, suministro, sale):
		"""
		Creamos las lineas de venta para los ajustes por redondeo
		El Ajuste por Redondeo tiene que ser Varios - Variable
		"""
		
		ret = []
		total = sale.total_amount
	
		i, d = divmod(total, 1)
		dec = int(d * 100)

		if suministro.servicio.name == 'Energia':
			if (not dec == 0):

				#SIEMPRE RESTA
				if (dec >= 1) and (dec <= 99):
					ajuste = Decimal(Decimal(-dec)/100)
				else:
					ajuste = Decimal(0)

				#ANTERIOR FORMULA
				#if (dec >= 1) and (dec <= 50):
				#    ajuste = Decimal(Decimal(-dec)/100)
				#elif (dec >= 51) and (dec <= 99):
				#    ajuste = 100 - dec
				#    ajuste = Decimal(Decimal(ajuste)/100)
				#else:
				#    ajuste = Decimal(0)
				
				producto_ajuste = Pool().get('product.product').search([('name', '=', 'Ajuste por redondeo')])[0]
				ret.append(self.crear_sale_line(1, producto_ajuste, Decimal(ajuste).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 23))
		
		elif suministro.servicio.name == 'Internet':
			if (not dec == 0):
				ajuste = 100 - dec
				ajuste = Decimal(Decimal(ajuste)/100)
			else:
				ajuste = Decimal(0)
			
				producto_ajuste = Pool().get('product.product').search([('name', '=', 'Ajuste por redondeo - internet')])[0]
				ret.append(self.crear_sale_line(1, producto_ajuste, Decimal(ajuste).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 23))


		return ret


	def crear_sale_line_internet_con_iva(self, suministro, sale, suministro_energia):
		"""
		Creamos las lineas de venta para internet como adicional
		"""
		ret = []
		nombre_producto_internet_iva = suministro.lista_precios.name #tarifa y nombre con iva es igual
		producto_internet_iva = Pool().get('product.product').search([('name', '=', nombre_producto_internet_iva)])[0]
		total = 0
		if producto_internet_iva:
			#CON IVA INCLUIDO, UN SOLO CONCEPTO, el precio esta en el product
			total = Decimal(producto_internet_iva.list_price).quantize(Decimal('.01'), rounding=ROUND_DOWN)
			if suministro.lineas_conceptos_suministro:
				for linea_concepto_suministro in suministro.lineas_conceptos_suministro:
					if linea_concepto_suministro.concepto.name == 'Adicional Ruralidad Internet':
						#Le sumo ruralidad
						total += linea_concepto_suministro.cantidad

			ret.append(self.crear_sale_line(1, producto_internet_iva, Decimal(total).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro_energia, 23))
		
		return ret

	def crear_sale_line_excedente_agua(self, suministro, excedente):
		"""
		Creamos las lineas de venta para el excedente de agua
		"""
		ret = []
		producto_excedente = Pool().get('product.product').search([('name', '=', 'M3 Excedente Agua')])[0]
						
		if producto_excedente:
			 for producto_en_pricelist in suministro.lista_precios.lines:
				if producto_en_pricelist.product == producto_excedente:
					#import pudb;pu.db
					up = producto_en_pricelist.formula
					#up = float(up)*float(excedente)
					up = Decimal(up).quantize(Decimal(".01"), rounding=ROUND_DOWN)
			
					ret.append(
						self.crear_sale_line(excedente, producto_excedente, up, suministro, 3)
					)
	
		return ret

	def crear_sale_line_diferencial_10(self, suministro, sale):
		"""
		Creamos las lineas de venta diferencial 10
		"""
				
		ret = []
		producto_diferencial = None
		if suministro.lista_precios.clave == 'T1R' or suministro.lista_precios.clave == 'T4' or suministro.lista_precios.clave == 'T1RE':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17')])[0]
		elif suministro.lista_precios.clave == 'T1RS' or suministro.lista_precios.clave == 'T4S':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T1RS')])[0]
		elif suministro.lista_precios.clave == 'T1AP':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T1AP')])[0]
		elif suministro.lista_precios.clave == 'T3BT' or suministro.lista_precios.clave == 'T3MT':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T3')])[0]
		elif suministro.lista_precios.clave == 'T4NR' or suministro.lista_precios.clave == 'T1G' or suministro.lista_precios.clave == 'T1GE' or suministro.lista_precios.clave == 'T1GEBP' or suministro.lista_precios.clave == 'T2BT':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T4NR')])[0]
		
		
		total = 0
		if producto_diferencial:
			subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			total = subtotal_cargos*Decimal(0.10)
			total = Decimal(total).quantize(Decimal('.01'), rounding=ROUND_DOWN)
			
			ret.append(self.crear_sale_line(1, producto_diferencial, Decimal(total).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 10))
		
		return ret

	def crear_sale_line_diferencial_20(self, suministro, sale):
		"""
		Creamos las lineas de venta diferencial
		"""
				
		ret = []
		producto_diferencial = None
		if suministro.lista_precios.clave == 'T1R' or suministro.lista_precios.clave == 'T4' or suministro.lista_precios.clave == 'T1RE':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17')])[0]
		elif suministro.lista_precios.clave == 'T1RS' or suministro.lista_precios.clave == 'T4S':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T1RS')])[0]
		elif suministro.lista_precios.clave == 'T1AP':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T1AP')])[0]
		elif suministro.lista_precios.clave == 'T3BT' or suministro.lista_precios.clave == 'T3MT':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T3')])[0]
		elif suministro.lista_precios.clave == 'T4NR' or suministro.lista_precios.clave == 'T1G' or suministro.lista_precios.clave == 'T1GE' or suministro.lista_precios.clave == 'T1GEBP' or suministro.lista_precios.clave == 'T2BT':
			producto_diferencial = Pool().get('product.product').search([('name', '=', 'Diferencial Res. MIySP Nro 419/17 - T4NR')])[0]
				
		total = 0
		if producto_diferencial:
			subtotal_cargos = self.get_subtotal_cargos(sale, 'cargos', suministro.servicio)
			total = subtotal_cargos*Decimal(0.20)
			total = Decimal(total).quantize(Decimal('.01'), rounding=ROUND_DOWN)
			
			ret.append(self.crear_sale_line(1, producto_diferencial, Decimal(total).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 10))
		
		return ret


	def crear_sale_line_bonificacion_riestra(self, party, price_list, suministro, consumos, sale_lines, sale, concepto):
				
		ret=[]
		if party.name[:8] == 'BOMBEROS':
			
			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			productos_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])
			for producto_consumo in productos_consumo:
				if producto_consumo.producto_id.template.name[:14] == 'Cargo Variable':
					producto = producto_consumo

			producto_bonificacion = Pool().get('product.product').search([('name', '=', 'Bonificacion Energia CCT')])[0]
								
			total_bonificacion = 0
			if producto_bonificacion:
				up = 0
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				up_consumidos = self.calcular_unit_price(kwh_consumidos, producto.producto_id, price_list, suministro.titular_id)
				
				if kwh_consumidos > 400:
					#BONIFICO LOS PRIMEROS 400
					total_bonificacion += float(up_consumidos)*400
				else:
					total_bonificacion += float(up_consumidos)*kwh_consumidos
							
				ret.append(self.crear_sale_line(1, producto_bonificacion, Decimal(-total_bonificacion).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 3))

		elif party.name[:18] == 'IGLESIA PARROQUIAL':

			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			productos_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])
			for producto_consumo in productos_consumo:
				if producto_consumo.producto_id.template.name[:14] == 'Cargo Variable':
					producto = producto_consumo

			producto_bonificacion = Pool().get('product.product').search([('name', '=', 'Bonificacion Energia CCT')])[0]
								
			total_bonificacion = 0
			if producto_bonificacion:
				up = 0
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				up_consumidos = self.calcular_unit_price(kwh_consumidos, producto.producto_id, price_list, suministro.titular_id)
				
				if kwh_consumidos > 366:
					#BONIFICO LOS PRIMEROS 366
					total_bonificacion += float(up_consumidos)*366
				else:
					total_bonificacion += float(up_consumidos)*kwh_consumidos
							
				ret.append(self.crear_sale_line(1, producto_bonificacion, Decimal(-total_bonificacion).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 3))


		elif party.name[:16] == 'CAPILLA SAN JOSE':

			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			productos_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])
			for producto_consumo in productos_consumo:
				if producto_consumo.producto_id.template.name[:14] == 'Cargo Variable':
					producto = producto_consumo

			producto_bonificacion = Pool().get('product.product').search([('name', '=', 'Bonificacion Energia CCT')])[0]
								
			total_bonificacion = 0
			if producto_bonificacion:
				up = 0
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				up_consumidos = self.calcular_unit_price(kwh_consumidos, producto.producto_id, price_list, suministro.titular_id)
				
				if kwh_consumidos > 259:
					#BONIFICO LOS PRIMEROS 259
					total_bonificacion += float(up_consumidos)*259
				else:
					total_bonificacion += float(up_consumidos)*kwh_consumidos
							
				ret.append(self.crear_sale_line(1, producto_bonificacion, Decimal(-total_bonificacion).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 3))


		elif party.empleado:

			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			productos_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])
			for producto_consumo in productos_consumo:
				if producto_consumo.producto_id.template.name[:14] == 'Cargo Variable':
					producto = producto_consumo

			producto_bonificacion = Pool().get('product.product').search([('name', '=', 'Bonificacion Energia CCT')])[0]
								
			total_bonificacion = 0
			if producto_bonificacion:
				up = 0
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				up_consumidos = self.calcular_unit_price(kwh_consumidos, producto.producto_id, price_list, suministro.titular_id)
				
				if kwh_consumidos > 200:
					#BONIFICO LOS PRIMEROS 200
					total_bonificacion += float(up_consumidos)*200
					kwh_excedentes = kwh_consumidos - 200
					total_excedentes = (float(up_consumidos)*kwh_excedentes)*0.75
					total_bonificacion += total_excedentes

				else:
					total_bonificacion += float(up_consumidos)*kwh_consumidos
							
				ret.append(self.crear_sale_line(1, producto_bonificacion, Decimal(-total_bonificacion).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 3))


		return ret


	def crear_sale_line_bonificacion_colina(self, party, price_list, suministro, consumos, sale_lines, sale, concepto):
				
		ret=[]
		if party.empleado:

			ProductoConsumo = Pool().get('sigcoop_wizard_ventas.producto_consumo')
			productos_consumo = ProductoConsumo.search([('concepto', '=', concepto), ('tarifa_id', '=', price_list), ('servicio', '=', suministro.servicio)])
			for producto_consumo in productos_consumo:
				if producto_consumo.producto_id.template.name[:14] == 'Cargo Variable':
					producto = producto_consumo

			producto_bonificacion = Pool().get('product.product').search([('name', '=', 'Bonificacion Energia CCT')])[0]
								
			total_bonificacion = 0
			if producto_bonificacion:
				up = 0
				kwh_consumidos = int(self.obtener_kwh_consumidos(consumos))
				up_consumidos = self.calcular_unit_price(kwh_consumidos, producto.producto_id, price_list, suministro.titular_id)
				
				if kwh_consumidos > 200:
					#BONIFICO LOS PRIMEROS 200
					total_bonificacion += float(up_consumidos)*200
					kwh_excedentes = kwh_consumidos - 200
					total_excedentes = (float(up_consumidos)*kwh_excedentes)*0.75
					total_bonificacion += total_excedentes

				else:
					total_bonificacion += float(up_consumidos)*kwh_consumidos
							
				ret.append(self.crear_sale_line(1, producto_bonificacion, Decimal(-total_bonificacion).quantize(Decimal(".01"), rounding=ROUND_DOWN), suministro, 3))


		return ret


	
	''''''''''''''''''''''''''''''''''''''
	'''FUNCION MADRE QUE CREA LA VENTA'''
	''''''''''''''''''''''''''''''''''''''

	def crear_venta_padre(self, suministro_id, forzarfac):
		Company = Pool().get('company.company')
		company = Company(Transaction().context.get('company')).party.name
		suministro = Pool().get('sigcoop_suministro.suministro')(suministro_id)				
		Invoice = Pool().get('account.invoice')
		
		if not forzarfac:
			#Chequeo si ya se facturo ese suministros para ese periodo (busco factura)
			
			#Si es factura electronica, que no exista tampoco en borrador
			#Si es agua o energia, busco confirmada
			if ((suministro.servicio.name == 'Energia') or (suministro.servicio.name == 'Agua')):
				invoice_facturada = Invoice.search([('periodo','=', self.periodo), ('suministro','=',suministro_id), ('state','=','posted')])
			else:
				invoice_facturada = Invoice.search([('periodo','=', self.periodo), ('suministro','=',suministro_id)])				
		else:
			#Hay que re-facturar
			#invoice_facturada = False
			#Para La Colina
			#if ((suministro.servicio.name == 'Energia') or (suministro.servicio.name == 'Agua')):
			#	invoice_facturada = Invoice.search([('periodo','=', self.periodo), ('suministro','=',suministro_id), ('state','=','posted')])
			#else:
			invoice_facturada = False
			



		if not invoice_facturada:
			#Cantidades para resumen
			cantidad_sin_consumo = 0
			sin_consumos = False
			consumos_a_facturar = None
			Consumos = Pool().get('sigcoop_consumos.consumo')
			#Esta funcion se llama una vez por suministro
			suministro = Pool().get('sigcoop_suministro.suministro')(suministro_id)
			
			if ((suministro.servicio.name == 'Energia') or (suministro.servicio.name == 'Agua')):
				#Chequear si tiene consumos, sino no se factura
				filtro_consumo = [
								('periodo', '=', self.periodo),
								('id_suministro', '=', suministro),
								]
				if not forzarfac:
					filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

				consumos_a_facturar = Consumos.search([filtro_consumo])
		
			else:
				#Telefonia, Celular, Internet, Sepelio, Cable
				sin_consumos = True

			if consumos_a_facturar or sin_consumos:
				#Variables varias
				dias_lectura = 0 #Para servicios sin consumo
				consumos = None
				consumos_totales  = None
			
				#TELEFONIA PADRE
				if suministro.servicio.name == 'Telefonia':

					#VENTA
					Sale = Pool().get('sale.sale')
					party = suministro.titular_id
					price_list = suministro.lista_precios
					#Buscar Pos - Ver configuracion final, por tipo de servicio
					pos = self.buscar_pos('Manual', str(suministro.servicio.name))
					
					with Transaction().set_context({"price_list": price_list, "customer": party, "dias_lectura": dias_lectura}):
						#Creamos la venta a la que le vamos a asociar las lineas de venta
						descripcion = str(suministro.titular_id.name.encode('utf-8')) + " - " + str(price_list.name.encode('utf-8'))
						sale = Sale(
								party = suministro.titular_id,
								price_list = price_list,
								description = descripcion,
								pos = pos
						)
						padre_listaprecios = price_list
						#Creamos las lineas para los distintos tipos de productos
						sale_lines = []

						#1 Cargos Fijos
						#Las lineas que no dependen del consumo, solo se crean una vez por venta
						sale_lines.extend(self.crear_sale_lines_independientes_consumo(suministro.titular_id, price_list, dias_lectura, None, suministro))
						sale.lines = sale_lines
						sale.save()
						sale_lines = []

						#2 Conceptos Especiales
						#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
						sale_lines.extend(self.crear_sale_lines_conceptos_especiales(suministro.titular_id, price_list, suministro, self.periodo, sale_lines, sale))
						sale.lines += tuple(sale_lines)
						sale.save()
						sale_lines = []

						#3 Consumos: a.urbanas b.interurbanas c.celulares d. internacionales
						Consumos = Pool().get('sigcoop_telefonia.consumo_telefonico')
						#Filtramos los consumos del periodo segun los parametros
						
						#Primero: urbano
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'urbano'),
								('bonificacion', '=', False)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_totales = None
						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, suministro.titular_id, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Segundo: urbano bonificacion
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'urbano'),
								('bonificacion', '=', True)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, party, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Tercero: interurbano
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'interurbano'),
								('bonificacion', '=', False)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, party, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Cuarto: interurbano bonificacion
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'interurbano'),
								('bonificacion', '=', True)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, party, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Quinto: celulares
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'celular'),
								('bonificacion', '=', False)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, party, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Sexto: internacional
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'internacional'),
								('bonificacion', '=', False)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, party, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Cuarto: internacional bonificacion
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
								('tipo', '=', 'internacional'),
								('bonificacion', '=', True)
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						if consumos_telefonicos:
							#Creamos las lineas que dependen de lo consumido
							for i in consumos_telefonicos:
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_telefonico(
										i.concepto, i.minutos, i.valor, party, suministro
										))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							if consumos_totales:
								consumos_totales += consumos_telefonicos
							else:
								consumos_totales = consumos_telefonicos
						#Capitalizacion
						if not suministro.exento_cta_capital:
							sale_lines.extend(self.crear_sale_line_retencion_capitalizacion(suministro.usuario_id, price_list, sale, None, suministro=suministro))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

						#PAGO FUERA DE TERMINO
						sale_lines.extend(self.crear_sale_lines_recargo_pago_fuera_de_termino(suministro, self.periodo, False))
						#ANTERIORES DEUDAS
						sale_lines.extend(self.crear_sale_lines_multiples_recargo_por_pago_fuera_de_termino(suministro, sale))
						#MORATORIA (Comentado por ahora)
						#sale_lines.extend(self.crear_sale_lines_moratoria(suministro, self.periodo))

						sale.lines += tuple(sale_lines)
						sale.save()
						sale_lines = []
						
										
						#Seteamos el estado de los consumos como facturado
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
						]
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_telefonicos = Consumos.search([filtro_consumo])
						for c in consumos_telefonicos:
							c.estado = '2'
							c.save()

						###HIJO DE TELEFONIA SOLO PUEDE SER INTERNET###

						 ##############################
						###SERVICIOS HIJOS####
						##############################

			
						Suministros = Pool().get('sigcoop_suministro.suministro')
						filtro_suministros_hijos = [
								('estado', '=', 'activo'),
								('tipo_servicio', '=', 'hijo'),
								('hijo_de_servicio', '=', suministro),
						]
						#Telefonia->Internet
						suministros_hijos = Suministros.search(filtro_suministros_hijos, order=[('servicio', 'ASC')])
													
						for suministro_hijo in suministros_hijos:
							
							#Traigo el periodo MM/AAAA - SERVICIO HIJO
							Periodo = Pool().get('sigcoop_periodo.periodo')
							periodo_hijo = Periodo.search([('periodo', '=', self.periodo.periodo), ('anio', '=', self.periodo.anio), ('category', '=',suministro_hijo.servicio.name)])
					
							dias_lectura = 0 #Para servicios sin consumo
							consumos = None
																		
							party = suministro_hijo.titular_id
							price_list = suministro_hijo.lista_precios
							
							#Sin consumos
						
							#Primero creamos las lineas
							sale_lines.extend(self.crear_sale_lines_sin_consumos(suministro_hijo, periodo_hijo[0]))
							#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
							sale_lines.extend(self.crear_sale_lines_conceptos_especiales(party, price_list, suministro_hijo, periodo_hijo[0], sale_lines, sale))
							
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

							#Capitalizacion
							if not suministro.exento_cta_capital:
								sale_lines.extend(self.crear_sale_line_retencion_capitalizacion(suministro_hijo.usuario_id, price_list, sale, None, suministro=suministro_hijo))
								sale.lines += tuple(sale_lines)
								sale.save()
								sale_lines = []


							#MORATORIA (Comentado por ahora)
							#sale_lines.extend(self.crear_sale_lines_moratoria(suministro_hijo, periodo_hijo[0]))
							
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
						
							cantidad_sin_consumo += 1

							sale.save()
											

					##############################
					###FIN HIJOS####
					##############################
			
				
				elif suministro.servicio.name == 'Telefonia Celular':
					#TELEFONIA CELULAR
					#VENTA
					Sale = Pool().get('sale.sale')
					party = suministro.titular_id
					price_list = suministro.lista_precios
					#Buscar Pos - Ver configuracion final, por tipo de servicio
					pos = self.buscar_pos('Manual', str(suministro.servicio.name))
					
					with Transaction().set_context({"price_list": price_list, "customer": party, "dias_lectura": dias_lectura}):
						#Creamos la venta a la que le vamos a asociar las lineas de venta
						descripcion = str(suministro.titular_id.name.encode('utf-8')) + " - " + str(price_list.name.encode('utf-8'))
						sale = Sale(
								party = suministro.titular_id,
								price_list = price_list,
								description = descripcion,
								pos = pos
						)
						padre_listaprecios = price_list
						#Creamos las lineas para los distintos tipos de productos
						sale_lines = []

						#1 Cargos Fijos
						#Las lineas que no dependen del consumo, solo se crean una vez por venta
						sale_lines.extend(self.crear_sale_lines_independientes_consumo(suministro.titular_id, price_list, dias_lectura, None, suministro))
						sale.lines = sale_lines
						sale.save()
						sale_lines = []

						#2 Conceptos Especiales
						#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
						sale_lines.extend(self.crear_sale_lines_conceptos_especiales(suministro.titular_id, price_list, suministro, self.periodo, sale_lines, sale))
						sale.lines += tuple(sale_lines)
						sale.save()
						sale_lines = []

						#3 Consumos: a.urbanas b.interurbanas c.celulares d. internacionales
						Consumos = Pool().get('sigcoop_telefonia_celular.consumo_celular')
						#Filtramos los consumos del periodo segun los parametros
						
						#Primero: urbano
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
						]
						
						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_totales = None
						consumos_celular = Consumos.search([filtro_consumo])
						if consumos_celular:
							#Creamos las lineas que dependen de lo consumido
							sale_lines.extend(
									self.crear_sale_lines_dependientes_consumo_celular(
									consumos_celular[0].concepto, consumos_celular[0].valor, suministro.titular_id, suministro
									))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
						
						#Seteamos el estado de los consumos como facturado
						filtro_consumo = [
								('periodo', '=', self.periodo),
								('suministro', '=', suministro),
						]

						if not forzarfac:
							filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

						consumos_celular = Consumos.search([filtro_consumo])
						for c in consumos_celular:
							c.estado = '2'
							c.save()

						##############################
						###SERVICIOS HIJOS
						##############################

			
						Suministros = Pool().get('sigcoop_suministro.suministro')
						filtro_suministros_hijos = [
								('estado', '=', 'activo'),
								('tipo_servicio', '=', 'hijo'),
								('hijo_de_servicio', '=', suministro),
						]
						#Celular
						
						
						suministros_hijos = Suministros.search(filtro_suministros_hijos, order=[('servicio', 'ASC')])
													
						for suministro_hijo in suministros_hijos:
														
							dias_lectura = 0 #Para servicios sin consumo
							consumos = None
																		
							party = suministro_hijo.titular_id
							price_list = suministro_hijo.lista_precios
							
							#1 Cargos Fijos
							#Las lineas que no dependen del consumo, solo se crean una vez por venta
							sale_lines.extend(self.crear_sale_lines_independientes_consumo(suministro_hijo.titular_id, price_list, dias_lectura, None, suministro_hijo))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

							#2 Conceptos Especiales
							#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
							sale_lines.extend(self.crear_sale_lines_conceptos_especiales(suministro_hijo.titular_id, price_list, suministro_hijo, self.periodo, sale_lines, sale))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

							#3 Consumos: a.urbanas b.interurbanas c.celulares d. internacionales
							Consumos = Pool().get('sigcoop_telefonia_celular.consumo_celular')
							#Filtramos los consumos del periodo segun los parametros
							
							#Primero: urbano
							filtro_consumo = [
									('periodo', '=', self.periodo),
									('suministro', '=', suministro_hijo),
							]
							
							if not forzarfac:
								filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

							consumos_totales = None
							consumos_celular = Consumos.search([filtro_consumo])
							if consumos_celular:
								#Creamos las lineas que dependen de lo consumido
								sale_lines.extend(
										self.crear_sale_lines_dependientes_consumo_celular(
										consumos_celular[0].concepto, consumos_celular[0].valor, suministro_hijo.titular_id, suministro_hijo
										))

								#Grabo por si se necesita la informacion
								sale.lines += tuple(sale_lines)
								sale.save()
							
							#Seteamos el estado de los consumos como facturado
							filtro_consumo = [
									('periodo', '=', self.periodo),
									('suministro', '=', suministro_hijo),
							]

							if not forzarfac:
								filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

							consumos_celular = Consumos.search([filtro_consumo])
							for c in consumos_celular:
								c.estado = '2'
								c.save()

													
							sale.lines += tuple(sale_lines)
							sale.save()
										

					##############################
					###FIN HIJOS####
					##############################
			

				else:
					#No es TELEFONIA ni CELULAR
					
					#CON CONSUMO
					#Filtramos los consumos del periodo segun los parametros
					filtro_consumo = [
							('periodo', '=', self.periodo),
							('id_suministro', '=', suministro),
					]
					if not forzarfac:
						filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

					consumos = Consumos.search(filtro_consumo, order=[('id', 'ASC')])
					
					if consumos:
						consumos_totales = consumos
						#Tomamos los dias del 1er consumo. Todos los consumos deberian tener los mismos dias.
						dias_lectura = consumos[0].dias

					#La price_lista es la del suministro
					price_list = suministro.lista_precios
					#Trato especial para T1R, T4, T1RE , T1RS y T4S

										
					if str(suministro.servicio.name) == str('Energia'):
						if suministro.lista_precios.clave == 'T1R':
							Tarifa = Pool().get('product.price_list')
							#Traigo consumo mismo periodo - anio anterior
							if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == 'COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA':
								consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
							else:
								consumo_anio_anterior = consumos[0].get_consumo_anio_2015()
							if consumo_anio_anterior:
								dias_anterior = 0
								if not consumo_anio_anterior.dias:
									dias_anterior = consumos[0].get_dias_consumos(self.periodo)
									#dias_anterior = 30
								else:
									dias_anterior = consumo_anio_anterior.dias
								if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
									consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
								else:
									consumo_diario_anterior = 0
								if consumos[0].dias > 0:
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
								else:
									consumo_diario_actual = 0
								
								if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
									diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
								else:
									diferencia = 100 #No puedo calcular ahorro

								if diferencia < float(100):
									#Hay ahorro
									if (float(100) - diferencia) > float(20):
										#Mas de 20 - Usa otra tarifa
										tarifa_estimulo = Tarifa.search([('clave','=','T1R20')])[0]
										if tarifa_estimulo:
											price_list = tarifa_estimulo
						elif suministro.lista_precios.clave == 'T1RE':
							Tarifa = Pool().get('product.price_list')
							#Traigo consumo mismo periodo - anio anterior
							if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
								consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
							else:
								consumo_anio_anterior = consumos[0].get_consumo_anio_2015()

							if consumo_anio_anterior:
								dias_anterior = 0
								if not consumo_anio_anterior.dias:
									dias_anterior = consumos[0].get_dias_consumos(self.periodo)
									#dias_anterior = 30
								else:
									dias_anterior = consumo_anio_anterior.dias
								if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
									consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
								else:
									consumo_diario_anterior = 0
								
								if consumos[0].dias > 0:
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
								else:
									consumo_diario_actual = 0
								
								if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
									diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
								else:
									diferencia = 100 #No puedo calcular ahorro

								if diferencia < float(100):
									#Hay ahorro
									if (float(100) - diferencia) > float(20):
										#Mas de 20 - Usa otra tarifa
										tarifa_estimulo = Tarifa.search([('clave','=','T1RE20')])[0]
										if tarifa_estimulo:
											price_list = tarifa_estimulo
						elif suministro.lista_precios.clave == 'T4':

							#Chequeo el IVA (tiene que ser de CF 21 - Residencial rural)
							if 'CF' in suministro.iva.name:
								Tarifa = Pool().get('product.price_list')
								#Traigo consumo mismo periodo - anio anterior
								if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
									consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
								else:
									consumo_anio_anterior = consumos[0].get_consumo_anio_2015()
								if consumo_anio_anterior:
									dias_anterior = 0
									if not consumo_anio_anterior.dias:
										dias_anterior = consumos[0].get_dias_consumos(self.periodo)
										#dias_anterior = 30
									else:
										dias_anterior = consumo_anio_anterior.dias
									
									if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
										consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
									else:
										consumo_diario_anterior = 0
								
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
									
									if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
										diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
									else:
										diferencia = 100 #No puedo calcular ahorro
								

									if diferencia < float(100):
										if (float(100) - diferencia) > float(20):
											#Mas de 20 - Usa otra tarifa
											tarifa_estimulo = Tarifa.search([('clave','=','T420')])[0]
											if tarifa_estimulo:
												price_list = tarifa_estimulo
						
						elif suministro.lista_precios.clave == 'T1RS':
							Tarifa = Pool().get('product.price_list')
							#Traigo consumo mismo periodo - anio anterior
							if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == 'COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA':
								consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
							else:
								consumo_anio_anterior = consumos[0].get_consumo_anio_2015()
							if consumo_anio_anterior:
								dias_anterior = 0
								if not consumo_anio_anterior.dias:
									dias_anterior = consumos[0].get_dias_consumos(self.periodo)
									#dias_anterior = 30
								else:
									dias_anterior = consumo_anio_anterior.dias
								if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
									consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
								else:
									consumo_diario_anterior = 0
								if consumos[0].dias > 0:
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
								else:
									consumo_diario_actual = 0
								
								if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
									diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
								else:
									diferencia = 100 #No puedo calcular ahorro

								if diferencia < float(100):
									#Hay ahorro
									if (float(100) - diferencia) > float(20):
										#Mas de 20 - Usa otra tarifa
										tarifa_estimulo = Tarifa.search([('clave','=','T1RS20')])[0]
										if tarifa_estimulo:
											price_list = tarifa_estimulo
							
						elif suministro.lista_precios.clave == 'T4S':
							Tarifa = Pool().get('product.price_list')
							#Traigo consumo mismo periodo - anio anterior
							if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == 'COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA':
								consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
							else:
								consumo_anio_anterior = consumos[0].get_consumo_anio_2015()
							if consumo_anio_anterior:
								dias_anterior = 0
								if not consumo_anio_anterior.dias:
									dias_anterior = consumos[0].get_dias_consumos(self.periodo)
									#dias_anterior = 30
								else:
									dias_anterior = consumo_anio_anterior.dias
								if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
									consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
								else:
									consumo_diario_anterior = 0
								if consumos[0].dias > 0:
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
								else:
									consumo_diario_actual = 0
								
								if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
									diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
								else:
									diferencia = 100 #No puedo calcular ahorro

								if diferencia < float(100):
									#Hay ahorro
									if (float(100) - diferencia) > float(20):
										#Mas de 20 - Usa otra tarifa
										tarifa_estimulo = Tarifa.search([('clave','=','T4S20')])[0]
										if tarifa_estimulo:
											price_list = tarifa_estimulo

							
						#ELECTRODEPENDIENTES
						elif suministro.lista_precios.clave == 'T1RSELE':
							
							Tarifa = Pool().get('product.price_list')
							#Chequeo consumo actual
							#<=600 queda la price_list actual
							if consumos[0].consumo_neto > float(600):
								#Traigo consumo mismo periodo - anio anterior
								if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
									consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
								else:
									consumo_anio_anterior = consumos[0].get_consumo_anio_2015()
								if consumo_anio_anterior:
									dias_anterior = 0
									if not consumo_anio_anterior.dias:
										dias_anterior = consumos[0].get_dias_consumos(self.periodo)
										#dias_anterior = 30
									else:
										dias_anterior = consumo_anio_anterior.dias
									
									if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
										consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
									else:
										consumo_diario_anterior = 0
																	
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
									
									if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
										diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
									else:
										diferencia = 100 #No puedo calcular ahorro

									if diferencia < float(100):
										#Hay estimulo
										tarifa_estimulo = Tarifa.search([('clave','=','T1RSELE600E')])[0]
										if tarifa_estimulo:
											price_list = tarifa_estimulo
									else:
										#Hay recargo
										tarifa = Tarifa.search([('clave','=','T1RSELE600')])[0]
										if tarifa:
											price_list = tarifa
								else:
									#Hay recargo
									tarifa = Tarifa.search([('clave','=','T1RSELE600')])[0]
									if tarifa:
										price_list = tarifa

						#ELECTRODEPENDIENTES RURALES
						elif suministro.lista_precios.clave == 'T4SELE':
							
							Tarifa = Pool().get('product.price_list')
							#Chequeo consumo actual
							#<=600 queda la price_list actual
							if consumos[0].consumo_neto > float(600):
								#Traigo consumo mismo periodo - anio anterior
								if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
									consumo_anio_anterior = consumos[0].get_consumo_anio_anterior()
								else:
									consumo_anio_anterior = consumos[0].get_consumo_anio_2015()
								if consumo_anio_anterior:
									dias_anterior = 0
									if not consumo_anio_anterior.dias:
										dias_anterior = consumos[0].get_dias_consumos(self.periodo)
										#dias_anterior = 30
									else:
										dias_anterior = consumo_anio_anterior.dias
									
									if consumo_anio_anterior.consumo_neto > Decimal('0') and dias_anterior > 0:
										consumo_diario_anterior = float(consumo_anio_anterior.consumo_neto/dias_anterior)
									else:
										consumo_diario_anterior = 0
																	
									consumo_diario_actual = float(consumos[0].consumo_neto/consumos[0].dias)
									
									if consumo_diario_anterior > Decimal('0') and dias_anterior > 0:
										diferencia = float(consumo_diario_actual * 100) / float(consumo_diario_anterior)
									else:
										diferencia = 100 #No puedo calcular ahorro

									if diferencia < float(100):
										#Hay estimulo
										tarifa_estimulo = Tarifa.search([('clave','=','T4SELE600E')])[0]
										if tarifa_estimulo:
											price_list = tarifa_estimulo
									else:
										#Hay recargo
										tarifa = Tarifa.search([('clave','=','T4SELE600')])[0]
										if tarifa:
											price_list = tarifa
								else:
									#Hay recargo
									tarifa = Tarifa.search([('clave','=','T4SELE600')])[0]
									if tarifa:
										price_list = tarifa	

					
					#PADRE AGUA
					if str(suministro.servicio.name) == str('Agua'):
						if company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
							#Agua y consumo cero => paso la tarifa a medio abono
							Tarifa = Pool().get('product.price_list')
							if float(consumos[0].consumo_neto) == float(0):
								tarifa = Tarifa.search([('clave','=','MAGU')])[0]
								if tarifa:
									price_list = tarifa


					#VENTA
					Sale = Pool().get('sale.sale')
					party = suministro.titular_id
					#Buscar Pos - Ver configuracion final, por tipo de servicio
					pos = self.buscar_pos('Manual', str(suministro.servicio.name))
					
					with Transaction().set_context({"price_list": price_list, "customer": party, "dias_lectura": dias_lectura}):
						#Creamos la venta a la que le vamos a asociar las lineas de venta
						descripcion = str(party.name.encode('utf-8')) + " - " + str(price_list.name.encode('utf-8'))
						sale = Sale(
								party = party,
								price_list = price_list,
								description = descripcion,
								pos = pos
						)

						padre_listaprecios = price_list
						#Creamos las lineas para los distintos tipos de productos
						sale_lines = []

						if consumos:
							#Las lineas que no dependen del consumo, solo se crean una vez por venta (le paso consumos para calcularlos para T1G, T3BT, T3MT)
							sale_lines.extend(self.crear_sale_lines_independientes_consumo(party, price_list, dias_lectura, consumos, suministro))
							sale.lines = sale_lines
							sale.save()
							sale_lines = []


							
							#Creamos las lineas que dependen de lo consumido
							for i in consumos:
								if suministro.servicio.name == 'Energia':
									concepto_riestra = i.concepto
								if i.adicionar_consumo:
									sale_lines.extend(
											self.crear_sale_lines_dependientes_consumo(
											i.concepto, i.consumo_neto + i.consumo_adic, party, price_list, suministro
											))
								else:
									#SAN MANUEL
									if suministro.servicio.name == 'Agua':
										sale_lines.extend(
														self.crear_sale_lines_dependientes_consumo(
														i.concepto, i.consumo_neto, party, price_list, suministro
														))
										if company == "COOPERATIVA ELECTRICA DE SM":
											if float(i.consumo_neto) > float(11):
												excedente = float(i.consumo_neto) - float(11)
												excedente = int(excedente)
												if excedente > 0:
													#Funcion para excedente
													sale_lines.extend(self.crear_sale_line_excedente_agua(suministro, excedente))

									else:
														
										sale_lines.extend(
												self.crear_sale_lines_dependientes_consumo(
												i.concepto, i.consumo_neto, party, price_list, suministro
												))

							#Grabo por si se necesita la informacion
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []


							#Lineas sin impuestos
							sale_lines.extend(self.crear_sale_lines_sin_impuestos(party, price_list, sale, suministro=suministro))
							#Grabo por el CARGO FIJO
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

							if company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
								#Solo SAN BLAS, descuento patagonico
								#Lineas sin impuestos
								sale_lines.extend(self.crear_sale_lines_sin_impuestos_variables(party, price_list, sale, suministro=suministro))
								#Grabo por el CARGO FIJO
								sale.lines += tuple(sale_lines)
								sale.save()
								sale_lines = []

							
							#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
							sale_lines.extend(self.crear_sale_lines_conceptos_especiales(party, price_list, suministro, self.periodo, sale_lines, sale))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

							
							#Bonificacion CCT Riestra
							if company == 'Cooperativa Electrica Limitada Norberto de la Riestra':
								sale_lines.extend(self.crear_sale_line_bonificacion_riestra(party, price_list, suministro, consumos, sale_lines, sale, concepto_riestra))
								sale.lines += tuple(sale_lines)
								sale.save()
								sale_lines = []

							#Bonificacion CCT Colina
							if company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
								sale_lines.extend(self.crear_sale_line_bonificacion_colina(party, price_list, suministro, consumos, sale_lines, sale, concepto_riestra))
								sale.lines += tuple(sale_lines)
								sale.save()
								sale_lines = []
								
							#Diferencial RIESTRA
							#if company == 'Cooperativa Electrica Limitada Norberto de la Riestra':
							#    sale_lines.extend(self.crear_sale_line_diferencial_10(suministro, sale))

							#SOLAMENTE SI LA FECHA DE ALTA ES ANTERIOR AL 30 de JUNIO						
							if suministro.fecha_alta <= datetime.datetime.strptime('30062017', '%d%m%Y').date():
								#DIFERENCIAL DEL 20% del NETO
								if suministro.servicio.name =='Energia':								
									if company == 'Cooperativa Electrica Limitada Norberto de la Riestra' or company == 'COOPERATIVA ELECTRICA DE CHASICO LIMITADA':
										sale_lines.extend(self.crear_sale_line_diferencial_10(suministro, sale))
										sale.lines += tuple(sale_lines)
										sale_lines = []								
									else: 				
										if company != "COOPERSIVE LTDA.":
											sale_lines.extend(self.crear_sale_line_diferencial_20(suministro, sale))            										
											sale.lines += tuple(sale_lines)
											sale_lines = []
								

							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							sale.save()

							
							#Capitalizacion
							if not suministro.exento_cta_capital:
								sale_lines.extend(self.crear_sale_line_retencion_capitalizacion(suministro.usuario_id, price_list, sale, consumos, suministro=suministro ))
								sale.lines += tuple(sale_lines)
								sale.save()
								sale_lines = []
							
							#Alumbrado Publico
							if str(suministro.servicio.name) == str('Energia'):
								#SAN MANUEL y T1RS no se crea ALUMBRADO
								if company == "COOPERATIVA ELECTRICA DE SM" or company == "COOPERATIVA ELECTRICA DE SM " or company == "COOPERATIVA ELECTRICA Y SERVICIOS ANEXOS DE SAN MANUEL LTDA":
									if suministro.lista_precios.clave != 'T1RS':
										sale_lines.extend(self.crear_sale_line_alumbrado_publico(party, price_list, suministro, consumos, sale.lines, sale))
								else:
									sale_lines.extend(self.crear_sale_line_alumbrado_publico(party, price_list, suministro, consumos, sale.lines, sale))
								sale.lines += tuple(sale_lines)
								sale.save()
								sale_lines = []
																																			
							
							if not suministro.titular_id.es_gobierno:
								#PAGO FUERA DE TERMINO
								sale_lines.extend(self.crear_sale_lines_recargo_pago_fuera_de_termino(suministro, self.periodo, False))
								#ANTERIORES DEUDAS
								sale_lines.extend(self.crear_sale_lines_multiples_recargo_por_pago_fuera_de_termino(suministro, sale))
												  						
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []

							#PUREE
							#if str(suministro.servicio.name) == str('Energia'):
							#    sale_lines.extend(self.crear_sale_lines_puree(suministro, self.periodo))

							#MORATORIA (Comentado por ahora)
							#sale_lines.extend(self.crear_sale_lines_moratoria(suministro, self.periodo))

							
							#Seteamos el estado de los consumos como facturado
							for c in consumos:
								c.estado = '2'
								c.save()

							


						else:
							#Sin consumos

						
							#Primero creamos las lineas
							sale_lines.extend(self.crear_sale_lines_sin_consumos(suministro, self.periodo))
							sale.lines = sale_lines
							sale.save()
							sale_lines = []
							#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
							sale_lines.extend(self.crear_sale_lines_conceptos_especiales(party, price_list, suministro, self.periodo, sale_lines, sale))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							#PAGO FUERA DE TERMINO
							sale_lines.extend(self.crear_sale_lines_recargo_pago_fuera_de_termino(suministro, self.periodo,  True))
							#ANTERIORES DEUDAS
							sale_lines.extend(self.crear_sale_lines_multiples_recargo_por_pago_fuera_de_termino(suministro, sale))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							
							#Capitalizacion
							if not suministro.exento_cta_capital:
								sale_lines.extend(self.crear_sale_line_retencion_capitalizacion(suministro.usuario_id, price_list, sale, None,  suministro=suministro))
								sale.lines += tuple(sale_lines)
								sale_lines = []
							
							#MORATORIA (Comentado por ahora)
							#sale_lines.extend(self.crear_sale_lines_moratoria(suministro, self.periodo))
							sale.lines += tuple(sale_lines)
							sale.save()
							sale_lines = []
							
							cantidad_sin_consumo += 1

							sale.save()
										

						
						

						##############################
						###SERVICIOS HIJOS####
						##############################
						Suministros = Pool().get('sigcoop_suministro.suministro')
						filtro_suministros_hijos = [
								('estado', '=', 'activo'),
								('tipo_servicio', '=', 'hijo'),
								('hijo_de_servicio', '=', suministro),
						]
						#Orden Ideal: Energia->Agua->Cable->Servicios Sociales
						#o Telefonia->Internet
						suministros_hijos = Suministros.search(filtro_suministros_hijos, order=[('servicio', 'ASC')])
						
						
					
						
						if suministros_hijos:
							
							#Si es RIESTRA, busco hijos pero para agregar adicional, no para facturarlo como hijo
							if company == 'Cooperativa Electrica Limitada Norberto de la Riestra':
								#ENERGIA CON INTERNET HIJO
								for suministro_hijo in suministros_hijos:
									#Tomar el nombre y valor del producto segun nombre de Tarifa del suministro
									#Si tiene adicionales, sumarselo al costo del producto
									#Agregar esa sola linea
									#En conceptos especiales exceptuar Adicional Internet
									
									sale_lines.extend(self.crear_sale_line_internet_con_iva(suministro_hijo, sale, suministro))
									sale.lines += tuple(sale_lines)
									sale_lines = []
									sale.save()
							else:
								for suministro_hijo in suministros_hijos:
									
									#Traigo el periodo MM/AAAA - SERVICIO HIJO
									Periodo = Pool().get('sigcoop_periodo.periodo')
									periodo_hijo = Periodo.search([('periodo', '=', self.periodo.periodo), ('anio', '=', self.periodo.anio), ('category', '=',suministro_hijo.servicio.name)])
							
									dias_lectura = 0 #Para servicios sin consumo
									consumos = None
										
									Consumos = Pool().get('sigcoop_consumos.consumo')
									#Filtramos los consumos del periodo segun los parametros
									filtro_consumo = [
											('periodo', '=', periodo_hijo[0]),
											('id_suministro', '=', suministro_hijo),
									]
									if not forzarfac:
										filtro_consumo.append(('estado', '=', '1')) #Estado 1 es facturable.

									consumos = Consumos.search(filtro_consumo, order=[('id', 'ASC')])
									if consumos:
										if consumos_totales:
											consumos_totales += consumos
										else:
											consumos_totales = consumos
										#Tomamos los dias del 1er consumo. Todos los consumos deberian tener los mismos dias.
										dias_lectura = consumos[0].dias
							
									party = suministro_hijo.titular_id
									price_list = suministro_hijo.lista_precios

									if consumos:

										#HIJO AGUA - VILLA IRIS
										if str(suministro_hijo.servicio.name) == str('Agua'):											
											if company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
												#Agua y consumo cero => paso la tarifa a medio abono
												Tarifa = Pool().get('product.price_list')
												if float(consumos[0].consumo_neto) == float(0):
													tarifa = Tarifa.search([('clave','=','MAGU')])[0]
													if tarifa:
														price_list = tarifa				

										#Las lineas que no dependen del consumo, solo se crean una vez por venta (le paso consumos para calcularlos para T1G, T3BT, T3MT)
										sale_lines.extend(self.crear_sale_lines_independientes_consumo(party, price_list, dias_lectura, consumos, suministro_hijo))
										sale.lines += tuple(sale_lines)
										sale.save()
										sale_lines = []
												
									
										#Creamos las lineas que dependen de lo consumido
										for i in consumos:
											if i.adicionar_consumo:
												sale_lines.extend(
													self.crear_sale_lines_dependientes_consumo(
													i.concepto, i.consumo_neto + i.consumo_adic, party, price_list, suministro_hijo
													))
											else:
												sale_lines.extend(
													self.crear_sale_lines_dependientes_consumo(
													i.concepto, i.consumo_neto, party, price_list, suministro_hijo
													))
											

										#Grabo por si se necesita la informacion
										sale.lines += tuple(sale_lines)
										sale.save()
										sale_lines = []


										#Lineas sin impuestos
										sale_lines.extend(self.crear_sale_lines_sin_impuestos(party, price_list, sale, suministro=suministro_hijo))
										#Grabo por el CARGO FIJO
										sale.lines += tuple(sale_lines)
										sale.save()
										sale_lines = []
										
										#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
										sale_lines.extend(self.crear_sale_lines_conceptos_especiales(party, price_list, suministro_hijo, periodo_hijo[0], sale_lines, sale))
										sale.lines += tuple(sale_lines)
										sale.save()
										sale_lines = []
										
										#Capitalizacion
										if not suministro.exento_cta_capital:
											sale_lines.extend(self.crear_sale_line_retencion_capitalizacion(suministro_hijo.usuario_id, price_list, sale, None, suministro=suministro_hijo))
										
										if str(suministro_hijo.servicio.name) == str('Energia'):
											#Alumbrado Publico
											sale_lines.extend(self.crear_sale_line_alumbrado_publico(party, price_list, suministro_hijo, consumos, sale.lines, sale))
									
																		
										#MORATORIA (Comentado por ahora)
										#sale_lines.extend(self.crear_sale_lines_moratoria(suministro_hijo, periodo_hijo[0]))

										sale.lines += tuple(sale_lines)
										sale_lines = []
															
										sale.save()

										#Seteamos el estado de los consumos como facturado
										for c in consumos:
											c.estado = '2'
											c.save()

									else:
										#Sin consumos
										#Primero creamos las lineas
										sale_lines.extend(self.crear_sale_lines_sin_consumos(suministro_hijo, periodo_hijo[0]))
										#CONCEPTOS O BONIFICACIONES ESPECIALES (VER LISTADO POSIBLE)
										sale_lines.extend(self.crear_sale_lines_conceptos_especiales(party, price_list, suministro_hijo, periodo_hijo[0], sale_lines, sale))
									
										sale.lines += tuple(sale_lines)
										sale.save()
										sale_lines = []
										#Capitalizacion
										if not suministro.exento_cta_capital:
											sale_lines.extend(self.crear_sale_line_retencion_capitalizacion(suministro_hijo.usuario_id, price_list, sale, None, suministro=suministro_hijo))
											
											sale.lines += tuple(sale_lines)
											sale_lines = []
									
										#MORATORIA (Comentado por ahora)
										#sale_lines.extend(self.crear_sale_lines_moratoria(suministro_hijo, periodo_hijo[0]))
										
											sale.lines += tuple(sale_lines)
											sale_lines = []
									

										cantidad_sin_consumo += 1

										sale.save()
											

					##############################
					###FIN HIJOS####
					##############################


				
									

				sale.save()

				#PERCEPCIONES IIBB
				percepcion = 0
				if company == 'COOPERATIVA ELECTRICA DE SM':
					if suministro.iva:
						if ('IVA RI' in suministro.iva.name) or ('IVA RMT' in suministro.iva.name) or ('IVA NO CAT' in suministro.iva.name):
							if len(sale.party.vat_number)==11:
								get_percepcion = self.percepcion_iibb(sale.party.vat_number)
								#el CUIT existe en el padron se aplica la alicuota correspondiente
								#segun el padron vigente en la base de datos.
								if (get_percepcion!=None and len(get_percepcion)==1):
									if get_percepcion[0]>0:
										percepcion = get_percepcion[0]
									else:
										percepcion = 0
								
								#el CUIT no existe en el padron se lo penaliza
								#con el 8% de multa. (multa por no figurar en el padron jaja)
								else:
									percepcion = 8

							
				#IMPUESTOS - SE LLAMA UNA SOLA VEZ
				#Aplicamos los impuestos que correspondan a cada linea de venta y los del suministro-usuarios
				Tax = Pool().get('account.tax')
				for i in sale.lines:
					#Revisar CAMPO exento_leyes_prov para no agregar leyes provinciales
					up = i.unit_price
					tax_ids = i.on_change_product().get("taxes")#lista de ids
					if i.product.calcular_por_dia:
						i.unit_price = i.amount
					i.unit_price = up
					tax_browse_records = Tax.browse(tax_ids) or []
					extra_tax_browse_records = self.get_extra_taxes(i.product, suministro, party, i.servicio, percepcion)
					i.taxes = tuple(tax_browse_records) + tuple(extra_tax_browse_records)
					i.save()

					
				if company == 'Cooperativa Electrica Limitada Norberto de la Riestra':
					sale_lines.extend(self.crear_sale_line_ajuste(suministro, sale))
					sale.lines += tuple(sale_lines)
					sale_lines = []
					sale.save()
				

				#Avanzamos a presupuesto
				sale.invoice_address = sale.party.address_get(type='invoice')
				sale.shipment_address = sale.party.address_get(type='delivery')
				sale.quote([sale])


				#Avanzamos a confirmado
				sale.confirm([sale])


				#Controlo que no sea menor a cero el total
				if sale.total_amount >= Decimal('0'):
					#Avanzamos a procesado. En este estado se crea la factura
					#de la venta.
					    					
					sale.process([sale])

					#Luego de ejecutar el workflow de la venta, la guardamos.
					sale.save()
								
					#Seteamos las fechas de creacion, vencimiento de la factura y recargo por vencimiento.
					#Tambien seteamos el suministro.
					hoy = datetime.date.today()
					if sale.invoices:
						#import pudb;pu.db
						sale.invoices[0].percepcioniibb = percepcion
						sale.invoices[0].lista_precios = padre_listaprecios
						sale.invoices[0].periodo = self.periodo
						sale.invoices[0].invoice_date = self.fecha_emision_factura
						sale.invoices[0].fecha_vencimiento_proxima_factura = self.fecha_vencimiento_proxima_factura
						sale.invoices[0].vencimiento_1 = self.fecha_vencimiento_1
						sale.invoices[0].vencimiento_2 = self.fecha_vencimiento_2
						#REVISAR
						if company == "COOPERATIVA ELECTRICA DE CHASICO LIMITADA":
							recargo_vencimiento = Decimal('0')
						else:
							recargo_vencimiento = Decimal(self.calcular_recargo_vencimiento(self.fecha_vencimiento_1, self.fecha_vencimiento_2,  sale.invoices[0]))
						sale.invoices[0].recargo_vencimiento = recargo_vencimiento
						recargo_solo = Decimal(recargo_vencimiento) / Decimal(1.21)
						recargo_solo = Decimal(recargo_solo).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						recargo_iva = recargo_vencimiento - recargo_solo
						sale.invoices[0].iva_recargo_vencimiento = Decimal(recargo_iva).quantize(Decimal(".01"), rounding=ROUND_DOWN)
						
						#Le cargo el Suministro Padre a la factura
						sale.invoices[0].suministro = suministro
						sale.invoices[0].pos = pos
												
						invoice_type_ret = sale.invoices[0].on_change_pos()["invoice_type"]
						if suministro.servicio.name=='Energia' or suministro.servicio.name=='Agua':
							if company == "COOPERATIVA ELECTRICA DE SM":
								#SM
								if suministro.servicio.name=='Energia':
									if invoice_type_ret == 1:
										sale.invoices[0].invoice_type = 17
									elif invoice_type_ret == 2:
										sale.invoices[0].invoice_type = 18
								elif suministro.servicio.name=='Agua':
									if invoice_type_ret == 5:
										sale.invoices[0].invoice_type = 19
									elif invoice_type_ret == 6:
										sale.invoices[0].invoice_type = 20
							elif company == "COOPERSIVE LTDA.":
								#SIERRA
								if invoice_type_ret == 2:
									sale.invoices[0].invoice_type = 6
								elif invoice_type_ret == 1:
									sale.invoices[0].invoice_type = 5
							elif company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
								#COLINA
								if invoice_type_ret == 3:
									sale.invoices[0].invoice_type = 1
								elif invoice_type_ret == 4:
									sale.invoices[0].invoice_type = 2
							
							elif company == "Cooperativa Electrica Limitada Norberto de la Riestra":
								#RIESTRA
								if invoice_type_ret == 2:
									sale.invoices[0].invoice_type = 6
								elif invoice_type_ret == 1:
									sale.invoices[0].invoice_type = 5
							elif company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
								#SANBLAS
								if invoice_type_ret == 14:
									sale.invoices[0].invoice_type = 2
								elif invoice_type_ret == 13:
									sale.invoices[0].invoice_type = 1
							elif company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
								#VILLA IRIS
								if invoice_type_ret == 16:
									sale.invoices[0].invoice_type = 2
								elif invoice_type_ret == 15:
									sale.invoices[0].invoice_type = 1
							elif company == "COOPERATIVA ELECTRICA DE CHASICO LIMITADA":
								#CHASICO
								if invoice_type_ret == 1:
									sale.invoices[0].invoice_type = 3
								elif invoice_type_ret == 2:
									sale.invoices[0].invoice_type = 4
							elif company == 'COOPERATIVA DE PROVISION DE SERVICIOS PUBLICOS, VIVIENDA Y SERVICIOS SOCIALES DE COPETONAS LIMITADA':
								#COPETONAS
								if invoice_type_ret == 1:
									sale.invoices[0].invoice_type = 3
								elif invoice_type_ret == 2:
									sale.invoices[0].invoice_type = 4
							elif company == "Cooperativa ELECTRICA Ltda. de GOYENA":
								#GOYENA
								if invoice_type_ret == 1:
									sale.invoices[0].invoice_type = 3
								elif invoice_type_ret == 2:
									sale.invoices[0].invoice_type = 4
						else:
							sale.invoices[0].invoice_type = sale.invoices[0].on_change_pos()["invoice_type"]
						
					
						#Numero de CESP
						if self.numerocesp:
							sale.invoices[0].numerocesp = self.numerocesp
						sale.invoices[0].save()

						if consumos_totales:
							self.asociar_invoice_consumo(sale.invoices[0], consumos_totales)
						self.asociar_invoice_leyendas(sale.invoices[0])
						sale.invoices[0].save()

						
						try:
							codigo = ''
							descri = ''
							estadoa = 'OK'
							#Confirmo la factura
							if company == "COOPERATIVA ELECTRICA DE SM":
								if (suministro.servicio.name == 'Energia' or suministro.servicio.name == 'Agua'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == "COOPERSIVE LTDA." or company == "COOPERATIVA DE ELECTRICIDAD Y SERVICIOS ANEXOS LA COLINA LIMITADA":
								if (suministro.servicio.name == 'Energia'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == "Cooperativa Electrica Limitada Norberto de la Riestra":
								if (suministro.servicio.name == 'Energia'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
								if (suministro.servicio.name == 'Energia'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == "COOPERATIVA DE ELECTRICIDAD, SERVICIOS, OBRAS PUBLICAS, VIVIENDA Y CREDITO DE VILLA IRIS LIMITADA":
								if (suministro.servicio.name == 'Energia' or suministro.servicio.name == 'Agua'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == "COOPERATIVA ELECTRICA DE CHASICO LIMITADA":
								if (suministro.servicio.name == 'Energia'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == 'COOPERATIVA DE PROVISION DE SERVICIOS PUBLICOS, VIVIENDA Y SERVICIOS SOCIALES DE COPETONAS LIMITADA':                                                        							
								if (suministro.servicio.name == 'Energia'):
									sale.invoices[0].post([sale.invoices[0]])
							elif company == "Cooperativa ELECTRICA Ltda. de GOYENA":
								if (suministro.servicio.name == 'Energia'  or suministro.servicio.name == 'Agua'):
									sale.invoices[0].post([sale.invoices[0]])
							else:
								pass
																		
						except Exception, e:
							codigo = ''
							descri = e.message
							estadoa = 'Error'

								
						User = Pool().get('res.user')
						user = User(Transaction().user)
						RegistroFacturacion = Pool().get('sigcoop_wizard_ventas.registro_facturacion')

						registrofacturacion = RegistroFacturacion(
							suministro = suministro,
							ruta = suministro.ruta,
							periodo = self.periodo,
							operador = user,
							estado = estadoa,
							codigo = str(codigo),
							mensaje = str(descri),
							)
						registrofacturacion.save()

						Controlfac = Pool().get('sigcoop_wizard_ventas.registro_control')
						controlfac = Controlfac.search([('controlid','=','0')])
					
						regi = controlfac[0].posicion + 1
						controlfac[0].posicion = regi
						controlfac[0].save()

						os.system('clear')
						print 'Generando Factura al Suministro', suministro.name
						print 'Titular:',suministro.titular_id.name
						print 'Estado', estadoa
						print 'Ruta', suministro.ruta
						print '\n'
						
						self.progress(regi, controlfac[0].totalreg+1, status='Facturacion completada.')
						
						Transaction().cursor.commit()


				else:
					User = Pool().get('res.user')
					user = User(Transaction().user)
					RegistroFacturacion = Pool().get('sigcoop_wizard_ventas.registro_facturacion')

					registrofacturacion = RegistroFacturacion(
						suministro = suministro,
						ruta = suministro.ruta,
						periodo = self.periodo,
						operador = user,
						estado = "Error",
						codigo = '',
						mensaje = "El total de la factura es menor a cero:" + str(sale.total_amount),
						)
					registrofacturacion.save()

				self.actualizar_resumen_importacion(sale)

		return self.get_resumen_creacion()
 

	

	def percepcion_iibb(self, cuit):
		sql = '''SELECT alicuota from percepciones
				 where cuit = \'%s\'
		''' % (cuit)
		cur.execute(sql)
		return cur.fetchone()



	def progress(self, count, total, status=''):
		bar_len = 60
		filled_len = int(round(bar_len * count / float(total)))

		percents = round(100.0 * count / float(total), 1)
		bar = '=' * filled_len + '-' * (bar_len - filled_len)

		sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
		sys.stdout.flush()
		