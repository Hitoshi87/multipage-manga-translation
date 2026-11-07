"""Exploratory geometry-only candidates for a cropped balloon. Never auto-authorizes clean."""
from dataclasses import dataclass,asdict
import cv2
import numpy as np

@dataclass(frozen=True)
class ComponentConfig:
    gray_threshold: int = 210
    min_area: int = 3
    max_area: int = 1000
    max_width: int = 60
    max_height: int = 80
    min_polygon_distance: float = 3.0
    dilation_px: int = 1
    diacritic_proximity_px: int = 5

def propose_components(rgb, polygon, config=ComponentConfig()):
    image=np.asarray(rgb,dtype=np.uint8);inside=np.asarray(polygon)>0
    if image.ndim!=3 or image.shape[2]!=3 or image.shape[:2]!=inside.shape:
        raise ValueError('invalid image/polygon geometry')
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    distance=cv2.distanceTransform(inside.astype('uint8'),cv2.DIST_L2,5)
    n,labels,stats,_=cv2.connectedComponentsWithStats((gray<config.gray_threshold).astype('uint8'),8)
    selected=np.zeros(inside.shape,np.uint8);accepted=[];rejected=[]
    for i in range(1,n):
        x,y,w,h,area=map(int,stats[i]);dist=distance[labels==i];min_dist=float(dist.min()) if dist.size else 0
        reasons=[]
        if not config.min_area<=area<=config.max_area:reasons.append('AREA')
        if w>config.max_width or h>config.max_height:reasons.append('SIZE')
        if min_dist<config.min_polygon_distance:reasons.append('NEAR_ESTIMATED_POLYGON')
        record={'component_id':i,'box':[x,y,w,h],'area':area,'min_polygon_distance':round(min_dist,2),'reasons':reasons}
        if reasons:rejected.append(record)
        else:selected[labels==i]=1;accepted.append(record)
    # Small marks close to accepted glyph components may be diacritics.
    # Keep them as unverified candidates; this is not artwork protection.
    recovered=[]
    for record in rejected:
        x,y,w,h=record['box']; p=config.diacritic_proximity_px
        if record['reasons']!=['NEAR_ESTIMATED_POLYGON'] or record['min_polygon_distance']<=0 or max(w,h)>20:
            continue
        if any(max(x-p,a['box'][0])<min(x+w+p,a['box'][0]+a['box'][2]) and max(y-p,a['box'][1])<min(y+h+p,a['box'][1]+a['box'][3]) for a in accepted):
            selected[labels==record['component_id']]=1
            recovered.append(record)
    k=2*config.dilation_px+1
    mask=cv2.dilate(selected,np.ones((k,k),np.uint8))>0
    return mask,{'accepted':accepted,'rejected':rejected,'near_glyph_recovered':recovered,'thresholds':asdict(config),'calibrated':False,'artwork_safety':'unverified','authorized_to_clean':False,'note':'polygon is a model estimate; geometry alone can select artwork'}
