import copy
import tempfile
from pathlib import Path
import unittest
import cv2
import numpy as np
from PIL import Image
from thermal_lab.stereo_calibration import object_points,solve_calibration,detect_pair,projection_maps,save_calibration,read_calibration


def observations():
    rng=np.random.default_rng(60);obj=object_points(25)
    kt=np.array([[230.,0,128],[0,225,96],[0,0,1]]);ko=np.array([[220.,0,127],[0,218,95],[0,0,1]])
    rotation=cv2.Rodrigues(np.array([.01,.015,-.008]))[0];translation=np.array([.012,.001,.002]);pairs=[]
    for i in range(16):
        r=cv2.Rodrigues(np.array([-.3+.2*(i%4),-.3+.2*(i//4),.04*((i%3)-1)]))[0]
        z=.46+.025*(i%3);center=np.array([85+28*(i%4),63+20*(i//4)])
        v=np.r_[(center-[128,96])*z/[230,225],z]-r@obj.mean(axis=0)
        points=obj@r.T+v
        t=cv2.projectPoints(points,np.zeros(3),np.zeros(3),kt,np.zeros(5))[0].reshape(-1,2)
        o=cv2.projectPoints(points@rotation.T+translation,np.zeros(3),np.zeros(3),ko,np.zeros(5))[0].reshape(-1,2)
        pairs.append(dict(thermal=(t+rng.normal(0,.025,t.shape)).tolist(),optical=(o+rng.normal(0,.025,o.shape)).tolist()))
    return pairs


class CalibrationTests(unittest.TestCase):
    def test_recover_stereo_geometry_and_save_camera_bound_calibration(self):
        value=solve_calibration(observations(),'camera-a',25)
        self.assertLess(max(value['validation_rms_px']),.2)
        self.assertAlmostEqual(value['translation_m'][0],.012,delta=.002)
        mx,my=projection_maps(value,1);self.assertEqual(mx.shape,(192,256));self.assertTrue(np.isfinite(my).all())
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'calibration.json';save_calibration(path,value)
            self.assertEqual(read_calibration(path,'camera-a')['poses'],16)
            with self.assertRaises(ValueError):read_calibration(path,'camera-b')

    def test_reject_repeated_and_misordered_pairs(self):
        pairs=observations()
        with self.assertRaisesRegex(ValueError,'Repeated'):solve_calibration([pairs[0]]*12,'camera-a',25)
        pairs[3]['optical'].reverse()
        with self.assertRaisesRegex(ValueError,'rejected'):solve_calibration(pairs,'camera-a',25)

    def test_detector_requires_both_modalities(self):
        pattern=np.full((192,256),125,np.uint8)
        for y in range(6):
            for x in range(8):pattern[21+y*25:21+(y+1)*25,28+x*25:28+(x+1)*25]=255*((x+y)%2)
        optical=Image.fromarray(pattern).convert('RGB').resize((1024,768))
        pair=detect_pair(20+pattern.astype(float)/20,optical)
        self.assertEqual(len(pair['thermal']),35);self.assertEqual(len(pair['optical']),35)
        with self.assertRaises(ValueError):detect_pair(np.ones((192,256))*25,optical)


if __name__=='__main__':unittest.main()
