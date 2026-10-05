"""LLM provider config routes + Scribe extraction/apply."""
import io
import zipfile
from unittest.mock import patch

def test_llm_config_roundtrip(client):
    r = client.get('/api/llm/config')
    assert r.status_code == 200
    data = r.get_json()
    assert data['provider'] == 'anthropic'
    assert data['model'] == 'claude-opus-5'
    assert data['has_api_key'] is False

    r = client.put('/api/llm/config', json={
        'provider': 'openai-compatible',
        'base_url': 'http://localhost:11434/v1/',
        'model': 'llama3',
        'api_key': 'secret-key-12345',
    })
    assert r.status_code == 200

    r = client.get('/api/llm/config')
    data = r.get_json()
    assert data['provider'] == 'openai-compatible'
    assert data['base_url'] == 'http://localhost:11434/v1'  # trailing slash stripped
    assert data['model'] == 'llama3'
    assert data['has_api_key'] is True
    assert 'secret-key-12345' not in r.get_data(as_text=True)
    assert data['api_key_hint'] == '…2345'

    r = client.put('/api/llm/config', json={'provider': 'bogus'})
    assert r.status_code == 400

def test_llm_chat_requires_messages(client):
    r = client.post('/api/llm/chat', json={})
    assert r.status_code == 400

def test_openai_style_wire_format(client):
    client.put('/api/llm/config', json={
        'provider': 'openai-compatible',
        'base_url': 'http://fake-server/v1',
        'model': 'test-model',
    })
    captured = {}
    class FakeResp:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': 'hello back'}}]}
    def fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url; captured['body'] = json
        return FakeResp()
    with patch('backend.services.llm.requests.post', side_effect=fake_post):
        r = client.post('/api/llm/chat', json={
            'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': 'hi'},
                {'type': 'image', 'media_type': 'image/png', 'data': 'AAAA'},
            ]}],
            'system': 'be brief',
        })
    assert r.status_code == 200
    assert r.get_json()['text'] == 'hello back'
    assert captured['url'] == 'http://fake-server/v1/chat/completions'
    msgs = captured['body']['messages']
    assert msgs[0] == {'role': 'system', 'content': 'be brief'}
    parts = msgs[1]['content']
    assert parts[1]['image_url']['url'].startswith('data:image/png;base64,')

def test_anthropic_requires_key(client):
    client.put('/api/llm/config', json={'provider': 'anthropic', 'api_key': ''})
    r = client.post('/api/llm/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]})
    assert r.status_code == 502
    assert 'API key' in r.get_json()['error']




def make_epub():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml', '''<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
 <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')
        z.writestr('OEBPS/content.opf', '''<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
 <manifest>
  <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
  <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
 </manifest>
 <spine><itemref idref="ch1"/><itemref idref="ch2"/></spine>
</package>''')
        z.writestr('OEBPS/ch1.xhtml', '<html><body><h1>The Fool</h1><p>New beginnings &amp; leaps of faith.</p></body></html>')
        z.writestr('OEBPS/ch2.xhtml', '<html><body><h1>The Magician</h1><p>Will and skill.</p></body></html>')
    return buf.getvalue()

def test_epub_extraction(client):
    r = client.post('/api/scribe/extract-text',
                    data={'file': (io.BytesIO(make_epub()), 'book.epub')},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    # Spine order respected: Fool chapter before Magician
    assert data['text'].index('The Fool') < data['text'].index('The Magician')
    assert 'New beginnings & leaps' in data['text']
    assert data['warning'] is None

def test_txt_and_unsupported(client):
    r = client.post('/api/scribe/extract-text',
                    data={'file': (io.BytesIO('hello world'.encode()), 'notes.txt')},
                    content_type='multipart/form-data')
    assert r.status_code == 200 and r.get_json()['text'] == 'hello world'
    r = client.post('/api/scribe/extract-text',
                    data={'file': (io.BytesIO(b'x'), 'thing.docx')},
                    content_type='multipart/form-data')
    assert r.status_code == 422

def test_apply_writes(client, db):
    # archetype target: need an archetype + source field
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    src = client.post('/api/reference/sources',
                      json={'name': 'Test Book', 'cartomancy_types': [tname]}).get_json()
    field = client.post(f"/api/reference/sources/{src['id']}/fields",
                        json={'name': 'Meaning', 'cartomancy_type': tname}).get_json()
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    arch_id = archetypes[0]['id']

    # card target: create deck + card
    deck = client.post('/api/decks', json={'name': 'Scribe Deck', 'type_ids': [types[0]['id']]}).get_json()
    card = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'Test Card'}).get_json()

    r = client.post('/api/scribe/apply', json={'writes': [
        {'target': 'archetype', 'archetype_id': arch_id, 'field_id': field['id'], 'content': 'A meaning.'},
        {'target': 'card', 'card_id': card['id'], 'field_name': 'Keywords', 'content': 'alpha, beta'},
        {'target': 'card', 'card_id': card['id'], 'field_name': 'keywords', 'content': 'gamma'},  # upsert same field
        {'target': 'bogus'},
    ]})
    assert r.status_code == 200
    data = r.get_json()
    assert data['applied'] == 3
    assert len(data['errors']) == 1 and data['errors'][0]['index'] == 3

    fields = client.get(f"/api/cards/{card['id']}").get_json()['card_custom_fields']
    kw = [f for f in fields if f['field_name'].lower() == 'keywords']
    assert len(kw) == 1 and kw[0]['field_value'] == 'gamma'

    # A new imported field name creates a deck-level definition too,
    # so it shows in the deck editor and on every card of the deck.
    deck_fields = client.get(f"/api/decks/{deck['id']}/custom-fields").get_json()
    assert any(f['field_name'].lower() == 'keywords' for f in deck_fields)
    assert sum(1 for f in deck_fields if f['field_name'].lower() == 'keywords') == 1

    entries = client.get(f"/api/archetypes/{arch_id}/source-entries").get_json()
    assert any(e.get('content') == 'A meaning.' for e in entries)


