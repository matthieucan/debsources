# Copyright (C) 2013-2015  The Debsources developers <info@sources.debian.net>.
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
import magic
import fnmatch

from sqlalchemy import and_

from debsources.models import (Checksum, File,
                               Package, PackageName)
from debsources import filetype
from debsources.consts import AREAS
from debsources.debmirror import SourcePackage
from debsources.excepts import FileOrFolderNotFound, \
    InvalidPackageOrVersionError
import debsources.query as qry


class Location(object):
    """ a location in a package, can be a directory or a file """

    def _get_debian_path(self, session):
        """
        Returns the Debian path of a package version.
        For example: main/h
                     contrib/libz
        It's the path of a *version*, since a package can have multiple
        versions in multiple areas (ie main/contrib/nonfree).

        sources_dir: the sources directory, usually comes from the app config
        """
        prefix = SourcePackage.pkg_prefix(self.package)
        prefix_b = bytes(prefix, encoding='ascii')

        try:
            p_id = session.query(PackageName) \
                          .filter(PackageName.name == self.package).first().id
            varea = session.query(Package) \
                           .filter(and_(Package.name_id == p_id,
                                        Package.version == self.version)) \
                           .first().area
            varea_b = bytes(varea, encoding='ascii')
        except:
            # the package or version doesn't exist in the database
            # BUT: packages are stored for a longer time in the filesystem
            # to allow codesearch.d.n and other less up-to-date platforms
            # to point here.
            # Problem: we don't know the area of such a package
            # so we try in main, contrib and non-free.
            for area in AREAS:
                area_b = bytes(area, encoding='ascii')
                if os.path.exists(os.path.join(self.sources_dir,
                                               area_b,
                                               prefix_b,
                                               self.package_b,
                                               self.version_b)):
                    return os.path.join(area_b, prefix_b)

            raise InvalidPackageOrVersionError("%s %s" % (package, version))

        return os.path.join(varea_b, prefix_b)

    def __init__(self, session, sources_dir, sources_static,
                 package, version="", path=""):
        """ Constructs a location.

        If provided, the path argument must be binary """

        self.sources_dir = sources_dir
        self.sources_static = sources_static

        self.package = package
        self.version = version
        # for use in paths:
        self.package_b = bytes(package, encoding='utf8', errors='surrogateescape')
        self.version_b = bytes(version, encoding='utf8', errors='surrogateescape')

        self.path = path

        debian_path = self._get_debian_path(session)

        # print(package + '  ' + str(type(package)))
        # print(version + '  ' + str(type(version)))
        # print(path + '  ' + str(type(path)))
        # print(path.encode('utf8', errors='surrogateescape'))# + '  ' + str(type(path)))
        self.path_to = os.path.join(self.package_b, self.version_b, self.path)

        # print(type(path))
        # try:
        #     path.decode('utf8')
        # except UnicodeEncodeError as e:
        #     raise e

        self.sources_path = os.path.join(
            self.sources_dir,
            debian_path,
            self.path_to)

        self.version_path = os.path.join(
            self.sources_dir,
            debian_path,
            self.package_b,
            self.version_b)

        if not(os.path.exists(self.sources_path)):
            raise FileOrFolderNotFound("%s" % (self.path_to))

        self.sources_path_static = os.path.join(
            self.sources_static,
            debian_path,
            self.path_to)

    def is_dir(self):
        """ True if self is a directory, False if it's not """
        return os.path.isdir(self.sources_path)

    def is_file(self):
        """ True if sels is a file, False if it's not """
        return os.path.isfile(self.sources_path)

    def is_symlink(self):
        """ True if a folder/file is a symbolic link file, False if it's not
        """
        return os.path.islink(self.sources_path)

    def get_package(self):
        return self.package

    def get_version(self):
        return self.version

    def get_path(self):
        return self.path

    def get_deepest_element(self):
        if self.version == "":
            return self.package
        elif self.path == "":
            return self.version
        else:
            return self.path.split(b"/")[-1]

    def get_path_to(self):
        return self.path_to.rstrip(b"/")

    def get_parent_path(self):
        return os.path.dirname(self.get_path_to())
        #return b'/'.join(path.split(b'/')[:-1])


class Directory(object):
    """ a folder in a package """

    def __init__(self, location, hidden_files=[]):
        # if the directory is a toplevel one, we remove the .pc folder
#        self.sources_path = location.sources_path
        self.location = location
        self.hidden_files = hidden_files

    def get_listing(self):
        """
        returns the list of folders/files in a directory,
        along with their type (directory/file)
        in a tuple (name, type)
        """
        def get_type(f):
            if os.path.isdir(os.path.join(self.location.sources_path, f)):
                return "directory"
            else:
                return "file"
        get_stat = qry.location_get_stat
        listing = sorted([dict(name=f, type=get_type(f), hidden=False,
                              stat=get_stat(os.path.join(self.location.sources_path, f)))
                         for f in os.listdir(self.location.sources_path)],
                         key=lambda x: x['name'])
        print(self.hidden_files)
        for hidden_file in self.hidden_files:
            for f in listing:
                full_path = os.path.join(self.location.sources_path,
                                         f['name'])
                if f['type'] == "directory":
                    full_path += b"/"
                f['hidden'] = (f['hidden'] or
                               fnmatch.fnmatch(full_path, bytes(hidden_file, encoding='ascii')))

        return listing


class SourceFile(object):
    """ a source file in a package """

    def __init__(self, location):
        self.location = location
        self.sources_path = location.sources_path
        self.sources_path_static = location.sources_path_static
        self.mime = self._find_mime()

    def _find_mime(self):
        """ returns the mime encoding and type of a file """
        mime = magic.open(magic.MIME_TYPE)
        mime.load()
        type_ = mime.file(self.sources_path)
        mime.close()
        mime = magic.open(magic.MIME_ENCODING)
        mime.load()
        encoding = mime.file(self.sources_path)
        mime.close()
        return dict(encoding=encoding, type=type_)

    def get_mime(self):
        return self.mime

    def get_sha256sum(self, session):
        """
        Queries the DB and returns the shasum of the file.
        """
        shasum = session.query(Checksum.sha256) \
                        .filter(Checksum.package_id == Package.id) \
                        .filter(Package.name_id == PackageName.id) \
                        .filter(File.id == Checksum.file_id) \
                        .filter(PackageName.name == self.location.package) \
                        .filter(Package.version == self.location.version) \
                        .filter(File.path == self.location.path.encode('utf8')) \
                        .first()
        # WARNING: in the DB path is binary, and here
        # location.path is unicode, because the path comes from
        # the URL. TODO: check with non-unicode paths
        if shasum:
            shasum = shasum[0]
        return shasum

    def istextfile(self):
        """True if self is a text file, False if it's not.

        """
        return filetype.is_text_file(self.mime['type'])
        # for substring in text_file_mimes:
        #     if substring in self.mime['type']:
        #         return True
        # return False

    def get_raw_url(self):
        """ return the raw url on disk (e.g. data/main/a/azerty/foo.bar) """
        return self.sources_path_static
