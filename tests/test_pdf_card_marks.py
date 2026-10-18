"""Birth/name card marks in the journal-entry PDF."""
from io import BytesIO

import pytest
from pypdf import PdfReader

from conftest import make_deck_with_card


def _pdf_text(client, entry_id, body):
    res = client.post(f'/api/entries/{entry_id}/export-pdf', json=body)
    assert res.status_code == 200, res.get_data(as_text=True)[:300]
    return ''.join(p.extract_text() for p in PdfReader(BytesIO(res.data)).pages)


def _weasyprint_available():
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _weasyprint_available(),
                    reason='weasyprint needs DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib')
def test_marked_tarot_card_shows_its_role(client, db):
    deck_id, card_id = make_deck_with_card(db)
    eid = client.post('/api/entries', json={'title': 'Marks'}).get_json()['id']
    client.put(f'/api/entries/{eid}/readings', json={'readings': [{
        'deck_id': deck_id, 'cartomancy_type': 'Tarot',
        'cards_used': [{'name': 'The Fool', 'card_id': card_id, 'position_index': 0}],
    }]})

    marks = {'the fool': {'label': 'Anna: Soul', 'colors': ['#c0392b', 'red;}x{']}}
    assert 'Anna: Soul' in _pdf_text(client, eid, {'card_marks': marks})
    assert 'Anna: Soul' not in _pdf_text(client, eid, {})