def test_anthropic_prompt_caching_shape(client):
    """The Anthropic call caches the system prompt and marks the end of
    the conversation, so refinement turns re-read the book at ~10% price."""
    client.put('/api/llm/config', json={
        'provider': 'anthropic', 'api_key': 'sk-ant-test', 'model': 'claude-opus-5',
    })

    captured = {}

    class FakeStream:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def get_final_message(self):
            class Block:
                type = 'text'
                text = 'extracted!'
            class Msg:
                stop_reason = 'end_turn'
                content = [Block()]
            return Msg()

    class FakeMessages:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return FakeStream()

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    with patch('anthropic.Anthropic', FakeClient):
        r = client.post('/api/llm/chat', json={
            'system': 'You are the Scribe.',
            'messages': [
                {'role': 'user', 'content': [{'type': 'text', 'text': 'book text here'}]},
                {'role': 'assistant', 'content': 'proposals...'},
                {'role': 'user', 'content': 'fix the Queen of Cups'},
            ],
        })

    assert r.status_code == 200 and r.get_json()['text'] == 'extracted!'
    # System prompt carries a cache marker
    assert captured['system'][0]['cache_control'] == {'type': 'ephemeral'}
    msgs = captured['messages']
    # Only the LAST message is marked; earlier ones stay unmarked so the
    # cached prefix bytes are identical across turns
    assert 'cache_control' not in msgs[0]['content'][-1]
    assert isinstance(msgs[1]['content'], str)
    # Final message: string content converted to block form + marked
    assert msgs[2]['content'][-1]['cache_control'] == {'type': 'ephemeral'}
    assert msgs[2]['content'][-1]['text'] == 'fix the Queen of Cups'

    # One-shot requests (cache: false) skip the conversation marker —
    # only the reusable system prompt stays cached.
    with patch('anthropic.Anthropic', FakeClient):
        client.post('/api/llm/chat', json={
            'system': 'You are the Scribe.',
            'cache': False,
            'messages': [{'role': 'user', 'content': 'one-shot part text'}],
        })
    assert captured['system'][0]['cache_control'] == {'type': 'ephemeral'}
    last = captured['messages'][-1]['content']
    if isinstance(last, list):
        assert 'cache_control' not in last[-1]
    else:
        assert isinstance(last, str)


def test_bulk_llm_export(client):
    """Bulk export bundles entries chronologically with app-computed stats."""
    types = client.get('/api/types').get_json()
    deck = client.post('/api/decks', json={'name': 'Bulk Deck', 'type_ids': [types[0]['id']]}).get_json()

    def make_entry(title, when, cards):
        e = client.post('/api/entries', json={'title': title, 'reading_datetime': when}).get_json()
        client.put(f"/api/entries/{e['id']}/readings", json={'readings': [{
            'deck_id': deck['id'], 'deck_name': 'Bulk Deck',
            'cards_used': [
                {'name': n, 'reversed': rev, 'deck_id': deck['id'], 'position_index': i}
                for i, (n, rev) in enumerate(cards)
            ],
        }]})
        return e['id']

    id_newer = make_entry('Second', '2026-07-20 10:00', [('The Fool', False), ('Death', True)])
    id_older = make_entry('First', '2026-07-01 09:00', [('The Fool', False)])

    r = client.post('/api/entries/llm-export', json={'ids': [id_newer, id_older]})
    assert r.status_code == 200
    data = r.get_json()
    assert data['entry_count'] == 2
    md = data['markdown']
    # Chronological: "First" appears before "Second"
    assert md.index('First') < md.index('Second')
    # Stats present and correct
    assert 'The Fool ×2' in md
    assert 'Cards drawn: 3 (1 reversed)' in md
    assert '2026-07-01 to 2026-07-20' in md
    assert data['char_count'] == len(md)

    assert client.post('/api/entries/llm-export', json={}).status_code == 400
    assert client.post('/api/entries/llm-export', json={'ids': [99999]}).status_code == 404


