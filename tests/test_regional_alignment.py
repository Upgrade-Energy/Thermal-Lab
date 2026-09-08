import unittest
import cv2
import numpy as np
from PIL import Image
from thermal_lab.regional_alignment import estimate_regions,render_regions,similarity_maps
from thermal_lab.auto_alignment import AlignmentCancelled


class RegionalTests(unittest.TestCase):
    def texture(self,seed=721):
        return cv2.GaussianBlur(np.random.default_rng(seed).uniform(0,1,(192,256)).astype(np.float32),(5,5),.8)

    def test_two_depth_regions_recover_opposing_offsets_and_preserve_source(self):
        a=self.texture();thermal=20+15*a
        moving=np.concatenate([np.roll(a,5,axis=1)[:,:128],np.roll(a,-5,axis=1)[:,128:]],axis=1)
        optical=Image.fromarray(np.uint8(255*(1-moving))).convert('RGB').resize((1024,768))
        original=thermal.copy();raw=optical.tobytes();result=estimate_regions(thermal,optical,similarity_maps({}))
        self.assertGreater(result['coverage'],.25,result['cells'])
        for cell in result['cells']:
            if cell['x']<104:self.assertEqual(cell['dx'],5)
            if cell['x']>152:self.assertEqual(cell['dx'],-5)
            self.assertEqual(cell['dy'],0)
        np.testing.assert_array_equal(original,thermal);self.assertEqual(raw,optical.tobytes())

    def test_unrelated_flat_and_single_edge_regions_stay_unsupported(self):
        optical=Image.fromarray(np.uint8(255*self.texture(823))).convert('RGB').resize((1024,768))
        for a in (self.texture(),np.ones((192,256)),np.tile(np.arange(256)>100,(192,1)).astype(float)):
            result=estimate_regions(20+15*a,optical,similarity_maps({}))
            self.assertEqual(result['coverage'],0)
            thermal=Image.new('RGB',(1024,768),(125,80,90))
            rendered=render_regions(thermal,optical,similarity_maps({}),result,False)
            self.assertEqual(rendered.tobytes(),thermal.tobytes())

    def test_occlusion_is_not_filled_with_optical_guesses(self):
        a=self.texture();moving=a.copy();moving[40:152,64:192]=self.texture(949)[40:152,64:192]
        optical=Image.fromarray(np.uint8(moving*255)).convert('RGB').resize((1024,768))
        result=estimate_regions(20+15*a,optical,similarity_maps({}))
        self.assertEqual(float(result['support'][64:128,88:168].sum()),0)

    def test_cancel_and_invalid_temperature(self):
        optical=Image.new('RGB',(1024,768))
        with self.assertRaises(AlignmentCancelled):estimate_regions(np.ones((192,256)),optical,similarity_maps({}),cancelled=lambda:True)
        with self.assertRaises(ValueError):estimate_regions(np.full((192,256),np.nan),optical,similarity_maps({}))


if __name__=='__main__':unittest.main()
