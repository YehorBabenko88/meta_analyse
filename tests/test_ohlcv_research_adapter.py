"""SYNTHETIC_TEST_INPUT OHLCV only; no historical observation/authenticity claim."""
import copy,hashlib,json,time
from pathlib import Path
import shutil
import pytest
from meta_analyse import ohlcv_research_adapter as adapter
from test_headless_service import capsule,launch,request,TOKEN

NOW=360000
SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','DOTUSDT')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def reseal(p):
    fields=('venue','market_type','symbol','timeframe','units','start_ms','end_ms','source','evidence_class','rows')
    p['dataset_id']=digest(dict(schema='meta.ohlcv.dataset.v1',**{k:p[k] for k in fields}))
def payload(symbol='ETHUSDT',start=0,retrieved=240000,asof=300000):
    p=dict(schema='meta.ohlcv.research.request.v1',venue='bybit',market_type='linear',symbol=symbol,timeframe='1m',units={'price':'USDT/'+symbol[:-4],'volume':symbol[:-4]},start_ms=start,end_ms=start+180000,as_of_ms=asof,evidence_class='SYNTHETIC',source=dict(kind='HISTORICAL_BACKFILL',identity='SYNTHETIC_TEST_INPUT',source_revision='a'*40,retrieval_id='SYNTHETIC_TEST_INPUT',retrieved_at_ms=retrieved,raw_sha256='b'*64),rows=[dict(event_start_ms=start+i*60000,event_end_ms=start+(i+1)*60000,open=o,high=h,low=l,close=c,volume=v) for i,(o,h,l,c,v) in enumerate(((10,12,8,11,3),(10,11,9,10,2),(11,12,10,12,4)))])
    reseal(p);return p


def test_independent_hand_calculated_levels_and_no_input_mutation():
    p=payload();before=copy.deepcopy(p);out=adapter.analyze_ohlcv_research(p,decision_ms=300000,now_ms=NOW)
    # Row2 touches both earlier highs. Earlier lows8/9 survive; row2 adds12/10.
    assert [(x['kind'],x['price'],x['source_start_ms']) for x in out['levels']]==[('low','8',0),('low','9',60000),('high','12',120000),('low','10',120000)]
    assert p==before and out['units']=={'price':'USDT/ETH','volume':'ETH'}
    assert out['dataset_id']==p['dataset_id']
    assert out['request_digest']==digest({'payload':p,'decision_ms':300000})
    assert out['data_available_at_ms']==240000 and out['calculated_at_ms']==NOW
    assert out['source_authenticity']=='NOT_EVALUATED' and out['quality_status']=='UNKNOWN'
    assert all(out[k] is False for k in ('execution_authority','trading_authorized','training_authorized','h_b_eligible'))
    assert out['clock_assumptions']['historical_observation_times']=='NOT_PROVIDED'
    assert {'AGGRESSOR_VOLUME','PUBLIC_TRADE_AGGREGATES','FUNDING','OPEN_INTEREST','GRID_V1_1_RECEIPTS'}<=set(out['missing_capabilities'])
    assert all('available_at_ms' not in row for row in out['rows'])
    out['source']['identity']='changed';out['rows'][0]['close']=99;assert p==before


@pytest.mark.parametrize('symbol',SYMBOLS)
def test_ten_original_asset_units_are_preserved(symbol):
    out=adapter.analyze_ohlcv_research(payload(symbol),decision_ms=300000,now_ms=NOW)
    assert out['symbol']==symbol and out['units']=={'price':'USDT/'+symbol[:-4],'volume':symbol[:-4]}
    if symbol!='BTCUSDT':assert 'BTC' not in json.dumps(out['units'])


@pytest.mark.parametrize('mutate',[
 lambda p:p.update(schema='grid.history.v1.1'),lambda p:p.update(symbol='OTHERUSDT'),
 lambda p:p.update(units={'price':'USDT/BTC','volume':'BTC'}),lambda p:p.update(market_type='spot'),
 lambda p:p.update(as_of_ms=NOW+1),lambda p:p['source'].update(retrieved_at_ms=NOW+1),
 lambda p:p['source'].update(retrieved_at_ms=179999),lambda p:p['source'].update(kind='LIVE_GRID'),
 lambda p:p['source'].update(raw_sha256='invalid'),lambda p:p['source'].update(source_revision='b'*64),
 lambda p:p['source'].update(identity='postgres://private'),lambda p:p['source'].update(retrieval_id='C:/private'),
 lambda p:p['source'].update(available_at_ms=60000),lambda p:p['rows'][0].update(available_at_ms=60000),
 lambda p:p['rows'][0].update(source_receipt_hash='c'*64),lambda p:p['rows'][0].update(buy_volume=3),
 lambda p:p['rows'][0].update(close=True),lambda p:p['rows'][0].update(close=float('nan')),
 lambda p:p['rows'][0].update(volume=-1),lambda p:p['rows'][0].update(high=9),
 lambda p:p['rows'][0].update(low=0),lambda p:p['rows'][0].update(event_end_ms=60001),
 lambda p:p['rows'][1].update(event_start_ms=120000),lambda p:p['rows'].reverse(),
 lambda p:p['rows'].__setitem__(1,copy.deepcopy(p['rows'][0])),lambda p:p['rows'].pop(),
 lambda p:p.update(training_authorized=True),lambda p:p.update(evidence_class='LIVE'),
])
def test_resealed_invalid_inputs_still_reject(mutate):
    p=payload();mutate(p)
    try:reseal(p)
    except ValueError:pass # NaN cannot be canonically sealed.
    with pytest.raises(ValueError):adapter.analyze_ohlcv_research(p,decision_ms=300000,now_ms=NOW)