def test_feature_model_overrides(client):
    """Per-feature model overrides fall back to the default model."""
    r = client.put('/api/llm/config', json={
        'provider': 'anthropic', 'api_key': 'sk-ant-test',
        'model': 'claude-sonnet-5',
        'feature_models': {'mirror': 'claude-haiku-4-5', 'scribe': ''},
    })
    assert r.status_code == 200
    cfg = client.get('/api/llm/config').get_json()
    assert cfg['feature_models']['mirror'] == 'claude-haiku-4-5'
    assert cfg['feature_models']['scribe'] == ''
    assert cfg['model'] == 'claude-sonnet-5'

    captured = {}

    class FakeStream:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def get_final_message(self):
            class Block:
                type = 'text'
                text = 'ok'
            class Msg:
                stop_reason = 'end_turn'
                content = [Block()]
            return Msg()

    class FakeMessages:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return FakeStream()

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    msgs = [{'role': 'user', 'content': 'hi'}]
    with patch('anthropic.Anthropic', FakeClient):
        # mirror → its override
        client.post('/api/llm/chat', json={'messages': msgs, 'feature': 'mirror'})
        assert captured['model'] == 'claude-haiku-4-5'
        # scribe (blank override) → default
        client.post('/api/llm/chat', json={'messages': msgs, 'feature': 'scribe'})
        assert captured['model'] == 'claude-sonnet-5'
        # no feature → default
        client.post('/api/llm/chat', json={'messages': msgs})
        assert captured['model'] == 'claude-sonnet-5'
        # unknown feature name → default, no crash
        client.post('/api/llm/chat', json={'messages': msgs, 'feature': 'bogus'})
        assert captured['model'] == 'claude-sonnet-5'


def test_batch_rename_cards(client):
    """Deck-scoped batch rename: applies valid rows, rejects foreign cards."""
    types = client.get('/api/types').get_json()
    deck = client.post('/api/decks', json={'name': 'Rename Deck', 'type_ids': [types[0]['id']]}).get_json()
    other = client.post('/api/decks', json={'name': 'Other Deck', 'type_ids': [types[0]['id']]}).get_json()
    c1 = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'The Fool'}).get_json()
    c2 = client.post('/api/cards', json={'deck_id': other['id'], 'name': 'Foreign'}).get_json()

    r = client.post(f"/api/decks/{deck['id']}/rename-cards", json={'renames': [
        {'card_id': c1['id'], 'name': 'El Loco'},
        {'card_id': c2['id'], 'name': 'Nope'},      # wrong deck
        {'card_id': c1['id'], 'name': '  '},        # blank
    ]})
    assert r.status_code == 200
    data = r.get_json()
    assert data['applied'] == 1 and len(data['errors']) == 2

    card = client.get(f"/api/cards/{c1['id']}").get_json()
    assert card['name'] == 'El Loco'
    foreign = client.get(f"/api/cards/{c2['id']}").get_json()
    assert foreign['name'] == 'Foreign'


def test_insights_endpoint(client):
    """Aggregates: counts, cadence shape, reversal rate, suit rollup."""
    types = client.get('/api/types').get_json()
    tarot = next(t for t in types if t['name'] == 'Tarot')
    deck = client.post('/api/decks', json={'name': 'Ins Deck', 'type_ids': [tarot['id']]}).get_json()
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d 12:00')
    e = client.post('/api/entries', json={'title': 'I1', 'reading_datetime': now}).get_json()
    client.put(f"/api/entries/{e['id']}/readings", json={'readings': [{
        'deck_id': deck['id'],
        'cards_used': [
            {'name': 'Ace of Wands', 'reversed': True, 'position_index': 0},
            {'name': 'The Fool', 'reversed': False, 'position_index': 1},
        ],
    }]})
    r = client.get('/api/stats/insights')
    assert r.status_code == 200
    d = r.get_json()
    assert d['entries'] == 1
    assert d['cards_drawn'] == 2 and d['reversed_count'] == 1
    assert d['reversal_rate'] == 50.0
    assert len(d['cadence']) == 14 and d['cadence'][-1]['current'] is True
    assert d['cadence'][-1]['count'] == 1
    assert d['entries_this_month'] == 1
    names = {c['name'] for c in d['top_cards']}
    assert {'Ace of Wands', 'The Fool'} <= names
    assert any(s['suit'] == 'Wands' for s in d['suits'])
    # days filter excludes nothing here; a tiny window excludes all
    d2 = client.get('/api/stats/insights?days=100000').get_json()
    assert d2['entries'] == 1


def test_spread_archiving(client):
    """Archived spreads keep existing (old entries stay intact) but
    carry the flag so pickers can hide them."""
    sp = client.post('/api/spreads', json={
        'name': 'Old Faithful', 'positions': [{'x': 0, 'y': 0, 'label': 'One'}],
    }).get_json()
    r = client.put(f"/api/spreads/{sp['id']}", json={'archived': True})
    assert r.status_code == 200
    got = client.get(f"/api/spreads/{sp['id']}").get_json()
    assert got['archived'] == 1
    # Unarchive round-trip
    client.put(f"/api/spreads/{sp['id']}", json={'archived': False})
    assert client.get(f"/api/spreads/{sp['id']}").get_json()['archived'] == 0
    # Favorite round-trip, independent of archiving
    client.put(f"/api/spreads/{sp['id']}", json={'favorite': True})
    got = client.get(f"/api/spreads/{sp['id']}").get_json()
    assert got['favorite'] == 1 and got['archived'] == 0
    client.put(f"/api/spreads/{sp['id']}", json={'favorite': False})
    assert client.get(f"/api/spreads/{sp['id']}").get_json()['favorite'] == 0


def test_spread_tags(client):
    """Spread tags: CRUD + assignment + tags attached to the list."""
    tag = client.post('/api/spread-tags', json={'name': 'daily', 'color': '#123456'}).get_json()
    sp = client.post('/api/spreads', json={
        'name': 'Tagged Spread', 'positions': [{'x': 0, 'y': 0, 'label': 'One'}],
    }).get_json()
    r = client.put(f"/api/spreads/{sp['id']}/tags", json={'tag_ids': [tag['id']]})
    assert r.status_code == 200
    listed = client.get('/api/spreads').get_json()
    mine = next(s for s in listed if s['id'] == sp['id'])
    assert [t['name'] for t in mine['tags']] == ['daily']


