"""Three normal mean-diameter additions, then refresh the combined four-panel figure."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import run_normal_equal_mean as runner

ROOT = runner.ROOT
INPUTS = ROOT / 'simulation_inputs/Normal Distribution/bp-equal-mean-round2'
BATCH = ROOT / 'simulation_outputs/normal_equal_mean_round2_batch'
runner.BATCH = BATCH


def load_cases():
    files = list(INPUTS.glob('*.xml'))
    expected = {f'normal_round2_mean_{d:03d}um': d for d in (120,130,140)}
    if len(files) != 3 or {p.stem for p in files} != set(expected):
        raise ValueError('Expected precisely the 120, 130, 140 micron additions')
    baseline = ROOT / 'simulation_inputs/Normal Distribution/bp-equal-mean-4all-phases/bp_same_size_case_13.xml'
    original = ET.parse(baseline).getroot()
    for element in original.findall('material/size/loc'):
        element.text = 'VARIED'
    def controls(root):
        return [(e.tag, (e.text or '').strip(), sorted(e.attrib.items())) for e in root.iter()]
    rows = []
    for path in files:
        root = ET.parse(path).getroot()
        sizes = root.findall('material/size')
        mean = expected[path.stem]/1000
        if len(sizes) != 4:
            raise ValueError('Expected four phases')
        for size in sizes:
            if size.findtext('dist_type','').strip() != 'norm' or size.find('scale') is not None or not math.isclose(float(size.findtext('loc')),mean):
                raise ValueError('Invalid normal distribution controls')
            size.find('loc').text = 'VARIED'
        if controls(root) != controls(original):
            raise ValueError('Non-mean controls differ from round 1')
        rows.append({'case':path.stem,'input':str(path.relative_to(ROOT)),'mean_mm':mean,'input_sha256':runner.digest(path)})
    return sorted(rows,key=lambda r:r['mean_mm'],reverse=True)


def main():
    runner.configure_console()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--verify-inputs',action='store_true')
    args=parser.parse_args()
    os.chdir(ROOT)
    rows=load_cases()
    runner.preflight(rows)
    for row in rows:
        print('[ROUND 2]',row['case'],row['mean_mm'],'mm',flush=True)
    if args.verify_inputs:
        runner.verify_inputs(rows)
        return
    if args.dry_run:
        print('[OK] Three fresh inputs verified; no simulations launched.',flush=True)
        return
    runner.run_batch(rows)
    status=BATCH/'plot_status.json'
    status.write_text(json.dumps({'state':'running'}))
    command=[sys.executable,'-X','utf8','-u','01_Secondary_Scripts/plot_normal_stress_and_mesh_quality.py','--include-round2']
    with (BATCH/'plot_refresh.log').open('w',encoding='utf-8') as log:
        with subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace') as process:
            for line in process.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
            code=process.wait()
    if code:
        status.write_text(json.dumps({'state':'failed','returncode':code}))
        raise RuntimeError('Simulations completed, but plot refresh failed; inspect plot_refresh.log')
    verify_path=ROOT/'simulation_outputs/normal_equal_mean_batch/stress_and_mesh_quality/verification.json'
    verified=json.loads(verify_path.read_text())
    assert verified['cases']==24 and verified['round_counts']=={'1':21,'2':3}
    assert verified['violin_center']=='mean'
    status.write_text(json.dumps({'state':'completed','cases':24,'verification':str(verify_path)},indent=2))
    (BATCH/'ROUND2_COMPLETE.json').write_text(json.dumps({'simulations':3,'combined_cases':24,'figure':verified['figure']},indent=2))
    print('[ROUND 2 COMPLETE] Three solves verified; combined 24-case mean-marker figure saved.',flush=True)


if __name__=='__main__':
    main()
