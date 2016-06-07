# Copyright (C) 2015  The Debsources developers <info@sources.debian.net>.
# See the AUTHORS file at the top-level directory of this distribution and at
# https://anonscm.debian.org/gitweb/?p=qa/debsources.git;a=blob;f=AUTHORS;hb=HEAD
#
# This file is part of Debsources. Debsources is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.  For more information
# see the COPYING file at the top-level directory of this distribution and at
# https://anonscm.debian.org/gitweb/?p=qa/debsources.git;a=blob;f=COPYING;hb=HEAD

from __future__ import absolute_import

import os
from collections import OrderedDict
from flask import request, current_app

from ..views import GeneralView, session
from debsources.excepts import (Http404ErrorSuggestions, FileOrFolderNotFound,
                                InvalidPackageOrVersionError, Http404Error)
import debsources.query as qry
from ..sourcecode import SourceCodeIterator
from . import patches_helper as helper


class VersionsView(GeneralView):
    def get_objects(self, packagename):
        suite = request.args.get("suite") or ""
        suite = suite.lower()
        if suite == "all":
            suite = ""
        # we list the version with suites it belongs to
        try:
            versions_w_suites = qry.pkg_names_list_versions_w_suites(
                session, packagename, suite, reverse=True)
        except InvalidPackageOrVersionError:
            raise Http404Error("%s not found" % packagename)
        empty = False
        for i, v in enumerate(versions_w_suites):
            try:
                format_file = helper.get_patch_format(session, packagename,
                                                      v['version'],
                                                      current_app.config)
            except FileOrFolderNotFound:
                format_file = ""
                versions_w_suites[i]['supported'] = False
            if not helper.is_supported(format_file.rstrip()):
                versions_w_suites[i]['supported'] = False
            else:
                versions_w_suites[i]['supported'] = True
                try:
                    series = helper.get_patch_series(session, packagename,
                                                     v['version'],
                                                     current_app.config)
                except (FileOrFolderNotFound, InvalidPackageOrVersionError):
                    series = []
                if len(series) == 0:
                    empty = True
                versions_w_suites[i]['series'] = len(series)

        return dict(type="package",
                    package=packagename,
                    versions=versions_w_suites,
                    path=packagename,
                    suite=suite,
                    is_empty=empty)


class SummaryView(GeneralView):
    def _parse_file_deltas(self, summary, package, version):
        """ Parse a file deltas summary to create links to Debsources

        """
        file_deltas = []
        lines = summary.splitlines()
        for line in lines[0:-1]:
            filepath, deltas = line.split(b'|')
            file_deltas.append(dict(filepath=filepath.replace(b' ', b''),
                                    deltas=deltas))
        deltas_summary = b'\n' + lines[-1]
        return file_deltas, deltas_summary

    def parse_patch_series(self, session, package, version, config, series):
        """ Parse a list of patches available in `series` and create a dict
            with important information such as description if it exists, file
            changes.

        """
        patches_info = OrderedDict()
        for serie in series:
            serie = serie.strip()
            if not serie.startswith(b'#') and not serie == b"":
                patch = serie.split(b' ')[0]
                try:
                    path = os.path.join(b'debian/patches/', patch)
                    serie_path, loc = helper.get_sources_path(
                        session, package, version, current_app.config, path)
                    summary = helper.get_file_deltas(serie_path)
                    deltas, deltas_summary = self._parse_file_deltas(summary,
                                                                     package,
                                                                     version)
                    description, bug = helper.get_patch_details(serie_path)
                    patches_info[serie] = dict(deltas=deltas,
                                               summary=deltas_summary,
                                               download=loc.get_raw_url(),
                                               description=description,
                                               bug=bug,
                                               path=path)
                except (FileOrFolderNotFound, InvalidPackageOrVersionError):
                    patches_info[serie] = dict(summary='Patch does not exist',
                                               description='---',
                                               bug='')
        return patches_info

    def get_objects(self, packagename, version):
        path_to = os.path.join(bytes(packagename, encoding='utf8'),
                               bytes(version, encoding='utf8'))
        series_path_to = os.path.join(path_to, helper.SERIES_PATH)

        try:
            format_file = helper.get_patch_format(session, packagename,
                                                  version, current_app.config)
        except InvalidPackageOrVersionError:
            raise Http404ErrorSuggestions(packagename, version, '')
        except FileOrFolderNotFound:
                return dict(package=packagename,
                            version=version,
                            path=path_to,
                            patches=[],
                            format='unknown')
        if not helper.is_supported(format_file):
            return dict(package=packagename,
                        version=version,
                        path=path_to,
                        format=format_file,
                        patches=[],
                        supported=False,
                        series_path_to = series_path_to)

        # are there any patches for the package?
        try:
            series = helper.get_patch_series(session, packagename, version,
                                             current_app.config)
        except (FileOrFolderNotFound, InvalidPackageOrVersionError):
            return dict(package=packagename,
                        version=version,
                        path=path_to,
                        format=format_file,
                        patches=[],
                        supported=True,
                        series_path_to = series_path_to)

        info = self.parse_patch_series(session, packagename, version,
                                       current_app.config, series)
        if 'api' in request.endpoint:
            return dict(package=packagename,
                        version=version,
                        format=format_file,
                        patches=[key.rstrip() for key in info.keys()],
                        series_path_to = series_path_to)
        from pprint import pprint
        pprint(info)
        return dict(package=packagename,
                    version=version,
                    path=path_to.decode('utf8'),
                    format=format_file,
                    series=info.keys(),
                    patches=info,
                    supported=True,
                    series_path_to = series_path_to,
                    joinpath=os.path.join)


class PatchView(GeneralView):

    def get_objects(self, packagename, version, path_to):
        print(path_to)
        print(type(path_to))
        # we receive a string from flask
        # but paths are bytes
        path_to = path_to.encode('utf8', errors='surrogateescape')
        try:
            serie_path, loc = helper.get_sources_path(
                session, packagename, version, current_app.config,
                b'debian/patches/' + path_to.rstrip())
        except (FileOrFolderNotFound, InvalidPackageOrVersionError):
            raise Http404ErrorSuggestions(packagename, version,
                                          b'debian/patches/' + path_to.rstrip())
        if 'api' in request.endpoint:
            summary = helper.get_file_deltas(serie_path)
            description, bug = helper.get_patch_details(serie_path)
            return dict(package=packagename,
                        version=version,
                        url=loc.get_raw_url(),
                        name=path_to,
                        description=description,
                        bug=bug,
                        file_deltas=summary)
        sourcefile = SourceCodeIterator(serie_path)

        return dict(package=packagename,
                    version=version,
                    nlines=sourcefile.get_number_of_lines(),
                    file_language='diff',
                    code=sourcefile)
