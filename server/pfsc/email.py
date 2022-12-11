# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

import traceback

from flask_mail import Message
import jinja2
from rq.job import get_current_job

from pfsc import get_app, mail, check_config
from pfsc.rq import get_rqueue
from pfsc.constants import MAIN_TASK_QUEUE_NAME


templates_dir = check_config("EMAIL_TEMPLATE_DIR")
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))


def send_error_report_mail(
        body='',
        exc_info=None,
        asyncr=None
):
    """
    Report a 500 internal error to configured recipients.
    """
    subject = '[500] PISE System Error'
    if exc_info is not None:
        body += ''.join(traceback.format_exception(*exc_info))
    app, _ = get_app()
    recips = app.config['ERR_MAIL_RECIPS']
    return send_mail(subject, body, recips, asyncr=asyncr)


def send_hosting_request_recd_mail_to_user(user_email_addr, userpath, repopath, version, comment):
    """
    Send a user an email confirming that their hosting request has been
    received.
    """
    app, _ = get_app()
    subject='PISE Hosting Request Received'
    recips = [user_email_addr]

    branding_img_url = app.config.get('EMAIL_BRANDING_IMG_URL')
    branding_img_title = app.config.get('EMAIL_BRANDING_IMG_TITLE')
    hosting_phrase = app.config.get('HOSTING_PHRASE')

    html_template = jinja_env.get_template(f'hosting_req_for_user.html')
    html = html_template.render(
        branding_img_url=branding_img_url,
        branding_img_title=branding_img_title,
        hosting_phrase=hosting_phrase,
        userpath=userpath,
        repopath=repopath,
        version=version,
        comment=comment,
    ).strip()

    body_template = jinja_env.get_template(f'hosting_req_for_user.txt')
    body = body_template.render(
        branding_img_url=branding_img_url,
        branding_img_title=branding_img_title,
        hosting_phrase=hosting_phrase,
        userpath=userpath,
        repopath=repopath,
        version=version,
        comment=comment,
    ).strip()

    return send_mail(subject, body, recips, html=html)


def send_hosting_request_mail_to_reviewers(user_email_addr, userpath, repopath, version, comment):
    """
    Report a hosting request to configured reviewers.
    """
    ...
    app, _ = get_app()
    subject='PISE Hosting Request -- Please Review'
    recips = app.config['HOSTING_REQ_REVIEWER_ADDRS']

    branding_img_url = app.config.get('EMAIL_BRANDING_IMG_URL')
    branding_img_title = app.config.get('EMAIL_BRANDING_IMG_TITLE')
    hosting_phrase = app.config.get('HOSTING_PHRASE')

    html_template = jinja_env.get_template(f'hosting_req_for_reviewer.html')
    html = html_template.render(
        branding_img_url=branding_img_url,
        branding_img_title=branding_img_title,
        hosting_phrase=hosting_phrase,
        user_email_addr=user_email_addr,
        userpath=userpath,
        repopath=repopath,
        version=version,
        comment=comment,
    ).strip()

    body_template = jinja_env.get_template(f'hosting_req_for_reviewer.txt')
    body = body_template.render(
        branding_img_url=branding_img_url,
        branding_img_title=branding_img_title,
        hosting_phrase=hosting_phrase,
        user_email_addr=user_email_addr,
        userpath=userpath,
        repopath=repopath,
        version=version,
        comment=comment,
    ).strip()

    return send_mail(subject, body, recips, html=html)


def send_mail(subject, body, recips, html=None, sender=None, asyncr=None):
    """
    Send an email.

    @param subject: string
    @param body: string
    @param recips: list of email addresses (strings)
    @param sender: email address (string), or None. If None, we use the
        value of the MAIL_FROM_ADDR config var.
    @param html: optional string, to be sent as HTML, _in addition to_ the
        plain text body.
    @param asyncr: boolean or None. Set True/False to control whether the mail
        is sent asynchronously or not; leave as `None` to allow this setting
        to be made automatically, based on whether we are already within
        an RQ job (sync) or not (async).
    """
    app, _ = get_app()
    sender = sender or app.config['MAIL_FROM_ADDR']
    testing = app.config.get("TESTING")
    if asyncr is None:
        asyncr = get_current_job() is None
    if asyncr and not testing:
        q = get_rqueue(MAIN_TASK_QUEUE_NAME)
        return q.enqueue(
            send_mail_core,
            args=[subject, body, recips, sender],
            kwargs={'html': html},
        )
    else:
        return send_mail_core(subject, body, recips, sender, html=html)


def send_mail_core(subject, body, recips, sender, html=None):
    app, _ = get_app()
    with app.app_context():
        if app.config["PRINT_EMAILS_INSTEAD_OF_SENDING"]:
            msg = DummyMessage(subject, sender, recips, body, html=html)
            print()
            print('~' * 80)
            print(msg)
        else:
            msg = Message(subject, sender=sender, recipients=recips)
            if html:
                msg.html = html
            msg.body = body
            mail.send(msg)
    return msg


class DummyMessage:
    """
    In our `send_mail_core()` function, we would like to form an ordinary
    `Message` even when testing, convert to a string, and print. Unfortnately,
    `flask_mail.Message.__init__()` makes a call to `make_msgid()` which is
    extremely slow (abt 5s). So we use this dummy message class instead.
    """

    def __init__(self, subject, sender, recipients, body, html=None):
        self.subject = subject
        self.sender = sender
        self.recipients = recipients
        self.body = body
        self.html = html

    def __str__(self):
        """
        We do not attempt to produce all the headers you would find in an
        actual email, just a subset.
        """
        h = (
            f'Subject: {self.subject}\n'
            f'From: {self.sender}\n'
            f'To: {", ".join(self.recipients)}\n'
            f'\n'
        )
        h += self.body
        if self.html:
            h += self.html
        return h
