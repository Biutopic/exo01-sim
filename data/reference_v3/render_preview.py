"""Render the actual tessellated model to reviewable PNGs (no generated imagery)."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.collections import PolyCollection
from PIL import Image

ROOT=Path(__file__).resolve().parent
cache=json.loads((ROOT/'preview_mesh.json').read_text())
colors={'aluminium':'#a6b6c0','deck':'#9daeb5','observation_deck':'#b9c4bf','joint':'#bd872f','float':'#24313b','panel':'#17364d','panel_grid':'#628196','battery':'#ee6d28','electronics':'#2d9598','dark':'#29343e'}
BG='#f3f6f7'; INK='#182d3b'; MUTED='#536c7a'

def faces(part):
    tri=np.array(part['tri'])
    n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);length=np.linalg.norm(n,axis=1)
    n=n/np.maximum(length[:,None],1e-12)
    light=np.array([-.3,-.5,1]);light=light/np.linalg.norm(light)
    shade=.68+.32*np.abs(n@light)
    base=np.array(matplotlib.colors.to_rgb(colors[part['mat']]))
    return tri,np.clip(shade[:,None]*base,0,1)

def raster(u,v,back,width=1800,height=1200,bounds=None):
    """Orthographic z-buffer, so panels/decks cannot hide nearer equipment."""
    all_tri=[];all_fc=[]
    for part in cache:
        tri,fc=faces(part);all_tri.append(tri);all_fc.append(fc)
    tri=np.concatenate(all_tri);fc=np.concatenate(all_fc)
    u,v,back=np.array(u),np.array(v),np.array(back)
    px=tri@u;py=tri@v;depth=tri@back
    if bounds is None:
        xmin,xmax=px.min(),px.max();ymin,ymax=py.min(),py.max()
        dx=(xmax-xmin)*.035;dy=(ymax-ymin)*.045
        xmin-=dx;xmax+=dx;ymin-=dy;ymax+=dy
        # Expand the viewing window to match the output aspect ratio.
        if (xmax-xmin)/(ymax-ymin)>width/height:
            extra=((xmax-xmin)*height/width-(ymax-ymin))/2;ymin-=extra;ymax+=extra
        else:
            extra=((ymax-ymin)*width/height-(xmax-xmin))/2;xmin-=extra;xmax+=extra
    else:xmin,xmax,ymin,ymax=bounds
    sx=(px-xmin)/(xmax-xmin)*(width-1);sy=(ymax-py)/(ymax-ymin)*(height-1)
    rgb=np.empty((height,width,3),dtype=np.uint8);rgb[:]=np.array(matplotlib.colors.to_rgb(BG))*255
    zbuf=np.full((height,width),-np.inf,dtype=np.float32)
    for i in range(len(tri)):
        xs,ys=sx[i],sy[i]
        x0=max(0,int(np.floor(xs.min())));x1=min(width-1,int(np.ceil(xs.max())))
        y0=max(0,int(np.floor(ys.min())));y1=min(height-1,int(np.ceil(ys.max())))
        if x1<x0 or y1<y0:continue
        den=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(den)<1e-9:continue
        xx=np.arange(x0,x1+1,dtype=np.float32)[None,:]+.5
        yy=np.arange(y0,y1+1,dtype=np.float32)[:,None]+.5
        a=((ys[1]-ys[2])*(xx-xs[2])+(xs[2]-xs[1])*(yy-ys[2]))/den
        b=((ys[2]-ys[0])*(xx-xs[2])+(xs[0]-xs[2])*(yy-ys[2]))/den
        c=1-a-b;d=a*depth[i,0]+b*depth[i,1]+c*depth[i,2]
        zz=zbuf[y0:y1+1,x0:x1+1]
        mask=(a>=-1e-6)&(b>=-1e-6)&(c>=-1e-6)&(d>zz)
        zz[mask]=d[mask];rgb[y0:y1+1,x0:x1+1][mask]=(fc[i]*255).astype(np.uint8)
    return rgb,[xmin,xmax,ymin,ymax]

fig=plt.figure(figsize=(15,10),facecolor=BG)
fig.text(.05,.94,'EXO-01',fontsize=27,fontweight='bold',color=INK)
fig.text(.05,.908,'Lowered observation platform + front-only panel overhang · Revision 3',fontsize=13,color=MUTED)
fig.text(.95,.94,'840 kg',fontsize=29,fontweight='bold',color=INK,ha='right')
fig.text(.95,.91,'Listed components only',fontsize=12,color=MUTED,ha='right')
az,el=np.deg2rad([-139,25]);back=np.array([np.cos(az)*np.cos(el),np.sin(az)*np.cos(el),np.sin(el)])
right=np.cross([0,0,1],back);right/=np.linalg.norm(right);up=np.cross(back,right)
rendered,_=raster(right,up,back,1800,1250)
ax=fig.add_axes([.025,.17,.70,.71],facecolor=BG);ax.imshow(rendered);ax.set_axis_off()
fig.text(.76,.81,'MASS REGISTER',fontsize=11,color=MUTED,fontweight='bold')
rows=[('Batteries','2 × 120 kg','240 kg'),('Solar panels','4 × 20 kg','80 kg'),('Electronics','Lumped equipment','50 kg'),('Rear deck section','1 × 150 kg','150 kg'),('Other frame sections','2 × 70 kg','140 kg'),('Floats','6 × 30 kg','180 kg')]
for i,(label,detail,total) in enumerate(rows):
    y=.76-i*.075
    fig.text(.76,y,label,fontsize=12,color=INK)
    fig.text(.76,y-.024,detail,fontsize=10,color=MUTED)
    fig.text(.95,y,total,fontsize=12,color=INK,ha='right',fontweight='bold')
fig.text(.76,.265,'FRAME DIMENSIONS',fontsize=11,color=MUTED,fontweight='bold')
fig.text(.76,.228,'4.950 × 4.547 m',fontsize=16,color=INK)
fig.text(.76,.198,'2.700 m above deck',fontsize=12,color=MUTED)
fig.text(.05,.13,'Observation surface: 0.50 m below top frame  ·  No side overhang  ·  Front projection provisional',fontsize=11,color=INK)
fig.text(.05,.088,'840 kg is the supplied mass subtotal. People are additional; deck-surface inclusion in the section weight is unconfirmed.',fontsize=11,color=MUTED)
fig.text(.05,.057,'Battery locations and float shapes remain approximate. No centre of gravity, wave response or deck capacity calculated.',fontsize=11,color=MUTED)
fig.savefig(ROOT/'EXO01_preview.png',dpi=150,facecolor=BG)
plt.close(fig)

fig=plt.figure(figsize=(15,11),facecolor=BG)
fig.text(.05,.953,'EXO-01 / reference views',fontsize=25,fontweight='bold',color=INK)
fig.text(.05,.921,'Revision 3 · observation surface 0.50 m below top frame; four panels within frame width, projecting at front only.',fontsize=11,color=MUTED)

def orthographic(ax,axes,depth,title,reverse=False):
    eye=np.eye(3)
    bounds=([-0.3,5.9,-2.9,2.9] if axes==[0,1] else [-.3,5.9,-.75,3] if axes==[0,2] else [-2.9,2.9,-.75,3])
    rendered,extent=raster(eye[axes[0]],eye[axes[1]],eye[depth]*(-1 if reverse else 1),1600,1400 if axes==[0,1] else 1000,bounds)
    ax.imshow(rendered,extent=extent,origin='upper');ax.set_aspect('equal');ax.set_facecolor(BG)
    ax.set_title(title,loc='left',color=INK,fontsize=13,pad=13)
    ax.tick_params(colors=MUTED,labelsize=9)
    for s in ax.spines.values():s.set_visible(False)
    ax.set_xlabel(['X — longitudinal (m)','Y — transverse (m)','Z — above deck (m)'][axes[0]],color=MUTED,fontsize=10)
    ax.set_ylabel(['X — longitudinal (m)','Y — transverse (m)','Z — above deck (m)'][axes[1]],color=MUTED,fontsize=10)
    ax.grid(alpha=.15,color='#7d929d');ax.set_axisbelow(True)

ax1=fig.add_axes([.07,.12,.40,.71]);orthographic(ax1,[0,1],2,'Top · observation deck + panel row')
ax1.set_xlim(-.3,5.9);ax1.set_ylim(-2.9,2.9)
ax2=fig.add_axes([.56,.53,.38,.31]);orthographic(ax2,[0,2],1,'Side · 2.100 + 1.425 + 1.425 m',True)
ax2.set_xlim(-.3,5.9);ax2.set_ylim(-.75,3.0)
ax2.annotate('',xy=(2.65,2.2),xytext=(2.65,2.7),arrowprops=dict(arrowstyle='<->',color='#9a5747',lw=1.3))
ax2.text(2.76,2.45,'0.50 m',fontsize=9,color='#9a5747',va='center',bbox=dict(facecolor=BG,edgecolor='none',pad=1.5))
ax3=fig.add_axes([.56,.13,.38,.31]);orthographic(ax3,[1,2],0,'End · 4.547 m frame width',True)
ax3.set_xlim(-2.9,2.9);ax3.set_ylim(-.75,3.0)
fig.text(.05,.045,'REFERENCE GEOMETRY ONLY  ·  840 kg listed mass  ·  30 mm unresolved overall-length difference  ·  No hydrostatic or structural validation',fontsize=10,color=MUTED)
fig.savefig(ROOT/'EXO01_reference_views.png',dpi=150,facecolor=BG)
plt.close(fig)
print('Rendered EXO01_preview.png and EXO01_reference_views.png')
