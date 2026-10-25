"""Paired bootstrap timing intervals conditional on the fixed measured workload."""
from pathlib import Path
import argparse,gzip,json,random,statistics,math

def main(receipt,output):
 raw=receipt.read_bytes();d=json.loads(gzip.decompress(raw) if receipt.suffix=='.gz' else raw);rng=random.Random(89347);out=[]
 def quant(values,p):return sorted(values)[min(len(values)-1,int(p*(len(values)-1)))]
 for engine in ['Neo4j','SQLite']:
  phases={p:[next(x['milliseconds'] for x in d['maintenance'] if x['engine']==engine and x['phase']==p and x['cycle']==i) for i in range(7)] for p in ['initial_stored','invalidate','refresh_stored']}
  for workload in sorted({x['workload'] for x in d['timings']}):
   arms={s:[next(x['milliseconds'] for x in d['timings'] if x['state']=='October' and x['engine']==engine and x['workload']==workload and x['stored']==s and x['repeat']==i) for i in range(15)] for s in [False,True]};savings=[];thresholds=[]
   for _ in range(5000):
    reps=[rng.randrange(15) for _ in range(15)];cycles=[rng.randrange(7) for _ in range(7)];saving=statistics.median(arms[False][i] for i in reps)-statistics.median(arms[True][i] for i in reps);overhead=sum(statistics.median(v[i] for i in cycles) for v in phases.values());savings.append(saving);thresholds.append(math.ceil(overhead/saving) if saving>0 else math.inf)
   lower,upper=quant(thresholds,.025),quant(thresholds,.975);out.append({'engine':engine,'workload':workload,'saving_ms_interval':[quant(savings,.025),quant(savings,.975)],'break_even_requests_interval':[lower if math.isfinite(lower) else None,upper if math.isfinite(upper) else None],'interval_scope':'paired bootstrap 95% intervals over 15 interleaved repetitions and seven maintenance cycles; fixed datasets, queries and deployment; null means no finite upper/lower threshold'})
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'seed':89347,'resamples':5000,'intervals':out},indent=2,allow_nan=False)+'\n');print(json.dumps(out[:5],indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.receipt,a.output)
