#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ruff: noqa: F821
# (ruff don't see read variables from release.py)

# pyright: reportMissingModuleSource=false
from setuptools import find_namespace_packages, setup
from os.path import join, dirname


exec(open(join(dirname(__file__), 'odoo', 'release.py'), 'rb').read())  # Load release variables
lib_name = 'odoo'

# 更新分类器以解决许可证警告
updated_classifiers = []
for c in classifiers.split('\n'):
    if c and 'License :: OSI Approved :: GNU Lesser General Public License v3' not in c:
        updated_classifiers.append(c)

setup(
    name='odoo',
    version=version,
    description=description,
    long_description=long_desc,
    url=url,
    author=author,
    author_email=author_email,
    classifiers=[c for c in updated_classifiers if c] + [
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python'
    ],
    license=license,
    scripts=['setup/odoo'],
    packages=find_namespace_packages(),
    package_dir={'%s' % lib_name: 'odoo'},
    include_package_data=True,
    install_requires=[
        'asn1crypto',
        'babel >= 1.0',
        'cbor2',
        'chardet',
        'cryptography',
        'docutils',
        'geoip2',
        'gevent',
        'greenlet',
        'idna',
        'Jinja2',
        'lxml',  # windows binary http://www.lfd.uci.edu/~gohlke/pythonlibs/
        'lxml_html_clean',
        'libsass',
        'MarkupSafe',
        'num2words',
        'ofxparse',
        'openpyxl',
        'passlib',
        'pillow',  # windows binary http://www.lfd.uci.edu/~gohlke/pythonlibs/
        'polib',
        'psutil',  # windows binary code.google.com/p/psutil/downloads/list
        'psycopg2 >= 2.2',
        'pyopenssl',
        'PyPDF2',
        'pyserial',
        'python-dateutil',
        'python-stdnum',
        'pytz',
        'pyusb >= 1.0.0b1',
        'qrcode',
        'reportlab',  # windows binary pypi.python.org/pypi/reportlab
        'rjsmin',
        'requests',
        'urllib3',
        'vobject',
        'werkzeug',
        'xlrd',
        'xlsxwriter',
        'xlwt',
        'zeep',
    ],
    python_requires='>=' + ".".join(map(str, MIN_PY_VERSION)),
    extras_require={
        'ldap': ['python-ldap'],
    },
    tests_require=[
        'freezegun',
    ],
)