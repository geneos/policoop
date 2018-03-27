# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2017 Luis Falcon <falcon@gnu.org>
#    Copyright (C) 2011-2017 GNU Solidario <health@gnusolidario.org>
#
#    MODULE : Emergency Management
# 
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
#
#
# The documentation of the module goes in the "doc" directory.

from datetime import datetime, timedelta, date

from trytond import backend
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal
from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique, Check
from trytond.pool import Pool
from trytond.transaction import Transaction


__all__ = [
    'PolicoopSequences','TransportRequest', 'AmbulanceTransport',
    'TransportHealthProfessional', 'InventoryLine']

class PolicoopSequences(ModelSingleton, ModelSQL, ModelView):
    "Standard Sequences for Policoop"
    __name__ = "policoop.sequences"

    transport_request_code_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Transport Request Sequence', 
        domain=[('code', '=', 'policoop.transport_request')],
        required=True))

class TransportRequest(ModelSQL, ModelView):
    'Transport Request Registration'
    __name__ = 'policoop.transport_request'
    _rec_name = 'code'

    code = fields.Char('Code',help='Request Code', readonly=True)

    operator = fields.Many2One(
        'gnuhealth.healthprofessional', 'Operator',
        help="Operator who took the call / support request")

    requestor = fields.Many2One('party.party', 'Requestor',
    domain=[('is_person', '=', True)], help="Related party (person)")

    patient = fields.Many2One('gnuhealth.patient', 'Patient')

    request_date = fields.DateTime('Date', required=True,
        help="Date and time of the call for help")

    return_date = fields.DateTime('Return_date', required=True,
        help="Date and time of return")
    
    latitude = fields.Numeric('Latidude', digits=(3, 14))
    longitude = fields.Numeric('Longitude', digits=(4, 14))

    address = fields.Text("Address", help="Free text address / location")
    urladdr = fields.Char(
        'OSM Map',
        help="Maps the location on Open Street Map")
   
    place_occurrance = fields.Selection([
        (None, ''),
        ('home', 'Home'),
        ('street', 'Street'),
        ('institution', 'Institution'),
        ('school', 'School'),
        ('commerce', 'Commercial Area'),
        ('recreational', 'Recreational Area'),
        ('transportation', 'Public transportation'),
        ('sports', 'Sports event'),
        ('publicbuilding', 'Public Building'),
        ('unknown', 'Unknown'),
        ('urbanzone', 'Urban Zone'),
        ('ruralzone', 'Rural zone'),
        ], 'Origin', help="Place of occurrance",sort=False)

    event_type = fields.Selection([
        (None, ''),
        ('event1', 'Zonal'),
        ('event2', 'Urbano'),
        ], 'Event type')

    service_type = fields.Selection([
        (None, ''),
        ('event1', 'Alta'),
        ('event2', 'Internación'),
        ], 'Tipo de Servicio')

    escort = fields.Text("Acompañante", help="Persona que acompaña al afectado en la ambulancia / Descripción o relación")

    wait = fields.Selection([
        (None, ''),
        ('event1', 'Si'),
        ('event2', 'No'),
        ], '¿Con espera?', help="¿La ambulancia se queda esperando en el lugar?")

    ambulances = fields.One2Many(
        'policoop.ambulance.transport', 'sr',
        'Ambulances', help='Ambulances requested in this Support Request')

    request_extra_info = fields.Text('Details')

    state = fields.Selection([
        (None, ''),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ], 'State', sort=False, readonly=True)

    lines = fields.One2Many(
        'policoop.transport.line', 'inventory', 'Lines')
 
    @staticmethod
    def default_request_date():
        return datetime.now()

    @staticmethod
    def default_operator():
        pool = Pool()
        HealthProf= pool.get('gnuhealth.healthprofessional')
        operator = HealthProf.get_health_professional()
        return operator

    @staticmethod
    def default_state():
        return 'open'


    @fields.depends('latitude', 'longitude')
    def on_change_with_urladdr(self):
        # Generates the URL to be used in OpenStreetMap
        # The address will be mapped to the URL in the following way
        # If the latitud and longitude of the Accident / Injury 
        # are given, then those parameters will be used.

        ret_url = ''
        if (self.latitude and self.longitude):
            ret_url = 'http://openstreetmap.org/?mlat=' + \
                str(self.latitude) + '&mlon=' + str(self.longitude)

        return ret_url

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('policoop.sequences')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                config = Config(1)
                values['code'] = Sequence.get_id(
                    config.transport_request_code_sequence.id)

        return super(TransportRequest, cls).create(vlist)


    @classmethod
    def __setup__(cls):
        super(TransportRequest, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_uniq', Unique(t,t.code), 
            'This Request Code already exists'),
        ]

        cls._buttons.update({
            'open_support': {'invisible': Equal(Eval('state'), 'open')},
            'close_support': {'invisible': Equal(Eval('state'), 'closed')},
            })


    @classmethod
    @ModelView.button
    def open_support(cls, srs):
        cls.write(srs, {
            'state': 'open'})

    @classmethod
    @ModelView.button
    def close_support(cls, srs):
        cls.write(srs, {
            'state': 'closed'})


