import tempfile
from pathlib import Path
import unittest
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from thermal_lab.auto_alignment import fit_alignment, alignment_from_regions, alignment_from_points, AlignmentCancelled
from thermal_lab.alignment_profiles import at_distance,read_profiles,save_profiles
from thermal_lab.imaging import aligned_optical


def fixture():
    image=Image.new('L',(256,192),30);draw=ImageDraw.Draw(image);rng=np.random.default_rng(67)
    for _ in range(45):
        x,y=rng.integers(8,220),rng.integers(8,150);w,h=rng.integers(8,40,size=2)
        draw.ellipse((x,y,x+w,y+h),fill=int(rng.integers(45,250)))
    return image.filter(ImageFilter.GaussianBlur(1.2)).convert('RGB').resize((1024,768))


class AutoAlignmentTests(unittest.TestCase):
    def test_automatic_selected_subject_changes_distance_from_near_setting(self):
        import cv2
        from thermal_lab.edge_alignment import fit_edges
        mask=np.zeros((192,256),np.uint8);cv2.ellipse(mask,(135,85),(22,33),0,0,360,255,-1)
        rgb=Image.fromarray(np.where(mask,230,25).astype(np.uint8)).convert('RGB').resize((1024,768))
        initial=dict(dx=-20,dy=-13,scale=1.25,angle=0)
        for truth in [initial,dict(dx=-3,dy=7,scale=1.05,angle=0)]:
            moved=np.asarray(aligned_optical(Image.fromarray(mask).convert('RGB').resize((1024,768)),truth).resize((256,192)).convert('L'))>120
            y,x=np.where(moved);region=[(x.min()-3)/256,(y.min()-3)/192,(x.max()+4)/256,(y.max()+4)/192]
            result=fit_edges(np.where(moved,33,20),rgb,initial,region)
            self.assertTrue(result['reliable'])
            for key,tolerance in [('dx',2),('dy',2),('scale',.035),('angle',2)]:
                self.assertAlmostEqual(result['alignment'][key],truth[key],delta=tolerance)

    def test_shared_points_solve_selected_depth_without_prior_alignment(self):
        from thermal_lab.imaging import alignment_matrix
        optical=np.array([[.25,.35],[.45,.35],[.35,.50],[.28,.54]])
        for truth in [dict(dx=-20,dy=-13,scale=1.25,angle=.5),dict(dx=-3,dy=7,scale=1.05,angle=-2)]:
            thermal=(np.c_[optical*[256,192],np.ones(4)]@alignment_matrix(truth).T)[:,:2]/[256,192]
            result=alignment_from_points(thermal,optical)
            for key in truth:self.assertAlmostEqual(result['alignment'][key],truth[key],places=7)
            self.assertLess(result['rms_pixels'],1e-8)

    def test_shared_points_reject_degenerate_and_inconsistent_pairs(self):
        for points in [[],[[.2,.2],[.3,.3]],[[.2,.2],[.3,.3],[.4,.4]]]:
            with self.assertRaises(ValueError):alignment_from_points(points,points)
        points=np.array([[.2,.2],[.6,.2],[.2,.6],[.6,.6]])
        wrong=points.copy();wrong[-1]=[.4,.8]
        with self.assertRaisesRegex(ValueError,'disagree'):alignment_from_points(wrong,points)

    def test_target_outline_with_unrelated_heat_and_printed_label(self):
        import cv2
        from thermal_lab.edge_alignment import fit_edges
        mask=np.zeros((192,256),np.uint8);cv2.rectangle(mask,(80,48),(152,132),255,-1)
        optical=np.full((192,256),60,np.uint8);optical[mask>0]=210
        cv2.putText(optical,'TEST',(85,100),cv2.FONT_HERSHEY_SIMPLEX,.55,20,2)
        rgb=Image.fromarray(optical).convert('RGB').resize((1024,768))
        truth=dict(dx=-12,dy=-6,scale=1.25,angle=0)
        moved=np.asarray(aligned_optical(Image.fromarray(mask).convert('RGB').resize((1024,768)),truth).resize((256,192)).convert('L'))>120
        yy,xx=np.mgrid[:192,:256];thermal=np.where(moved,27+yy*.04+8*np.exp(-((xx-110)**2+(yy-115)**2)/150),20)
        y,x=np.where(moved);region=[(x.min()-3)/256,(y.min()-3)/192,(x.max()+4)/256,(y.max()+4)/192]
        result=fit_edges(thermal,rgb,{},region)
        self.assertTrue(result['reliable'],{k:v for k,v in result.items() if k!='outline_points'})
        for key,tolerance in [('dx',3),('dy',3),('scale',.05),('angle',2)]:self.assertAlmostEqual(result['alignment'][key],truth[key],delta=tolerance)
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
