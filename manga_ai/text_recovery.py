"""Bounded Japanese OCR retries and conservative punctuation evidence.

Punctuation is inferred from repeated glyph geometry inside a strong AI balloon,
never from a fabricated OCR confidence. All cleaning masks remain pixel-local.
"""
import re
import cv2
import numpy as np


def outline_interior(region):
    x,y,w,h=region['box']
    points=np.asarray(region.get('outline',[]),dtype=np.int32)
    if points.ndim!=2 or points.shape[1]!=2 or len(points)<3:return None
    mask=np.zeros((h,w),np.uint8)
    cv2.fillPoly(mask,[points-np.array([x,y])],255)
    return mask


def quality(words):
    text=''.join(w['text'] for w in words)
    chars=len(re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]',text))
    conf=sum(w['confidence'] for w in words)/len(words) if words else 0
    ratio=chars/max(1,len(text))
    return conf+min(chars,12)*1.2+ratio*15 if chars else -1


def recover_words(rgb, candidate, base, read_words, check):
    text=''.join(w['text'] for w in base)
    chars=len(re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]',text))
    conf=sum(w['confidence'] for w in base)/len(base) if base else 0
    if (chars>=3 and conf>=80) or (chars>=1 and conf>=88):
        return base
    x,y,w,h=candidate['box'];crop=rgb[y:y+h,x:x+w].copy()
    interior=cv2.erode(candidate['interior'],np.ones((3,3),np.uint8))
    crop[interior==0]=255
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    yy,xx=np.nonzero((gray<190)&(interior>0))
    if not len(xx):return base
    left=max(0,int(xx.min())-5);top=max(0,int(yy.min())-5)
    right=min(w,int(xx.max())+6);bottom=min(h,int(yy.max())+6)
    tight=crop[top:bottom,left:right]
    scale=min(3.0,1600/max(tight.shape[:2]))
    tight=cv2.resize(tight,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    gray_tight=cv2.cvtColor(tight,cv2.COLOR_RGB2GRAY)
    _,binary=cv2.threshold(gray_tight,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    passes=[(tight,'jpn_vert',5,'tight_vertical'),(binary,'jpn_vert',5,'binary_vertical')]
    if chars<3 or right-left>(bottom-top)*.65:
        passes.append((tight,'jpn',6,'tight_horizontal'))
    best=base;best_score=quality(base)
    for image,lang,psm,name in passes:
        check()
        padded=cv2.copyMakeBorder(image,15,15,15,15,cv2.BORDER_CONSTANT,value=255 if image.ndim==2 else (255,255,255))
        try:words=read_words(padded,lang,psm,4)
        except RuntimeError:continue
        for word in words:
            wx,wy,ww,wh=word['box']
            word['box']=[x+left+round((wx-15)/scale),y+top+round((wy-15)/scale),max(1,round(ww/scale)),max(1,round(wh/scale))]
            word['ocr_pass']=name
        score=quality(words)
        if score>best_score+3:best=words;best_score=score
    return best


def punctuation_mask(rgb, interior):
    """Only repeated dots or matched ! stem/dot pairs on a flat white interior."""
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    inner=cv2.erode(interior,np.ones((3,3),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)
    total=cv2.countNonZero(inner)
    if not total:return None
    background=rgb[(inner>0)&(gray>=220)]
    if len(background)<total*.8 or np.min(np.median(background,axis=0))<245 or np.max(np.std(background.astype(float),axis=0))>7:
        return None
    ink=(gray<130)&(inner>0)
    n,labels,stats,_=cv2.connectedComponentsWithStats(ink.astype(np.uint8),8)
    parts=[list(map(int,s)) for s in stats[1:] if s[4]>=2]
    if not 2<=len(parts)<=40:return None
    kind=None
    dot_limit=max(5,min(8,round(min(gray.shape)*.08)))
    if len(parts)>=3 and all(max(s[2:4])<=dot_limit and .45<=s[2]/s[3]<=2.2 and s[4]/(s[2]*s[3])>=.4 for s in parts):
        for axis in (0,1):
            groups=[];tolerance=max(3,float(np.median([s[axis+2] for s in parts]))*2)
            for s in sorted(parts,key=lambda s:s[axis]+s[axis+2]/2):
                center=s[axis]+s[axis+2]/2
                if not groups or abs(center-np.mean([v[axis]+v[axis+2]/2 for v in groups[-1]]))>tolerance:groups.append([])
                groups[-1].append(s)
            if len(groups)>3 or any(len(g)<3 for g in groups):continue
            valid=True;other=1-axis
            for group in groups:
                centers=sorted(s[other]+s[other+2]/2 for s in group);gaps=np.diff(centers)
                diameter=np.median([s[other+2] for s in group])
                if min(gaps)<diameter*1.3 or max(gaps)>diameter*6 or np.std(gaps)/np.mean(gaps)>.25:valid=False
            if valid:kind='ellipsis';break
    if kind is None and len(parts) in (2,4):
        stems=[s for s in parts if s[3]>=10 and s[3]>=s[2]*3]
        dots=[s for s in parts if .5<=s[2]/s[3]<=2 and max(s[2:4])<=dot_limit+1]
        if len(stems)==len(dots) and len(stems) in (1,2) and len(stems)+len(dots)==len(parts):
            matched=set();valid=True
            for stem in stems:
                matches=[i for i,d in enumerate(dots) if i not in matched and abs(d[0]+d[2]/2-stem[0]-stem[2]/2)<=max(stem[2],d[2])*.6 and 0<=d[1]-stem[1]-stem[3]<=stem[3]*.4 and 1.8<=stem[4]/d[4]<=18]
                if len(matches)!=1:valid=False;break
                matched.add(matches[0])
            if valid:kind='!'*len(stems)
    if kind is None:return None
    boxes=np.zeros_like(gray)
    for x,y,w,h,_ in parts:
        boxes[max(0,y-2):y+h+2,max(0,x-2):x+w+2]=255
    dark=(gray<220)&(inner>0)
    if np.count_nonzero(dark)/total>.15 or np.count_nonzero(dark&(boxes==0))>max(2,np.count_nonzero(dark)*.03):return None
    mask=(dark&(boxes>0)).astype(np.uint8)*255
    mask=cv2.bitwise_and(cv2.dilate(mask,np.ones((3,3),np.uint8)),inner)
    return mask,kind
