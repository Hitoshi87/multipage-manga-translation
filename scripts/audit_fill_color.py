#!/usr/bin/env python3
"""Opt-in diagnostic for a source/clean/mask crop; never modifies its inputs."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from manga_ai.shadow_color_audit import ColorAuditConfig,audit_fill

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('source','clean','mask','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--sigma',type=float,default=12.0);p.add_argument('--bright-floor',type=int,default=245);p.add_argument('--minimum-weight',type=float,default=.02);p.add_argument('--warning-delta',type=float,default=3.0)
 a=p.parse_args()
 if a.sigma<=0 or not 0<=a.bright_floor<=255 or not 0<a.minimum_weight<=1 or a.warning_delta<0:p.error('invalid thresholds')
 paths=[a.source,a.clean,a.mask]
 for f in paths:
  if not f.is_file():p.error('not a file: '+str(f))
 cfg=ColorAuditConfig(a.sigma,a.bright_floor,a.minimum_weight,a.warning_delta)
 source=np.asarray(Image.open(a.source).convert('RGB'));clean=np.asarray(Image.open(a.clean).convert('RGB'));mask=np.asarray(Image.open(a.mask).convert('L'))>0
 preview,heat,report=audit_fill(source,clean,mask,cfg)
 a.out.mkdir(parents=True,exist_ok=False)
 Image.fromarray(preview).save(a.out/'local_fill_SHADOW.png');Image.fromarray(heat).save(a.out/'color_delta_heat_x16.png')
 report['inputs']={name:{'path':str(f.resolve()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for name,f in zip(('source','clean','mask'),paths)}
 (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
