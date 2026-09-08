import unittest
from thermal_lab.connection_guidance import connection_guidance


def device(controller=3,ports=(2,)):
    return dict(problem_code=0,location_paths=[f'PCIROOT(0)#PCI(0801)#PCI(000{controller})#USBROOT(0)'+''.join(f'#USB({p})' for p in ports)])


class ConnectionGuidanceTests(unittest.TestCase):
    def test_nested_hubs_share_upstream_link(self):
        self.assertIn('SHARED HUB PATH',connection_guidance([device(3,(2,1)),device(3,(2,4,1))]))

    def test_separate_controllers_and_root_ports(self):
        self.assertIn('Separate USB controllers',connection_guidance([device(3),device(4)]))
        self.assertIn('unverified',connection_guidance([device(3,(1,)),device(3,(2,))]))

    def test_missing_path_and_unhealthy_camera(self):
        self.assertIn('unknown',connection_guidance([device(),dict(problem_code=0)]))
        self.assertIn('One camera',connection_guidance([device(),dict(problem_code=10)]))
        self.assertIn('No healthy',connection_guidance([]))
