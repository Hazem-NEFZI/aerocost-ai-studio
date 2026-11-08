"""AEROCOST AI Studio: local web server using the original synthetic trained estimator."""
from __future__ import annotations
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import argparse
import json
import math
import os
import traceback

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
quotes = pd.read_csv(DATA / "quotations.csv", low_memory=False)
quotes = quotes.set_index("quote_id", drop=False)
art = joblib.load(MODELS / "aerocost_models.joblib")
ops = pd.read_csv(DATA / "manufacturing_operations.csv").set_index("quote_id", drop=False)
inspection = pd.read_csv(DATA / "quality_inspection_plans.csv").set_index("quote_id", drop=False)
suppliers = pd.read_csv(DATA / "fictional_supplier_quotes.csv").set_index("quote_id", drop=False)
energy = pd.read_csv(DATA / "illustrative_energy_scrap.csv").set_index("quote_id", drop=False)
metrics = pd.read_csv(MODELS / "model_metrics.csv")
family_metric = pd.read_csv(MODELS / "family_breakdown.csv")

def scrub(d):
    if isinstance(d, dict): return {str(k):scrub(v) for k,v in d.items()}
    if isinstance(d,(list,tuple)): return [scrub(x) for x in d]
    if isinstance(d,(np.integer,)): return int(d)
    if isinstance(d,(np.floating,)): return float(d) if np.isfinite(d) else None
    if isinstance(d,(np.bool_,)): return bool(d)
    if isinstance(d, float) and not math.isfinite(d): return None
    if pd.isna(d) if not isinstance(d,(dict,list,tuple,np.ndarray)) else False: return None
    return d

def list_records(indexed, quote_id):
    if quote_id not in indexed.index: return []
    item = indexed.loc[[quote_id]]
    return scrub(item.to_dict(orient="records"))

def examples():
    selected=[]
    for family, frame in quotes.groupby("product_family", sort=True):
        sample = frame.sort_values("engineering_estimate_eur")
        chosen = np.unique(np.linspace(0,len(sample)-1,12,dtype=int))
        for _, r in sample.iloc[chosen].iterrows():
            selected.append(case_summary(r))
    return selected

def case_summary(r):
    return scrub({k:r[k] for k in ["quote_id","product_family","material","batch_qty","engineering_estimate_eur","length_mm","width_mm","height_mm","minimum_tolerance_mm","surface_roughness_Ra_um","route_operations","delivery_priority","geometric_complexity"]})

def bootstrap():
    families=[]
    for family, g in quotes.groupby("product_family",sort=True):
        families.append({"name":family,"count":len(g),"median":round(float(g.engineering_estimate_eur.median()),2),"min":round(float(g.engineering_estimate_eur.quantile(.1)),2),"max":round(float(g.engineering_estimate_eur.quantile(.9)),2)})
    return {"ok":True,"mode":"live","families":families,"examples":examples(),"metrics":scrub(metrics.to_dict("records")),"family_metrics":scrub(family_metric.to_dict("records")),"counts":{"quotes":len(quotes),"operations":len(ops),"materials":int(quotes.material.nunique()),"families":int(quotes.product_family.nunique())},"model":art["best_model"],"validation_error90":13.23,"materials":scrub(quotes.material.value_counts().to_dict()),"splits":scrub(quotes.groupby('split').size().to_dict())}

BOOTSTRAP=bootstrap()

def get_case(quote_id):
    if quote_id not in quotes.index: raise ValueError("Quote ID not found")
    r=quotes.loc[quote_id]
    return {"quote":scrub(r.to_dict()),"operations":list_records(ops,quote_id),"suppliers":list_records(suppliers,quote_id),"inspection":list_records(inspection,quote_id),"energy":list_records(energy,quote_id)}