@pytest.mark.parametrize('decision',(-1,True,239999,300001,NOW+1))
def test_decision_cannot_precede_actual_retrieval_or_exceed_asof(decision):
    with pytest.raises(ValueError):adapter.analyze_ohlcv_research(payload(),decision_ms=decision,now_ms=NOW)


def test_dataset_and_request_bindings_and_row_limit():
    p=payload();p['rows'][0]['close']=10
    with pytest.raises(ValueError):adapter.analyze_ohlcv_research(p,decision_ms=300000,now_ms=NOW)
    p=payload();p['rows']=[dict(event_start_ms=i*60000,event_end_ms=(i+1)*60000,open=10,high=12,low=8,close=11,volume=3) for i in range(2001)];p.update(end_ms=2001*60000,as_of_ms=2001*60000+100);p['source']['retrieved_at_ms']=p['as_of_ms'];reseal(p)
    with pytest.raises(ValueError):adapter.analyze_ohlcv_research(p,decision_ms=p['as_of_ms'],now_ms=p['as_of_ms'])
    original=payload();later=copy.deepcopy(original);later['as_of_ms']=310000
    a=adapter.analyze_ohlcv_research(original,decision_ms=300000,now_ms=NOW);b=adapter.analyze_ohlcv_research(later,decision_ms=310000,now_ms=NOW)
    assert a['dataset_id']==b['dataset_id'] and a['request_digest']!=b['request_digest']


@pytest.fixture
def ohlcv_capsule(capsule):
    root,env,git=capsule
    shutil.copyfile(Path(adapter.__file__),root/'src/meta_analyse/ohlcv_research_adapter.py')
    git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','synthetic OHLCV route fixture')
    env['UNIFIED_SOURCE_COMMIT']=git('rev-parse','HEAD')
    return capsule


def test_real_authenticated_route_preserves_grid_route_and_rejects_mutation(ohlcv_capsule):
    process,port=launch(ohlcv_capsule);root,_,_=ohlcv_capsule
    path='/internal/v1/research/ohlcv/analyze';headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'}
    now=int(time.time()*1000);end=(now//60000)*60000;p=payload(start=end-180000,retrieved=now-10,asof=now)
    try:
        status,out=request(port,'POST',path,json.dumps({'payload':p,'decision_ms':now}),headers)
        assert status==200 and out['schema']=='meta.ohlcv.research.result.v1' and out['symbol']=='ETHUSDT'
        assert out['source']==p['source'] and out['request_digest']==digest({'payload':p,'decision_ms':now})
        assert request(port,'POST',path,'{}',{})[0]==401
        assert request(port,'POST',path,'{}',dict(headers,Origin='https://outside.invalid'))[0]==403
        assert request(port,'POST',path,'{}',dict(headers,**{'Content-Type':'text/plain'}))[0]==415
        assert request(port,'POST',path,'{}',headers)[0]==422
        assert request(port,'POST',path,json.dumps({'payload':p,'decision_ms':now,'now_ms':now+60000}),headers)[0]==422
        assert request(port,'POST',path,'{}',dict(headers,**{'Content-Length':'8388609'}))[0]==413
        bad=copy.deepcopy(p);bad['source']['retrieved_at_ms']=now+60000;reseal(bad)
        assert request(port,'POST',path,json.dumps({'payload':bad,'decision_ms':now}),headers)[0]==422
        original=json.loads((Path(__file__).parent/'fixtures/grid_history/synthetic-v11.json').read_bytes())
        assert request(port,'POST','/internal/v1/history/analyze',json.dumps({'payload':original,'decision_ms':180000}),headers)[0]==200
        with (root/'src/meta_analyse/ohlcv_research_adapter.py').open('a') as stream:stream.write('\n# mutation\n')
        assert request(port,'POST',path,json.dumps({'payload':p,'decision_ms':now}),headers)[0]==422
        assert request(port)[0]==503
    finally:process.terminate();process.communicate(timeout=5)


def test_closed_zero_volume_rows_and_exact_2000_row_boundary():
    p=payload();p['rows']=[dict(event_start_ms=i*60000,event_end_ms=(i+1)*60000,open=10,high=10,low=10,close=10,volume=0) for i in range(2000)]
    p.update(end_ms=120000000,as_of_ms=120000001);p['source']['retrieved_at_ms']=p['as_of_ms'];reseal(p)
    out=adapter.analyze_ohlcv_research(p,decision_ms=p['as_of_ms'],now_ms=p['as_of_ms'])
    assert len(out['rows'])==2000 and [l['price'] for l in out['levels']]==['10','10']


def test_backend_drift_cannot_promote_new_contract():
    from meta_analyse.headless_service import admitted_ohlcv_result
    out=adapter.analyze_ohlcv_research(payload(),decision_ms=300000,now_ms=NOW)
    assert admitted_ohlcv_result(out) is out
    for key,value in [('schema','meta.grid.history.analysis.v1'),('execution_authority',True),('training_authorized',True),('trading_authorized',True),('h_b_eligible',True),('source_authenticity','AUTHENTICATED'),('quality_status','GOOD'),('coverage_status','COMPLETE')]:
        with pytest.raises(ValueError):admitted_ohlcv_result({**out,key:value})
