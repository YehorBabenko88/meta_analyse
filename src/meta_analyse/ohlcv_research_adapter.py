"""Inert OHLCV backfill research using existing candle/level semantics.

A declared retrieval clock establishes no historical observation availability or
source authenticity. This adapter does not manufacture Grid records, aggressor
volumes, funding, training capability or execution signals.
"""
from __future__ import annotations
import copy
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import hashlib
import json
import math
import re
import time
from .core import Candle,untouched_levels

SYMBOLS=frozenset(('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','DOTUSDT'))
MAX_ROWS=2000
MAX_BYTES=8*1024*1024
_DATASET_FIELDS=('venue','market_type','symbol','timeframe','units','start_ms','end_ms','source','evidence_class','rows')
_EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)
_LABEL=re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
_DIGEST=re.compile(r'[a-f0-9]{64}\Z')


def _need(ok):
    if not ok:raise ValueError('INVALID_OHLCV_RESEARCH')


def _fields(value,names):_need(type(value) is dict and set(value)==set(names))
def _clock(value):_need(type(value) is int and 0<=value<=2**53-1);return value
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def _digest(value):return hashlib.sha256(_canonical(value)).hexdigest()
def _label(value):_need(type(value) is str and _LABEL.fullmatch(value) is not None)


def analyze_ohlcv_research(payload,*,decision_ms,now_ms=None):
    """Analyze only a fully retrieved, closed, contiguous one-minute backfill.

    Source retrieval is caller-declared and cannot be verified by this stateless
    adapter. It must precede the analysis decision and as-of time. No row-level
    historical availability or raw-trade observation clocks are accepted/inferred.
    now_ms is a pure-test clock; the HTTP route always uses the local wall clock.
    """
    try:return _analyze(payload,decision_ms,now_ms)
    except (KeyError,TypeError,OverflowError,RecursionError,UnicodeError) as exc:
        raise ValueError('INVALID_OHLCV_RESEARCH') from exc


def _analyze(p,decision,override_now):
    now=_clock(int(time.time()*1000) if override_now is None else override_now)
    _clock(decision)
    _fields(p,('schema',*_DATASET_FIELDS,'as_of_ms','dataset_id'))
    _need(p['schema']=='meta.ohlcv.research.request.v1' and p['venue']=='bybit' and p['market_type']=='linear')
    _need(type(p['symbol']) is str and p['symbol'] in SYMBOLS and p['timeframe']=='1m')
    _need(p['units']=={'price':'USDT/'+p['symbol'][:-4],'volume':p['symbol'][:-4]})
    _need(p['evidence_class'] in ('SYNTHETIC','HISTORICAL'))
    source=p['source']
    _fields(source,('kind','identity','source_revision','retrieval_id','retrieved_at_ms','raw_sha256'))
    _need(source['kind']=='HISTORICAL_BACKFILL');_label(source['identity']);_label(source['retrieval_id'])
    _need(type(source['source_revision']) is str and re.fullmatch('[a-f0-9]{40}',source['source_revision']) is not None)
    _need(type(source['raw_sha256']) is str and _DIGEST.fullmatch(source['raw_sha256']) is not None)
    start,end,asof=(_clock(p[k]) for k in ('start_ms','end_ms','as_of_ms'))
    retrieved=_clock(source['retrieved_at_ms'])
    _need(start%60000==end%60000==0 and 1<=(end-start)//60000<=MAX_ROWS)
    _need(end<=retrieved<=decision<=asof<=now)
    rows=p['rows'];_need(type(rows) is list and len(rows)==(end-start)//60000)
    for index,row in enumerate(rows):
        _fields(row,('event_start_ms','event_end_ms','open','high','low','close','volume'))
        lo=start+index*60000;hi=lo+60000
        _need(_clock(row['event_start_ms'])==lo and _clock(row['event_end_ms'])==hi and hi<=retrieved)
        for name in ('open','high','low','close','volume'):
            value=row[name];_need(type(value) in (int,float) and math.isfinite(value) and abs(value)<=1e15)
        _need(0<row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high'] and row['volume']>=0)
    _need(len(_canonical(p))<=MAX_BYTES)
    content=dict(schema='meta.ohlcv.dataset.v1',**{k:p[k] for k in _DATASET_FIELDS})
    _need(type(p['dataset_id']) is str and _DIGEST.fullmatch(p['dataset_id']) is not None and _digest(content)==p['dataset_id'])
    candles=[Candle(_EPOCH+timedelta(milliseconds=r['event_start_ms']),*(Decimal(str(r[k])) for k in ('high','low','open','close','volume'))) for r in rows]
    levels=untouched_levels(candles,'1m')
    result={
        'schema':'meta.ohlcv.research.result.v1','mode':'HISTORICAL_RESEARCH',
        'venue':p['venue'],'market_type':p['market_type'],'symbol':p['symbol'],
        'timeframe':'1m','units':copy.deepcopy(p['units']),
        'evidence_class':p['evidence_class'],'source':copy.deepcopy(source),
        'dataset_id':p['dataset_id'],
        'request_digest':_digest({'payload':p,'decision_ms':decision}),
        'decision_ms':decision,'snapshot_as_of_ms':asof,
        'window_start_ms':start,'window_end_ms':end,'data_available_at_ms':retrieved,
        'calculated_at_ms':now if override_now is not None else int(time.time()*1000),
        'rows':copy.deepcopy(rows),
        'levels':[{'price':str(level.price),'kind':level.kind,'timeframe':level.timeframe,
                   'source_start_ms':int((level.source_start-_EPOCH).total_seconds())*1000}
                  for level in levels],
        'quality_status':'UNKNOWN','coverage_status':'DECLARED_COMPLETE_UNVERIFIED',
        'source_authenticity':'NOT_EVALUATED',
        'clock_assumptions':{
            'availability_policy':'WHOLE_BACKFILL_AVAILABLE_AT_DECLARED_RETRIEVAL',
            'historical_observation_times':'NOT_PROVIDED',
            'bar_clock':'DECLARED_UTC_MINUTE_BOUNDARIES',
            'analysis_clock':'CALCULATED_NOW_NOT_HISTORICAL_OBSERVATION'},
        'missing_capabilities':['HISTORICAL_POINT_IN_TIME_AVAILABILITY',
            'RAW_SOURCE_EVENT_BOUNDS','AGGRESSOR_VOLUME','PUBLIC_TRADE_AGGREGATES',
            'OPEN_INTEREST','FUNDING','ORDERBOOK_L2','GRID_V1_1_RECEIPTS','H_B_ELIGIBILITY'],
        'execution_authority':False,'trading_authorized':False,
        'training_authorized':False,'h_b_eligible':False,
    }
    _need(len(_canonical(result))<=16*1024*1024)
    return result
