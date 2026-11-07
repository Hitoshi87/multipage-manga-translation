"""Conservative second opinion for text in learned white speech balloons.

Requires agreement of balloon, text-box and text-pixel models, excludes heads,
and is recomputed from source pixels when rendering. No rectangle is erased.
"""
import cv2
import numpy as np
from .text_recovery import outline_interior


def supported_mask(rgb, region, text_mask, detections, heads):
    if region.get('detector')!='ai_balloon' or region.get('detector_confidence',0)<.9:
        return None
    x,y,w,h=region['box']
    if w*h>rgb.shape[0]*rgb.shape[1]*.08:return None
    polygon=outline_interior(region)
    if polygon is None:return None
    support=np.zeros((h,w),np.uint8)
    for d in detections:
        if d['kind']!='in_bubble' or d['confidence']<.9:continue
        tx,ty,tw,th=d['box']
        overlap=max(0,min(x+w,tx+tw)-max(x,tx))*max(0,min(y+h,ty+th)-max(y,ty))
        if overlap/(tw*th)<.85:continue
        support[max(0,ty-y-3):min(h,ty+th-y+3),max(0,tx-x-3):min(w,tx+tw-x+3)]=1
    from .clean_refinement import complete_glyphs, enclosed_text_support
    refined=complete_glyphs(rgb,text_mask,detections)
    target=(refined[y:y+h,x:x+w]>0)&(support>0)
    if target.sum()<8:return None
    allowed=cv2.erode(polygon,np.ones((3,3),np.uint8))>0
    enclosed=enclosed_text_support(rgb,detections)[y:y+h,x:x+w] if heads else np.zeros((h,w),np.uint8)
    for hx,hy,hw,hh in heads:
        left=max(0,hx-x);right=min(w,hx+hw-x);top=max(0,hy-y);bottom=min(h,hy+hh-y)
        if right>left and bottom>top:allowed[top:bottom,left:right]&=enclosed[top:bottom,left:right]>0
    if np.count_nonzero(target&allowed)/target.sum()<.98:return None
    mask=cv2.dilate(target.astype(np.uint8),np.ones((3,3),np.uint8))*(allowed.astype(np.uint8))
    gray=cv2.cvtColor(rgb[y:y+h,x:x+w],cv2.COLOR_RGB2GRAY)
    # Drawing/texture around the proposed text is not a flat balloon background.
    ring=(cv2.dilate(mask,np.ones((7,7),np.uint8))>0)&(mask==0)&allowed
    if ring.sum()<10 or np.mean(gray[ring]>=220)<.9:return None
    if mask.sum()/max(1,np.count_nonzero(allowed))>.24:return None
    return mask*255
