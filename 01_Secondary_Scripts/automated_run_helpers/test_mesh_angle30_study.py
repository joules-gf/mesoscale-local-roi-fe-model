import unittest
import importlib.util
from pathlib import Path
import math
import tempfile

class MeshTests(unittest.TestCase):
    def module(self):
        p=Path(__file__).with_name('mesh_angle30_quality.py')
        self.assertTrue(p.exists(), 'quality implementation missing')
        spec=importlib.util.spec_from_file_location('quality',p)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m
    def test_equilateral(self):
        m=self.module(); q=m.triangle_quality([(0,0),(1,0),(.5,math.sqrt(3)/2)])
        self.assertAlmostEqual(q['r_over_R'],.5)
        self.assertAlmostEqual(q['min_angle_deg'],60)
        self.assertAlmostEqual(q['edge_ratio'],1)
    def test_skinny(self):
        q=self.module().triangle_quality([(0,0),(1,0),(.5,.001)])
        self.assertLess(q['r_over_R'],.001)
        self.assertLess(q['min_angle_deg'],1)
    def test_degenerate_rejected(self):
        with self.assertRaises(ValueError): self.module().triangle_quality([(0,0),(1,0),(2,0)])
    def test_arbitrary_ids_sections(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mesh.inp'
            p.write_text('*Part,name=P\n*Node\n11,0,0\n70,1,0\n99,0,1\n*Nset,nset=X\n11,70\n*Element,type=CPS3\n870,11,70,99\n*End Part\n*Assembly\n*Node\n999,5,5\n*End Assembly\n')
            nodes,elements=m.parse_mesh(p)
            self.assertEqual(elements,{870:('CPS3',(11,70,99))})
            self.assertEqual(len(nodes),3)
            p.write_text('*Node\n1,0,0\n2,1,0\n3,1,1\n4,0,1\n*Element,type=CPS4\n1,1,2,3,4\n')
            with self.assertRaises(ValueError): m.parse_mesh(p)
    def test_cached_polygon_rounding_is_explicit(self):
        import sys
        from types import SimpleNamespace
        sys.path.insert(0,str(Path(__file__).parent))
        from run_mesh_angle30_comparison import geometry_check
        with tempfile.TemporaryDirectory() as d:
            source=Path(d); (source/'msp_mesh_files').mkdir()
            (source/'msp_mesh_files'/'trimesh.inp').write_text('*Node\n1,0,0\n2,1,0\n3,0,1\n*Element,type=CPS3\n1,1,2,3\n*Elset,elset=Set-E-Seed-0\n1\n*Elset,elset=Set-E-Material-0\nSet-E-Seed-0\n*Surface,name=Surface-0,type=element\n1,S1\n')
            poly=SimpleNamespace(points=[(0,4e-8),(1,4e-8)],facets=[(0,1)])
            proof=geometry_check(source,poly,[SimpleNamespace(phase=0)])
            self.assertTrue(proof['all_facets_and_materials_match'])
            self.assertEqual(proof['geometry_tolerance_mm'],1e-7)
            self.assertAlmostEqual(proof['max_facet_distance_error_mm'],4e-8)
            # A displacement beyond the absolute bound must never be excused
            # as cache rounding, nor may altered material or coverage pass.
            poly.points=[(0,2e-7),(1,2e-7)]
            with self.assertRaises(ValueError): geometry_check(source,poly,[SimpleNamespace(phase=0)])
            poly.points=[(0,4e-8),(.999999,4e-8)]
            with self.assertRaises(ValueError): geometry_check(source,poly,[SimpleNamespace(phase=0)])
            poly.points=[(0,4e-8),(1,4e-8)]
            with self.assertRaises(ValueError): geometry_check(source,poly,[SimpleNamespace(phase=1)])
    def test_stress_interpolation(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.csv'; p.write_text('time,strain,stress\n0,0,0\n1,.02,500\n')
            self.assertAlmostEqual(m.read_stress(p),250)

if __name__=='__main__': unittest.main()
