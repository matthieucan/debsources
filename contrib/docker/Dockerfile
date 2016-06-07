FROM debian:testing
# jessie is needed for libjs-highlight
MAINTAINER Matthieu Caneill <matthieu.caneill@gmail.com>

ENV DEBIAN_FRONTEND noninteractive

# PACKAGES
RUN apt-get update && \
    apt-get install -y \
    apache2 \
    libapache2-mod-fcgid \
    libapache2-mod-wsgi \
    libjs-jquery \
    libjs-highlight \
    python-debian \
    python3-debian \
    python-flask \
    python3-flask \
    python-flup \
    python-magic \
    python3-magic \
    tango-icon-theme \
    debmirror \
    exuberant-ctags \
    postgresql-9.5 \
    python-matplotlib \
    python3-matplotlib \
    python-psycopg2 \
    python3-psycopg2 \
    python-sqlalchemy \
    python3-sqlalchemy \
    sloccount \
    python-nose \
    python3-nose \
    python-nose2-cov \
    python3-nose2-cov \
    python-flaskext.wtf \
    python3-flaskext.wtf \
    dpkg-dev \
    diffstat \
    netcat \
    git \
    python-setuptools \
    postgresql-client-9.4
    python2.7 \
    python3 \
    lynx \
    emacs

# SETUP
ADD scripts/* /opt/
RUN mkdir /etc/debsources
RUN echo coucou
ADD config.ini /etc/debsources/
RUN mkdir /opt/debsources

ENV PYTHONPATH /opt/debsources

EXPOSE 5000
