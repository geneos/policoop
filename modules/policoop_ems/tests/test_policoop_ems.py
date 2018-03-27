import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class PolicoopISSTestCase(ModuleTestCase):
    '''
    Test Health ISS module.
    '''
    module = 'policoop_iss'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        PolicoopISSTestCase))
    return suite
