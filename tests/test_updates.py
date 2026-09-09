import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.request
import lab_update as u

SETTINGS=dict(app_id='PowerLab',name='Power Lab',repository='Upgrade-Energy/Power-Lab',version='0.2.0-dev5',asset_prefix='Power-Lab-Setup-')


def release(version='0.2.0-dev6', data=b'MZverified installer', **changes):
    asset=dict(id=12,name='Power-Lab-Setup-'+version+'.exe',size=len(data),state='uploaded',digest='sha256:'+hashlib.sha256(data).hexdigest())
    result=dict(tag_name='v'+version,prerelease=True,draft=False,assets=[asset],body='Fixes and improvements')
    result.update(changes);return result


class UpdateTests(unittest.TestCase):
    def test_semantic_order_and_existing_formats(self):
        versions=['0.1.0-rc2.4','0.2.0-DEV4','0.2.0.dev5','v0.2.0-dev10','0.2.0-rc1','0.2.0','0.2.1-dev1']
        self.assertEqual(sorted(versions,key=u.version_key),versions)
        for invalid in ['main','v1.2.3/evil','1.2.3;cmd','1.2.3.4','1.2.3\n']:
            with self.assertRaises(u.UpdateError):u.version_key(invalid)

    def test_uses_latest_own_app_complete_release_not_list_order(self):
        old=release('0.2.0-dev4');new=release('0.2.0-dev10');mid=release()
        wrong=release('0.3.0');wrong['assets'][0]['name']='Thermal-Lab-Setup-0.3.0.exe'
        draft=release('0.9.0',draft=True)
        self.assertEqual(u.select_release([draft,wrong,mid,new,old],SETTINGS,True)['version'],'0.2.0-dev10')

    def test_stable_channel_and_no_downgrades(self):
        self.assertIsNone(u.select_release([release(),release('0.2.0-dev4')],SETTINGS,False))
        stable=release('0.2.0',prerelease=False)
        self.assertEqual(u.select_release([stable,release('0.3.0-dev1')],SETTINGS,False)['version'],'0.2.0')
        self.assertIsNone(u.select_release([release('0.2.0-dev5')],SETTINGS,True))

    def test_requires_complete_checksum_and_bounded_asset(self):
        for key,value in [('digest',None),('digest','sha256:bad'),('size',u.MAX_INSTALLER+1),('size',True),('id','../x'),('state','new')]:
            item=release();item['assets'][0][key]=value
            self.assertIsNone(u.select_release([item],SETTINGS,True))

    def test_verified_download_and_corruption_cleanup(self):
        data=b'MZverified installer';candidate=u.select_release([release(data=data)],SETTINGS,True)
        with tempfile.TemporaryDirectory() as tmp,patch.object(u,'data_root',return_value=Path(tmp)):
            with patch.object(u,'request',return_value=io.BytesIO(data)):
                path=u.download(SETTINGS,candidate,token='test');self.assertEqual(path.read_bytes(),data)
            for invalid in [b'MZtampered installer',data+b'X',b'MZ',b'XXverified installer']:
                with patch.object(u,'request',return_value=io.BytesIO(invalid)):
                    with self.assertRaises(u.UpdateError):u.download(SETTINGS,candidate,token='test')
                self.assertFalse(path.with_suffix('.part').exists())
                self.assertEqual(path.read_bytes(),data)

    def test_download_is_exact_repository_asset_endpoint(self):
        data=b'MZhello';candidate=u.select_release([release(data=data)],SETTINGS,True)
        with tempfile.TemporaryDirectory() as tmp,patch.object(u,'data_root',return_value=Path(tmp)),patch.object(u,'request',return_value=io.BytesIO(data)) as request:
            u.download(SETTINGS,candidate,token='private')
            request.assert_called_once_with('/repos/Upgrade-Energy/Power-Lab/releases/assets/12','private',binary=True)

    def test_redirect_never_leaks_token_and_rejects_other_hosts(self):
        request=urllib.request.Request('https://api.github.com/repos/Upgrade-Energy/Power-Lab/releases/assets/12',headers={'Authorization':'Bearer private'})
        handler=u.ReleaseRedirect()
        result=handler.redirect_request(request,None,302,'',{},'https://release-assets.githubusercontent.com/release-asset/file?signature=example')
        self.assertIsNone(result.get_header('Authorization'))
        for url in ['http://api.github.com/file','https://attacker.example/file','https://api.github.com@attacker.example/file','https://api.github.com:8443/file']:
            with self.assertRaises(u.UpdateError):handler.redirect_request(request,None,302,'',{},url)

    def test_install_rechecks_hash_and_running_apps(self):
        data=b'MZhello';candidate=u.select_release([release(data=data)],SETTINGS,True)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/candidate['name'];path.write_bytes(data)
            # Avoid changing pathlib platform behavior while mocking Windows.
            with patch.object(u.os,'name','nt'),patch.object(u,'app_running',return_value=True),patch.object(u.subprocess,'Popen') as launch:
                with self.assertRaises(u.UpdateError):u.launch_installer(path,candidate,SETTINGS)
                launch.assert_not_called()
            with patch.object(u.os,'name','nt'),patch.object(u,'app_running',return_value=False),patch.object(u,'verify_installer',side_effect=u.UpdateError('checksum')),patch.object(u.subprocess,'Popen') as launch:
                with self.assertRaises(u.UpdateError):u.launch_installer(path,candidate,SETTINGS)
                launch.assert_not_called()

    def test_pagination_includes_later_page(self):
        import json
        first=[release('0.2.0-dev4') for _ in range(100)]
        with patch.object(u,'request',side_effect=[io.BytesIO(json.dumps(first).encode()),io.BytesIO(json.dumps([release()]).encode())]):
            self.assertEqual(u.check(SETTINGS,True,token='test')['version'],'0.2.0-dev6')


if __name__=='__main__':unittest.main()