def test_deck_image_health(client, tmp_path):
    """Image health reports files present vs missing, with the lost folder."""
    deck = client.post('/api/decks', json={'name': 'Health Deck', 'type_ids': [1]}).get_json()
    real = tmp_path / 'real.jpg'
    real.write_bytes(b'x')
    for name, path in [('Here', str(real)), ('Gone', str(tmp_path / 'lost' / 'gone.jpg'))]:
        client.post('/api/cards', json={
            'deck_id': deck['id'], 'name': name, 'image_path': path,
        })
    health = client.get(f"/api/decks/{deck['id']}/image-health").get_json()
    assert health['total'] == 2
    assert health['with_images'] == 2
    assert health['missing_count'] == 1
    assert health['missing_dir'] == str(tmp_path / 'lost')


def test_deck_field_coverage(client):
    """Field coverage counts cards with non-empty content per field."""
    deck = client.post('/api/decks', json={'name': 'Coverage Deck', 'type_ids': [1]}).get_json()
    card_ids = []
    for name in ['One', 'Two', 'Three']:
        r = client.post('/api/cards', json={'deck_id': deck['id'], 'name': name})
        card_ids.append(r.get_json()['id'])
    # Keywords on two cards; Book Meaning on one; empty content ignored
    client.post('/api/scribe/apply', json={'writes': [
        {'target': 'card', 'card_id': card_ids[0], 'field_name': 'Keywords', 'content': 'sun'},
        {'target': 'card', 'card_id': card_ids[1], 'field_name': 'keywords', 'content': 'moon'},
        {'target': 'card', 'card_id': card_ids[2], 'field_name': 'Keywords', 'content': '   '},
        {'target': 'card', 'card_id': card_ids[0], 'field_name': 'Book Meaning', 'content': 'text'},
    ]})
    cov = client.get(f"/api/decks/{deck['id']}/field-coverage").get_json()
    assert cov['card_count'] == 3
    filled = {k.lower(): v for k, v in cov['fields'].items()}
    assert filled['keywords'] == 2
    assert filled['book meaning'] == 1


def test_convert_image_heic(client, tmp_path):
    """HEIC uploads come back as downscaled base64 JPEG (via sips)."""
    import base64
    import io as _io
    import shutil
    import subprocess
    import pytest
    from PIL import Image
    if not shutil.which('sips'):
        pytest.skip('sips not available (macOS-only)')
    png = tmp_path / 'src.png'
    Image.new('RGB', (2400, 1200), (120, 40, 200)).save(png)
    heic = tmp_path / 'photo.heic'
    subprocess.run(['sips', '-s', 'format', 'heic', str(png), '--out', str(heic)],
                   check=True, capture_output=True)
    r = client.post('/api/scribe/convert-image',
                    data={'file': (open(heic, 'rb'), 'photo.heic')},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['media_type'] == 'image/jpeg'
    img = Image.open(_io.BytesIO(base64.b64decode(body['data'])))
    assert img.format == 'JPEG'
    assert max(img.size) == 2000  # downscaled from 2400

    r = client.post('/api/scribe/convert-image',
                    data={'file': (_io.BytesIO(b'not an image'), 'junk.heic')},
                    content_type='multipart/form-data')
    assert r.status_code == 422


def test_per_feature_providers_and_deepseek(client):
    """Each role can use its own provider; keys stay per-provider."""
    # Default: Anthropic with its key. Mirror: DeepSeek with its own.
    client.put('/api/llm/config', json={
        'provider': 'anthropic',
        'model': 'claude-opus-5',
        'api_keys': {'anthropic': 'sk-ant-aaaa1111', 'deepseek': 'sk-ds-bbbb2222'},
        'feature_providers': {'mirror': 'deepseek'},
        'feature_models': {'mirror': ''},
    })
    cfg = client.get('/api/llm/config').get_json()
    assert cfg['provider'] == 'anthropic'
    assert cfg['feature_providers']['mirror'] == 'deepseek'
    assert cfg['api_keys']['anthropic']['has_key'] is True
    assert cfg['api_keys']['anthropic']['hint'] == '…1111'
    assert cfg['api_keys']['deepseek']['hint'] == '…2222'
    assert cfg['api_keys']['openai']['has_key'] is False
    assert 'sk-ds-bbbb2222' not in str(cfg)

    # The mirror resolves to DeepSeek's default model + DeepSeek's key,
    # and the wire call goes to api.deepseek.com with that key.
    captured = {}
    class FakeResp:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': 'hi'}, 'finish_reason': 'stop'}]}
    def fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url
        captured['auth'] = headers.get('Authorization')
        captured['model'] = json['model']
        return FakeResp()
    with patch('backend.services.llm.requests.post', side_effect=fake_post):
        r = client.post('/api/llm/chat', json={
            'feature': 'mirror',
            'messages': [{'role': 'user', 'content': 'hello'}],
        })
    assert r.status_code == 200
    assert captured['url'] == 'https://api.deepseek.com/v1/chat/completions'
    assert captured['auth'] == 'Bearer sk-ds-bbbb2222'
    assert captured['model'] == 'deepseek-chat'

    # Image content is refused up front for DeepSeek (no vision).
    client.put('/api/llm/config', json={'feature_providers': {'scribe': 'deepseek'}})
    r = client.post('/api/llm/chat', json={
        'feature': 'scribe',
        'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'media_type': 'image/png', 'data': 'AAAA'},
        ]}],
    })
    assert r.status_code == 502
    assert "can't read images" in r.get_json()['error']



