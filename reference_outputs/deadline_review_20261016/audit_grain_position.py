"""Read-only source audit; writes only deadline_review_20261016 audit artifacts."""
from pathlib import Path
import csv, json, hashlib, re, ast, statistics as st, xml.etree.ElementTree as ET
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'reference_outputs/Uniform Distribution/Sensitivity Study'
def digest(b): return hashlib.sha256(b).hexdigest()
def fingerprint(obj): return digest(json.dumps(obj,separators=(',',':')).encode())
def scan():
    result=[]
    for name in ['Grain Position','RNG']:
        p=STUDY/name
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file() and not any(part.startswith('bp_') for part in f.relative_to(p).parts[:-1]):
                    result.append({'path':str(f.relative_to(ROOT)),'bytes':f.stat().st_size,'sha256':digest(f.read_bytes())})
    return result
artifacts=scan()
rows=[]; groups={}
for prefix in ['bp_position','bp_rng_size']:
    cases=sorted(p.parent for p in STUDY.rglob(prefix+'*_resolved_input.xml'))
    assert len(cases)==18,(prefix,len(cases))
    for case in cases:
        name=case.name
        xp=case/(name+'_resolved_input.xml'); cp=case/(name+'.csv'); sp=case/'msp_mesh_files/seeds.txt'
        xb=xp.read_bytes(); cb=cp.read_bytes(); sb=sp.read_bytes()
        x=ET.fromstring(xb)
        rng={e.tag:int(e.text.strip()) for e in x.findall('./settings/rng_seeds/*')}
        mats=[{e.tag:({s.tag:s.text.strip() for s in e} if len(e) else e.text.strip()) for e in m} for m in x.findall('material')]
        assert float(x.findtext('./domain/side_length'))==1
        numeric=[]
        for line in csv.reader(cb.decode().splitlines()):
            try: numeric.append(tuple(float(v) for v in line))
            except ValueError: pass
        assert numeric and all(b[1]>=a[1] for a,b in zip(numeric,numeric[1:])),name
        target=.01
        exact=[v for v in numeric if v[1]==target]
        near=[v for v in numeric if abs(v[1]-target)<=5e-10 and abs(v[0]-1)<=1e-9]
        if exact: endpoint=exact[0][2]; method='exact'; used=exact[0][1]
        elif near: endpoint=near[0][2]; method='nominal terminal 1% (single-precision displacement tolerance 5e-10)'; used=near[0][1]
        else:
            pairs=[(a,b) for a,b in zip(numeric,numeric[1:]) if a[1]<target<b[1]]
            assert len(pairs)==1,(name,'no target bracket')
            a,b=pairs[0]; endpoint=a[2]+(target-a[1])*(b[2]-a[2])/(b[1]-a[1]);method='linear interpolation';used=target
        pairs=[]; positions=[]
        for block in sb.decode().split('Geometry:')[1:]:
            radius=float(re.search(r'^Radius:\s*(.*)$',block,re.M).group(1)); phase=int(re.search(r'^Phase:\s*(.*)$',block,re.M).group(1))
            pos=ast.literal_eval(re.search(r'^Position:\s*(.*)$',block,re.M).group(1))
            pairs.append([phase,2*radius]);positions.append(pos)
        row={'case':name,'folder':str(case.relative_to(ROOT)),'ensemble':prefix,'size_rng_xml':rng.get('size'),'size_rng_effective':rng.get('size',0),'position_rng':rng.get('position',0),'stress_at_1pct_MPa':endpoint,'sampled_strain':used,'endpoint_method':method,'n_curve_rows':len(numeric),'seed_count':len(pairs),'phase_diameter_sha256':fingerprint(pairs),'positions_sha256':fingerprint(positions),'csv_sha256':digest(cb),'xml_sha256':digest(xb),'seeds_sha256':digest(sb)}
        rows.append(row)
        groups.setdefault(prefix,{'rng_xml':[],'material_distributions':[],'inventories':{},'cases':[]})
        g=groups[prefix];g['rng_xml'].append(rng);g['cases'].append(name)
        if mats not in g['material_distributions']:g['material_distributions'].append(mats)
        g['inventories'].setdefault(row['phase_diameter_sha256'],{'n':len(pairs),'phase_counts':{str(p):sum(v[0]==p for v in pairs) for p in sorted(set(v[0] for v in pairs))},'diameter_min_mm':min(v[1] for v in pairs),'diameter_max_mm':max(v[1] for v in pairs),'diameter_mean_mm':st.mean(v[1] for v in pairs)})
