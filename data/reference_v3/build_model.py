"""Rebuild the EXO-01 reference assembly, not a validated engineering model.

Requires Python 3.10+, cadquery 2.7, numpy. Run from any working directory.
All CAD coordinates are millimetres; GLB coordinates are converted to metres.
User masses are assigned to 16 parent components, never inferred from volume.
"""
from pathlib import Path
import base64
import json
import math
import struct
import time
import numpy as np
import cadquery as cq

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / 'parameters.json').read_text())
L0, L1, L2 = P['section_lengths_mm']
L = L0 + L1 + L2
W = P['frame_width_mm']
H = P['frame_height_above_deck_mm']
OBS_TOP = H - P['observation_deck_drop_below_top_frame_mm']
OBS_THICKNESS = P['observation_deck_thickness_proxy_mm']
Y = W / 2 - 25
STATIONS = [0, L0, L0 + L1, L]

MATERIALS = {
    'aluminium': ([0.67, 0.73, 0.76, 1], 0.62, 0.34),
    'deck': ([0.57, 0.64, 0.66, 1], 0.4, 0.65),
    'observation_deck': ([0.72, 0.77, 0.75, 1], 0.15, 0.75),
    'joint': ([0.75, 0.51, 0.17, 1], 0.55, 0.4),
    'float': ([0.10, 0.14, 0.17, 1], 0.0, 0.65),
    'panel': ([0.035, 0.11, 0.19, 1], 0.18, 0.29),
    'panel_grid': ([0.24, 0.36, 0.48, 1], 0.15, 0.5),
    'battery': ([0.94, 0.41, 0.13, 1], 0.1, 0.47),
    'electronics': ([0.15, 0.57, 0.57, 1], 0.2, 0.4),
    'dark': ([0.08, 0.11, 0.14, 1], 0.2, 0.4),
}
parts = []
components = []
stats = {'invalid_shapes': [], 'solid_count': 0}


def component(cid, label, kind, mass, location_status, note, centroid=None):
    c = dict(component_id=cid, name=label, category=kind, mass_kg=mass,
             mass_source='User supplied, 2026-10-28', mass_status=('user_estimate' if kind=='electronics' else 'user_reported'),
             mass_measurement_tolerance_kg=None,
             mass_counting_rule='Count this parent once; child meshes have no additional mass',
             location_status=location_status, geometry_status='raster_reconstruction_proxy',
             geometry_notes=note, installed_centre_of_mass_m=None,
             inertia_tensor_kg_m2=None, preview_anchor_m=centroid)
    components.append(c)
    return c


def add(c, name, shape, mat='aluminium', metadata=None):
    if not shape.isValid():
        stats['invalid_shapes'].append(c['component_id'] + '/' + name)
    stats['solid_count'] += len(shape.Solids())
    parts.append(dict(cid=c['component_id'], name=name, shape=shape, mat=mat, metadata=metadata or {}))


def box(c, name, centre, size, mat='aluminium', metadata=None):
    s = cq.Workplane('XY').box(*size).translate(tuple(centre)).val()
    add(c, name, s, mat, metadata)


def beam(c, name, a, b, width=50, depth=50, mat='aluminium'):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    vec = b - a
    length = np.linalg.norm(vec)
    z = vec / length
    ref = np.array([0, 0, 1.0]) if abs(z[2]) < .9 else np.array([0, 1.0, 0])
    x = np.cross(ref, z)
    x /= np.linalg.norm(x)
    plane = cq.Plane(origin=tuple(a), xDir=tuple(x), normal=tuple(z))
    shape = cq.Workplane(plane).rect(width, depth).extrude(length).val()
    add(c, name, shape, mat)


def joint(c, name, centre, radius=125):
    # Disc envelopes with a centre opening; exact joint drawings are unavailable.
    pnt = (centre[0], centre[1]-6, centre[2])
    outer = cq.Solid.makeCylinder(radius, 12, pnt, (0, 1, 0))
    inner = cq.Solid.makeCylinder(20, 14, (pnt[0],pnt[1]-1,pnt[2]), (0,1,0))
    clip = cq.Solid.makeBox(L, 30, H, (0, centre[1]-15, 0))
    add(c, name, outer.cut(inner).intersect(clip), 'joint')


