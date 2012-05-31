# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2010, 2011, 2012 Participatory Culture Foundation
# 
# Miro Community is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
# 
# Miro Community is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Miro Community.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import markdown

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.defaultfilters import striptags
from django.template import Context, loader
from localtv.models import Video

from mirocommunity_saas.models import SiteTierInfo


#: The minimum number of days between video limit warnings.
VIDEO_LIMIT_MIN_DAYS = 5
#: The minimum ratio of videos which must be used before a warning is sent
#: to the site owners.
VIDEO_LIMIT_MIN_RATIO = .66
#: The minimum change to the remaining number of videos, as a ratio. For
#: example, a value of .5 would mean that half of the remaining videos must
#: be used up before a new warning will be sent.
VIDEO_LIMIT_MIN_CHANGE_RATIO = .5
#: Number of days before the end of the free trial to warn the site's owners.
FREE_TRIAL_WARNING_DAYS = 5


def render_to_email(subject_template, body_template, context, to, from_email):
    """
    Renders the given templates as an EmailMessage, with plaintext and HTML
    alternatives.

    """
    subject = striptags(subject_template.render(context))
    body = striptags(body_template.render(context))
    msg = EmailMultiAlternatives(subject, body, from_email, to)

    html_body = markdown.markdown(body, output_format="html5")
    msg.attach_alternative(html_body, "text/html")
    return msg


def send_mail(subject_template_name, body_template_name, users=None,
              from_email=None, extra_context=None, fail_silently=False):
    """
    Send mail to the given users (or to the site devs if no users are
    provided) rendered with the given templates.

    Default context for the templates is:

    * site: The current Site instance.
    * tier_info: The SiteTierInfo instance for the current site.
    * tier: The currently selected Tier.
    * user: The current user being emailed, if applicable.

    :param subject_template_name: This the name of a template for the email's
                                  subject line. After the template is
                                  rendered, all HTML tags will be stripped.
    :param body_template_name: This should be the name of a template for the
                               body text. After the template is rendered, it
                               will be passed through a markdown filter.
    :param users: An iterable of users to email, or ``None`` to email the
                  site devs (according to the ``ADMINS`` setting.)
    :param from_email: The email these messages should be sent from, or
                       ``None`` to use the ``DEFAULT_FROM_EMAIL`` setting.
    :param extra_context: Additional context variables for the templates;
                          This will override the default context.
    :param fail_silently: This has the same meaning as for django's core mail
                          functionality.

    """
    tier_info = SiteTierInfo.objects.get_current()
    context = Context({
        'tier_info': tier_info,
        'site': tier_info.site,
        'tier': tier_info.tier
    })
    context.update(extra_context or {})
    subject_template = loader.get_template(subject_template_name)
    body_template = loader.get_template(body_template_name)
    from_email = from_email or settings.DEFAULT_FROM_EMAIL

    if users is not None:
        for user in users:
            if not user.email:
                continue
            context.push()
            context['user'] = user
            msg = render_to_email(subject_template, body_template, context,
                                  [user.email], from_email)
            msg.send(fail_silently=fail_silently)
            context.pop()
    else:
        to = [admin[1] for admin in settings.ADMINS]
        msg = render_to_email(subject_template, body_template, context, to,
                              from_email)
        msg.send(fail_silently=fail_silently)



def send_welcome_email():
    tier_info = SiteTierInfo.objects.get_current()
    if tier_info.welcome_email_sent:
        return
    send_mail('mirocommunity_saas/mail/welcome/subject.txt',
              'mirocommunity_saas/mail/welcome/body.md',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True))
    tier_info.welcome_email_sent = datetime.datetime.now()
    tier_info.save()


def send_video_limit_warning():
    tier_info = SiteTierInfo.objects.get_current()

    # Don't send an email if there is no limit.
    if tier_info.tier.video_limit is None:
        return

    # Don't send an email if one was sent recently.
    resend = datetime.timedelta(VIDEO_LIMIT_MIN_DAYS)
    last_sent = tier_info.video_limit_warning_sent
    if last_sent is not None and datetime.datetime.now() - last_sent < resend:
        return

    # Don't send an email if the ratio of used videos is too low.
    video_limit = tier_info.tier.video_limit
    video_count = Video.objects.filter(status=Video.ACTIVE,
                                       site=settings.SITE_ID).count()
    ratio = float(video_count) / video_limit
    if ratio < VIDEO_LIMIT_MIN_RATIO:
        return

    # Don't send an email if the ratio hasn't changed noticeably since the
    # last email was sent.
    old_video_count = tier_info.video_count_when_warned
    if old_video_count is not None:
        old_ratio = float(old_video_count) / video_limit
        ratio_change = VIDEO_LIMIT_MIN_CHANGE_RATIO * (1 - old_ratio)
        next_ratio = old_ratio + ratio_change
        if ratio < next_ratio:
            return

    send_mail('mirocommunity_saas/mail/video_limit/subject.txt',
              'mirocommunity_saas/mail/video_limit/body.md',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True),
              extra_context={'ratio': ratio})
    tier_info.video_limit_warning_sent = datetime.datetime.now()
    tier_info.video_count_when_warned = video_count
    tier_info.save()


def send_free_trial_ending():
    tier_info = SiteTierInfo.objects.get_current()
    # Only one free trial, so this can only be sent once.
    if tier_info.free_trial_ending_sent:
        return

    # If they haven't started a free trial, don't send.
    end = tier_info.get_free_trial_end()
    if end is None:
        return

    # If it is not exactly within the right timespan, don't send the email.
    warn_after = end - datetime.timedelta(FREE_TRIAL_WARNING_DAYS)
    now = datetime.datetime.now()
    if not (now < end and now > warn_after):
        return

    send_mail('mirocommunity_saas/mail/free_trial/subject.txt',
              'mirocommunity_saas/mail/free_trial/body.md',
              # site owners are currently all superusers.
              User.objects.filter(is_superuser=True))
    tier_info.free_trial_ending_sent = datetime.datetime.now()
    tier_info.save()