class AmbulanceTransport(ModelSQL, ModelView):
    'Ambulance associated to a Transport Request'
    __name__ = 'policoop.ambulance.transport'

    sr = fields.Many2One('policoop.transport_request',
        'SR', help="Transport Request", required=True)

    ambulance = fields.Many2One('gnuhealth.ambulance','Ambulance',
        domain=[('state', '=', 'available')],)
    
    healthprofs = fields.One2Many('policoop.transport_hp','name',
        'Health Professionals')

    @classmethod
    def __setup__(cls):
        super(AmbulanceTransport, cls).__setup__()


class TransportHealthProfessional(ModelSQL, ModelView):
    'Transport Health Professionals'
    __name__ = 'policoop.transport_hp'

    name = fields.Many2One('policoop.ambulance.transport', 'SR')

    healthprof = fields.Many2One(
        'gnuhealth.healthprofessional', 'Health Prof',
        help='Health Professional for this ambulance and transport request')


# Copiado de tryton_stock/inventory.py
class InventoryLine(ModelSQL, ModelView):
    'Stock Inventory Line'
    __name__ = 'policoop.transport.line'

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ])
    uom = fields.Function(fields.Many2One('product.uom', 'UOM'), 'get_uom')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
    
    @classmethod
    def __setup__(cls):
        super(InventoryLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_line_qty_pos', Check(t, t.quantity >= 0),
                'Line quantity must be positive.'),
            ]
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Move = pool.get('stock.move')
        sql_table = cls.__table__()
        move_table = Move.__table__()

        super(InventoryLine, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        # Migration from 2.8: Remove constraint inventory_product_uniq
        table.drop_constraint('inventory_product_uniq')

        # Migration from 3.0: use Move origin
        if table.column_exist('move'):
            cursor.execute(*sql_table.select(sql_table.id, sql_table.move,
                    where=sql_table.move != Null))
            for line_id, move_id in cursor.fetchall():
                cursor.execute(*move_table.update(
                        columns=[move_table.origin],
                        values=['%s,%s' % (cls.__name__, line_id)],
                        where=move_table.id == move_id))
            table.drop_column('move')

    @staticmethod
    def default_unit_digits():
        return 2

    @fields.depends('product')
    def on_change_product(self):
        self.unit_digits = 2
        if self.product:
            self.uom = self.product.default_uom
            self.unit_digits = self.product.default_uom.digits

    def get_rec_name(self, name):
        return self.product.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product',) + tuple(clause[1:])]

    def get_uom(self, name):
        return self.product.default_uom.id

    def get_unit_digits(self, name):
        return self.product.default_uom.digits

    @property
    def unique_key(self):
        key = []
        for fname in self.inventory.grouping():
            value = getattr(self, fname)
            if isinstance(value, Model):
                value = value.id
            key.append(value)
        return tuple(key)

    @classmethod
    def cancel_move(cls, lines):
        Move = Pool().get('stock.move')
        moves = [m for l in lines for m in l.moves if l.moves]
        Move.cancel(moves)
        Move.delete(moves)

    def get_move(self):
        '''
        Return Move instance for the inventory line
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')

        delta_qty = Uom.compute_qty(self.uom,
            - self.quantity,
            self.uom)
        if delta_qty == 0.0:
            return
        from_location = self.inventory.location
        to_location = self.inventory.lost_found
        if delta_qty < 0:
            (from_location, to_location, delta_qty) = \
                (to_location, from_location, -delta_qty)

        return Move(
            from_location=from_location,
            to_location=to_location,
            quantity=delta_qty,
            product=self.product,
            uom=self.uom,
            company=self.inventory.company,
            effective_date=self.inventory.date,
            origin=self,
            )
