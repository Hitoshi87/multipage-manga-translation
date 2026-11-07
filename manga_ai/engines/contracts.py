"""Versioned, JSON-compatible clean results; legacy fields remain readable."""
RESULT_SCHEMA=1


def normalize_result(result, mapping):
    if not isinstance(result,dict):raise ValueError('Engine phải trả object')
    for name in ('overlay','applied','skipped','blocked'):
        if name not in result:raise ValueError('Thiếu field engine: '+name)
    selected={r['id'] for r in mapping if r.get('clean',True) and str(r.get('translation','')).strip()}
    groups={}
    for name in ('applied','skipped','review_ids'):
        values=result.get(name,[])
        if not isinstance(values,list) or any(not isinstance(x,str) for x in values) or len(values)!=len(set(values)):
            raise ValueError('Danh sách ID engine không hợp lệ: '+name)
        groups[name]=set(values)
        if not groups[name]<=selected:raise ValueError('Engine trả ID không được chọn: '+name)
    if groups['applied']&groups['skipped']:raise ValueError('Region vừa applied vừa skipped')
    if groups['review_ids']&groups['applied']:raise ValueError('Region vừa applied vừa review')
    for name in ('blocked','skip_reason_codes'):
        values=result.get(name,{})
        if not isinstance(values,dict) or not set(values)<=selected or any(not isinstance(v,str) for v in values.values()):raise ValueError('Reason map không hợp lệ: '+name)
    if not isinstance(result['overlay'],(str,type(None))):raise ValueError('Overlay phải là đường dẫn hoặc null')
    records=[]
    for item in mapping:
        rid=item['id']
        if rid not in selected:continue
        decision='review' if rid in groups['review_ids'] else 'applied' if rid in groups['applied'] else 'skip' if rid in groups['skipped'] else 'unreported'
        if decision=='unreported':raise ValueError('Engine thiếu quyết định region: '+rid)
        records.append({'region_id':rid,'decision':decision,'reason_code':result.get('skip_reason_codes',{}).get(rid),'reason':result['blocked'].get(rid)})
    result.update(result_schema=RESULT_SCHEMA,review_ids=result.get('review_ids',[]),region_results=records)
    result['counts']={k:sum(r['decision']==k for r in records) for k in ('applied','review','skip')}
    return result
