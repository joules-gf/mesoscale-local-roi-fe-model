"""Isolated, resume-safe 75/150/155/160 um mesh_min_angle=30 study.

No original input/output is altered. Direct use of established generation helpers
permits an isolated output root without patching the global pipeline. Midpoints
without saved polygon caches are regenerated deterministically, then every
polygon facet and material/seed mapping is checked against the solved source INP.
Successful solves are never re-submitted. Run with repo Windows Python.
"""
from pathlib import Path
import sys
import os
import csv
import time
import json
import shutil
import re
import math
import xml.etree.ElementTree as ET
from datetime import datetime

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'00_Main_Scripts'))
from mesh_angle30_quality import STUDY, REF, NEW_SOURCES, parse_mesh, sha, succeeded, read_stress, write_csv, analyze
INPUT=ROOT/'simulation_inputs'/'Uniform Distribution'/'sensitivity-study-AA7075-T651'/'bp_same_mean_diameter'/'mesh-min-angle-30-comparison'

def geometry_check(source,pmesh,seeds):
    """Check all subdivided solved facets against regenerated polygon facets.

For each Surface-i, all nodes must lie on facet i, span both endpoints and
have summed length equal to the polygon edge. Material elsets must associate
every occupied seed with the same phase as the regenerated seed list.
"""
    path=source/'msp_mesh_files'/'trimesh.inp';nodes,elements=parse_mesh(path)
    surfaces={};materials={};seedsets={};state=None;current=None
    for line in path.read_text().splitlines():
        s=line.strip()
        if not s or s.startswith('**'):continue
        if s.startswith('*'):
            state=None
            mt=re.search(r'^\*Surface,\s*name=Surface-(\d+),\s*type=element',s,re.I)
            if mt:state='surface';current=int(mt.group(1));surfaces[current]=[]
            mt=re.search(r'^\*Elset,\s*elset=Set-E-Material-(\d+)',s,re.I)
            if mt:state='material';current=int(mt.group(1));materials[current]=set()
            mt=re.search(r'^\*Elset,\s*elset=Set-E-Seed-(\d+)',s,re.I)
            if mt:state='seed';current=int(mt.group(1));seedsets[current]=set()
            continue
        if state=='surface':
            eid,face=s.split(',')[:2];surf=face.strip().upper();idx={'S1':(0,1),'S2':(1,2),'S3':(2,0)}[surf];ids=elements[int(eid)][1]
            surfaces[current].append((nodes[ids[idx[0]]],nodes[ids[idx[1]]]))
        elif state=='material':materials[current].update(int(n) for n in re.findall(r'Set-E-Seed-(\d+)',s))
        elif state=='seed':seedsets[current].update(int(n.strip()) for n in s.split(',') if n.strip())
    if set(surfaces)!=set(range(len(pmesh.facets))):raise ValueError('Polygon facet number mismatch')
    # MicroStructPy's TXT polygon cache uses six digits after the scientific
    # decimal: coordinates can differ by ~5e-8 mm from the full-precision INP.
    # This is a bounded serialization limitation, NOT exact geometry identity.
    tolerance=1e-7
    max_error=0;max_endpoint_error=0
    for i,facet in enumerate(pmesh.facets):
        if len(facet)!=2:raise ValueError('Expected 2D facets')
        a,b=[pmesh.points[j] for j in facet];length=math.dist(a,b);dx=b[0]-a[0];dy=b[1]-a[1];ts=[];segment_sum=0
        for c,d in surfaces[i]:
            segment_sum+=math.dist(c,d)
            for p in (c,d):
                error=abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))/length;max_error=max(max_error,error)
                t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(length*length);ts.append(t)
                if error>tolerance or t*length< -tolerance or (t-1)*length>tolerance:raise ValueError(f'Facet {i} geometry mismatch')
        endpoint_error=max(abs(min(ts)),abs(max(ts)-1))*length;max_endpoint_error=max(max_endpoint_error,endpoint_error)
        if endpoint_error>tolerance or abs(segment_sum-length)>2*tolerance:raise ValueError(f'Facet {i} endpoint/coverage mismatch')
    for phase,ids in materials.items():
        if any(seeds[i].phase!=phase for i in ids):raise ValueError('Material assignment mismatch')
    if set().union(*materials.values())!=set(seedsets):raise ValueError('Seed material coverage mismatch')
    return {'source_mesh_sha256':sha(path),'polygon_facet_count':len(surfaces),'occupied_seed_count':len(seedsets),'max_facet_distance_error_mm':max_error,'max_endpoint_projection_error_mm':max_endpoint_error,'geometry_tolerance_mm':tolerance,'all_facets_and_materials_match':True,'exact_geometry_identity':False,'limitation':'MicroStructPy TXT caches round polygon coordinates; facet/material geometry verified within 1e-7 mm, not bitwise identical coordinates.'}

