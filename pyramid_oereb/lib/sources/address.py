# -*- coding: utf-8 -*-
from geoalchemy2.elements import _SpatialElement
from geoalchemy2.shape import to_shape
from pyramid.config import ConfigurationError
from pyramid.path import DottedNameResolver

from pyramid_oereb.lib.sources import BaseDatabaseSource
from pyramid_oereb.lib.records.address import AddressRecord


class AddressDatabaseSource(BaseDatabaseSource):

    def __init__(self, **kwargs):
        """
        The plug for real estates which uses a database as source.
        :param kwargs: Arbitrary keyword arguments. It must contain the keys 'db_connection' and 'model'
        """
        if kwargs.get('db_connection'):
            key = kwargs.get('db_connection')
        else:
            raise ConfigurationError('"db_connection" for source has to be defined in used yaml '
                                     'configuration file')
        if kwargs.get('model'):
            model = DottedNameResolver().resolve(kwargs.get('model'))
        else:
            raise ConfigurationError('"model" for source has to be defined in used yaml configuration file')

        super(AddressDatabaseSource, self).__init__(key, model)

    def read(self, **kwargs):
        """
        Central method to read all plrs.
        :param kwargs: Arbitrary keyword arguments. It must contain the keys 'street_name', 'zip_code' and
        'street_number'.
        """
        session = self._adapter_.get_session(self._key_)
        query = session.query(self._model_)
        if kwargs.get('street_name') and kwargs.get('zip_code') and kwargs.get('street_number'):
            results = [query.filter(
                self._model_.street_name == kwargs.get('street_name')
            ).filter(
                self._model_.zip_code == kwargs.get('zip_code')
            ).filter(
                self._model_.street_number == kwargs.get('street_number')
            ).one()]
        else:
            raise AttributeError('Necessary parameter were missing.')

        self.records = list()
        for result in results:
            self.records.append(AddressRecord(
                result.street_name,
                result.zip_code,
                result.street_number,
                to_shape(result.geometry).wkt if isinstance(result.geometry, _SpatialElement) else None
            ))
