"""Reproducible quality audit of actual Abaqus CPS3 meshes; no solver calls."""
from pathlib import Path
import csv
import math
import re
import json
import hashlib
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'simulation_outputs'/'mesh_min_angle_30_comparison'
REF=ROOT/'reference_outputs'/'Uniform Distribution'/'Sensitivity Study'/'mesh-min-angle-30-comparison'
ORIGINAL=ROOT/'simulation_outputs'/'sensitivity-mean-diameter-diff-4all-phases'
MIDPOINTS=['bp_same_size_case_07_08_mid_070um','bp_same_size_case_08_09_mid_080um','bp_same_size_case_15_16_mid_150um','bp_same_size_case_16_17_mid_160um']
NEW_SOURCES={75:ORIGINAL/'bp_same_size_case_08',150:ROOT/'simulation_outputs'/MIDPOINTS[2],155:ORIGINAL/'bp_same_size_case_16',160:ROOT/'simulation_outputs'/MIDPOINTS[3]}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
    return h.hexdigest()

def parse_mesh(path):
    """Parse all part node/element sections, reject unsupported topology/duplicates."""
    nodes={}; elements={}; state=None; typ=None; in_assembly=False
    for line in Path(path).read_text().splitlines():
        s=line.strip()
        if not s or s.startswith('**'): continue
        if s.startswith('*'):
            key=s.split(',')[0].lower()
            if key=='*assembly': in_assembly=True
            if key=='*end assembly': in_assembly=False
            state=None
            if key=='*node' and not in_assembly: state='node'
            if key=='*element' and not in_assembly:
                match=re.search(r'type\s*=\s*([^,]+)',s,re.I)
                typ=match.group(1).strip().upper() if match else ''
                if typ not in ('CPS3','CPE3','CAX3','S3','STRI3'): raise ValueError(f'Unsupported element type {typ}: {path}')
                state='element'
            continue
        vals=[v.strip() for v in s.split(',') if v.strip()]
        if state=='node':
            nid=int(vals[0]); xy=tuple(float(v) for v in vals[1:])
            if nid in nodes or len(xy)<2: raise ValueError('Duplicate/invalid node')
            if len(xy)>2 and abs(xy[2])>1e-12: raise ValueError('Nonplanar node')
            nodes[nid]=xy[:2]
        elif state=='element':
            eid=int(vals[0]); ids=tuple(map(int,vals[1:]))
            if eid in elements or len(ids)!=3 or len(set(ids))!=3: raise ValueError('Duplicate/nontriangle element')
            elements[eid]=(typ,ids)
    if not nodes or not elements: raise ValueError(f'Empty mesh: {path}')
    for _,ids in elements.values():
        if any(n not in nodes for n in ids): raise ValueError('Undefined node')
    return nodes,elements

def triangle_quality(points):
    if len(points)!=3: raise ValueError('Triangle requires three nodes')
    a,b,c=points
    edges=[math.dist(a,b),math.dist(b,c),math.dist(c,a)]
    area=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
    if min(edges)<=0 or area<=0: raise ValueError('Degenerate triangle')
    angles=[]
    for i in range(3):
        p=points[i]; q=points[(i+1)%3]; r=points[(i+2)%3]
        u=(q[0]-p[0],q[1]-p[1]); v=(r[0]-p[0],r[1]-p[1])
        angles.append(math.degrees(math.atan2(abs(u[0]*v[1]-u[1]*v[0]),u[0]*v[0]+u[1]*v[1])))
    s=sum(edges)/2
    return {'edge_ratio':max(edges)/min(edges),'r_over_R':4*area*area/(s*math.prod(edges)), 'min_angle_deg':min(angles),'area_mm2':area,'longest_edge_mm':max(edges),'shortest_edge_mm':min(edges)}

def read_stress(path,target=.01):
    pts=[]
    with Path(path).open(newline='') as f:
        for row in csv.reader(f):
            try: pts.append((float(row[1]),float(row[2])))
            except (ValueError,IndexError): pass
    pts.sort()
    for x,y in pts:
        if abs(x-target)<1e-8:return y
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        if x0<=target<=x1:return y0+(target-x0)*(y1-y0)/(x1-x0)
    raise ValueError(f'Target strain outside data: {path}')

