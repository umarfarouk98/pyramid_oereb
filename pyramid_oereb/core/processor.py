# -*- coding: utf-8 -*-
import logging

from operator import attrgetter

from pyramid.path import DottedNameResolver

from pyramid_oereb.core.config import Config
from pyramid_oereb.core.records.plr import PlrRecord
from pyramid_oereb.core.readers.extract import ExtractReader
from pyramid_oereb.core.readers.real_estate import RealEstateReader


log = logging.getLogger(__name__)


class Processor(object):

    def __init__(self, real_estate_reader, plr_sources, extract_reader):
        """
        The Processor class is directly bound to the get_extract_by_id service in this application. It's task
        is to unsnarl the difficult model of the oereb extract and handle all objects inside this extract
        correctly. In addition it provides an easy to use method interface to access the information.
        It is also used to wrap all accessors in one point to have a processing interface.

        Args:
            real_estate_reader (pyramid_oereb.lib.readers.real_estate.RealEstateReader): The
                real estate reader instance for runtime use.
            plr_sources (list of pyramid_oereb.standard.sources.plr.DatabaseSource): The
                public law restriction source instances for runtime use wrapped in a list.
            extract_reader (pyramid_oereb.lib.readers.extract.ExtractReader): The extract reader
                instance for runtime use.
        """
        self._real_estate_reader_ = real_estate_reader
        self._plr_sources_ = plr_sources
        self._extract_reader_ = extract_reader

    def filter_published_documents(self, record):
        """
        Filter only published documents.

        Args:
            record (pyramid_oereb.core.records.plr.PlrRecord or
                pyramid_oereb.core.records.documents.DocumentRecord): The public law restriction or
                document record.
        """
        published_docs = list()
        if isinstance(record, PlrRecord):
            for doc in record.documents:
                if doc.published:
                    published_docs.append(doc)
                else:
                    log.debug("filtering out non-published document {}".format(doc))
            record.documents = published_docs
        return record

    def filter_documents_by_fosnr(self, record, fosnr):
        """
        Filter documents that are only relevant for one municipality.

        Args:
            record (pyramid_oereb.core.records.plr.PlrRecord or
                pyramid_oereb.core.records.documents.DocumentRecord): The public law restriction or
                document record.
            fosnr (int): The fosnr (= id bfs) of the municipality.
        """
        relevant_docs = list()
        if isinstance(record, PlrRecord):
            for doc in record.documents:
                if doc.only_in_municipality in [None, fosnr]:
                    relevant_docs.append(doc)
                else:
                    log.debug("filtering out document (not relevant for this municipality) {}".format(doc))
            record.documents = relevant_docs
        return record

    def plr_tolerance_check(self, extract):
        """
        The function checks if the found plr results exceed the minimal surface or length
        value defined in the configuration and therefore should be represented in the extract
        or if they should be considered as 'false trues' and be removed from the results.
        In addition, this function filters these documents out that are not published or that are not
        relevant for the municipality the real estate is located in.

        Args:
            extract (pyramid_oereb.lib.records.extract.ExtractRecord): The extract in it's
                unvalidated form

        Returns:
            pyramid_oereb.lib.records.extract.ExtractRecord: Returns the updated extract
        """

        real_estate = extract.real_estate
        inside_plrs = []
        outside_plrs = []

        for public_law_restriction in real_estate.public_law_restrictions:
            if isinstance(public_law_restriction, PlrRecord) and public_law_restriction.published:
                # Test if the geometries list is now empty - if so remove plr from plr list
                if public_law_restriction.calculate(real_estate, Config.get('geometry_types')):
                    log.debug("plr_tolerance_check: keeping as potentially concerned plr {}".
                              format(public_law_restriction))
                    public_law_restriction = self.filter_documents_by_fosnr(public_law_restriction,
                                                                            real_estate.fosnr)
                    public_law_restriction = self.filter_published_documents(public_law_restriction)
                    inside_plrs.append(public_law_restriction)
                else:
                    log.debug("plr_tolerance_check: removing from the concerned plrs {}".
                              format(public_law_restriction))
                    outside_plrs.append(public_law_restriction)

        # Check if theme is concerned
        def is_inside_plr(theme_code):
            for plr in inside_plrs:
                if plr.theme.code == theme_code:
                    return True
            return False

        # Ensure only ConcernedThemes are contained in PLRs
        themes_to_move = []
        for i, theme in enumerate(extract.concerned_theme):
            if not is_inside_plr(theme.code):
                themes_to_move.append(i)

        if len(themes_to_move) > 0:
            themes_to_move.reverse()
            for idx in themes_to_move:
                new_not_concerned_theme = extract.concerned_theme.pop(idx)
                log.debug("plr_tolerance_check() moving from concerned_theme to not_concerned_theme: {}"
                          .format(new_not_concerned_theme)
                          )
                extract.not_concerned_theme.append(new_not_concerned_theme)
            # Need to reorder, because order must stay exactly as defined in configuration
            extract.not_concerned_theme = sorted(extract.not_concerned_theme, key=attrgetter('extract_index'))

        real_estate.public_law_restrictions = self.get_legend_entries(inside_plrs, outside_plrs)
        return extract

    @staticmethod
    def view_service_handling(real_estate, images, extract_format, language):
        """
        Handles all view service related stuff. In the moment this is:
            * construction of the correct url (reference_wms, multilingual) depending on the real estate
            * downloading of the image (if parameter was set) for the requested or default language

        Args:
            real_estate (pyramid_oereb.lib.records.real_estate.RealEstateRecord):
                The real estate record to be updated.
            images (bool): Switch whether the images should be downloaded or not.
            extract_format (string): The format currently used. For 'pdf' format,
                the used map size will be adapted to the pdf format.
            language (string or None): Which language of the reference WMS should be used

        Returns:
            pyramid_oereb.lib.records.real_estate.RealEstateRecord: The updated extract.
        """
        language = language or Config.get('default_language')
        map_size = Config.get_map_size(extract_format)
        bbox = Config.get_bbox(real_estate.limit)
        real_estate.plan_for_land_register.get_full_wms_url(
            language,
            map_size[0],
            map_size[1],
            bbox
        )
        real_estate.plan_for_land_register_main_page.get_full_wms_url(
            language,
            map_size[0],
            map_size[1],
            bbox
        )
        if images:
            real_estate.plan_for_land_register.download_wms_content(language)
            real_estate.plan_for_land_register_main_page.download_wms_content(language)

        for public_law_restriction in real_estate.public_law_restrictions:
            public_law_restriction.view_service.get_full_wms_url(language, map_size[0], map_size[1], bbox)
            if images:
                public_law_restriction.view_service.download_wms_content(language)
        return real_estate

    @staticmethod
    def get_legend_entries(inside_plrs, outside_plrs):
        """
        We need to apply the right legend entries to each plr record which is intersecting the real estate.
        The result will be the "other legend".
        Since we already have a list of legend entries which are in the view bbox from calculated in the
        plr source, its only necessary to omit the legend entries which are on the real estate from the list
        of "other legend".

        Args:
            inside_plrs (list of pyramid_oereb.lib.records.plr.PlrRecord): The PLR's which are intersecting
                the real estate
            outside_plrs (list of pyramid_oereb.lib.records.plr.PlrRecord): The PLR's which are in the BBOX
                of the view but not intersecting the real estate
        Returns:
            list of pyramid_oereb.core.records.plr.PlrRecord: The updated records with the hopefully correct
                legend entries assigned.
        """
        # first we create a dict of theme codes which holds all the type_codes we will remove later from
        # the legend entries.
        type_codes_to_remove = {}
        for inside_plr in inside_plrs:
            view_service_id = str(inside_plr.view_service_id)
            theme_code = inside_plr.theme.code
            type_code = inside_plr.type_code
            if not type_codes_to_remove.get(theme_code):
                type_codes_to_remove[theme_code] = {}
            if not type_codes_to_remove[theme_code].get(view_service_id):
                type_codes_to_remove[theme_code][view_service_id] = {
                    'codes_to_rm': [],
                    'legend_entries': None
                }

            if type_code not in type_codes_to_remove[theme_code][view_service_id]['codes_to_rm']:
                type_codes_to_remove[theme_code][view_service_id]['codes_to_rm'].append(type_code)
            if not type_codes_to_remove[theme_code][view_service_id]['legend_entries']:
                type_codes_to_remove[theme_code][view_service_id]['legend_entries'] = inside_plr.\
                    view_service.legends

        for key in type_codes_to_remove.keys():
            for view_service_key in type_codes_to_remove[key]:
                for legend_entry in list(type_codes_to_remove[key][view_service_key]['legend_entries']):
                    if legend_entry.type_code in type_codes_to_remove[key][view_service_key]['codes_to_rm']:
                        type_codes_to_remove[key][view_service_key]['legend_entries'].remove(legend_entry)

        for inside_plr in inside_plrs:
            theme_code = inside_plr.theme.code
            view_service_id = str(inside_plr.view_service_id)
            inside_plr.view_service.legends = type_codes_to_remove[
                theme_code
            ][view_service_id]['legend_entries']

        return inside_plrs

    @property
    def real_estate_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.real_estate.RealEstateReader: The real estate reader
            instance.
        """
        return self._real_estate_reader_

    @property
    def plr_sources(self):
        """
        Returns:
            list of pyramid_oereb.core.sources.plr.DatabaseSource: The list of plr
            source instances.
        """
        return self._plr_sources_

    @property
    def extract_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.extract.ExtractReader: The extract reader instance.
        """
        return self._extract_reader_

    def process(self, real_estate, params, sld_url):
        """
        Central processing method to hook in from webservice.

        Args:
            real_estate (pyramid_oereb.lib.records.real_estate.RealEstateRecord): The real
                estate reader to obtain the real estates record.
            params (pyramid_oereb.views.webservice.Parameter): The parameters of the extract
                request.
            sld_url (str): The URL which provides the sld to style and filter the highlight of the real
                estate.

        Returns:
            pyramid_oereb.lib.records.extract.ExtractRecord: The generated extract record.
        """
        log.debug("process() start")
        municipality = Config.municipality_by_fosnr(real_estate.fosnr)
        extract_raw = self._extract_reader_.read(params, real_estate, municipality)
        extract = self.plr_tolerance_check(extract_raw)

        resolver = DottedNameResolver()
        sort_within_themes_method_string = Config.get('extract').get('sort_within_themes_method')
        if sort_within_themes_method_string:
            sort_within_themes_method = resolver.resolve(sort_within_themes_method_string)
            extract = sort_within_themes_method(extract)
        else:
            log.info("No configuration is provided for extract sort_within_themes_method;"
                     " no further sorting is applied.")

        # the selection of view services is done after the tolerance check. This enables us to take
        # care about the circumstance that after tolerance check plrs will be dismissed which were
        # recognized as intersecting before. To avoid this the tolerance check is gathering all plrs
        # intersecting and not intersecting and starts the legend entry sorting after.
        self.view_service_handling(extract.real_estate, params.images, params.format, params.language)

        extract.disclaimers = Config.disclaimers
        extract.glossaries = Config.glossaries
        log.debug("process() done, returning extract.")
        return extract


def create_processor():
    """
    Creates and returns a processor based on the application configuration.
    You should use one (and only one) processor per request. Otherwise some results can be mixed or
    missing.

    Returns:
        pyramid_oereb.lib.processor.Processor: A processor.
    """

    real_estate_config = Config.get_real_estate_config()

    plr_cadastre_authority = Config.get_plr_cadastre_authority()

    real_estate_reader = RealEstateReader(
        real_estate_config.get('source').get('class'),
        **real_estate_config.get('source').get('params')
    )

    plr_sources = []
    for plr in Config.get('plrs'):
        plr_source_class = DottedNameResolver().maybe_resolve(plr.get('source').get('class'))
        plr_sources.append(plr_source_class(**plr))

    extract_reader = ExtractReader(
        plr_sources,
        plr_cadastre_authority
    )

    return Processor(
        real_estate_reader=real_estate_reader,
        plr_sources=plr_sources,
        extract_reader=extract_reader,
    )
