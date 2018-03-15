#-*- coding: utf-8 -*-
from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
import datetime
from decimal import Decimal


class AutorizarFeStart(ModelView):
    'Autorizar Fe Start'
    __name__ = 'sigcoop_wizard_ventas.autorizarfe.start'
    fecha_emision = fields.Date('Fecha Emision')
    pos = fields.Many2One('account.pos', 'Punto de Venta',
        required=True, domain=([('pos_type', '=', 'electronic')]))
    errorfe = fields.Boolean('Incluir Facturas en Error')

 

class AutorizarFe(Wizard):
    'Autorizar Fe'
    __name__ = 'sigcoop_wizard_ventas.autorizarfe'

    start = StateView('sigcoop_wizard_ventas.autorizarfe.start',
        'sigcoop_wizard_ventas.autorizarfe_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Autorizar Comprobantes', 'autorizar', 'tryton-ok', default=True),
            ])
 
    autorizar = StateTransition()


    def transition_autorizar(self):
        self.solictarcae()
        return 'end'


    def confirmarfac(self, factura):
        pool = Pool()
        Invoices = pool.get('account.invoice')
        invoice = Invoices.search([('id','=', factura)])[0]
 
        #try:
        #    invoice.post([invoice])
        #except Exception, e:
        #    pass

        invoice.post([invoice])

        Transaction().cursor.commit()



    def solictarcae(self):
        """
        Company = Pool().get('company.company')
        company = Company(Transaction().context.get('company')).party.name
        Pos = Pool().get('account.pos')
        if company=="COOPERATIVA ELECTRICA DE SM" or company == "COOPERATIVA ELECTRICA DE SM " or company == "COOPERATIVA ELECTRICA Y SERVICIOS ANEXOS DE SAN MANUEL LTDA":
            pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 8)])
        elif company == "COOPERSIVE LTDA.":
            pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 4)])
        elif company == "Cooperativa Electrica Limitada Norberto de la Riestra":
            pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 6)])
        elif company == "COOPERATIVA LIMITADA DE CONSUMO POPULAR DE ELECTRICIDAD Y SERVICIOS ANEXOS DE BAHIA SAN BLAS":
            pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 3)])
        else:
            self.raise_user_error('No esta definido el punto de venta electronico para la cooperativa actual.')
        """

        query = '''SELECT id from account_invoice
                    where state in ('draft','validated')
                    and type in ('out_invoice', 'out_credit_note')
                '''

 
        query += '''and pos = \'%s\' ''' % (self.start.pos.id)

        if self.start.fecha_emision:
            query += '''and invoice_date = \'%s\' ''' % (self.start.fecha_emision)

        if not self.start.errorfe:
            query += '''and (resultado_fe = false or resultado_fe is null) '''

        cursor = Transaction().cursor
        cursor.execute(query)
        invoices = cursor.fetchall()
 

        for item in invoices:
            try:
                self.confirmarfac(item[0])
            except Exception as e:
                self.raise_user_error('Error autorizando factura id: ' + str(item[0]))

            