rear = component('EXO_REAR_150', 'Rear deck section', 'structure',
                 P['rear_module_mass_kg'], 'inferred_from_drawing',
                 '150 kg assigned to the 2100 mm rear section; mapping needs confirmation. Includes its deck, access ladder, rails and support stand for bookkeeping.')
mid = component('EXO_MIDDLE_70', 'Middle frame / upper observation deck', 'structure',
                P['other_module_mass_kg'], 'inferred_from_drawing',
                '70 kg assigned to the middle 1425 mm bay. The rest/observation surface is approximately 500 mm below the top frame per the user, modelled at Z=2200 mm. Whether its surface is included in this 70 kg is unconfirmed. Occupants are not included.')
end = component('EXO_END_70', 'End frame section', 'structure',
                P['other_module_mass_kg'], 'inferred_from_drawing',
                '70 kg assigned to the end 1425 mm bay. Member sections and mass distribution are unknown.')

# Rear deck: the source sheet shows a full-width platform and two open frame bays.
box(rear, 'deck_plate_proxy', (L0/2, 0, -9), (L0, W, 18), 'deck')
for side in [-1, 1]:
    beam(rear, f'deck_edge_{side}', (25,side*Y,-45), (L0-25,side*Y,-45), 50, 70)
for i,x in enumerate([25,600,1200,1775,L0-25]):
    beam(rear, f'deck_crossmember_{i}', (x,-Y,-45), (x,Y,-45), 50, 70)
for side in [-1, 1]:
    for z in [390,740]:
        beam(rear, f'guardrail_{side}_{z}', (630,side*Y,z), (L0,side*Y,z), 35,35)
    for x in [630,1200,L0]:
        beam(rear, f'guardpost_{side}_{x}', (x,side*Y,0), (x,side*Y,760),35,35)

# Open framed bays. Portal ownership avoids duplicate members and double mass.
for c,x0,x1 in [(mid,L0,L0+L1),(end,L0+L1,L)]:
    for side in [-1,1]:
        for z in [-35,H-25]:
            beam(c, f'longeron_{side}_{z}',(x0,side*Y,z),(x1-25,side*Y,z),50,60)
        box(c,f'walkway_{side}',((x0+x1)/2,side*(Y-115),-8),(x1-x0,260,16),'deck')
        beam(c,f'midrail_{side}',(x0,side*Y,H/2),(x1-25,side*Y,H/2),30,30)
        centre=((x0+x1)/2,side*(Y-8),H/2)
        for j,(x,z) in enumerate([(x0,60),(x0,H-60),(x1-25,60),(x1-25,H-60)]):
            beam(c,f'brace_{side}_{j}',(x,side*(Y-8),z),centre,16,16)
        joint(c,f'brace_hub_{side}',centre,100)
    beam(c,'base_crossmember_end',(x1-25,-Y,-35),(x1-25,Y,-35),50,70)

for i,x in enumerate([L0,L0+L1,L-25]):
    c=mid if i==0 else end
    for side in [-1,1]:
        beam(c,f'portal_{i}_post_{side}',(x,side*Y,0),(x,side*Y,H),50,50)
        joint(c,f'portal_{i}_foot_joint_{side}',(x,side*(Y+22),70),160)
        joint(c,f'portal_{i}_upper_joint_{side}',(x,side*(Y+22),H-100),140)
    beam(c,f'portal_{i}_top',(x,-Y,H-25),(x,Y,H-25),50,50)
    # Proxy headers beneath the lowered deck, keeping the stated underside.
    # This adjustment is visual only; it is not a member-sizing calculation.
    header_bottom = P['drawing_clear_height_mm']
    header_top = OBS_TOP-OBS_THICKNESS if i < 2 else 2220
    header_z = (header_bottom+header_top)/2
    beam(c,f'portal_{i}_header',(x,-Y,header_z),(x,Y,header_z),70,header_top-header_bottom)

# Access ladder, as a visual proxy from the side/front views.
for side in [-1,1]:
    beam(rear,f'ladder_rail_{side}',(1130,850+side*300,40),(L0,850+side*300,OBS_TOP),35,50)