def estimate(req):
    quote_id=str(req.get('quote_id',''))
    if quote_id not in quotes.index: raise ValueError("Unknown case")
    r=quotes.loc[quote_id].copy()
    orig_qty=int(r.batch_qty)
    qty=int(req.get('batch_qty',orig_qty))
    if not 1<=qty<=1000:raise ValueError("Batch must be from 1 to 1,000")
    mat=float(req.get('material_multiplier',1))
    productivity=float(req.get('productivity_multiplier',1))
    machine=float(req.get('machine_multiplier',1))
    scrap_delta=float(req.get('scrap_delta',0))
    prio=str(req.get('priority',r.delivery_priority))
    if prio not in ['standard','expedited','critical']:raise ValueError("Invalid delivery priority")
    if not (.5<=mat<=2 and .6<=productivity<=1.5 and .6<=machine<=1.6 and -5<=scrap_delta<=10):raise ValueError('Scenario parameter out of range')
    scrap=float(np.clip(float(r.demo_expected_scrap_rate)+scrap_delta/100,.001,.45))
    pieces={
        'Material':float(r.demo_material_cost_eur)*mat,
        'Machining & labor':float(r.demo_machine_labor_eur)*machine/productivity,
        'Setup':float(r.demo_setup_amortized_eur)*orig_qty/qty,
        'CAM programming':float(r.demo_CAM_amortized_eur)*orig_qty/qty,
        'Tooling & energy':float(r.demo_tool_energy_eur)/productivity*(1+2*max(0,productivity-1)**2),
        'Inspection & quality':float(r.demo_quality_inspection_eur),
        'Special processes':float(r.demo_outsource_eur),
        'Expected rework':float(r.demo_expected_rework_eur),
    }
    subtotal=sum(pieces.values())
    scrap_reserve=subtotal/(1-scrap)-subtotal
    premium={'standard':0,'expedited':34,'critical':130}[prio]
    baseline=subtotal+scrap_reserve+premium
    r['batch_qty']=qty
    r['delivery_priority']=prio
    r['demo_material_price_eur_kg']=float(r.demo_material_price_eur_kg)*mat
    X=pd.DataFrame([r])[art['categorical']+art['numeric']]
    correction=float(np.exp(art['models']['Physics_plus_ML'].predict(X))[0])
    hybrid=baseline*correction
    # We expose cost components of engineering baseline; hybrid correction separate.
    breakdown=[{'name':k,'value':round(v,2)} for k,v in pieces.items()]
    breakdown += [{'name':'Expected scrap allowance','value':round(scrap_reserve,2)},{'name':'Delivery premium','value':round(premium,2)}]
    breakdown += [{'name':'ML calibration','value':round(hybrid-baseline,2)}]
    return scrub({
      'quote_id':quote_id,'family':str(r.product_family),'material':str(r.material),
      'model':'Physics + ML residual calibration','unit_cost':round(hybrid,2),
      'batch_cost':round(hybrid*qty,2),'engineering_baseline':round(baseline,2),
      'ml_adjustment':round(hybrid-baseline,2), 'ml_factor':round(correction,5),
      'batch_qty':qty,'scrap_rate_percent':round(scrap*100,2),'breakdown':breakdown,
      'parameters':{'material_multiplier':mat,'productivity_multiplier':productivity,'machine_multiplier':machine,'scrap_delta':scrap_delta,'priority':prio},
      'is_synthetic':True,'live_ml':True,
      'explanation':'Engineering costs are recomputed from recorded synthetic components and scenario multipliers; the trained ML model recalibrates the baseline. Productivity, machine-rate and scrap changes are scenario approximations, not learned features.',
      'validation_reference':'90th percentile of absolute relative error on synthetic validation cases: 13.23%. This is not a calibrated prediction interval.'
    })

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def send_json(self,obj,status=200):
        body=json.dumps(scrub(obj),allow_nan=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path=='/api/bootstrap': return self.send_json(BOOTSTRAP)
        if parsed.path=='/api/case':
            try:
                qid=parse_qs(parsed.query).get('id',[''])[0]
                return self.send_json(get_case(qid))
            except Exception as e:return self.send_json({'error':str(e)},400)
        if parsed.path=='/api/health':return self.send_json({'ok':True,'model_loaded':True,'quotes':len(quotes)})
        return super().do_GET()
    def do_POST(self):
        parsed=urlparse(self.path)
        if parsed.path not in ['/api/estimate','/api/sweep']:return self.send_json({'error':'Not found'},404)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>10000:raise ValueError('Request too large')
            body=json.loads(self.rfile.read(length).decode('utf8'))
            if parsed.path=='/api/estimate':return self.send_json(estimate(body))
            sweep=[]
            for qty in [1,2,4,8,12,20,32,50,80,120,200]:
                case={**body,'batch_qty':qty}
                res=estimate(case)
                sweep.append({'batch':qty,'unit_cost':res['unit_cost'],'total_cost':res['batch_cost']})
            return self.send_json({'sweep':sweep})
        except Exception as e:
            return self.send_json({'error':str(e)},400)
    def log_message(self,fmt,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',default=8502,type=int);args=p.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'\nAEROCOST AI Studio → http://{args.host}:{args.port}\nModel: {art["best_model"]} | Synthetic quote records: {len(quotes):,}\nCtrl+C to stop.\n')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
