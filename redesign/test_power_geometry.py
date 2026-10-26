"""Regression cases for false assurance from disconnected cross-section sums."""
import unittest
from power_geometry import neck
from shapely.geometry import box


class ConnectedWidthTests(unittest.TestCase):
    def test_disconnected_pours_are_not_added(self):
        shape=box(0,0,20,10).union(box(21,0,50,10))
        self.assertIsNone(neck(shape,(5,5),(45,5)))

    def test_local_neck_limits_a_large_pour(self):
        shape=box(0,0,50,10).difference(box(20,2,25,10))
        self.assertAlmostEqual(neck(shape,(5,5),(45,5)),2,delta=.03)

    def test_wide_connected_detour_counts(self):
        shape=box(0,0,50,20).difference(box(20,5,25,15))
        self.assertAlmostEqual(neck(shape,(5,10),(45,10)),5,delta=.03)


if __name__=='__main__': unittest.main()
