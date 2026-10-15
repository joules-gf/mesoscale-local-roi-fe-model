"""Independent durable readback verifier; run only after all28 analyses finish."""
from pathlib import Path
import csv
import json
import math
import sys
from mesh_angle30_quality import ROOT,STUDY,REF,NEW_SOURCES,all_cases,parse_mesh,sha,read_stress,succeeded

def verify():
    with (STUDY/'case_quality_summary.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    expected={p.name for p,_ in all_cases()}
    baseline=json.loads((STUDY/'original24_pre_resume_hashes.json').read_text())
    assert len(baseline)==24
    for old in baseline:
        assert sha(old['source_mesh'])==old['source_mesh_sha256'] and sha(old['source_csv'])==old['source_csv_sha256']
    assert len(rows)==28 and {r['case'] for r in rows}==expected
    assert sum(r['group']!='angle30' for r in rows)==24
    verified=[]
    for r in rows:
        case=r['case'];elements=int(r['element_count']);path=Path(r['source_mesh']);sourcecsv=Path(r['source_csv']);case_dir=path.parent.parent
        assert succeeded(case_dir)
        assert sha(path)==r['source_mesh_sha256'] and sha(sourcecsv)==r['source_csv_sha256']
        assert math.isclose(read_stress(sourcecsv),float(r['stress_at_1pct_MPa']),rel_tol=1e-12)
        import numpy as np
        nodes,mesh_elements=parse_mesh(path)
        raw_nodes,raw_elements=parse_mesh(case_dir/'msp_mesh_files'/'trimesh.inp')
        assert nodes==raw_nodes and mesh_elements==raw_elements and len(mesh_elements)==elements
        ids=set();counts={k:0 for k in ('r_over_R_lt_0p2','r_over_R_0p2_to_0p3','min_angle_below_requested','min_angle_below_25','min_angle_below_30')};minima={k:float('inf') for k in ('edge_ratio','r_over_R','min_angle_deg')};maxima={k:float('-inf') for k in minima}
        values={k:[] for k in minima};worst={}
        # Independently derive metrics from solved nodes, not reported columns.
        p=Path(r['per_element_csv'])
        with p.open(newline='') as f:
            for elem in csv.DictReader(f):
                eid=int(elem['element_id']);assert eid not in ids;ids.add(eid)
                typ,nids=mesh_elements[eid]
                assert typ==elem['element_type'] and nids==tuple(int(elem[f'node_{i}']) for i in (1,2,3))
                pts=[nodes[n] for n in nids]
                for i,pt in enumerate(pts,1):
                    assert pt==(float(elem[f'x{i}_mm']),float(elem[f'y{i}_mm']))
                lengths=[math.dist(pts[i],pts[(i+1)%3]) for i in range(3)]
                angles=[]
                for i in range(3):
                    a,b,c=pts[i],pts[(i+1)%3],pts[(i+2)%3]
                    u=(b[0]-a[0],b[1]-a[1]);v=(c[0]-a[0],c[1]-a[1])
                    angles.append(math.atan2(abs(u[0]*v[1]-u[1]*v[0]),u[0]*v[0]+u[1]*v[1]))
                independent={'edge_ratio':max(lengths)/min(lengths),'r_over_R':4*math.prod(math.sin(a/2) for a in angles),'min_angle_deg':math.degrees(min(angles))}
                for k in minima:
                    v=float(elem[k]);assert math.isfinite(v) and math.isclose(v,independent[k],rel_tol=1e-9,abs_tol=1e-12)
                    minima[k]=min(minima[k],v);maxima[k]=max(maxima[k],v);values[k].append(v)
                    if k not in worst or (v>worst[k][0] if k=='edge_ratio' else v<worst[k][0]):worst[k]=(v,eid)
                q=float(elem['r_over_R']);angle=float(elem['min_angle_deg']);assert 0<q<=.5+1e-12 and angle>0
                counts['r_over_R_lt_0p2']+=q<.2;counts['r_over_R_0p2_to_0p3']+=.2<=q<.3;counts['min_angle_below_requested']+=angle<float(r['requested_min_angle_deg'])-1e-6
                counts['min_angle_below_25']+=angle<25-1e-6;counts['min_angle_below_30']+=angle<30-1e-6
        assert len(ids)==elements
        for k in minima:
            assert math.isclose(minima[k],float(r[k+'_min']),rel_tol=1e-12)
            assert math.isclose(maxima[k],float(r[k+'_max']),rel_tol=1e-12)
            for tag,v in zip(('p05','median','p95'),np.percentile(values[k],[5,50,95])):
                assert math.isclose(float(v),float(r[k+'_'+tag]),rel_tol=1e-12)
            assert worst[k][1]==int(r[k+'_worst_element_id'])
            centroid=tuple(sum(nodes[n][i] for n in mesh_elements[worst[k][1]][1])/3 for i in (0,1))
            assert centroid==(float(r[k+'_worst_centroid_x_mm']),float(r[k+'_worst_centroid_y_mm']))
        for k,n in counts.items():assert n==int(r[k+'_count']) and math.isclose(n/elements,float(r[k+'_fraction']),rel_tol=1e-12,abs_tol=1e-15)
        if r['group']=='angle30':
            proof=json.loads((case_dir/'geometry_preservation.json').read_text())
            assert proof['all_facets_and_materials_match'] and proof['preserved_hashes'] and proof['triangle_artifacts_omitted']
            for label in ('loaded_cache_vs_source_mesh','loaded_cache_vs_new_mesh'):
                check=proof[label];assert check['all_facets_and_materials_match'] and not check['exact_geometry_identity']
                assert check['geometry_tolerance_mm']==1e-7
                assert check['max_facet_distance_error_mm']<=1e-7 and check['max_endpoint_projection_error_mm']<=1e-7
            with (case_dir/'runtime_result.csv').open(newline='') as f:runtime=list(csv.DictReader(f))
            assert len(runtime)==1 and float(runtime[0]['elapsed_seconds'])>0
            assert math.isclose(float(runtime[0]['stress_at_1pct_MPa']),float(r['stress_at_1pct_MPa']),rel_tol=1e-12)
            for f,h in proof['new_cache_hashes_before'].items():assert sha(case_dir/'msp_mesh_files'/f)==h
            source=NEW_SOURCES[int(float(r['diameter_microns']))]
            assert sha(source/'msp_mesh_files'/'trimesh.inp')==proof['source_mesh_sha256']
            for f,h in proof['source_cache_hashes'].items():assert sha(source/'msp_mesh_files'/f)==h
        verified.append({'case':case,'actual_csv_elements':len(ids),'csv_sha256':sha(p),'source_hashes_unchanged':True})
        print('VERIFIED',case,len(ids),flush=True)
    with (REF/'paired_stress_comparison.csv').open(newline='') as f:pairs=list(csv.DictReader(f))
    assert len(pairs)==4
    lookup={r['case']:r for r in rows}
    for pair in pairs:
        old=float(lookup[pair['source_case']]['stress_at_1pct_MPa']);new=float(lookup[pair['new_case']]['stress_at_1pct_MPa'])
        assert math.isclose(float(pair['delta_MPa']),new-old,rel_tol=1e-12)
        assert math.isclose(float(pair['delta_percent']),100*(new/old-1),rel_tol=1e-12)
    from PIL import Image
    plot_report=json.loads((REF/'verification.json').read_text())
    assert plot_report['case_count']==28 and plot_report['new_count']==4 and len(plot_report['figures'])==3
    for fig in plot_report['figures']:
        assert sha(fig['path'])==fig['sha256']
        with Image.open(fig['path']) as im:im.verify()
    result={'all_acceptance_checks_passed':True,'independent_node_based_metrics_passed':True,'percentiles_bands_worst_ids_passed':True,'original24_pre_resume_hashes_unchanged':True,'paired_stresses_and_three_figures_passed':True,'exact_cases':28,'existing_cases':24,'new_cases':4,'per_element_csvs':len(verified),'actual_csv_element_rows':sum(v['actual_csv_elements'] for v in verified),'cases':verified}
    (REF/'independent_readback_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2),flush=True)

if __name__=='__main__':verify()
