"""Actual Grid v1.1 synthetic export; checksums confer no source authority."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from meta_analyse.grid_history_adapter import analyze_grid_history


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent/'fixtures/grid_history/synthetic-v11.json').read_text())


def reseal(p):
    q=p['request']
    p['dataset_id']=digest({'schema':'grid.dataset.v1.1','source':p['source'],
        'identity':{k:q[k] for k in ('venue','market_type','symbol','units')},
        'timeframe':'1m','representation':'historical_aggregate','evidence_class':p['evidence_class'],
        'rows':p['rows'],'source_receipts':p['source_receipts']})
    p['dataset_fingerprint']=digest({k:v for k,v in p.items() if k!='dataset_fingerprint'})


def test_actual_grid_export_reuses_candle_level_rules_without_promotion(payload):
    before=copy.deepcopy(payload)
    out=analyze_grid_history(payload,decision_ms=180000)
    assert payload==before
    assert out['dataset_id']==payload['dataset_id']
    assert out['dataset_fingerprint']==payload['dataset_fingerprint']
    assert out['source']==payload['source'] and out['evidence_class']=='SYNTHETIC'
    assert out['symbol']=='BTCUSDT' and out['timeframe']=='1m'
    assert [c['close'] for c in out['candles']]==['101.0','101.1','101.2']
    assert [(x['kind'],x['price']) for x in out['levels']]==[('low','99.0'),('low','99.1'),('high','102.2'),('low','99.2')]
    assert out['rows']==payload['rows']
    assert out['quality_status']=='UNKNOWN' and out['coverage_status']=='DECLARED_COMPLETE_UNVERIFIED'
    assert out['source_authenticity']=='NOT_EVALUATED'
    assert all(out[k] is False for k in ('execution_authority','trading_authorized','training_authorized'))
    out['source']['identity']='changed'
    assert payload==before


def test_delayed_availability_excludes_closed_but_not_known_candle(payload):
    payload['rows'][1]['available_at_ms']=150000
    reseal(payload)
    out=analyze_grid_history(payload,decision_ms=120000)
    assert len(out['candles'])==1 and len(out['rows'])==1
    assert out['coverage_status']=='PARTIAL' and out['excluded_rows']==2
    assert out['levels'][0]['available_at_ms']==60000


def test_decision_before_first_availability_has_no_levels(payload):
    out=analyze_grid_history(payload,decision_ms=59999)
    assert out['coverage_status']=='UNAVAILABLE' and out['candles']==[] and out['levels']==[]


@pytest.mark.parametrize('mutate',[
    lambda p:p.update(schema='grid.history.v1'),
    lambda p:p.update(execution_authority=True),
    lambda p:p.update(training_authorized=True),
    lambda p:p['request'].update(units={'price':'USD/BTC','volume':'BTC'}),
    lambda p:p['request'].update(symbol='ETHUSDT'),
    lambda p:p['rows'][0].update(event_start_ms=True),
    lambda p:p['rows'][0].update(available_at_ms=59999),
    lambda p:p['rows'][0].update(watermark_ms=60001),
    lambda p:p['rows'][0].update(source_event_end_ms=60000),
    lambda p:p['rows'][0].update(close=999),
    lambda p:p['rows'][0].update(volume=-1),
    lambda p:p['rows'][0].update(open=float('nan')),
    lambda p:p['rows'][0].update(source_receipt_hash='f'*64),
    lambda p:p['rows'].reverse(),
    lambda p:p['rows'].pop(),
    lambda p:p.update(rows=p['rows']*1000),
    lambda p:p['source'].update(source_revision='not-a-revision'),
])
def test_malformed_even_resealed_export_is_rejected(payload,mutate):
    mutate(payload)
    try:reseal(payload)
    except ValueError:pass
    with pytest.raises(ValueError):analyze_grid_history(payload,decision_ms=180000)


def test_corruption_is_rejected_without_resealing(payload):
    payload['rows'][0]['close']=100.5
    with pytest.raises(ValueError):analyze_grid_history(payload,decision_ms=180000)


@pytest.mark.parametrize('decision',[True,-1,2**53,180001])
def test_invalid_or_stale_decision_rejected(payload,decision):
    if decision==180001:payload['request']['max_age_ms']=0;reseal(payload)
    with pytest.raises(ValueError):analyze_grid_history(payload,decision_ms=decision)


def test_noncontiguous_known_rows_do_not_bridge_gap_for_levels(payload):
    payload['rows'][0]['available_at_ms']=170000
    reseal(payload)
    out=analyze_grid_history(payload,decision_ms=120000)
    assert out['coverage_status']=='GAP' and out['levels']==[]
    assert [r['event_start_ms'] for r in out['rows']]==[60000]


def test_historical_label_and_valid_checksums_never_authenticate(payload):
    payload['evidence_class']='HISTORICAL'
    reseal(payload)
    result=analyze_grid_history(payload,decision_ms=180000)
    assert result['evidence_class']=='HISTORICAL'
    assert result['source_authenticity']=='NOT_EVALUATED'
    assert result['quality_status']=='UNKNOWN'
    assert result['coverage_status']=='DECLARED_COMPLETE_UNVERIFIED'
    assert result['execution_authority'] is False


def test_surviving_level_availability_binds_all_observed_wicks(payload):
    result=analyze_grid_history(payload,decision_ms=180000)
    first_low=next(level for level in result['levels'] if level['source_start_ms']==0)
    assert first_low['available_at_ms']==180000
    json.dumps(result,allow_nan=False)


def test_earlier_decision_does_not_inspect_future_wicks_for_levels(payload):
    first=analyze_grid_history(payload,decision_ms=60000)
    payload['rows'][-1]['low']=1
    reseal(payload)
    second=analyze_grid_history(payload,decision_ms=60000)
    assert first['candles']==second['candles'] and first['levels']==second['levels']


def test_extra_or_missing_row_fields_rejected(payload):
    payload['rows'][0]['orderbook']={}
    reseal(payload)
    with pytest.raises(ValueError):analyze_grid_history(payload,decision_ms=180000)
