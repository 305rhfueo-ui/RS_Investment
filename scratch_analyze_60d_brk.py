import json
import os
import collections
import math

with open('static/history_index.json', 'r', encoding='utf-8') as f:
    history_index = json.load(f)

dates_info = list(reversed(history_index['dates']))

history_data = {}
for di in dates_info:
    date_str = di['date']
    filename = 'static/' + di['filename']
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read().replace('NaN', 'null')
                data = json.loads(content).get('data', [])
                history_data[date_str] = {item['Ticker']: item for item in data if 'Ticker' in item}
        except Exception as e:
            pass

success_list = []
fail_list = []

for i in range(len(dates_info) - 5):
    d0_str = dates_info[i]['date']
    d5_str = dates_info[i+5]['date']
    if d0_str not in history_data or d5_str not in history_data: continue
    
    d0_data = history_data[d0_str]
    d5_data = history_data[d5_str]
    for ticker, row0 in d0_data.items():
        if row0.get('BRK_60D') == 'YES':
            if ticker in d5_data:
                p0 = row0.get('Price', 0) or 0
                p5 = d5_data[ticker].get('Price', 0) or 0
                if p5 > p0: success_list.append(row0)
                else: fail_list.append(row0)

def parse_market_cap(mc_str):
    if not isinstance(mc_str, str): return 0
    mc_str = mc_str.upper().strip()
    if mc_str.endswith('T'): return float(mc_str[:-1]) * 1000
    if mc_str.endswith('B'): return float(mc_str[:-1])
    if mc_str.endswith('M'): return float(mc_str[:-1]) / 1000
    try: return float(mc_str) / 1e9
    except: return 0

def safe_float(val):
    try:
        f = float(val)
        if math.isnan(f): return 0
        return f
    except:
        return 0

def analyze_group(group, name):
    if not group: return {}
    n = len(group)
    res = {
        'Count': n,
        'Avg_RS_Rank_Pct': sum(safe_float(r.get('RS_Rank_Pct')) for r in group) / n,
        'Avg_RS_6mo': sum(safe_float(r.get('RS_6mo')) for r in group) / n,
        'Avg_RS_3mo': sum(safe_float(r.get('RS_3mo')) for r in group) / n,
        'Avg_RS_1mo': sum(safe_float(r.get('RS_1mo')) for r in group) / n,
        'Avg_VOL_X': sum(safe_float(r.get('VOL_X')) for r in group) / n,
        'Avg_ADR_20D': sum(safe_float(r.get('ADR_20D')) for r in group) / n,
        'Avg_Market_Cap_B': sum(parse_market_cap(r.get('Market Cap') or '0') for r in group) / n,
        'Jungjanggi_YES_Ratio': sum(1 for r in group if r.get('Jungjanggi Jeongbaeyeol') == 'YES') / n * 100,
        'Target_Status_YES_Ratio': sum(1 for r in group if r.get('Target_Status') == 'YES') / n * 100,
    }
    sectors = collections.Counter(r.get('Sector', 'Unknown') for r in group)
    industries = collections.Counter(r.get('Industry', 'Unknown') for r in group)
    res['Top_Sectors'] = sectors.most_common(5)
    res['Top_Industries'] = industries.most_common(10)
    return res

out = {
    'Success_Stats': analyze_group(success_list, "Success"),
    'Fail_Stats': analyze_group(fail_list, "Fail")
}
with open('scratch_analysis_result.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=4, ensure_ascii=False)
