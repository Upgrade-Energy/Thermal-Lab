import unittest
import numpy as np
from PIL import Image
from thermal_lab.imaging import optical_image, alignment_matrix, aligned_optical, sensor_to_view, view_to_sensor, thermal_image, canvas_to_sensor
from thermal_lab.tc001_max import FRAME_BYTES


class ImagingTests(unittest.TestCase):
    def test_zoomed_panels_cannot_claim_neighboring_pixels(self):
        left=(-100,0,3,256,192,0,400,28,550)
        right=(300,0,3,256,192,400,800,28,550)
        self.assertIsNone(canvas_to_sensor(450,200,left,0))
        self.assertEqual(canvas_to_sensor(450,200,right,0),(50,200/3))
        self.assertIsNone(canvas_to_sensor(450,10,right,0))

    def test_yuyv_luma_chroma_layout(self):
        raw=bytearray(FRAME_BYTES)
        raw[197632:]=bytes([16,128,235,128])*(1024*768//2)
        image=optical_image(raw)
        self.assertEqual(image.size,(1024,768))
        self.assertEqual(image.getpixel((0,0)),(0,0,0))
        self.assertTrue(all(v>=254 for v in image.getpixel((1,0))))
        with self.assertRaises(ValueError):optical_image(raw[:-1])

    def test_alignment_moves_optical_landmark_in_thermal_pixel_units(self):
        source=Image.new('RGB',(1024,768));source.putpixel((400,300),(255,255,255))
        aligned=aligned_optical(source,dict(dx=10,dy=-5,scale=1,angle=0))
        self.assertEqual(aligned.getpixel((440,280)),(255,255,255))
        self.assertEqual(aligned.getpixel((400,300)),(0,0,0))

    def test_transform_inverse_roundtrip_and_temperature_independence(self):
        matrix=alignment_matrix(dict(dx=17,dy=-9,scale=1.3,angle=23))
        point=np.array([113.5,80.5,1]);np.testing.assert_allclose(np.linalg.inv(matrix)@(matrix@point),point)
        values=[22.0]*49152;values[80*256+113]=37.25
        before=values.copy()
        for rotation in (0,90,180,270):
            x,y=view_to_sensor(*sensor_to_view(113.5,80.5,rotation),rotation)
            self.assertEqual(values[int(y)*256+int(x)],37.25)
        thermal_image(values,'Iron',(20,40));self.assertEqual(values,before)

    def test_rotation_edges_and_scale_limits(self):
        for rotation in (0,90,180,270):
            for x,y in [(0,0),(255.9,191.9),(20.5,60.5)]:
                np.testing.assert_allclose(view_to_sensor(*sensor_to_view(x,y,rotation),rotation),(x,y),atol=1e-10)
        for value in [0,-1,float('nan'),9]:
            with self.assertRaises(ValueError):alignment_matrix({'scale':value})
