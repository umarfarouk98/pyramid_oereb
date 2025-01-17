# -*- coding: utf-8 -*-
import pytest

from pyramid_oereb.core.sources import Base
from pyramid_oereb.core.readers.disclaimer import DisclaimerReader
from pyramid_oereb.core.records.disclaimer import DisclaimerRecord


@pytest.fixture
def disclaimer_data(dbsession, transact):
    from pyramid_oereb.contrib.data_sources.standard.models.main import Disclaimer
    del transact
    disclaimers = [
        Disclaimer(**{
            'id': 1,
            'title': {
                'de': u'Haftungsausschluss Kataster der belasteten Standorte',
                'fr': u'Clause de non-responsabilité du cadastre des sites pollués (CSP)',
                'it': u'Clausola di esclusione della responsabilità ...',
                'rm': u''
            },
            'content': {
                'de': u'Der Kataster der belasteten Standorte (KbS) \
                      wurde anhand der vom Bundesamt für Umwelt BAFU fe ...',
                'fr': u'Le cadastre des sites pollués (CSP) est établi d’après \
                      les critères émis par l’Office fédéral ...',
                'it': u'Il catasto dei siti inquinati (CSIN) è stato elaborato sulla \
                      base dei criteri definiti dall ...',
                'rm': u'',
            }
        })
    ]
    dbsession.add_all(disclaimers)
    dbsession.flush()
    yield disclaimers


@pytest.mark.run(order=2)
def test_init(pyramid_oereb_test_config):
    reader = DisclaimerReader(
        pyramid_oereb_test_config.get_disclaimer_config().get('source').get('class'),
        **pyramid_oereb_test_config.get_disclaimer_config().get('source').get('params')
    )
    assert isinstance(reader._source_, Base)


@pytest.mark.run(order=2)
def test_read(pyramid_oereb_test_config, disclaimer_data):
    reader = DisclaimerReader(
        pyramid_oereb_test_config.get_disclaimer_config().get('source').get('class'),
        **pyramid_oereb_test_config.get_disclaimer_config().get('source').get('params')
    )
    results = reader.read()
    assert isinstance(results, list)
    assert len(results) == len(disclaimer_data)
    assert isinstance(results[0], DisclaimerRecord)
    assert len(results[0].title) == len(disclaimer_data[0].title)
    assert len(results[0].content) == len(disclaimer_data[0].content)
    assert 'du cadastre des sites' in results[0].title['fr']
    assert 'Kataster der belasteten Standorte' in results[0].content['de']