def test_backup_saves_server_side(client, tmp_path):
    """POST /api/backup writes the zip to disk and returns its path —
    no multi-GB blob ever travels to the frontend."""
    import os
    import zipfile as _zip
    r = client.post('/api/backup', json={'dest_dir': str(tmp_path)})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['path'].startswith(str(tmp_path))
    assert body['path'].endswith('.zip')
    assert os.path.getsize(body['path']) == body['bytes'] > 0
    names = _zip.ZipFile(body['path']).namelist()
    assert any(n.endswith('.db') or n.endswith('.json') for n in names)
    # Bookkeeping: the status endpoint now knows about this backup.
    status = client.get('/api/backup/status').get_json()
    assert status['last_backup_time'] is not None


def test_scanned_pdf_becomes_page_images(client, tmp_path):
    """A PDF with no text layer is rasterized to page images."""
    import base64
    import shutil
    import pytest
    from PIL import Image
    from backend.services.source_text import _find_pdftoppm
    if not _find_pdftoppm():
        pytest.skip('pdftoppm not installed')
    pdf = tmp_path / 'scan.pdf'
    page1 = Image.new('RGB', (850, 1100), (250, 248, 240))
    page2 = Image.new('RGB', (850, 1100), (240, 240, 250))
    page1.save(pdf, save_all=True, append_images=[page2])
    r = client.post('/api/scribe/extract-text',
                    data={'file': (open(pdf, 'rb'), 'scan.pdf')},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['text'] == ''
    assert len(body['images']) == 2
    assert body['images'][0]['media_type'] == 'image/jpeg'
    assert 'converted 2 pages' in body['warning']
    # Pages decode to real JPEGs
    import io as _io
    img = Image.open(_io.BytesIO(base64.b64decode(body['images'][0]['data'])))
    assert img.format == 'JPEG' and img.width > 500


def test_llm_export_include_reference(client):
    """include_reference=1 appends deck fields + archetype notes."""
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    deck = client.post('/api/decks', json={'name': 'Mirror Deck', 'type_ids': [types[0]['id']]}).get_json()
    card = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'The Fool'}).get_json()
    client.post('/api/scribe/apply', json={'writes': [
        {'target': 'card', 'card_id': card['id'], 'field_name': 'Keywords',
         'content': 'leaps of faith, yes-energy'},
    ]})
    src = client.post('/api/reference/sources',
                      json={'name': 'Mirror Book', 'cartomancy_types': [tname]}).get_json()
    field = client.post(f"/api/reference/sources/{src['id']}/fields",
                        json={'name': 'Meaning', 'cartomancy_type': tname}).get_json()
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    arch = next((a for a in archetypes if a['name'] == 'The Fool'), archetypes[0])
    client.post('/api/scribe/apply', json={'writes': [
        {'target': 'archetype', 'archetype_id': arch['id'], 'field_id': field['id'],
         'content': 'New beginnings and holy folly.'},
    ]})

    entry = client.post('/api/entries', json={'title': 'Mirror Test'}).get_json()
    client.put(f"/api/entries/{entry['id']}/readings", json={'readings': [{
        'deck_id': deck['id'], 'deck_name': 'Mirror Deck',
        'cartomancy_type': tname,
        'cards_used': [{'name': 'The Fool', 'card_id': card['id'], 'position_index': 0}],
    }]})

    plain = client.get(f"/api/entries/{entry['id']}/llm-export").get_json()['markdown']
    assert 'yes-energy' not in plain
    rich = client.get(f"/api/entries/{entry['id']}/llm-export?include_reference=1").get_json()['markdown']
    assert 'Reference material for the drawn cards' in rich
    assert 'Deck field "Keywords": leaps of faith, yes-energy' in rich
    assert 'Mirror Book' in rich and 'holy folly' in rich


def test_prompt_presets_crud(client):
    """Preset CRUD + active switching per assistant."""
    r = client.get('/api/prompts/mirror').get_json()
    assert r == {'presets': [], 'active_id': None}

    p1 = client.post('/api/prompts/mirror/presets',
                     json={'name': 'Gentler', 'content': 'Be very gentle.'}).get_json()
    client.post('/api/prompts/mirror/presets',
                json={'name': 'Blunt', 'content': 'Be blunt.'})
    r = client.get('/api/prompts/mirror').get_json()
    assert [p['name'] for p in r['presets']] == ['Blunt', 'Gentler']
    assert r['active_id'] is None

    # Activate, edit, verify
    assert client.put('/api/prompts/mirror/active',
                      json={'preset_id': p1['id']}).status_code == 200
    client.put(f"/api/prompts/presets/{p1['id']}", json={'content': 'Be gentle and slow.'})
    r = client.get('/api/prompts/mirror').get_json()
    assert r['active_id'] == p1['id']
    active = next(p for p in r['presets'] if p['id'] == p1['id'])
    assert active['content'] == 'Be gentle and slow.'

    # Presets are per-assistant; wrong-feature activation rejected
    assert client.get('/api/prompts/analyst').get_json()['presets'] == []
    assert client.put('/api/prompts/analyst/active',
                      json={'preset_id': p1['id']}).status_code == 404

    # Deleting the active preset falls back to the default
    client.delete(f"/api/prompts/presets/{p1['id']}")
    r = client.get('/api/prompts/mirror').get_json()
    assert r['active_id'] is None
    assert [p['name'] for p in r['presets']] == ['Blunt']

    assert client.get('/api/prompts/bogus').status_code == 404