for i,t in enumerate(np.linspace(.08,.94,11)):
    x=1130+(L0-1130)*t
    z=40+(OBS_TOP-40)*t
    beam(rear,f'ladder_rung_{i}',(x,550,z),(x,1150,z),30,35)

# Small stand visible on the rear deck. Its envelope is not a load-bearing design.
box(rear,'equipment_stand_top',(1600,-950,780),(720,520,35),'deck')
for x in [1270,1930]:
    for y in [-1175,-725]:
        beam(rear,f'stand_leg_{x}_{y}',(x,y,0),(x,y,770),30,30)

# Six independent watertight visual proxy floats; volumes are NOT design inputs.
radius=P['float_diameter_proxy_mm']/2
for side in [-1,1]:
    for i,(xa,xb) in enumerate(P['float_spans_proxy_mm']):
        cid=f'FLOAT_{"NEG_Y" if side<0 else "POS_Y"}_{i+1}'
        y=side*P['float_centerline_y_proxy_mm']
        c=component(cid,f'Float {"−Y" if side<0 else "+Y"} / section {i+1}', 'float',
                    P['float_mass_each_kg'], 'inferred_from_drawing',
                    'Count and dry mass confirmed; diameter, length, end shape, installed position and displacement are unconfirmed visual approximations.',
                    [(xa+xb)/2000,y/1000,-radius/1000])
        a,b=xa+radius,xb-radius
        # A cylinder and two hemispherical ends. The drawing does not resolve exact shapes.
        cylinder=cq.Solid.makeCylinder(radius,b-a,(a,y,-radius),(1,0,0))
        cap0=cq.Solid.makeSphere(radius,(a,y,-radius),(1,0,0),-90,90,360)
        cap1=cq.Solid.makeSphere(radius,(b,y,-radius),(1,0,0),-90,90,360)
        shape=cylinder.fuse(cap0,cap1).clean()
        add(c,'float_envelope_proxy',shape,'float')

# The annotated correction identifies the bay reached by the ladder as an upper
# rest/observation area. Surface geometry does not invent a measured deck mass.
deck_meta={'role':'upper_rest_observation_deck','mass_is_in_parent':None,
           'surface_mass_kg':None,'mass_coverage_status':'unconfirmed_within_70kg_section',
           'occupants_mass_kg':None,'geometry_source':'user_annotation_and_50cm_drop_clarification',
           'surface_top_z_m':OBS_TOP/1000,
           'drop_below_top_frame_m':P['observation_deck_drop_below_top_frame_mm']/1000,
           'structural_capacity_validated':False}
box(mid,'upper_observation_deck_proxy',((L0+L0+L1)/2,0,OBS_TOP-OBS_THICKNESS/2),
    (L1,W-50,OBS_THICKNESS),'observation_deck',deck_meta)

# Four panels in one transverse row on the end bay, long dimension along X.
# The proxy width fits the frame without side overhang; front overhang is provisional.
for i,centre in enumerate(P['solar_preview_centres_mm']):
    c=component(f'SOLAR_{i+1}',f'Solar panel {i+1}', 'solar',P['solar_mass_each_kg'],
                'layout_from_user_exact_position_provisional',
                '20 kg user mass. Four panels lie side by side on the end bay, leaving the lowered observation deck clear. No left/right overhang per the user; only the front (+X framed end) overhangs. Panel widths are fitted preview envelopes, not measured dimensions. Exact front overhang and tilt are provisional.',
                [v/1000 for v in centre])
    sx,sy,sz=P['solar_proxy_size_mm']
    x,y,z=centre
    box(c,'panel_frame',centre,(sx,sy,sz),'aluminium')
    box(c,'panel_face',(x,y,z+sz/2+1),(sx-28,sy-28,3),'panel')
    for j in range(1,7):
        box(c,f'cell_line_x_{j}',(x-sx/2+j*sx/7,y,z+sz/2+3),(2,sy-36,1),'panel_grid')
    for j in range(1,12):
        box(c,f'cell_line_y_{j}',(x,y-sy/2+j*sy/12,z+sz/2+3),(sx-36,2,1),'panel_grid')

