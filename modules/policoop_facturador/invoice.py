from trytond.model import Workflow, ModelView, ModelSQL
from trytond.pool import Pool

__all__ = ['Invoice']

class Invoice(Workflow, ModelSQL, ModelView):
    'Invoice'
    __name__ = 'account.invoice'

    def get_fecha_pago(self):
        if self.move:
            proximo_number = int(self.move.number) + 1
            proximo_move = Pool().get('account.move').search([('number', '=', str(proximo_number))])
            if proximo_move:
                return proximo_move[0].date
        return None
