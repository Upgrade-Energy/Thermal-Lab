import unittest
from thermal_lab.extrema import extrema
from thermal_lab.imaging import sensor_to_view, view_to_sensor


class ExtremaTests(unittest.TestCase):
    def test_tracks_numerical_extremes_not_palette_or_alignment(self):
        values=[22.0]*(256*192);values[0]=-12.5;values[-1]=83.125
        original=values.copy();hot,cold=extrema(values)
        self.assertEqual((hot['x'],hot['y'],hot['value']),(255.5,191.5,83.125))
        self.assertEqual((cold['x'],cold['y'],cold['value']),(.5,.5,-12.5))
        self.assertEqual(values,original)
        values[42]=110
        self.assertEqual(extrema(values)[0]['x'],42.5)
        for rotation in (0,90,180,270):
            self.assertEqual(view_to_sensor(*sensor_to_view(hot['x'],hot['y'],rotation),rotation),(hot['x'],hot['y']))

    def test_uniform_and_invalid_grids_have_honest_markers(self):
        self.assertEqual(len(extrema([25]*49152)),1)
        self.assertEqual(extrema([float('nan')]*49152),[])
        values=[float('nan')]*49152;values[2]=21;values[3]=float('inf');values[8]=30
        hot,cold=extrema(values)
        self.assertEqual((hot['value'],cold['value']),(30,21))
        with self.assertRaises(ValueError):extrema([1,2])