def test_reversed_combinations(client):
    """Reversed flags key separate combinations; per-type toggle persists."""
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    a1, a2 = archetypes[0]['id'], archetypes[1]['id']

    # Toggle roundtrip
    assert client.get('/api/combinations/reversed-types').get_json() == {'types': []}
    client.put('/api/combinations/reversed-types', json={'types': [tname]})
    assert client.get('/api/combinations/reversed-types').get_json() == {'types': [tname]}

    # Upright pair and reversed-first pair are distinct combinations
    client.post('/api/combinations/meanings', json={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2,
        'meaning': 'Upright pairing.',
    })
    client.post('/api/combinations/meanings', json={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2,
        'card_1_reversed': True, 'meaning': 'First card reversed.',
    })
    upright = client.get('/api/combinations/meanings', query_string={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2,
    }).get_json()
    reversed_ = client.get('/api/combinations/meanings', query_string={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2, 'card_1_reversed': '1',
    }).get_json()
    assert [m['meaning'] for m in upright] == ['Upright pairing.']
    assert [m['meaning'] for m in reversed_] == ['First card reversed.']
    assert reversed_[0]['archetype_1_reversed'] == 1
    assert reversed_[0]['archetype_2_reversed'] == 0


def test_insights_rich_aggregates(client):
    """Deck/spread usage, co-occurring pairs, querent breakdown."""
    types = client.get('/api/types').get_json()
    deck = client.post('/api/decks', json={'name': 'Rich Deck', 'type_ids': [types[0]['id']]}).get_json()
    fool = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'The Fool'}).get_json()
    tower = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'The Tower'}).get_json()
    star = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'The Star'}).get_json()
    alice = client.post('/api/profiles', json={'name': 'Alice'}).get_json()

    def make_entry(cards, querent=None):
        e = client.post('/api/entries', json={'title': 'T'}).get_json()
        client.put(f"/api/entries/{e['id']}/readings", json={'readings': [{
            'deck_id': deck['id'], 'deck_name': 'Rich Deck',
            'spread_name': 'Pair Draw',
            'cards_used': [{'name': n, 'card_id': cid, 'position_index': i}
                           for i, (n, cid) in enumerate(cards)],
        }]})
        if querent:
            client.put(f"/api/entries/{e['id']}/querents", json={'profile_ids': [querent]})
        return e['id']

    make_entry([('The Fool', fool['id']), ('The Tower', tower['id'])], alice['id'])
    make_entry([('The Fool', fool['id']), ('The Tower', tower['id'])], alice['id'])
    make_entry([('The Fool', fool['id']), ('The Star', star['id'])])

    data = client.get('/api/stats/insights').get_json()
    decks = {d['name']: d for d in data['deck_usage']}
    assert decks['Rich Deck']['count'] == 3
    assert decks['Rich Deck']['last_used'] is not None
    spreads = {s['name']: s['count'] for s in data['spread_usage']}
    assert spreads['Pair Draw'] == 3
    pairs = {(p['a'], p['b']): p['count'] for p in data['co_occurrence']}
    assert pairs[('The Fool', 'The Tower')] == 2
    assert ('The Fool', 'The Star') not in pairs  # below MIN_PAIR_COUNT
    qb = {q['name']: q for q in data['querent_breakdown']}
    assert qb['Alice']['entries'] == 2
    assert 'The Fool' in qb['Alice']['top_cards']
    # Filtered to a querent, the breakdown hides itself
    filtered = client.get(f"/api/stats/insights?querent_id={alice['id']}").get_json()
    assert filtered['querent_breakdown'] == []


def test_insights_deck_filter_uses_card_level_decks(client):
    """Readings storing deck ids on cards (not the reading row) must
    still be found by the deck and type filters."""
    types = client.get('/api/types').get_json()
    t1 = types[0]
    deck = client.post('/api/decks', json={'name': 'CardLevel Deck', 'type_ids': [t1['id']]}).get_json()
    card = client.post('/api/cards', json={'deck_id': deck['id'], 'name': 'Ace of Filters'}).get_json()
    e = client.post('/api/entries', json={'title': 'Card-level deck entry'}).get_json()
    # NO reading-level deck_id — deck info only on the card.
    client.put(f"/api/entries/{e['id']}/readings", json={'readings': [{
        'spread_name': 'Filter Check',
        'cards_used': [{'name': 'Ace of Filters', 'card_id': card['id'],
                        'deck_id': deck['id'], 'position_index': 0}],
    }]})

    by_deck = client.get(f"/api/stats/insights?deck_id={deck['id']}").get_json()
    assert by_deck['entries'] >= 1
    assert any(c['name'] == 'Ace of Filters' for c in by_deck['top_cards'])

    by_type = client.get(f"/api/stats/insights?deck_type_id={t1['id']}").get_json()
    assert any(c['name'] == 'Ace of Filters' for c in by_type['top_cards'])


