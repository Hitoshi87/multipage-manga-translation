"""Analyze at a bounded resolution, preserve the original PSD pixel coordinates."""
import math
import cv2

ANALYSIS_EDGE = 1440


def analysis_image(rgb, detector):
    h,w=rgb.shape[:2]
    if detector!='ai' or max(w,h)<=ANALYSIS_EDGE:return rgb
    scale=ANALYSIS_EDGE/max(w,h)
    return cv2.resize(rgb,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)


def project_box(box, analysis_size, original_size, inward=False):
    sx=original_size[0]/analysis_size[0];sy=original_size[1]/analysis_size[1]
    x,y,w,h=box
    first=math.ceil if inward else math.floor
    last=math.floor if inward else math.ceil
    left,top=first(x*sx),first(y*sy);right,bottom=last((x+w)*sx),last((y+h)*sy)
    return [left,top,right-left,bottom-top]


def project_mask(mask, box):
    return cv2.resize(mask,(box[2],box[3]),interpolation=cv2.INTER_NEAREST)


def project_regions(regions, analysis_size, original_size):
    if analysis_size==original_size:return
    sx=original_size[0]/analysis_size[0];sy=original_size[1]/analysis_size[1]
    for region in regions:
        geometry={'box':region['box'][:],'outline':[p[:] for p in region['outline']]}
        region['analysis_box']=geometry['box']
        if region['clean_method'] in ('punctuation_components','model_supported_text') or region.get('detector')=='hybrid_closed_balloon':
            if region['clean_method']=='model_supported_text':
                geometry.update(detector=region.get('detector'),detector_confidence=region.get('detector_confidence',0))
            region['analysis_geometry']=geometry
        region['box']=project_box(region['box'],analysis_size,original_size)
        region['safe']=project_box(region['safe'],analysis_size,original_size,inward=True)
        region['outline']=[[round(x*sx),round(y*sy)] for x,y in region['outline']]
        region['_mask']=project_mask(region['_mask'],region['box'])
        shape=region.get('shape')
        if shape:
            rows=[]
            for yy,left,right in shape['rows']:
                for y in range(math.ceil(yy*sy),math.ceil((yy+1)*sy)):
                    rows.append([y,math.ceil(left*sx),math.floor(right*sx)])
            region['shape']={'rows':rows,'center':[shape['center'][0]*sx,shape['center'][1]*sy],
                             'box':[min(r[1] for r in rows),rows[0][0],
                                    max(r[2] for r in rows)-min(r[1] for r in rows),rows[-1][0]-rows[0][0]+1]}