def verify_loaded_geometry(source,dest,msp):
    proof_path=dest/'geometry_preservation.json';proof=json.loads(proof_path.read_text())
    meshdir=dest/'msp_mesh_files';poly=msp.meshing.PolyMesh.from_file(str(meshdir/'polymesh.txt'));seeds=msp.seeding.SeedList.from_file(str(meshdir/'seeds.txt'))
    proof['loaded_cache_vs_source_mesh']=geometry_check(source,poly,seeds)
    proof['loaded_cache_vs_new_mesh']=geometry_check(dest,poly,seeds)
    proof['limitation']='Polygon/material geometry checked within 1e-7 mm; TXT coordinate rounding prevents exact full-precision identity.'
    proof_path.write_text(json.dumps(proof,indent=2),encoding='utf-8')

def run_case(diameter):
    import abaqus_input_generation_v02 as gen
    from run_abaqus_sim import run_simulation
    from postprocessing_abaqus_sim_v01 import post_processing
    source=NEW_SOURCES[diameter];case=f'mesh_angle30_{diameter:03}um';dest=STUDY/case
    input_path=INPUT/(case+'.xml');INPUT.mkdir(parents=True,exist_ok=True);dest.mkdir(parents=True,exist_ok=True)
    start=datetime.now().isoformat();clock=time.perf_counter()
    print('START',case,start,flush=True)
    if succeeded(dest) and (dest/(case+'.csv')).exists():
        verify_loaded_geometry(source,dest,gen.get_microstructpy())
        print('RESUME successful solve: never rerun',case,read_stress(dest/(case+'.csv')),flush=True)
        return
    tree=ET.parse(source/(source.name+'_resolved_input.xml'));root=tree.getroot()
    root.find('settings/mesh_min_angle').text=' 30 ';root.find('settings/restart').text=' True '
    # Input copying is deterministic; refuse silently replacing any edited study input.
    ET.indent(tree,space='    ');text=ET.tostring(root,encoding='unicode')
    if input_path.exists() and input_path.read_text()!=text:raise ValueError('Existing study input differs')
    if not input_path.exists():input_path.write_text(text,encoding='utf-8')
    meshdir=dest/'msp_mesh_files';meshdir.mkdir(exist_ok=True);abdir=dest/'abaqus_files';abdir.mkdir(exist_ok=True)
    proof_path=dest/'geometry_preservation.json'
    completed_input,name,_,_,ec_dir,expanded=gen.complete_input_data(str(input_path))
    domain,phases,settings,abaqus=completed_input
    # Override only this invocation's explicit return paths/settings.
    settings['directory']=str(meshdir);settings['restart']=True;settings['mesh_min_angle']=30
    msp=gen.get_microstructpy()
    if not proof_path.exists():
        if (meshdir/'trimesh.txt').exists() or (meshdir/'trimesh.inp').exists():raise ValueError('Triangle artifacts exist without geometry proof')
        source_mesh=source/'msp_mesh_files';hashes={}
        if (source_mesh/'seeds.txt').exists() and (source_mesh/'polymesh.txt').exists():
            for filename in ('seeds.txt','polymesh.txt'):
                shutil.copy2(source_mesh/filename,meshdir/filename);hashes[filename]=sha(source_mesh/filename)
            seeds=msp.seeding.SeedList.from_file(str(meshdir/'seeds.txt'));poly=msp.meshing.PolyMesh.from_file(str(meshdir/'polymesh.txt'));method='copied exact source caches'
        else:
            print('Regenerating missing midpoint polygon caches deterministically',flush=True)
            rng=settings.get('rng_seeds',{});seeds=msp.cli._unpositioned_seeds(phases,domain,rng)
            seeds.position(domain,{i:p['position'] for i,p in enumerate(phases) if 'position' in p},rng.get('position',0),rtol=settings.get('rtol','fit'),verbose=True)
            poly=msp.meshing.PolyMesh.from_seeds(seeds,domain,settings.get('edge_opt',False),settings.get('edge_opt_n_iter',100),True)
            seeds.write(str(meshdir/'seeds.txt'),format='txt');poly.write(str(meshdir/'polymesh.txt'),'txt');method='deterministic geometry recovery; checked every source facet/material'
        proof=geometry_check(source,poly,seeds)
        proof.update({'method':method,'source_case':str(source),'source_cache_hashes':hashes,'new_cache_hashes_before':{f:sha(meshdir/f) for f in ('seeds.txt','polymesh.txt')},'triangle_artifacts_omitted':True,'requested_min_angle_deg':30,'requested_max_edge_mm':settings['mesh_max_edge_length']})
        proof_path.write_text(json.dumps(proof,indent=2),encoding='utf-8')
    proof=json.loads(proof_path.read_text())
    if not (abdir/(case+'.inp')).exists():
        shutil.copy2(expanded,dest/(case+'_resolved_input.xml'))
        msp.cli.run(phases=phases,domain=domain,**settings)
        after={f:sha(meshdir/f) for f in ('seeds.txt','polymesh.txt')}
        if after!=proof['new_cache_hashes_before']:raise ValueError('Polygon/seeds changed during triangulation')
        proof['new_cache_hashes_after']=after;proof['preserved_hashes']=True;proof_path.write_text(json.dumps(proof,indent=2),encoding='utf-8')
        shutil.copy2(meshdir/'trimesh.inp',abdir/(case+'.inp'))
        gen.abaqus_input_file_completion(str(abdir/(case+'.inp')),abaqus,phases,gen.extract_plastic_stresses(abaqus));gen.wrap_abaqus_elset_include_lines(str(abdir/(case+'.inp')))
    verify_loaded_geometry(source,dest,msp)
    if not succeeded(dest):run_simulation(str(abdir),case)
    if not succeeded(dest):raise RuntimeError('Abaqus .sta not successful '+case)
    if not (dest/(case+'.csv')).exists():post_processing(str(abdir),case,None)
    stress=read_stress(dest/(case+'.csv'));elapsed=time.perf_counter()-clock
    row={'case':case,'diameter_microns':diameter,'start_time':start,'end_time':datetime.now().isoformat(),'elapsed_seconds':elapsed,'stress_at_1pct_MPa':stress,'sta_success':True,'geometry_preserved':proof['all_facets_and_materials_match'],'output_dir':str(dest)}
    write_csv(dest/'runtime_result.csv',[row])
    rows=[]
    for p in STUDY.glob('mesh_angle30_*/runtime_result.csv'):
        with p.open(newline='') as f:rows.extend(csv.DictReader(f))
    write_csv(STUDY/'runtime_summary.csv',rows)
    print('DONE',case,'seconds',elapsed,'stress',stress,flush=True)

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--existing-only',action='store_true');p.add_argument('--case',type=int);p.add_argument('--analyze-only',action='store_true');args=p.parse_args()
    os.chdir(ROOT)
    for k,v in {'MPLBACKEND':'Agg','MICROSTRUCTURE_NONINTERACTIVE':'1','PYTHONIOENCODING':'utf-8','PYTHONUNBUFFERED':'1'}.items():os.environ[k]=v
    STUDY.mkdir(parents=True,exist_ok=True);REF.mkdir(parents=True,exist_ok=True)
    if args.existing_only:analyze(False);return
    if not args.analyze_only:
        for d in ([args.case] if args.case else [160,155,150,75]):run_case(d)
    if not args.case:analyze(True)
    (STUDY/'COMPLETED.txt').write_text(datetime.now().isoformat()+'\n',encoding='utf-8')

if __name__=='__main__':main()