for i,centre in enumerate(P['battery_preview_centres_mm']):
    c=component(f'BATTERY_{i+1}',f'Battery {i+1}', 'battery',P['battery_mass_each_kg'],
                'provisional_not_confirmed',
                '120 kg EACH as stated by the user. Orange box is an illustrative envelope, not the actual battery geometry or installed position.',
                [v/1000 for v in centre])
    sx,sy,sz=P['battery_proxy_size_mm']; x,y,z=centre
    box(c,'battery_proxy',centre,(sx,sy,sz),'battery')
    box(c,'lid',(x,y,z+sz/2),(sx+4,sy+4,18),'dark')
    for j,dy in enumerate([-90,90]):
        box(c,f'terminal_{j}',(x+sx/2-100,y+dy,z+sz/2+20),(30,30,25),'joint')

c=component('ELECTRONICS_50','Electronics and miscellaneous equipment','electronics',
            P['electronics_mass_kg'],'provisional_not_confirmed',
            'Single 50 kg lumped equipment group. Actual item breakdown, geometry and location are not supplied.',
            [v/1000 for v in P['electronics_preview_centre_mm']])
box(c,'electronics_proxy',P['electronics_preview_centre_mm'],P['electronics_proxy_size_mm'],'electronics')

total=sum(c['mass_kg'] for c in components)
manifest={
    'schema':'exo_reference_mass_manifest_v1',
    'model_id':'EXO01_REFERENCE',
    'revision':P['revision'], 'created_date':'2026-10-28',
    'status':'PRELIMINARY_GEOMETRY_AND_MASS_REGISTER_ONLY',
    'source':{k:P[k] for k in ['source_drawing','source_drawing_title','source_drawing_author','source_drawing_date','source_drawing_sheet','source_annotation']},
    'roof_layout':P['roof_layout'],
    'units':{'CAD_geometry':'mm','GLB_geometry':'m','mass':'kg'},
    'coordinate_system':{
        'CAD':'Right-handed: X from the open rear deck toward the framed end; Y transverse; Z up.',
        'origin':'X=0 at rear deck edge, Y=0 at transverse centreline, Z=0 at nominal deck datum. No waterline is defined.',
        'GLB':'Child geometry uses metres in CAD axes. Root rotation of -90 degrees about X converts to glTF Y-up: (x,y,z)CAD -> (x,z,-y)glTF.',
        'port_starboard':'Not assigned: vessel heading was not established from the drawing.'
    },
    'dimension_register':{
        'model_frame_length_m':L/1000,'dimension_chain_m':[v/1000 for v in P['section_lengths_mm']],
        'drawing_overall_length_m':P['drawing_overall_length_mm']/1000,
        'unresolved_length_difference_m':(P['drawing_overall_length_mm']-L)/1000,
        'drawing_frame_width_m':W/1000,'drawing_frame_height_above_deck_m':H/1000,
        'observation_surface_top_z_m':OBS_TOP/1000,
        'observation_surface_drop_below_top_frame_m':P['observation_deck_drop_below_top_frame_mm']/1000,
        'drawing_clear_height_m':2.1,'drawing_ladder_width_m':.6,
        'other_drawing_clearances_m':[3.2,3.353],
        'float_diameter_proxy_m':radius*2/1000,
        'dimension_confidence':'Numeric labels transcribed; geometry, member details and the 30 mm inconsistency need checking against original CAD/sheets 2 and 3.'
    },
    'mass_summary':{
        'batteries_kg':2*P['battery_mass_each_kg'],'solar_panels_kg':4*P['solar_mass_each_kg'],
        'electronics_kg':P['electronics_mass_kg'],'exo_structure_kg':P['rear_module_mass_kg']+2*P['other_module_mass_kg'],
        'floats_kg':6*P['float_mass_each_kg'],'total_listed_mass_kg':total,
        'included_component_count':len(components),'float_count_confirmed':6,
        'total_scope':'Only the listed EXO assembly and equipment; not the complete vessel operating displacement.',
        'accounting_assumption':'Section weights exclude separately listed floats and equipment. These masses are additive, subject to confirmation.',
        'unlisted_masses_are_zero':False
    },
    'pending_loads':{
        'observation_deck_surface_additional_mass_kg':None,
        'deck_surface_included_in_middle_section_mass':'unconfirmed',
        'upper_deck_occupant_count':None,'upper_deck_occupant_mass_kg':None,
        'occupant_centres_of_mass_m':None,
        'scope':'The 840 kg remains a listed-mass subtotal. Add the deck surface if not already included in the 70 kg section; occupants and their actual centres of mass must be added for occupied stability cases.'
    },
    'engineering_status':{
        'centre_of_gravity_m':None,'inertia_tensor_kg_m2':None,
        'hydrostatics_computed':False,'wave_response_computed':False,'structural_analysis_computed':False,
        'buoyancy_mesh_validated':False,'manufacturing_ready':False,
        'mass_positions_confirmed':False,
        'reason':'Equipment locations, component centres of mass, true hull/float shapes and the host boat mass are unknown. Proxy volumes must not be used to validate flotation or strength.'
    },
    'components':components,'assumptions_and_open_questions':P['notes']
}
(ROOT/'EXO01_mass_metadata.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')

