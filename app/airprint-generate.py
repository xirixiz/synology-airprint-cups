#!/usr/bin/env python3

"""
Copyright (c) 2010 Timothy J Fontaine <tjfontaine@atxconsulting.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Rewrite by Bram van Dartel (aka xirixiz) 2024-10
"""

import cups
import os
import re
import urllib.parse as urlparse
from io import StringIO
from xml.dom.minidom import parseString
from xml.dom import minidom
import argparse
import getpass
import sys

try:
    import lxml.etree as etree
except ImportError:
    try:
        from xml.etree.ElementTree import Element, ElementTree, tostring
        etree = None
    except ImportError:
        sys.exit('Failed to find python libxml or elementtree. Please install one of those.')

XML_TEMPLATE = """<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
<name replace-wildcards="yes"></name>
<service>
    <type>_ipp._tcp</type>
    <subtype>_universal._sub._ipp._tcp</subtype>
    <port>631</port>
    <txt-record>txtvers=1</txt-record>
    <txt-record>qtotal=1</txt-record>
    <txt-record>Transparent=T</txt-record>
    <txt-record>URF=none</txt-record>
</service>
</service-group>"""

DOCUMENT_TYPES = {
    'application/pdf': True,
    'application/postscript': True,
    'application/vnd.cups-raster': True,
    'application/octet-stream': True,
    'image/urf': True,
    'image/png': True,
    'image/tiff': True,
    'image/jpeg': True,
    'image/gif': True,
    'text/plain': True,
    'text/html': True,
    'image/x-xwindowdump': False,
    'image/x-xpixmap': False,
    'image/x-xbitmap': False,
    'application/x-shell': False,
    'application/x-perl': False,
    'application/x-csource': False,
    'application/x-cshell': False,
}

class AirPrintGenerate:
    def __init__(self, host=None, user=None, port=631, verbose=False, directory=None, prefix='AirPrint-', adminurl=False):
        self.host = host
        self.user = user
        self.port = port
        self.verbose = verbose
        self.directory = directory
        self.prefix = prefix
        self.adminurl = adminurl

        if self.user:
            cups.setUser(self.user)

    def generate(self):
        conn = cups.Connection(self.host, self.port) if self.host else cups.Connection()
        printers = conn.getPrinters()

        # Pre-parse the XML template once
        tree = ElementTree()
        tree.parse(StringIO(XML_TEMPLATE.replace('\n', '').replace('\r', '').replace('\t', '')))

        for p, v in printers.items():
            if v['printer-is-shared']:
                self._create_service_file(conn, p, v, tree)

    def _create_service_file(self, conn, printer_name, printer_attrs, xml_tree):
        uri = urlparse.urlparse(printer_attrs['printer-uri-supported'])
        name = xml_tree.find('name')
        name.text = f'AirPrint {printer_name} @ %h'

        service = xml_tree.find('service')

        # Port configuration
        port = service.find('port')
        port_no = uri.port if uri.port else self.port
        port.text = f'{port_no}'

        # Path parsing and attributes
        rp = re.sub(r'^/+', '', uri.path if uri.path else uri[2])
        path = Element('txt-record')
        path.text = f'rp={rp}'
        service.append(path)

        # Add more elements
        desc = Element('txt-record')
        desc.text = f'note={printer_attrs["printer-info"]}'
        service.append(desc)

        product = Element('txt-record')
        product.text = 'product=(GPL Ghostscript)'
        service.append(product)

        state = Element('txt-record')
        state.text = f'printer-state={printer_attrs["printer-state"]}'
        service.append(state)

        ptype = Element('txt-record')
        ptype.text = f'printer-type={hex(printer_attrs["printer-type"])}'
        service.append(ptype)

        if printer_attrs.get('color-supported'):
            color = Element('txt-record')
            color.text = 'Color=T'
            service.append(color)

        if printer_attrs.get('media-default') == 'iso_a4_210x297mm':
            max_paper = Element('txt-record')
            max_paper.text = 'PaperMax=legal-A4'
            service.append(max_paper)

        # Document formats and limit check
        pdl = Element('txt-record')

        if 'document-format-supported' in printer_attrs:
            fmts = [a for a in printer_attrs['document-format-supported'] if DOCUMENT_TYPES.get(a, False)]
            if 'image/urf' not in fmts:
                sys.stderr.write(f'image/urf not supported for {printer_name}, may not work on iOS6.\n')
            pdl.text = f'pdl={",".join(fmts)}'
        else:
            sys.stderr.write(f'Warning: No document format supported for {printer_name}.\n')
            pdl.text = 'pdl='

        service.append(pdl)

        if self.adminurl:
            admin = Element('txt-record')
            admin.text = f'adminurl={printer_attrs["printer-uri-supported"]}'
            service.append(admin)

        self._write_service_file(printer_name, xml_tree)

    def _write_service_file(self, printer_name, xml_tree):
        fname = os.path.join(self.directory or '', f'{self.prefix}{printer_name}.service')

        with open(fname, 'w') as f:
            if etree:
                xml_tree.write(f, pretty_print=True, xml_declaration=True, encoding="UTF-8")
            else:
                xmlstr = tostring(xml_tree.getroot())
                doc = parseString(xmlstr)
                dt = minidom.getDOMImplementation().createDocumentType('service-group', None, 'avahi-service.dtd')
                doc.insertBefore(dt, doc.documentElement)
                doc.writexml(f)

        if self.verbose:
            sys.stderr.write(f'Created: {fname}\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate AirPrint service files for CUPS printers")
    parser.add_argument('-H', '--host', type=str, help='Hostname of CUPS server (optional)')
    parser.add_argument('-P', '--port', type=int, help='Port number of CUPS server', default=631)
    parser.add_argument('-u', '--user', type=str, help='Username to authenticate with against CUPS')
    parser.add_argument('-d', '--directory', type=str, help='Directory to create service files')
    parser.add_argument('-v', '--verbose', action="store_true", help="Print debugging information to STDERR")
    parser.add_argument('-p', '--prefix', type=str, help='Prefix all files with this string', default='AirPrint-')
    parser.add_argument('-a', '--admin', action="store_true", help="Include the printer specified uri as the adminurl")

    args = parser.parse_args()

    # Prompt for password if required
    cups.setPasswordCB(getpass.getpass)

    # Create directory if it doesn't exist
    if args.directory and not os.path.exists(args.directory):
        os.mkdir(args.directory)

    apg = AirPrintGenerate(
        user=args.user,
        host=args.host,
        port=args.port,
        verbose=args.verbose,
        directory=args.directory,
        prefix=args.prefix,
        adminurl=args.admin
    )

    apg.generate()

