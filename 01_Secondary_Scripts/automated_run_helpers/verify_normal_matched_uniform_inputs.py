"""Verify matched moments through the actual input-completion path, without solving."""
import csv
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
NORMAL = ROOT / 'simulation_inputs/Normal Distribution/sensitivity-study-AA7075-T651/equal-mean-matched-uniform'
UNIFORM = ROOT / 'simulation_inputs/Uniform Distribution/sensitivity-study-AA7075-T651/bp_same_lower_bound_diameter'


def controls(root):
    """Compare every XML control except changed distribution and restart fields."""
    values = []
    def walk(element, path=''):
        here = path + '/' + element.tag
        if here in ('/input/material/size', '/input/settings/restart'):
            return
        values.append((here, (element.text or '').strip(), sorted(element.attrib.items())))
        for child in element:
            walk(child, here)
    walk(root)
    return values


def main():
    sys.path.insert(0, str(ROOT / '00_Main_Scripts'))
    from abaqus_input_generation_v02 import complete_input_data
    with (NORMAL / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 21
    assert sum(r['kind'] == 'sweep' for r in rows) == 20
    assert sum(r['kind'] == 'baseline' for r in rows) == 1
    assert len({r['case'] for r in rows}) == 21
    assert {p.name for p in NORMAL.glob('*.xml')} == {r['input_file'] for r in rows}
    for row in rows:
        normal_path = NORMAL / row['input_file']
        uniform_path = UNIFORM / (row['source_uniform_case'] + '.xml')
        normal_xml = ET.parse(normal_path).getroot()
        uniform_xml = ET.parse(uniform_path).getroot()
        assert controls(normal_xml) == controls(uniform_xml)
        assert normal_xml.findtext('settings/restart', '').strip().lower() == 'false'
        assert all(m.find('size/scale') is None for m in uniform_xml.findall('material'))
        completed = []
        try:
            for path in (uniform_path, normal_path):
                completed.append(complete_input_data(str(path)))
            udata, ndata = [result[0] for result in completed]
            assert udata[2].get('rng_seeds') == ndata[2].get('rng_seeds')
            assert ndata[2].get('rng_seeds') == {'size': 1000}
            assert len(udata[1]) == len(ndata[1]) == 4
            for uphase, nphase in zip(udata[1], ndata[1]):
                u, n = uphase['size'], nphase['size']
                assert u.dist.name == 'uniform' and n.dist.name == 'norm'
                assert math.isclose(u.mean(), n.mean(), rel_tol=1e-13)
                assert math.isclose(u.std(), n.std(), rel_tol=1e-13)
                assert math.isclose(n.mean(), float(row['normal_mean_mm']), rel_tol=1e-13)
                assert math.isclose(n.std(), float(row['normal_std_mm']), rel_tol=1e-13)
                assert math.isclose(u.kwds['loc'], float(row['uniform_lower_bound_mm']), rel_tol=1e-13)
                assert math.isclose(u.kwds['scale'], float(row['uniform_width_mm']), rel_tol=1e-13)
            print('[OK]', row['case'], 'mean=', ndata[1][0]['size'].mean(), 'std=', ndata[1][0]['size'].std())
        finally:
            for result in completed:
                Path(result[-1]).unlink(missing_ok=True)
    print('[VERIFIED] 20 sweep inputs + 1 baseline; matched moments and unchanged controls. No mesh/solver launched.')


if __name__ == '__main__':
    main()