print(f'Created {len(parts)} geometry parts in {len(components)} mass components; mass {total} kg.',flush=True)

# STEP retains assembly structure, component names, mass labels and colours.
# The JSON/GLB carry the full metadata; arbitrary JSON properties are not STEP attributes.
assembly=cq.Assembly(name='EXO01_REFERENCE_'+P['revision'].upper()+'_PRELIMINARY')
for comp in components:
    group=cq.Assembly(name=f"{comp['component_id']}__{comp['mass_kg']}kg")
    for part in parts:
        if part['cid']!=comp['component_id']: continue
        rgba=MATERIALS[part['mat']][0]
        group.add(part['shape'],name=part['name'],color=cq.Color(*rgba))
    assembly.add(group)
assembly.save(str(ROOT/'EXO01_reference.step'),'STEP',mode='default')
print('STEP exported.',flush=True)

# Build a portable GLB with explicit per-component extras and no external assets.
gltf={'asset':{'version':'2.0','generator':'EXO reference reconstruction / CadQuery 2.7',
               'extras':{'status':manifest['status'],'source_drawing':P['source_drawing']}},
      'scene':0,'scenes':[{'nodes':[0]}],
      'nodes':[{'name':'EXO01_REFERENCE_'+P['revision'].upper(),'rotation':[-math.sqrt(.5),0,0,math.sqrt(.5)],
                'children':[], 'extras':{k:manifest[k] for k in ['revision','status','coordinate_system','dimension_register','roof_layout','mass_summary','pending_loads','engineering_status','assumptions_and_open_questions']}}],
      'meshes':[],'accessors':[],'bufferViews':[],'buffers':[], 'materials':[]}
materials=list(MATERIALS)
for name,(rgba,metal,rough) in MATERIALS.items():
    gltf['materials'].append({'name':name,'pbrMetallicRoughness':{'baseColorFactor':rgba,'metallicFactor':metal,'roughnessFactor':rough},'doubleSided':True})
binary=bytearray()


def accessor(array,ctype,atype,target,include_bounds=False):
    while len(binary)%4: binary.extend(b'\0')
    offset=len(binary); binary.extend(array.tobytes())
    vi=len(gltf['bufferViews'])
    gltf['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':array.nbytes,'target':target})
    a={'bufferView':vi,'componentType':ctype,'count':len(array),'type':atype}
    if include_bounds:
        a['min']=array.min(axis=0).tolist(); a['max']=array.max(axis=0).tolist()
    ix=len(gltf['accessors']); gltf['accessors'].append(a); return ix