def test_three_card_combinations(client):
    """Two-card and three-card combos are distinct namespaces."""
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    a1, a2, a3 = (archetypes[i]['id'] for i in range(3))

    client.post('/api/combinations/meanings', json={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2,
        'meaning': 'Just the pair.',
    })
    client.post('/api/combinations/meanings', json={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2, 'card_3': a3,
        'meaning': 'The full triad.',
    })
    pair = client.get('/api/combinations/meanings', query_string={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2,
    }).get_json()
    triad = client.get('/api/combinations/meanings', query_string={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2, 'card_3': a3,
    }).get_json()
    assert [m['meaning'] for m in pair] == ['Just the pair.']
    assert [m['meaning'] for m in triad] == ['The full triad.']
    assert triad[0]['archetype_3_name'] == archetypes[2]['name']
    # Duplicate third card rejected
    bad = client.post('/api/combinations/meanings', json={
        'cartomancy_type': tname, 'card_1': a1, 'card_2': a2, 'card_3': a1,
        'meaning': 'Nope.',
    })
    assert bad.status_code == 400


def test_scribe_apply_combinations(client):
    """The combination write target: creates the pair + meaning with
    source attribution, dedupes exact re-imports, supports triads and
    reversal flags, and reports bad rows as per-row errors."""
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    src = client.post('/api/reference/sources',
                      json={'name': 'Combo Book', 'cartomancy_types': [tname]}).get_json()
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    a1, a2, a3 = archetypes[0]['id'], archetypes[1]['id'], archetypes[2]['id']

    r = client.post('/api/scribe/apply', json={'writes': [
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'content': 'Swift luck arriving.',
         'source_id': src['id']},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2, a3], 'content': 'A three-card story.'},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'reversed': [True, False],
         'content': 'Luck delayed.'},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1], 'content': 'too few cards'},
    ]})
    data = r.get_json()
    assert data['applied'] == 3
    assert data['skipped'] == 0
    assert len(data['errors']) == 1

    # The pair meaning landed with its source
    meanings = client.get(
        f'/api/combinations/meanings?cartomancy_type={tname}'
        f'&card_1={a1}&card_2={a2}').get_json()
    assert len(meanings) == 1
    assert meanings[0]['meaning'] == 'Swift luck arriving.'
    assert meanings[0]['source_name'] == 'Combo Book'

    # The reversed variant is a distinct combination
    rev = client.get(
        f'/api/combinations/meanings?cartomancy_type={tname}'
        f'&card_1={a1}&card_2={a2}&card_1_reversed=1').get_json()
    assert len(rev) == 1 and rev[0]['meaning'] == 'Luck delayed.'

    # Re-importing the identical meaning is skipped, not duplicated
    r = client.post('/api/scribe/apply', json={'writes': [
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'content': 'Swift luck arriving.',
         'source_id': src['id']},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'content': 'A different meaning.'},
    ]})
    data = r.get_json()
    assert data['applied'] == 1
    assert data['skipped'] == 1
    meanings = client.get(
        f'/api/combinations/meanings?cartomancy_type={tname}'
        f'&card_1={a1}&card_2={a2}').get_json()
    assert len(meanings) == 2


def test_combination_partners_hints(client):
    """The partners endpoint powering the picker dropdown hints:
    pair partners, triad second-slot partners, triad third-slot
    partners, with exact flags on chosen cards and any-variant
    matching on the partner."""
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    a1, a2, a3, a4 = [a['id'] for a in archetypes[:4]]

    client.post('/api/scribe/apply', json={'writes': [
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'content': 'Pair meaning one.'},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'content': 'Pair meaning two.'},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a3], 'reversed': [False, True],
         'content': 'Partner reversed still counts.'},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2, a4], 'content': 'A triad tale.'},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a2, a3], 'content': 'Different first card.'},
    ]})

    # Pair partners of a1: a2 (2 meanings) + a3 (reversed variant counts)
    res = client.get(f'/api/combinations/partners?cartomancy_type={tname}&card_1={a1}')
    partners = res.get_json()['partners']
    assert partners == {str(a2): 2, str(a3): 1}

    # Reversed first card has no combos
    res = client.get(f'/api/combinations/partners?cartomancy_type={tname}'
                     f'&card_1={a1}&card_1_reversed=1')
    assert res.get_json()['partners'] == {}

    # Triad second-slot partners of a1
    res = client.get(f'/api/combinations/partners?cartomancy_type={tname}'
                     f'&card_1={a1}&triad=1')
    assert res.get_json()['partners'] == {str(a2): 1}

    # Triad third-slot partners of (a1, a2)
    res = client.get(f'/api/combinations/partners?cartomancy_type={tname}'
                     f'&card_1={a1}&triad=1&card_2={a2}')
    assert res.get_json()['partners'] == {str(a4): 1}


