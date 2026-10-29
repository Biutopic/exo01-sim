"""Independent artifact checks: STEP read-back, GLB metadata and geometry scale."""
from pathlib import Path
import json, struct, re
import numpy as np
import cadquery as cq

root=Path(__file__).resolve().parent
meta=json.loads((root/'EXO01_mass_metadata.json').read_text())
params=json.loads((root/'parameters.json').read_text())
raw=(root/'EXO01_reference.glb').read_bytes()
magic,version,size=struct.unpack_from('<4sII',raw,0)
assert magic==b'glTF' and version==2 and size==len(raw)
json_len,json_type=struct.unpack_from('<I4s',raw,12)
assert json_type==b'JSON'
g=json.loads(raw[20:20+json_len])
bin_start=20+json_len
bin_len,bin_type=struct.unpack_from('<I4s',raw,bin_start)
assert bin_type==b'BIN\0'
data=raw[bin_start+8:bin_start+8+bin_len]
mass_nodes=[n for n in g['nodes'] if 'mass_kg' in n.get('extras',{})]
assert len(mass_nodes)==16
assert len({n['extras']['component_id'] for n in mass_nodes})==16
for n in mass_nodes:
    source=next(c for c in meta['components'] if c['component_id']==n['extras']['component_id'])
    assert n['extras']==source
    for child in n['children']:
        assert 'mass_kg' not in g['nodes'][child].get('extras',{})
total=sum(n['extras']['mass_kg'] for n in mass_nodes)
assert total==meta['mass_summary']['total_listed_mass_kg']
assert meta['engineering_status']['centre_of_gravity_m'] is None
assert not meta['engineering_status']['wave_response_computed']
assert not meta['engineering_status']['buoyancy_mesh_validated']
assert meta['mass_summary']['unlisted_masses_are_zero'] is False
assert meta['revision']==params['revision']=='v3'
assert meta['pending_loads']['upper_deck_occupant_mass_kg'] is None
assert meta['pending_loads']['observation_deck_surface_additional_mass_kg'] is None
deck_node=next(n for n in g['nodes'] if n.get('name')=='upper_observation_deck_proxy')
assert deck_node['extras']['mass_is_in_parent'] is None
assert deck_node['extras']['surface_mass_kg'] is None
panels=[c for c in meta['components'] if c['category']=='solar']
assert len({c['preview_anchor_m'][0] for c in panels})==1
assert len({c['preview_anchor_m'][1] for c in panels})==4
panel_half_length=params['solar_proxy_size_mm'][0]/2000
deck_end=meta['roof_layout']['observation_area']['x_span_m'][1]
assert all(c['preview_anchor_m'][0]-panel_half_length>=deck_end-1e-8 for c in panels)
assert meta['roof_layout']['solar_array']['preview_end_overhang_m']>0
assert meta['roof_layout']['solar_array']['preview_side_overhang_each_m']==0
assert meta['roof_layout']['solar_array']['overhang_measured'] is False
assert np.allclose(g['nodes'][0]['rotation'],[-np.sqrt(.5),0,0,np.sqrt(.5)])
positions=[]
def mesh_positions(mesh):
    prim=mesh['primitives'][0]
    a=g['accessors'][prim['attributes']['POSITION']]
    bv=g['bufferViews'][a['bufferView']]
    offset=bv.get('byteOffset',0)+a.get('byteOffset',0)
    return np.frombuffer(data,dtype='<f4',count=a['count']*3,offset=offset).reshape(-1,3)

# Check exported geometry, not just parameter labels, against the user correction.
deck_positions=mesh_positions(g['meshes'][deck_node['mesh']])
assert np.isclose(deck_positions[:,2].max(),2.2,atol=1e-6)
assert np.isclose(params['frame_height_above_deck_mm']/1000-deck_positions[:,2].max(),.5,atol=1e-6)
solar_nodes=[n for n in mass_nodes if n['extras']['category']=='solar']
solar_positions=np.concatenate([mesh_positions(g['meshes'][g['nodes'][ch]['mesh']]) for n in solar_nodes for ch in n['children']])
half_width=params['frame_width_mm']/2000
assert np.isclose(solar_positions[:,1].min(),-half_width,atol=1e-6)
assert np.isclose(solar_positions[:,1].max(),half_width,atol=1e-6)
assert np.isclose(solar_positions[:,0].min(),deck_end,atol=1e-6)
assert solar_positions[:,0].max()>sum(params['section_lengths_mm'])/1000
for mesh in g['meshes']:
    for prim in mesh['primitives']:
        ai=prim['attributes']['POSITION'];a=g['accessors'][ai];bv=g['bufferViews'][a['bufferView']]
        assert a['componentType']==5126 and a['type']=='VEC3'
        offset=bv.get('byteOffset',0)+a.get('byteOffset',0)
        p=np.frombuffer(data,dtype='<f4',count=a['count']*3,offset=offset).reshape(-1,3)
        assert np.isfinite(p).all() and len(p)%3==0
        assert np.allclose(p.min(axis=0),a['min']) and np.allclose(p.max(axis=0),a['max'])
        positions.append(p)
p=np.concatenate(positions)
mesh_min=p.min(axis=0);mesh_max=p.max(axis=0)
cad=cq.importers.importStep(str(root/'EXO01_reference.step'))
shapes=cad.vals()
compound=cq.Compound.makeCompound(shapes)
assert compound.isValid()
bb=compound.BoundingBox()
cad_min=np.array([bb.xmin,bb.ymin,bb.zmin])/1000
cad_max=np.array([bb.xmax,bb.ymax,bb.zmax])/1000
assert np.allclose(mesh_min,cad_min,atol=.003),(mesh_min,cad_min)
assert np.allclose(mesh_max,cad_max,atol=.003),(mesh_max,cad_max)
html=(root/'EXO01_3D_viewer.html').read_text()
assert '__MODEL_PAYLOAD__' not in html
payload=json.loads(re.search(r'<script id="model-data" type="application/json">(.*?)</script>',html,re.S).group(1))
assert payload['metadata']==meta
assert len(payload['components'])==16
counts={category:sum(c['category']==category for c in meta['components']) for category in ['structure','float','solar','battery','electronics']}
assert counts==dict(structure=3,float=6,solar=4,battery=2,electronics=1)
out={'status':'passed','component_counts':counts,'total_listed_mass_kg':total,
     'glb_mass_metadata_matches_json':True,'mass_double_counting_check':'passed',
     'STEP_readback_valid':True,'STEP_solid_count':len(compound.Solids()),
     'GLB_and_STEP_bounds_match_within_mm':3,
     'model_bounds_cad_m':{'minimum':cad_min.tolist(),'maximum':cad_max.tolist()},
     'centre_of_gravity_deliberately_unknown':True,
     'wave_and_hydrostatic_results_absent':True,
     'observation_deck_clear_of_solar_panels':True,
     'observation_surface_z_m':float(deck_positions[:,2].max()),
     'observation_drop_below_top_frame_m':.5,
     'solar_side_overhang_m':0,
     'solar_front_only_overhang_verified':True,
     'solar_layout':'four panels in one transverse row',
     'observation_deck_mass_coverage_and_occupant_load_unknown':True,
     'engineering_validation':'Not performed; geometry and mass-register integrity only.'}
(root/'artifact_validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