summary=[]
for name,g in groups.items():
    rr=[r for r in rows if r['ensemble']==name];v=[r['stress_at_1pct_MPa'] for r in rr];mu=st.mean(v);sd=st.stdev(v)
    s={'ensemble':name,'effective_size_rng':rr[0]['size_rng_effective'],'n':len(v),'mean_MPa':mu,'sample_std_MPa':sd,'min_MPa':min(v),'max_MPa':max(v),'range_MPa':max(v)-min(v),'relative_span_percent':100*(max(v)-min(v))/mu,'sample_CV_percent':100*sd/mu,'distinct_diameter_inventories':len(g['inventories']),'distinct_position_arrays':len(set(r['positions_sha256'] for r in rr))}
    assert s['distinct_diameter_inventories']==1 and s['distinct_position_arrays']==18
    summary.append(s)
    g['summary']=s
for filename,data in [('grain_position_cases.csv',rows),('grain_position_endpoint_statistics.csv',summary)]:
    with (OUT/filename).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
report={'audited_at_utc':datetime.now(timezone.utc).isoformat(),'source_root':str(ROOT),'target_strain':.01,'stress_units_note':'CSV index 1 is U_Y/strain for 1 mm side; index 2 is Total RF Y/nominal stress for unit section, MPa. No arbitrary summary CSV included.','endpoint_note':'All curves checked monotonic. Exact target preferred, bracket interpolation otherwise; completed step-time 1 row within 5e-10 strain accepted as nominal prescribed 1%, not extrapolated.','std_convention':'sample standard deviation ddof=1; sample CV=100*s/mean; span=100*(max-min)/mean','size_rng_default_evidence':'.venv/Lib/site-packages/microstructpy/seeding/seedlist.py documents default RNG seed 0; RNG XML lacks size field.','distribution_note':'Resolved XML uniform loc .05 mm with scale absent; abaqus_input_generation_v02.py complete_input_data supplies scale 20% of loc. Saved finite inventories verified directly, not final tessellated diameters.','aggregate_artifacts_at_initial_scan':artifacts,'groups':groups,'cases':rows}
(OUT/'grain_position_audit.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['# Grain-position audit / Figure 9a','',f"Source: `{ROOT}`.",'','## Verified endpoint statistics','At nominal 1% tensile strain, MPa. Sample SD uses ddof=1. Span is range/mean, not a confidence interval.','','| Fixed size RNG | n | Mean | Sample SD | Min | Max | Range | Span (%) | Sample CV (%) |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for s in summary: lines.append(f"| {s['effective_size_rng']} | {s['n']} | {s['mean_MPa']:.6f} | {s['sample_std_MPa']:.6f} | {s['min_MPa']:.6f} | {s['max_MPa']:.6f} | {s['range_MPa']:.6f} | {s['relative_span_percent']:.6f} | {s['sample_CV_percent']:.6f} |")
lines += ['','## Deadline-focused Figure 9a interpretation','- Both existing ensembles vary placement, not sampled size: each has exactly one ordered phase/diameter fingerprint and 18 distinct position fingerprints. `bp_position*` fixes size RNG 1000; misleadingly named `bp_rng_size*` omits size RNG (effective default 0) and varies position RNG. Treat them as two fixed-size placement ensembles, not 36 draws of grain size.','- Minimal suggested wording: “Changing the grain-position realization produced a small but nonzero variation in the macroscopic tensile response for each of the two fixed grain-size realizations examined.” Add the endpoint range percentages from the table if useful.','- If Figure 9a contains only the original `bp_position*` ensemble, quote its statistics only. A combined figure may show both ensembles with separate labels; do not pool them into a single position-only variance estimate or claim distribution-family robustness, local-field insensitivity, statistical convergence, or universal placement independence.','- A second fixed-size realization supports repeating the placement comparison, not broad inference over all size realizations. No new simulations are required to support this bounded wording.','','## Provenance and endpoint handling','- Saved CSV columns are read by numeric index 1 (strain/U_Y) and 2 (stress/Total RF Y); each source XML has unit domain side. All selected curves are monotonic.','- Completed step-time 1 endpoints are stored at 0.009999999776482582 strain (single-precision displacement); accepted as nominal prescribed 1% within 5e-10 absolute tolerance. No out-of-range extrapolation or arbitrary final-row selection.','- Material XML specifies uniform loc=0.05 mm, phase fractions 0.1/0.1/0.4/0.4, and no explicit scale. Generator fills missing scale with 20% of loc; saved inventories are the direct fixed-size evidence. These are seed sizes, not measured final tessellated-grain sizes.','','## New separate/combined plots and statistics','- Repeated bounded scans of the current Desktop `Grain Position` and `RNG` trees found case-level figures but no separate/combined aggregate plots or summary/statistics files at audit time. The equivalent Documents paths do not exist. This is a current snapshot, not a claim that another session cannot create them later.','- No original plot or case file was changed. Source paths and SHA-256 values are retained in JSON/CSV; final verification re-discovers moved cases by filename.']
(OUT/'grain_position_figure9a_review.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,indent=2))
print('WROTE',*[str(OUT/n) for n in ['grain_position_cases.csv','grain_position_endpoint_statistics.csv','grain_position_audit.json','grain_position_figure9a_review.md']],sep='\n')
