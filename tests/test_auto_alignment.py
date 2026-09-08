import tempfile
from pathlib import Path
import unittest
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from thermal_lab.auto_alignment import fit_alignment, alignment_from_regions, AlignmentCancelled
from thermal_lab.alignment_profiles import at_distance,read_profiles,save_profiles
from thermal_lab.imaging import aligned_optical


def fixture():
    image=Image.new('L',(256,192),30);draw=ImageDraw.Draw(image);rng=np.random.default_rng(67)
    for _ in range(45):
        x,y=rng.integers(8,220),rng.integers(8,150);w,h=rng.integers(8,40,size=2)
        draw.ellipse((x,y,x+w,y+h),fill=int(rng.integers(45,250)))
    return image.filter(ImageFilter.GaussianBlur(1.2)).convert('RGB').resize((1024,768))


class AutoAlignmentTests(unittest.TestCase):
    def test_inverted_modality_and_geometry_recovery(self):
        optical=fixture();truth=dict(dx=13,dy=-9,scale=1.12,angle=3)
        aligned=np.asarray(aligned_optical(optical,truth).convert('L').resize((256,192)),dtype=float)
        thermal=45-25*(aligned/255)**.7
        before=thermal.copy();result=fit_alignment(thermal.ravel(),optical,dict(dx=0,dy=0,scale=1,angle=0),[.12,.12,.88,.88])
        self.assertTrue(result['reliable'],result)
        for k,tolerance in [('dx',2),('dy',2),('scale',.025),('angle',1)]:self.assertAlmostEqual(result['alignment'][k],truth[k],delta=tolerance)
        np.testing.assert_array_equal(thermal,before)
    def test_flat_scene_and_cancel_rejected(self):
        with self.assertRaisesRegex(ValueError,'Too little'):fit_alignment([25]*49152,fixture(),{})
        values=np.arange(49152).reshape(192,256)/49152*20+20
        with self.assertRaises(AlignmentCancelled):fit_alignment(values,fixture(),{},cancelled=lambda:True)
    def test_unrelated_sensor_detail_is_not_accepted(self):
        noise=np.random.default_rng(489).uniform(20,40,(192,256))
        result=fit_alignment(noise,fixture(),{},[.1,.1,.9,.9])
        self.assertFalse(result['reliable'],result)
    def test_near_far_boxes_give_different_target_plane_alignment(self):
        optical=[.2,.2,.4,.4]
        near=alignment_from_regions([.3,.3,.6,.6],optical)
        far=alignment_from_regions([.22,.22,.42,.42],optical)
        self.assertAlmostEqual(near['scale'],1.5);self.assertAlmostEqual(far['scale'],1)
        self.assertNotAlmostEqual(near['dx'],far['dx'])
        from thermal_lab.imaging import alignment_matrix
        for box,alignment in [([.3,.3,.6,.6],near),([.22,.22,.42,.42],far)]:
            mapped=alignment_matrix(alignment)@np.array([.3*256,.3*192,1])
            np.testing.assert_allclose(mapped[:2],[(box[0]+box[2])*128,(box[1]+box[3])*96])
    def test_guided_refinement_stays_close_to_operator_target(self):
        optical=fixture();truth=dict(dx=13,dy=-9,scale=1.12,angle=3)
        aligned=np.asarray(aligned_optical(optical,truth).convert('L').resize((256,192)),dtype=float)
        result=fit_alignment((45-25*(aligned/255)**.7).ravel(),optical,dict(dx=11,dy=-8,scale=1.1,angle=2),[.12,.12,.88,.88],guided=True)
        self.assertAlmostEqual(result['alignment']['dx'],13,delta=2)
    def test_camera_bound_distance_profiles_and_no_extrapolation(self):
        value=dict(schema=1,camera_id='a',profiles=[dict(name='Near',distance_m=1,alignment=dict(dx=20,dy=0,scale=1,angle=179)),dict(name='Far',distance_m=4,alignment=dict(dx=5,dy=0,scale=1,angle=-179))])
        result=at_distance(value,2);self.assertAlmostEqual(result['dx'],10);self.assertGreater(abs(result['angle']),178)
        for distance in (.5,5,float('nan')):
            with self.assertRaises(ValueError):at_distance(value,distance)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'profiles.json';save_profiles(path,value)
            self.assertEqual(read_profiles(path,'a')['profiles'][0]['name'],'Near')
            with self.assertRaises(ValueError):read_profiles(path,'b')


if __name__=='__main__':unittest.main()
