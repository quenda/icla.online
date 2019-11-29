#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import uuid
import re
import sys
import os
import requests
import yaml
import datetime
from weasyprint import HTML, CSS
import pdfrw

PDF_ANNOT_KEY = '/Annots'
PDF_ANNOT_FIELD_KEY = '/T'
PDF_ANNOT_VAL_KEY = '/V'
PDF_ANNOT_RECT_KEY = '/Rect'
PDF_SUBTYPE_KEY = '/Subtype'
PDF_WIDGET_SUBTYPE_KEY = '/Widget'


yml = yaml.safe_load(open('../config.yaml').read())
js = json.loads(sys.stdin.read())

remoteip = os.environ.get('REMOTE_ADDR', '')
token = js['token']
recipient = js['recipient']
answers = js['answers']

today = datetime.date.today()
answers['date'] = today.strftime('%B %d, %Y')


js = {"error": "Invalid token or recipient organization"}

if re.match(r"^[-a-z0-9]+$", recipient):
    ryml = yaml.safe_load(open('../recipients/%s.yaml' % recipient).read())
else:
    token = ''

if re.match(r"^[-a-f0-9]+$", token):
    fpath = os.path.join(yml['storage']['tokens'], token)
    if os.path.exists(fpath):
        answers['email'] = open(fpath).read().strip()
        pdfid = str(uuid.uuid4()) + ".pdf"
        pdfpath = os.path.join(yml['storage']['pdf'], pdfid);
        os.unlink(fpath)
        keys = []
        template_path_pdf = "../recipients/%s.template.pdf" % recipient
        template_path_html = "../recipients/%s.template.html" % recipient
        if (os.path.exists(template_path_pdf)):
            pdfmap = {}
            if os.path.exists("%s.map.yaml" % template_path_pdf):
                pdfmap = yaml.safe_load(open("%s.map.yaml" % template_path_pdf).read())
            template_pdf = pdfrw.PdfReader(template_path_pdf)
            annotations = template_pdf.pages[0][PDF_ANNOT_KEY]
            for annotation in annotations:
                if annotation[PDF_SUBTYPE_KEY] == PDF_WIDGET_SUBTYPE_KEY:
                    if annotation[PDF_ANNOT_FIELD_KEY]:
                        key = annotation[PDF_ANNOT_FIELD_KEY][1:-1]
                        keys.append(key)
                        if key in answers.keys():
                            annotation.update(
                                pdfrw.PdfDict(V='{}'.format(answers[key]))
                            )
                        elif key in pdfmap.values():
                            xk = ''
                            for k,v in pdfmap.items():
                                if v == key: xk = k
                            annotation.update(
                                pdfrw.PdfDict(V='{}'.format(answers.get(xk, '')))
                            )
            pdfrw.PdfWriter().write(pdfpath, template_pdf)
        else:
            html = open(template_path_html, encoding='utf-8').read()
            html = re.sub(r"\$([a-z]+)", lambda v: answers.get(v.group(1), u"???"), html)
            
            css = [CSS(string="""@page { size: letter; margin: 1cm }""")]
            HTML(string=html, encoding='utf-8', base_url = './').write_pdf(pdfpath, stylesheets=css)
            
        js = {
            "file": pdfid
        }
        
        pdfdata = open(pdfpath, "rb").read()
        import smtplib
        import email.mime.text, email.header
        import email.mime.multipart
        import email.mime.application
        
        body = "Please see attached ICLA from %s, filed via %s.\nWith regards,\n%s\n" % (answers['legalname'], remoteip, yml['server']['whoami'])
        msg = email.mime.multipart.MIMEMultipart()
        msg['Subject'] = "[%s] ICLA for %s" % (yml['server']['hostname'], answers['publicname'])
        msg['From'] = yml['email']['sender']
        msg['To'] = ryml['meta']['recipient']
        msg['Reply-To'] = "%s <%s>" % (answers['publicname'], answers['email'])
        msg['Message-ID'] = str(email.utils.make_msgid())
        msg.preamble = "This shouldn't show up..."
        msg.attach( email.mime.text.MIMEText( body, 'plain' ) )
        attach =  email.mime.application.MIMEApplication( pdfdata, subtype='pdf')
        attach.add_header('Content-Disposition','attachment',filename='icla.pdf')
        msg.attach(attach)
        
        # Send the message via our own SMTP server.
        s = smtplib.SMTP('localhost')
        s.send_message(msg)
        s.quit()

print("Status: 200 Okay\r\nContent-Type: application/json\r\n\r\n")
print(json.dumps(js))

