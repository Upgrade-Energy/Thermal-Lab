import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock,patch
from thermal_lab.integration import CameraService,make_server
from thermal_lab.service_lease import service_lease


class LocalQueue(queue.Queue):
    def cancel_join_thread(self):pass
    def close(self):pass


class Process:
    def __init__(self,**kwargs):self.alive=False
    def start(self):self.alive=True
    def is_alive(self):return self.alive
    def terminate(self):self.alive=False
    def join(self,*args):pass


class IntegrationTests(unittest.TestCase):
    def test_service_lock_prevents_duplicate_owner_and_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'integration.json'
            with service_lease(path):
                with self.assertRaises(OSError):
                    with service_lease(path):pass
            with service_lease(path):pass
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.service=CameraService('.',self.temp.name,discover=lambda:[dict(instance_id='camera-a',problem_code=0)])
        self.service.quit.set();self.service.thread.join(1)
        self.service.ctx=Mock(Queue=lambda *args:LocalQueue(),Process=Process)
        self.owner='a'*32
        self.body=dict(session_id=self.owner,cameras=[dict(camera_id='camera-a',settings=dict(points=[dict(id='p',name='Probe',x=.5,y=.5)]))])
    def tearDown(self):
        for c in self.service.cameras:c['process'].terminate()
        self.service.close();self.temp.cleanup()
    def ready(self):
        self.service.connect(self.body);camera=self.service.cameras[0]
        camera['events'].put(dict(kind='connected'))
        camera['previews'].put(dict(received_at=time.monotonic(),frame=dict(camera_id='camera-a',width=256,height=192,temperatures=[25.]*49152,source='SIMULATION',arrival_sequence=1)))
        self.service._poll();return camera
    def test_exclusive_ownership_and_freshness(self):
        camera=self.ready()
        self.assertEqual(self.service.state()['cameras'][0]['measurements']['p']['value'],25.)
        with self.assertRaisesRegex(ValueError,'owned'):self.service.connect(dict(self.body,session_id='b'*32))
        camera['sample']['received_at']-=2
        state=self.service.state()['cameras'][0]
        self.assertFalse(state['fresh']);self.assertEqual(state['measurements'],{})
        with self.assertRaisesRegex(ValueError,'Fresh'):self.service.start(dict(session_id=self.owner,run_id='c'*32,run_origin_monotonic=time.monotonic()))
    def test_run_idempotency_and_stop_acknowledgement(self):
        camera=self.ready();body=dict(session_id=self.owner,run_id='c'*32,run_origin_monotonic=time.monotonic())
        first=self.service.start(body);self.assertEqual(first,self.service.start(body))
        with patch('thermal_lab.integration.time.monotonic',return_value=body['run_origin_monotonic']+120):
            self.assertEqual(first,self.service.start(body))
        self.assertEqual(first['status'],'STARTING')
        camera['events'].put(dict(kind='recording_started',path=first['cameras'][0]['path']))
        self.service._poll();self.assertEqual(self.service.state()['run']['status'],'STARTING')
        camera['sample']['run_id']=body['run_id']
        self.service._poll();self.assertEqual(self.service.state()['run']['status'],'RECORDING')
        self.service.stop(body);self.assertEqual(self.service.state()['run']['status'],'STOPPING')
        camera['events'].put(dict(kind='recording_finished',path=first['cameras'][0]['path'],status='COMPLETE',frames=10))
        self.service._poll();self.assertEqual(self.service.runs['c'*32]['status'],'COMPLETE')
        self.assertIsNone(self.service.active)
    def test_lost_client_aborts_recording_and_clears_measurements(self):
        camera=self.ready()
        self.service.start(dict(session_id=self.owner,run_id='c'*32,run_origin_monotonic=time.monotonic()))
        self.service.heartbeat_at-=20;self.service._poll()
        state=self.service.state();self.assertEqual(state['run']['status'],'FAILED')
        self.assertFalse(state['cameras'][0]['fresh']);self.assertEqual(state['cameras'][0]['measurements'],{})
        commands=[]
        while not camera['commands'].empty():commands.append(camera['commands'].get())
        self.assertEqual(commands[-1]['action'],'abort')
    def test_http_token_origin_and_size_checks(self):
        server=make_server(self.service,'test-secret-token-long-enough')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            for headers in ({},{'Authorization':'Bearer test-secret-token-long-enough','Origin':'https://example.com'}):
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(urllib.request.Request(url+'/v1/state',headers=headers))
                self.assertEqual(error.exception.code,403)
            headers={'Authorization':'Bearer test-secret-token-long-enough'}
            with urllib.request.urlopen(urllib.request.Request(url+'/v1/cameras',headers=headers)) as response:
                self.assertEqual(json.load(response)['cameras'][0]['instance_id'],'camera-a')
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(urllib.request.Request(url+'/v1/connect',data=b' '*65537,headers=headers))
            self.assertEqual(error.exception.code,400)
        finally:server.shutdown();server.server_close();thread.join(1)
