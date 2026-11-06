"""Independent SYNTHETIC OHLCV boundary tests; no endpoint/authenticity ACK."""
import copy
import hashlib
import json
import socket

import pytest
from meta_analyse.ohlcv_research_adapter import analyze_ohlcv_research

SYMBOLS = ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT',
           'DOGEUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','DOTUSDT')
DATASET_FIELDS = ('venue','market_type','symbol','timeframe','units','start_ms',
                  'end_ms','source','evidence_class','rows')


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',',':'),
                                     allow_nan=False).encode()).hexdigest()


def seal(payload):
    payload['dataset_id'] = sha(dict(schema='meta.ohlcv.dataset.v1',
                                    **{k:payload[k] for k in DATASET_FIELDS}))
    return payload


def dataset(symbol='ETHUSDT'):
    rows = [dict(event_start_ms=i*60000, event_end_ms=(i+1)*60000,
                 open=o, high=h, low=l, close=c, volume=3)
            for i,(o,h,l,c) in enumerate(((10,12,8,11),(10,11,9,10),(11,12,10,12)))]
    return seal(dict(schema='meta.ohlcv.research.request.v1', venue='bybit',
        market_type='linear', symbol=symbol, timeframe='1m',
        units={'price':'USDT/'+symbol[:-4], 'volume':symbol[:-4]},
        start_ms=0, end_ms=180000, as_of_ms=300000, evidence_class='SYNTHETIC',
        source=dict(kind='HISTORICAL_BACKFILL', identity='SYNTHETIC_AGENT7',
                    source_revision='a'*40, retrieval_id='fixture1',
                    retrieved_at_ms=240000, raw_sha256='b'*64), rows=rows))


@pytest.mark.parametrize('symbol', SYMBOLS)
def test_agent7_deterministic_derived_levels_and_capability_denial(symbol, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('offline feature computation reached network')
    monkeypatch.setattr(socket, 'socket', forbidden)
    payload = dataset(symbol); original = copy.deepcopy(payload)
    result = analyze_ohlcv_research(payload, decision_ms=300000, now_ms=360000)
    assert result == analyze_ohlcv_research(copy.deepcopy(payload), decision_ms=300000, now_ms=360000)
    # Later bars touch previous highs12/11; previous lows8/9 survive.
    assert [(x['kind'],x['price'],x['source_start_ms']) for x in result['levels']] == [
        ('low','8',0),('low','9',60000),('high','12',120000),('low','10',120000)]
    assert result['request_digest'] == sha({'payload':payload,'decision_ms':300000})
    assert result['dataset_id'] == payload['dataset_id']
    assert result['schema'] == 'meta.ohlcv.research.result.v1'
    assert result['source_authenticity'] == 'NOT_EVALUATED'
    assert result['coverage_status'] == 'DECLARED_COMPLETE_UNVERIFIED'
    for field in ('execution_authority','trading_authorized','training_authorized','h_b_eligible'):
        assert result[field] is False
    assert {'FUNDING','GRID_V1_1_RECEIPTS','HISTORICAL_POINT_IN_TIME_AVAILABILITY'} <= set(result['missing_capabilities'])
    result['rows'][0]['close'] = 99
    assert payload == original


@pytest.mark.parametrize('mutation', ('schema','gap','missing','duplicate','ohlc','future','symbol','extra','rows-limit'))
def test_agent7_resealed_invalid_dataset_still_fails_closed(mutation):
    payload = dataset()
    if mutation == 'schema': payload['schema'] = 'meta.ohlcv.research.request.v2'
    elif mutation == 'gap': payload['rows'][1]['event_start_ms'] += 60000
    elif mutation == 'missing': payload['rows'].pop()
    elif mutation == 'duplicate': payload['rows'][1] = copy.deepcopy(payload['rows'][0])
    elif mutation == 'ohlc': payload['rows'][0]['low'] = 20
    elif mutation == 'future': payload['source']['retrieved_at_ms'] = 360001
    elif mutation == 'symbol': payload['symbol'] = 'UNKNOWNUSDT'
    elif mutation == 'extra': payload['rows'][0]['execution_authority'] = True
    else: payload['end_ms'] = 2001*60000
    seal(payload)
    with pytest.raises(ValueError): analyze_ohlcv_research(payload, decision_ms=300000, now_ms=360000)


def test_agent7_untouched_digest_cannot_hide_changed_dataset():
    payload = dataset(); payload['rows'][0]['volume'] += 1
    with pytest.raises(ValueError): analyze_ohlcv_research(payload, decision_ms=300000, now_ms=360000)


@pytest.mark.parametrize('bad', (float('nan'),float('inf'),float('-inf')))
def test_agent7_nonfinite_input_rejected_before_result(bad):
    payload = dataset(); payload['rows'][0]['close'] = bad
    with pytest.raises(ValueError): analyze_ohlcv_research(payload, decision_ms=300000, now_ms=360000)


def test_agent7_resource_budget_precedes_candle_allocation(monkeypatch):
    import meta_analyse.ohlcv_research_adapter as adapter
    payload = dataset(); payload['end_ms'] = 2001*60000; seal(payload)
    def forbidden(*args, **kwargs): raise AssertionError('invalid window allocated Candle')
    monkeypatch.setattr(adapter, 'Candle', forbidden)
    with pytest.raises(ValueError): adapter.analyze_ohlcv_research(payload, decision_ms=300000, now_ms=360000)
