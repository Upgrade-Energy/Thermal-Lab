import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock
from thermal_lab.integration import CameraService,make_server
from thermal_lab.service_manager import service_request


class ServiceManagerTests(unittest.TestCase):
    def test_authenticated_status_and_refusal_to_stop_owned_service(self):
        with tempfile.TemporaryDirectory() as folder:
            service=CameraService(folder,Path(folder)/'records',discover=lambda:[])
            server=make_server(service,'local-test-token')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            descriptor=Path(folder)/'integration.json';descriptor.write_text(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}',token='local-test-token')))
            try:
                with patch('thermal_lab.service_manager.DESCRIPTOR',descriptor):
                    self.assertIsInstance(service_request('/v1/state'),dict)
                    service.owner='powerlab'
                    with self.assertRaises(Exception):service_request('/v1/shutdown',{})
                    self.assertEqual(service.owner,'powerlab')
                    service.owner=None
                    self.assertTrue(service_request('/v1/shutdown',{})['shutting_down'])
            finally:server.shutdown();server.server_close();service.close();thread.join(2)


if __name__=='__main__':unittest.main()
