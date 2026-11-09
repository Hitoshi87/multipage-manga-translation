"""Bounded translation groups; input limits are characters, not model tokens."""
import json
import re
import unicodedata
import uuid


def snapshot(segment, version):
    result={'id':segment['id'], 'jp':segment['jp'], 'source_revision':segment['source_revision'],
            'segment_version':version(segment), 'source_status':segment.get('source_status','unreviewed'),
            'source_provenance':segment.get('source_provenance'), 'ocr_evidence':segment.get('ocr_evidence'), 'page_id':segment['page_id'],
            'panel_id':segment.get('panel_id'), 'panel_status':segment.get('panel_status','unknown')}
    if segment.get('ruby'):result['ruby']=segment['ruby']
    if segment.get('visual_ocr'):result['visual_ocr']=segment['visual_ocr']
    raw=segment.get('raw_ocr')
    if isinstance(raw,str) and raw.strip() and raw.strip()!=segment['jp'].strip():
        result['ocr_alternative']={'text':raw, 'status':'unverified',
                                   'origin':(segment.get('ocr_evidence') or {}).get('origin','unknown')}
    return result


def payload_for_group(group):
    def semantic(t):
        result={'id':t['id'], 'jp':t['jp'], 'source_status':t.get('source_status','unreviewed'),
                'raw_ocr_evidence':t.get('ocr_evidence'), 'source_provenance':t.get('source_provenance'), 'page_id':t.get('page_id'),
                'panel_id':t.get('panel_id'), 'panel_status':t.get('panel_status','unknown')}
        if t.get('ruby'):result['furigana']=t['ruby']
        if t.get('visual_ocr',{}).get('main_text'):
            result['independent_visual_transcription']=t['visual_ocr']
        if t.get('ocr_alternative'):result['ocr_alternative']=t['ocr_alternative']
        return result
    result={'task':{'source_language':'ja','target_language':'vi','target_ids':[t['id'] for t in group['targets']]},
            'context_only':[semantic(t) for t in group['context']],
            'segments':[{**semantic(t),'speaker':{'status':'unknown'},'addressee':{'status':'unknown'}} for t in group['targets']]}
    if group.get('quote_links'):result['quote_links']=group['quote_links']
    return result


def input_chars(system, group):
    return len(system)+len(json.dumps(payload_for_group(group),ensure_ascii=False))


def _quote_links(ready):
    """Suggest local source-quote dependencies; never treat them as canon."""
    def clean(s):return ''.join(c for c in unicodedata.normalize('NFKC',s) if c.isalnum())
    normalized=[clean(s['jp']) for s in ready];links=[]
    for end,item in enumerate(ready):
        for raw in re.findall(r'「([^」]{1,40})」',item['jp']):
            quote=clean(raw)
            if not 3<=len(quote)<=16:continue
            for start in range(end-1,max(-1,end-17),-1):
                prev=ready[start];a=prev.get('page_ordinal');b=item.get('page_ordinal')
                near=(a is not None and b is not None and 0<=b-a<=1) or prev['page_id']==item['page_id']
                if near and quote in normalized[start]:
                    links.append((start,end,quote));break
    return links


def build_groups(ready, *, version, system, group_size, context_segments, max_input_chars, max_pages=None, prior_context=()):
    links=_quote_links(ready)
    cross_links=[]
    if prior_context:
        combined=list(prior_context)+ready
        for a,b,_ in _quote_links(combined):
            if a<len(prior_context)<=b:
                cross_links.append((combined[a]['id'],combined[b]['id']))
    groups=[];offset=0
    while offset < len(ready):
        before=(list(prior_context)+ready[max(0,offset-context_segments):offset])[-context_segments:] if context_segments else []
        context=[snapshot(s,version) for s in before]
        targets=[];chosen=None
        end=min(len(ready),offset+group_size)
        # Keep a local quoted phrase and its source together if the bounded
        # window allows; long links remain unresolved rather than unbounded.
        for start,finish,_ in links:
            if offset<=start<end<=finish and finish-offset<group_size+12:end=finish+1
        for item in ready[offset:end]:
            if max_pages and len({s['page_id'] for s in targets}|{item['page_id']})>max_pages:break
            trial=targets+[snapshot(item,version)];remaining=context[:]
            while remaining and input_chars(system,{'targets':trial,'context':remaining})>max_input_chars:
                remaining.pop(0)
            length=input_chars(system,{'targets':trial,'context':remaining})
            if length>max_input_chars:
                if not targets:raise ValueError('Một segment hoặc prompt vượt giới hạn đầu vào; tăng giới hạn hoặc sửa nguồn')
                break
            targets=trial
            chosen={'id':'group_'+uuid.uuid4().hex,'status':'pending','targets':targets[:],
                    'context':remaining,'omitted_context_count':len(before)-len(remaining),
                    'input_chars':length,'results':[],'attempts':[]}
        target_end=offset+len(targets)
        selected=[{'source_id':ready[a]['id'],'quote_id':ready[b]['id'],'source_quote':text,'status':'inferred'}
                  for a,b,text in links if offset<=a<b<target_end]
        unresolved=[{'source_id':ready[a]['id'],'quote_id':ready[b]['id']}
                    for a,b,_ in links if (offset<=a<target_end)!=(offset<=b<target_end)]
        new_ids={item['id'] for item in ready[offset:target_end]}
        unresolved.extend({'source_id':a,'quote_id':b} for a,b in cross_links if b in new_ids)
        for source_id,quote_id in cross_links:
            if quote_id not in new_ids or any(t['id']==source_id for t in chosen['context']):
                continue
            original=next((s for s in prior_context if s['id']==source_id),None)
            if original is None:
                continue
            candidate=[snapshot(original,version)]+chosen['context']
            trial={**chosen,'context':candidate}
            if input_chars(system,trial)<=max_input_chars:
                chosen['context']=candidate
                chosen['input_chars']=input_chars(system,trial)
        if selected:
            trial={**chosen,'quote_links':selected}
            if input_chars(system,trial)<=max_input_chars:chosen['quote_links']=selected;chosen['input_chars']=input_chars(system,trial)
            else:unresolved.extend({'source_id':x['source_id'],'quote_id':x['quote_id']} for x in selected)
        if unresolved:chosen['unresolved_quote_links']=unresolved
        groups.append(chosen);offset+=len(targets)
    return groups