mesh_cache=[]
viewer_draws=[]
viewer_data=[]
vertex_offset=0
for comp_index,comp in enumerate(components):
    ci=len(gltf['nodes']); gltf['nodes'].append({'name':comp['component_id'],'extras':comp,'children':[]})
    gltf['nodes'][0]['children'].append(ci)
    for part in parts:
        if part['cid']!=comp['component_id']: continue
        vv,ff=part['shape'].tessellate(2.0,.30)
        vv=np.array([v.toTuple() for v in vv],dtype=np.float64)/1000
        ff=np.array(ff,dtype=np.int32)
        tri=vv[ff]
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        norms=np.linalg.norm(normals,axis=1)
        valid=norms>1e-12
        tri=tri[valid]; normals=normals[valid]/norms[valid,None]
        positions=np.asarray(tri.reshape(-1,3),dtype='<f4')
        normal_data=np.asarray(np.repeat(normals,3,axis=0),dtype='<f4')
        pos=accessor(positions,5126,'VEC3',34962,True)
        nor=accessor(normal_data,5126,'VEC3',34962)
        mi=len(gltf['meshes'])
        gltf['meshes'].append({'name':comp['component_id']+'/'+part['name'],
          'primitives':[{'attributes':{'POSITION':pos,'NORMAL':nor},'material':materials.index(part['mat'])}]})
        ni=len(gltf['nodes']); gltf['nodes'].append({'name':part['name'],'mesh':mi,
                   'extras':{'mass_owner':comp['component_id'],'role':'visual_subpart','mass_is_in_parent':True,**part['metadata']}})
        gltf['nodes'][ci]['children'].append(ni)
        rgba=MATERIALS[part['mat']][0]
        vertex_color=np.tile(np.array(rgba[:3],dtype='<f4'),(len(positions),1))
        interleaved=np.concatenate([positions,normal_data,vertex_color],axis=1).astype('<f4')
        viewer_data.append(interleaved)
        viewer_draws.append({'start':vertex_offset,'count':len(positions),'component':comp_index,'material':part['mat']})
        vertex_offset+=len(positions)
        mesh_cache.append({'component':comp_index,'mat':part['mat'],'tri':tri})

gltf['buffers']=[{'byteLength':len(binary)}]
js=json.dumps(gltf,separators=(',',':'),ensure_ascii=False).encode('utf-8')
js+=b' '*((-len(js))%4)
binary+=b'\0'*((-len(binary))%4)
glb=struct.pack('<4sII',b'glTF',2,12+8+len(js)+8+len(binary))
glb+=struct.pack('<I4s',len(js),b'JSON')+js
glb+=struct.pack('<I4s',len(binary),b'BIN\0')+binary
(ROOT/'EXO01_reference.glb').write_bytes(glb)

payload={'components':components,'draws':viewer_draws,
         'vertices_b64':base64.b64encode(np.concatenate(viewer_data).tobytes()).decode(),
         'metadata':manifest}
template=(ROOT/'viewer_template.html').read_text()
(ROOT/'EXO01_3D_viewer.html').write_text(template.replace('__MODEL_PAYLOAD__',json.dumps(payload,separators=(',',':'),ensure_ascii=False)))

# An OBJ export is omitted: it would lose the per-component mass properties.
stats.update(total_listed_mass_kg=total, component_count=len(components),
             mesh_count=len(parts), vertex_count=vertex_offset,
             triangle_count=vertex_offset//3, glb_bytes=len(glb),
             frame_length_mm=L, frame_width_mm=W, frame_height_above_deck_mm=H,
             unresolved_dimension_difference_mm=P['drawing_overall_length_mm']-L,
             mass_positions_confirmed=False,centre_of_gravity_computed=False)
assert not stats['invalid_shapes'], stats['invalid_shapes']
expected_mass=P['rear_module_mass_kg']+2*P['other_module_mass_kg']+6*P['float_mass_each_kg']+2*P['battery_mass_each_kg']+4*P['solar_mass_each_kg']+P['electronics_mass_kg']
assert total==expected_mass and len(components)==16
assert sum(c['mass_kg'] for c in components if c['category']=='float')==6*P['float_mass_each_kg']
assert len([c for c in components if c['category']=='battery'])==2
assert len([c for c in components if c['category']=='solar'])==4
(ROOT/'validation.json').write_text(json.dumps(stats,indent=2)+'\n')
print(json.dumps(stats,indent=2),flush=True)

# Save a low-cost tessellation cache for the technical preview renderer only.
cache=[]
for v in mesh_cache:
    cache.append({'component':v['component'],'mat':v['mat'],'tri':np.round(v['tri'],5).tolist()})
(ROOT/'preview_mesh.json').write_text(json.dumps(cache,separators=(',',':')))
print('GLB, metadata and standalone viewer exported.',flush=True)
