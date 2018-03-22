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

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date

from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal
from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.pool import Pool


__all__ = [
    'PolicoopSequences','TransportRequest', 'AmbulanceTransport',
    'TransportHealthProfessional']

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

    return_date = fields.DateTime('Return_date', required=False,
        help="Date and time of return")
    
    latitude = fields.Numeric('Latidude', digits=(3, 14))
    longitude = fields.Numeric('Longitude', digits=(4, 14))

    address = fields.Text("Address", help="Free text address / location")
    urladdr = fields.Char(
        'OSM Map',
        help="Maps the location on Open Street Map")

    urgency = fields.Selection([
        (None, ''),
        ('low', 'Low'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
        ], 'Urgency', sort=False)
       
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
        ], 'Event type')

    escort = fields.Text("Acompañante", help="Acompañante / Descripción")

    wait = fields.Selection([
        (None, ''),
        ('event1', 'Si'),
        ('event2', 'No'),
        ], 'Event type')

    ambulances = fields.One2Many(
        'policoop.ambulance.transport', 'sr',
        'Ambulances', help='Ambulances requested in this Support Request')

    request_extra_info = fields.Text('Details')

    state = fields.Selection([
        (None, ''),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ], 'State', sort=False, readonly=True)
 
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
        'SR', help="Support Request", required=True)

    ambulance = fields.Many2One('gnuhealth.ambulance','Ambulance',
        domain=[('state', '=', 'available')],)
    
    healthprofs = fields.One2Many('policoop.transport_hp','name',
        'Health Professionals')

    state = fields.Selection([
        (None, ''),
        ('available', 'Available / At Station'),
        ('dispatched', 'Dispatched'),
        ('en_route', 'En Route'),
        ('on_location', 'On Location'),
        ('to_hospital', 'To Hospital'),
        ('at_hospital', 'At Hospital'),
        ('returning', 'Returning'),
        ('out_of_service', 'Out of service'),
        ], 'Status',sort=False, readonly=True, help="Vehicle status")

    @staticmethod
    def default_state():
        return 'available'


    @classmethod
    def __setup__(cls):
        super(TransportSupport, cls).__setup__()
        cls._buttons.update({
            'available': {'invisible': Equal(Eval('state'), 'available')},
            'dispatched': {'invisible': Equal(Eval('state'), 'dispatched')},
            'en_route': {'invisible': Equal(Eval('state'), 'en_route')},
            'on_location': {'invisible': Equal(Eval('state'), 'on_location')},
            'to_hospital': {'invisible': Equal(Eval('state'), 'to_hospital')},
            'at_hospital': {'invisible': Equal(Eval('state'), 'at_hospital')},
            'returning': {'invisible': Equal(Eval('state'), 'returning')},
            'out_of_service': {'invisible': Equal(Eval('state'),
            'out_of_service')},
            })


    @classmethod
    @ModelView.button
    def available(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='available')

    @classmethod
    @ModelView.button
    def dispatched(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='dispatched')

    @classmethod
    @ModelView.button
    def en_route(cls, ambulances):
         cls.update_ambulance_status(ambulances, status='en_route')

    @classmethod
    @ModelView.button
    def on_location(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='on_location')

    @classmethod
    @ModelView.button
    def to_hospital(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='to_hospital')

    @classmethod
    @ModelView.button
    def at_hospital(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='at_hospital')

    @classmethod
    @ModelView.button
    def returning(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='returning')

    @classmethod
    @ModelView.button
    def out_of_service(cls, ambulances):
        cls.update_ambulance_status(ambulances, status='out_of_service')


    @classmethod
    def update_ambulance_status(cls, ambulances, status):
        # Update status on local support model for this ambulance
        cls.write(ambulances, {
            'state': status})
            
        # Write current status on ambulance model
        Ambulance = Pool().get('gnuhealth.ambulance')
        vehicle = []
        
        vehicle.append(ambulances[0].ambulance)
        
        Ambulance.write(vehicle, {
            'state': status })


class TransportHealthProfessional(ModelSQL, ModelView):
    'Transport Health Professionals'
    __name__ = 'policoop.transport_hp'

    name = fields.Many2One('policoop.ambulance.transport', 'SR')

    healthprof = fields.Many2One(
        'gnuhealth.healthprofessional', 'Health Prof',
        help='Health Professional for this ambulance and transport request')
