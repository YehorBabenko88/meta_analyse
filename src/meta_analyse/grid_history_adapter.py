"""Read-only Grid v1.1 OHLCV bridge to existing candle/level analysis.

Digests bind bytes, not source authenticity. Grid's export drops raw quality and
coverage details: even a HISTORICAL label cannot establish completeness here.
No trades, order book, per-price volume, or execution signals are reconstructed.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import re

from .core import Candle, untouched_levels

_MAX_CLOCK = 2**53 - 1
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_ROW_FIELDS = {'open', 'high', 'low', 'close', 'volume', 'event_start_ms',
               'event_end_ms', 'available_at_ms', 'revision', 'source_event_start_ms',
               'source_event_end_ms', 'watermark_ms', 'source_receipt_hash'}


def _clock(value):
    if type(value) is not int or not 0 <= value <= _MAX_CLOCK:
        raise ValueError('INVALID_CLOCK')
    return value


def _hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('INVALID_DIGEST')
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _fields(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('INVALID_FIELDS')


def analyze_grid_history(payload, *, decision_ms):
    """Return inert JSON-compatible historical candles/levels, never authority.

    decision_ms may precede snapshot as_of_ms: only closed rows first available
    at that decision are exposed. Gaps suppress levels rather than treating an
    absent candle as evidence that a level remained untouched. Malformed exports
    fail without a result. No connections, files, imports of Grid, or writes.
    """
    try:
        return _analyze(payload, decision_ms)
    except (KeyError, TypeError, OverflowError, RecursionError) as exc:
        raise ValueError('INVALID_GRID_HISTORY') from exc


def _analyze(p, decision):
    _clock(decision)
    _fields(p, {'schema', 'request', 'source', 'evidence_class', 'rows',
                'source_receipts', 'execution_authority', 'trading_authorized',
                'watermark_ms', 'dataset_id', 'dataset_fingerprint'})
    if p['schema'] != 'grid.history.v1.1' or p['execution_authority'] is not False or p['trading_authorized'] is not False:
        raise ValueError('INVALID_CONTRACT')
    if p['evidence_class'] not in ('SYNTHETIC', 'HISTORICAL'):
        raise ValueError('INVALID_EVIDENCE_CLASS')
    q, source, rows = p['request'], p['source'], p['rows']
    _fields(q, {'schema', 'venue', 'market_type', 'symbol', 'start_ms', 'end_ms',
                'as_of_ms', 'max_age_ms', 'units'})
    _fields(source, {'identity', 'source_revision', 'epoch'})
    if any(type(source[k]) is not str or not 1 <= len(source[k]) <= 256 for k in source):
        raise ValueError('INVALID_SOURCE')
    if not re.fullmatch('[0-9a-f]{40}', source['source_revision']):
        raise ValueError('INVALID_SOURCE_REVISION')
    if q['schema'] != 'grid.history.request.v1' or q['venue'] != 'bybit' or q['market_type'] != 'linear':
        raise ValueError('UNSUPPORTED_MARKET')
    if type(q['symbol']) is not str or not re.fullmatch('[A-Z0-9]{1,24}USDT', q['symbol']):
        raise ValueError('UNSUPPORTED_SYMBOL')
    if q['units'] != {'price': 'USDT/'+q['symbol'][:-4], 'volume': q['symbol'][:-4]}:
        raise ValueError('UNSUPPORTED_UNITS')
    for key in ('start_ms', 'end_ms', 'as_of_ms', 'max_age_ms'):
        _clock(q[key])
    start, end, asof = q['start_ms'], q['end_ms'], q['as_of_ms']
    if start % 60000 or end % 60000 or not 1 <= (end-start)//60000 <= 2000:
        raise ValueError('INVALID_WINDOW')
    if not end <= asof or asof-end > q['max_age_ms'] or decision > asof or max(0, decision-end) > q['max_age_ms']:
        raise ValueError('INVALID_AS_OF')
    if type(rows) is not list or len(rows) != (end-start)//60000:
        raise ValueError('INCOMPLETE_EXPORT')
    if type(p['source_receipts']) is not list or len(p['source_receipts']) != len(rows):
        raise ValueError('INVALID_RECEIPTS')
    revisions = set()
    for i, row in enumerate(rows):
        _fields(row, _ROW_FIELDS)
        for k in ('event_start_ms', 'event_end_ms', 'available_at_ms',
                  'source_event_start_ms', 'source_event_end_ms', 'watermark_ms'):
            _clock(row[k])
        lo, hi = start+i*60000, start+(i+1)*60000
        if (row['event_start_ms'] != lo or row['event_end_ms'] != hi or
            not lo <= row['source_event_start_ms'] <= row['source_event_end_ms'] < hi or
            not hi <= row['watermark_ms'] <= row['available_at_ms'] <= asof):
            raise ValueError('INVALID_ROW_CLOCKS')
        for k in ('open', 'high', 'low', 'close', 'volume'):
            if type(row[k]) not in (int, float) or not math.isfinite(row[k]):
                raise ValueError('INVALID_OHLCV')
        if not 0 < row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high'] or row['volume'] < 0:
            raise ValueError('INVALID_OHLCV')
        revision = _hash(row['revision'])
        if revision in revisions:
            raise ValueError('DUPLICATE_REVISION')
        revisions.add(revision)
        if _hash(row['source_receipt_hash']) != _hash(p['source_receipts'][i]):
            raise ValueError('RECEIPT_MISMATCH')
    if _clock(p['watermark_ms']) != max(row['watermark_ms'] for row in rows):
        raise ValueError('WATERMARK_MISMATCH')
    if len(_canonical(p)) > 8*1024*1024:
        raise ValueError('BYTE_LIMIT')
    content = {'schema': 'grid.dataset.v1.1', 'source': source,
               'identity': {k: q[k] for k in ('venue', 'market_type', 'symbol', 'units')},
               'timeframe': '1m', 'representation': 'historical_aggregate',
               'evidence_class': p['evidence_class'], 'rows': rows, 'source_receipts': p['source_receipts']}
    if _hash(p['dataset_id']) != _digest(content) or _hash(p['dataset_fingerprint']) != _digest({k: v for k, v in p.items() if k != 'dataset_fingerprint'}):
        raise ValueError('INTEGRITY_MISMATCH')
    known = [r for r in rows if r['event_end_ms'] <= decision and r['available_at_ms'] <= decision]
    gap = any(r['event_start_ms'] != start+i*60000 for i, r in enumerate(known))
    candles = [Candle(_EPOCH+timedelta(milliseconds=r['event_start_ms']),
                      *(Decimal(str(r[k])) for k in ('high', 'low', 'open', 'close', 'volume'))) for r in known]
    levels = [] if gap else untouched_levels(candles, '1m')
    clocks = {c.start: r for c, r in zip(candles, known)}
    # A surviving level requires all later analyzed wicks; availability binds that
    # entire analysis prefix, not only the candle that first introduced the level.
    available = max((r['available_at_ms'] for r in known), default=None)
    return {'schema': 'meta.grid.history.analysis.v1',
            'dataset_id': p['dataset_id'], 'dataset_fingerprint': p['dataset_fingerprint'],
            'source': copy.deepcopy(source), 'evidence_class': p['evidence_class'],
            'symbol': q['symbol'], 'venue': q['venue'], 'market_type': q['market_type'],
            'timeframe': '1m', 'units': copy.deepcopy(q['units']), 'decision_ms': decision,
            'snapshot_as_of_ms': asof, 'window_start_ms': start, 'window_end_ms': end,
            'quality_status': 'UNKNOWN', 'source_authenticity': 'NOT_EVALUATED',
            'coverage_status': 'GAP' if gap else 'UNAVAILABLE' if not known else 'PARTIAL' if len(known) < len(rows) else 'DECLARED_COMPLETE_UNVERIFIED',
            'excluded_rows': len(rows)-len(known), 'rows': copy.deepcopy(known),
            'candles': [{'event_start_ms': r['event_start_ms'], 'event_end_ms': r['event_end_ms'],
                         'available_at_ms': r['available_at_ms'],
                         **{k: str(getattr(c, k)) for k in ('open', 'high', 'low', 'close', 'volume')}} for c, r in zip(candles, known)],
            'levels': [{'price': str(level.price), 'kind': level.kind, 'timeframe': level.timeframe,
                        'source_start_ms': clocks[level.source_start]['event_start_ms'],
                        'available_at_ms': available} for level in levels],
            'execution_authority': False, 'trading_authorized': False, 'training_authorized': False}
