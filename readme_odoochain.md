OdooChain Install
----

anaconda

```

#conda create -n ocb python=3.8

conda update -n base -c defaults conda

conda create -n ocb python=3.8

conda activate ocb

pip install -r requirements.txt

#Successfully built ebaysdk feedparser libsass Mako MarkupSafe ofxparse PyPDF2 python-stdnum pyusb vobject
Installing collected packages: urllib3, idna, chardet, soupsieve, six, requests, requests-toolbelt, pywin32, pytz, python-dateutil, pyparsing, Pillow, MarkupSafe, lxml, isodate, defusedxml, colorama, cached-property, beautifulsoup4, attrs, appdirs, zeep, xlwt, XlsxWriter, xlrd, Werkzeug, vobject, reportlab, qrcode, pyusb, python-stdnum, pyserial, pypiwin32, PyPDF2, pydot, psycopg2, psutil, polib, passlib, ofxparse, num2words, Mako, libsass, Jinja2, html2text, freezegun, feedparser, ebaysdk, docutils, decorator, Babel

pip install cython

 (to install python-imap)

pip install python-imap phonenumbers

pip3 install pdfminer.six
# https://www.odoo.com/documentation/14.0/setup/install.html#setup-install-source

npm install -g rtlcss

# -r odoochain -w *** --addons-path=addons,odoo/addons,addons_chain

# PYTHONUNBUFFERED=1;PYDEVD_USE_FRAME_EVAL=NO;TZ=UTC

# when 
python Scripts/pywin32_postinstall.py -install

```

-------------------------

## Installing via PIP

You can install pywin32 via pip:
> pip install pywin32

Note that if you want to use pywin32 for "system wide" features, such as
registering COM objects or implementing Windows Services, then you must run
the following command from an elevated command prompt:

> python Scripts/pywin32_postinstall.py -install

---------------------------

## installing Wkhtmltopdf in windows system

> scoop install Wkhtmltopdf

## database manager

http://127.0.0.1:8069/web/database/manager
http://127.0.0.1:8099/web/database/manager
