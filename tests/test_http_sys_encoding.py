"""Encoding boundaries only. No real netsh, host inventory or native probes."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
from evidence_schema import strict_loads
from host_identity import http_sys_owner
from http_sys_format import project

TEXT='Синтетический текст ёж'

@pytest.mark.parametrize('emitted',['cp866','utf-8'])
@pytest.mark.parametrize('decoded',['cp866','utf-8'])
@pytest.mark.parametrize('stdin_encoding',['ascii','utf-8'])
def test_two_stage_native_unicode_json_model(emitted,decoded,stdin_encoding):
    # Explicit model, not a claim about the encoding chosen by real netsh.
    native=TEXT.encode(emitted)
    captured=native.decode(decoded,errors='replace')
    wire=json.dumps({'text':captured},ensure_ascii=False).encode('utf-8')
    final=strict_loads(wire.decode('utf-8-sig'))['text']
    assert final==captured
    assert (final==TEXT)==(emitted==decoded)
    assert ('\ufffd' in captured)==(emitted=='cp866' and decoded=='utf-8')
    # No stdin is sent in this invocation. stdin_encoding has no role here.

@pytest.mark.parametrize('codec',['cp866','utf-8'])
def test_correct_unicode_does_not_make_unknown_headers_supported(codec):
    text='Неизвестное поле: синтетика\nЕщё неизвестное поле: 1\n17845\n'
    captured=text.encode(codec).decode(codec)
    final=strict_loads(json.dumps({'text':captured},ensure_ascii=False).encode('utf-8').decode('utf-8-sig'))['text']
    assert final==text
    with pytest.raises(ValueError):http_sys_owner(final,17845)
    assert project(final)['ownership']=='NOT_EVALUATED'
    assert project(final)['format_support']=='NOT_ATTESTED'

@pytest.mark.parametrize('bom',[b'',b'\xef\xbb\xbf'])
def test_outer_utf8_json_preserves_unicode_with_optional_bom(bom):
    raw=bom+json.dumps({'text':TEXT},ensure_ascii=False).encode('utf-8')
    assert strict_loads(raw.decode('utf-8-sig'))['text']==TEXT

@pytest.mark.parametrize('raw',[
    b'{"text":"\xff"}',b'{"text":"\xd0"}',
    json.dumps({'text':TEXT},ensure_ascii=False).encode('cp866'),
])
def test_outer_wire_never_falls_back_to_cp866(raw):
    with pytest.raises(UnicodeDecodeError):raw.decode('utf-8-sig')

@pytest.mark.parametrize('text',[
    '{"text":"one","text":"two"}', '{"text":NaN}', '{"text":Infinity}',
])
def test_malformed_json_never_becomes_valid_through_encoding(text):
    with pytest.raises(ValueError):strict_loads(text.encode('utf-8').decode('utf-8-sig'))

@pytest.mark.parametrize('codec',['cp866','utf-8'])
def test_ambiguous_http_queue_refused_after_correct_transcoding(codec):
    single=('Request queue name: synthetic\n Number of active processes attached: 1\n'
      ' Processes:\n  ID: 777, image: синтетика\n Registered URLs:\n  HTTP://127.0.0.1:17845/\n')
    value=(single+single).encode(codec).decode(codec)
    with pytest.raises(ValueError):http_sys_owner(value,17845)


def test_synthetic_checker_source_has_no_real_collection():
    path=Path(__file__).resolve().parents[1]/'scripts/check_http_sys_encoding_contract.py'
    source=path.read_text(encoding='utf-8')
    assert 'CREATE_NO_WINDOW' in source and "'-File'" in source
    assert "'-ExecutionPolicy'" not in source and 'Add-Type' not in source
    assert 'netsh.exe' not in source and 'Get-CimInstance' not in source
    assert 'StandardOutput' not in source  # Test actual PS native capture, not a .NET decoder model.