def write_csv(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: raise ValueError('Empty CSV not allowed')
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def succeeded(case_dir):
    p=Path(case_dir)/'abaqus_files'/(Path(case_dir).name+'.sta')
    return p.exists() and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in p.read_text(errors='replace').upper()

def audit_case(case_dir,group):
    import numpy as np
    case_dir=Path(case_dir);case=case_dir.name
    mesh=case_dir/'abaqus_files'/(case+'.inp'); raw=case_dir/'msp_mesh_files'/'trimesh.inp'
    nodes,elements=parse_mesh(mesh);rn,relems=parse_mesh(raw)
    if nodes!=rn or elements!=relems:raise ValueError(f'Solved vs MSP mismatch {case}')
    if not succeeded(case_dir):raise ValueError(f'Unsuccessful .sta {case}')
    xml=case_dir/(case+'_resolved_input.xml'); root=ET.parse(xml).getroot()
    diameters=[float(x.text)*1000 for x in root.findall('material/size/loc')]
    if len(diameters)!=4 or len(set(diameters))!=1: raise ValueError('Unequal/missing diameters')
    requested=float(root.findtext('settings/mesh_min_angle'));stress_csv=case_dir/(case+'.csv')
    result={'case':case,'group':group,'diameter_microns':diameters[0],'requested_min_angle_deg':requested,'element_count':len(elements),'node_count':len(nodes),'element_types':';'.join(sorted(set(t for t,_ in elements.values()))),'stress_at_1pct_MPa':read_stress(stress_csv),'source_mesh':str(mesh),'source_mesh_sha256':sha(mesh),'source_csv':str(stress_csv),'source_csv_sha256':sha(stress_csv),'sta_success':True,'solved_msp_mesh_match':True}
    metrics={'edge_ratio':[],'r_over_R':[],'min_angle_deg':[]};worst={}; counts={'r_over_R_lt_0p2':0,'r_over_R_0p2_to_0p3':0,'min_angle_below_requested':0,'min_angle_below_25':0,'min_angle_below_30':0}
    out=STUDY/'per_element'/(case+'_element_quality.csv');out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=None
        for eid,(typ,ids) in elements.items():
            points=[nodes[n] for n in ids];q=triangle_quality(points)
            row={'element_id':eid,'element_type':typ,'node_1':ids[0],'node_2':ids[1],'node_3':ids[2], 'x1_mm':points[0][0],'y1_mm':points[0][1],'x2_mm':points[1][0],'y2_mm':points[1][1],'x3_mm':points[2][0],'y3_mm':points[2][1],'centroid_x_mm':sum(p[0] for p in points)/3,'centroid_y_mm':sum(p[1] for p in points)/3,**q}
            if w is None:w=csv.DictWriter(f,fieldnames=list(row));w.writeheader()
            w.writerow(row)
            for k in metrics:
                metrics[k].append(q[k])
                if k not in worst or (q[k]>worst[k][k] if k=='edge_ratio' else q[k]<worst[k][k]):worst[k]=row.copy()
            counts['r_over_R_lt_0p2']+=q['r_over_R']<.2
            counts['r_over_R_0p2_to_0p3']+=.2<=q['r_over_R']<.3
            counts['min_angle_below_requested']+=q['min_angle_deg']<requested-1e-6
            counts['min_angle_below_25']+=q['min_angle_deg']<25-1e-6
            counts['min_angle_below_30']+=q['min_angle_deg']<30-1e-6
    for k,vals in metrics.items():
        for tag,v in zip(('min','p05','median','p95','max'),np.percentile(vals,[0,5,50,95,100])):result[k+'_'+tag]=float(v)
        row=worst[k]
        for field in ('element_id','centroid_x_mm','centroid_y_mm','node_1','node_2','node_3','x1_mm','y1_mm','x2_mm','y2_mm','x3_mm','y3_mm'):result[k+'_worst_'+field]=row[field]
    for k,n in counts.items():result[k+'_count']=n;result[k+'_fraction']=n/len(elements)
    result['per_element_csv']=str(out)
    warnings=[]
    for ext in ('.dat','.msg'):
        p=case_dir/'abaqus_files'/(case+ext)
        if p.exists():
            lines=p.read_text(errors='replace').splitlines()
            warnings.extend([ext+': '+x.strip() for x in lines if re.search(r'warning|distort|negative eigen|numerical singular|zero pivot',x,re.I)])
    (STUDY/'warnings').mkdir(exist_ok=True)
    (STUDY/'warnings'/(case+'.txt')).write_text('\n'.join(warnings),encoding='utf-8')
    result['warning_line_count']=len(warnings)
    write_csv(STUDY/'per_case'/(case+'_summary.csv'),[result])
    print('AUDIT',case,len(elements),'stress',result['stress_at_1pct_MPa'],flush=True)
    return result

def all_cases():
    return [(ORIGINAL/f'bp_same_size_case_{i:02}','original') for i in range(1,21)]+[(ROOT/'simulation_outputs'/c,'midpoint') for c in MIDPOINTS]+[(STUDY/f'mesh_angle30_{d:03}um','angle30') for d in sorted(NEW_SOURCES)]

def analyze(include_new=True):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    STUDY.mkdir(parents=True,exist_ok=True);REF.mkdir(parents=True,exist_ok=True)
    rows=[]
    for case,group in all_cases():
        if group=='angle30' and not include_new:continue
        rows.append(audit_case(case,group))
        write_csv(STUDY/'case_quality_summary.csv',rows)
    expected=28 if include_new else 24
    if len(rows)!=expected or len({r['case'] for r in rows})!=expected:raise ValueError('Case count mismatch')
    rows.sort(key=lambda r:(r['diameter_microns'],r['group']))
    write_csv(STUDY/'case_quality_summary.csv',rows);write_csv(REF/'case_quality_summary.csv',rows)
    old=sorted([r for r in rows if r['group']!='angle30'],key=lambda r:r['diameter_microns']);new=sorted([r for r in rows if r['group']=='angle30'],key=lambda r:r['diameter_microns'])
    fig,ax=plt.subplots(figsize=(10,6))
    ax.plot([r['diameter_microns'] for r in old],[r['stress_at_1pct_MPa'] for r in old],'o-',label='Original 20 + midpoint 4 (25 deg)',lw=1.8)
    if new:ax.plot([r['diameter_microns'] for r in new],[r['stress_at_1pct_MPa'] for r in new],'X',ms=10,color='tab:red',label='Re-triangulated 4 (30 deg)')
    ax.set(xlabel='Phase mean diameter (microns)',ylabel='Stress at 1% strain (MPa)',title='Mesh-angle comparison: actual solved stress')
    ax.grid(alpha=.3);ax.legend();fig.tight_layout();fig.savefig(REF/'stress_original24_vs_angle30_4.png',dpi=240,bbox_inches='tight');plt.close(fig)
    labels=[(f"{r['diameter_microns']:g}"+(' A30' if r['group']=='angle30' else ' M' if r['group']=='midpoint' else '')) for r in rows]
    fig,axes=plt.subplots(3,1,figsize=(15,12),sharex=True)
    for ax,k,ylabel in zip(axes,('edge_ratio','r_over_R','min_angle_deg'),('Longest / shortest edge','Inradius / circumradius','Minimum angle (degrees)')):
        for i,r in enumerate(rows):
            color='tab:red' if r['group']=='angle30' else 'tab:blue'
            ax.plot([i,i],[r[k+'_min'],r[k+'_max']],color=color,alpha=.45)
            ax.plot([i,i],[r[k+'_p05'],r[k+'_p95']],color=color,lw=5,alpha=.65)
            ax.scatter(i,r[k+'_median'],c=color,s=18,zorder=3)
        if k=='r_over_R':ax.axhline(.2,color='orange',ls='--');ax.axhline(.3,color='green',ls='--')
        if k=='min_angle_deg':ax.axhline(25,color='blue',ls='--');ax.axhline(30,color='red',ls='--')
        ax.set_ylabel(ylabel);ax.grid(alpha=.25)
    axes[0].set_title('All case quality distributions: range, p05-p95, median; red = 30 deg')
    axes[-1].set_xticks(range(len(rows)),labels,rotation=65,ha='right');axes[-1].set_xlabel('Diameter (microns); M=midpoint; A30=new')
    fig.tight_layout();fig.savefig(REF/'quality_all28_distributions.png',dpi=220,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(15,8),sharex=True)
    x=np.arange(len(rows));axes[0].bar(x,[r['r_over_R_lt_0p2_fraction'] for r in rows],label='r/R < 0.2');axes[0].bar(x,[r['r_over_R_0p2_to_0p3_fraction'] for r in rows],bottom=[r['r_over_R_lt_0p2_fraction'] for r in rows],label='0.2 <= r/R < 0.3');axes[0].legend();axes[0].set_ylabel('Element fraction')
    axes[1].bar(x,[r['min_angle_below_requested_fraction'] for r in rows],color=['tab:red' if r['group']=='angle30' else 'tab:blue' for r in rows]);axes[1].set_ylabel('Fraction below requested angle');axes[1].set_xticks(x,labels,rotation=65,ha='right');fig.tight_layout();fig.savefig(REF/'quality_all28_threshold_fractions.png',dpi=220,bbox_inches='tight');plt.close(fig)
    pairs=[]
    for r in new:
        src=NEW_SOURCES[int(r['diameter_microns'])].name;orig=next(a for a in rows if a['case']==src)
        pairs.append({'diameter_microns':r['diameter_microns'],'source_case':src,'new_case':r['case'],'original_stress_MPa':orig['stress_at_1pct_MPa'],'new_stress_MPa':r['stress_at_1pct_MPa'],'delta_MPa':r['stress_at_1pct_MPa']-orig['stress_at_1pct_MPa'],'delta_percent':100*(r['stress_at_1pct_MPa']/orig['stress_at_1pct_MPa']-1),'original_elements':orig['element_count'],'new_elements':r['element_count']})
    if pairs:write_csv(REF/'paired_stress_comparison.csv',pairs)
    report=['# Mesh-angle study outlier report','',f'Verified cases: {len(old)} existing + {len(new)} new; all .sta successful and actual solved meshes match MSP nodes/connectivity.','Quality criteria are professor study criteria, not universal acceptance limits: r/R < 0.2 poor-screening; 0.2 <= r/R < 0.3 caution; >=0.3 good-screening. Edge ratio is descriptive, without an imposed acceptance criterion.','Angle violation tolerance: 1e-6 degrees. Requested 30 degrees is not a guarantee, especially at constrained small input angles.','r/R = 4 A^2/(s a b c); equilateral r/R=0.5. All elements included, no degenerates/nontriangles permitted.','', '## Paired stress changes']
    for p in pairs:report.append(f"- {p['diameter_microns']:g} microns: {p['original_stress_MPa']:.6f} -> {p['new_stress_MPa']:.6f} MPa ({p['delta_percent']:+.4f}%).")
    report+=['','## Empirical IQR screening (not numerical causation)']
    for metric in ('edge_ratio_max','r_over_R_lt_0p2_fraction','min_angle_below_requested_fraction','stress_at_1pct_MPa'):
        vals=np.array([r[metric] for r in old]);q1,q3=np.percentile(vals,[25,75]);lo=q1-1.5*(q3-q1);hi=q3+1.5*(q3-q1)
        flagged=[r for r in rows if r[metric]<lo or r[metric]>hi]
        report.append(f'- {metric}: existing24 IQR fences [{lo:.6g}, {hi:.6g}]; '+(', '.join(f"{r['case']}={r[metric]:.6g}" for r in flagged) or 'none'))
    report+=['','## Worst actual elements']
    for r in sorted(rows,key=lambda r:r['r_over_R_min'])[:5]:report.append(f"- {r['case']}: min r/R={r['r_over_R_min']:.6g}, element {r['r_over_R_worst_element_id']}, centroid ({r['r_over_R_worst_centroid_x_mm']:.8g}, {r['r_over_R_worst_centroid_y_mm']:.8g}) mm; min angle={r['min_angle_deg_min']:.6g} deg, max edge ratio={r['edge_ratio_max']:.6g}.")
    report+=['','Warnings are saved per case in simulation study/warnings; successful solves do not prove convergence or that morphology/mesh quality caused stress outliers.','Primary sources: MicroStructPy installed cli.py restart branches (seeds/poly reuse but omitted trimesh.txt triggers new triangulation); MicroStructPy settings documentation; Triangle -q documentation.','https://docs.microstructpy.org/en/latest/cli/settings.html','https://www.cs.cmu.edu/~quake/triangle.q.html']
    (REF/'outlier_report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    integrity=[]
    for p in REF.glob('*.png'):
        with Image.open(p) as im:im.verify()
        with Image.open(p) as im:
            arr=np.asarray(im.convert('RGB'));assert arr.std()>1;integrity.append({'path':str(p),'width':im.width,'height':im.height,'bytes':p.stat().st_size,'sha256':sha(p)})
    verification={'case_count':len(rows),'existing_count':len(old),'new_count':len(new),'all_sta_success':True,'all_mesh_matches':True,'per_element_csv_count':len(list((STUDY/'per_element').glob('*.csv'))),'total_elements':sum(r['element_count'] for r in rows),'figures':integrity}
    (REF/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    print(json.dumps(verification,indent=2),flush=True)
    return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--existing-only',action='store_true');args=p.parse_args();analyze(not args.existing_only)