def test_combinations_by_source(client):
    """Browse-by-source: meanings filtered by source (or unattributed),
    with combination info for the click-through."""
    types = client.get('/api/types').get_json()
    tname = types[0]['name']
    src = client.post('/api/reference/sources',
                      json={'name': 'Browse Book', 'cartomancy_types': [tname]}).get_json()
    archetypes = client.get(f'/api/archetypes?cartomancy_type={tname}').get_json()
    a1, a2, a3 = archetypes[0]['id'], archetypes[1]['id'], archetypes[2]['id']

    client.post('/api/scribe/apply', json={'writes': [
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2], 'content': 'From the book.',
         'source_id': src['id']},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a1, a2, a3], 'content': 'Triad from the book.',
         'source_id': src['id']},
        {'target': 'combination', 'cartomancy_type': tname,
         'archetype_ids': [a2, a3], 'content': 'Unattributed note.'},
    ]})

    rows = client.get(
        f"/api/combinations/by-source?cartomancy_type={tname}&source_id={src['id']}"
    ).get_json()
    assert len(rows) == 2
    assert {r['meaning'] for r in rows} == {'From the book.', 'Triad from the book.'}
    triad_row = next(r for r in rows if r['archetype_3_id'])
    assert triad_row['archetype_3_name'] == archetypes[2]['name']

    rows = client.get(
        f'/api/combinations/by-source?cartomancy_type={tname}&source_id=none'
    ).get_json()
    assert len(rows) == 1
    assert rows[0]['meaning'] == 'Unattributed note.'

    assert client.get('/api/combinations/by-source').status_code == 400


def test_apply_entity_note_merge_semantics(client):
    """Scribe entity-note writes: set when empty, append when the note
    holds other text, skip when it already contains the content."""
    src = client.post('/api/reference/sources', json={
        'name': 'ZZ Entity Import', 'cartomancy_types': ['Tarot'],
    }).get_json()['id']

    def write(content):
        return client.post('/api/scribe/apply', json={'writes': [
            {'target': 'entity_note', 'kind': 'suit', 'key': 'Tarot::Wands',
             'source_id': src, 'content': content}]}).get_json()

    r = write('<p>Fire and will.</p>')
    assert (r['applied'], r['skipped']) == (1, 0)
    # Identical content again (even re-wrapped) is skipped
    r = write('<p>Fire and  will.</p>')
    assert (r['applied'], r['skipped']) == (0, 1)
    # New content appends rather than clobbering
    r = write('<p>The suit of growth.</p>')
    assert (r['applied'], r['skipped']) == (1, 0)
    notes = client.get(
        '/api/reference/entity-notes?kind=suit&key=Tarot::Wands'
    ).get_json()['notes']
    assert len(notes) == 1
    assert 'Fire and will' in notes[0]['content']
    assert 'suit of growth' in notes[0]['content']

    # Bad rows error without stopping the batch
    r = client.post('/api/scribe/apply', json={'writes': [
        {'target': 'entity_note', 'kind': 'geese', 'key': 'X',
         'source_id': src, 'content': 'x'},
        {'target': 'entity_note', 'kind': 'rank', 'key': 'Tarot::Queen',
         'source_id': src, 'content': '<p>ok</p>'}]}).get_json()
    assert r['applied'] == 1
    assert len(r['errors']) == 1


def test_other_reversal_count_hint(client):
    """The viewer's "n more meanings with reversals" hint counts the
    same pair's meanings under other reversal states."""
    a1 = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Hint A'}).get_json()['id']
    a2 = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Hint B'}).get_json()['id']
    client.post('/api/scribe/apply', json={'writes': [
        {'target': 'combination', 'cartomancy_type': 'Tarot',
         'archetype_ids': [a1, a2], 'reversed': [True, False],
         'content': 'Reversed meaning one.'},
        {'target': 'combination', 'cartomancy_type': 'Tarot',
         'archetype_ids': [a1, a2], 'reversed': [True, True],
         'content': 'Both reversed.'},
        {'target': 'combination', 'cartomancy_type': 'Tarot',
         'archetype_ids': [a1, a2], 'content': 'Upright meaning.'}]})

    def count(qs=''):
        return client.get(
            f'/api/combinations/meanings/other-reversals?cartomancy_type=Tarot'
            f'&card_1={a1}&card_2={a2}{qs}').get_json()['count']

    assert count() == 2                            # viewing upright
    assert count('&card_1_reversed=1') == 2        # viewing rev+upright
    assert count('&card_1_reversed=1&card_2_reversed=1') == 2


def test_reading_querents(client):
    """Each reading can be 'for' one of the entry's querents; the link
    clears when that person leaves the entry or the profile is deleted."""
    anna = client.post('/api/profiles', json={'name': 'Anna'}).get_json()['id']
    ben = client.post('/api/profiles', json={'name': 'Ben'}).get_json()['id']
    eid = client.post('/api/entries', json={'title': 'Two people'}).get_json()['id']
    client.put(f'/api/entries/{eid}/querents', json={'profile_ids': [anna, ben]})
    client.put(f'/api/entries/{eid}/readings', json={'readings': [
        {'spread_name': 'One', 'querent_id': anna},
        {'spread_name': 'Two', 'querent_id': ben},
    ]})
    got = client.get(f'/api/entries/{eid}').get_json()['readings']
    assert [r['querent_id'] for r in got] == [anna, ben]

    client.put(f'/api/entries/{eid}/querents', json={'profile_ids': [anna]})
    got = client.get(f'/api/entries/{eid}').get_json()['readings']
    assert [r['querent_id'] for r in got] == [anna, None]

    client.delete(f'/api/profiles/{anna}')
    got = client.get(f'/api/entries/{eid}').get_json()['readings']
    assert [r['querent_id'] for r in got] == [None, None]
