import logging
import math

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.utils.datastructures import SortedDict
from django.views.generic import TemplateView, View
from localtv.admin.views import IndexView
from localtv.decorators import require_site_admin
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.forms import (TierChangeForm,
                                            DowngradeConfirmationForm,
                                            PayPalCancellationForm,
                                            PayPalSubscriptionForm)
from mirocommunity_saas.models import SiteTierInfo, Tier
from mirocommunity_saas.utils.tiers import (admins_to_demote,
                                            videos_to_deactivate,
                                            set_tier)


class TierIndexView(IndexView):
    """
    Overrides the base admin index view to add the percent of videos used
    to the context.

    """
    def get_context_data(self, **kwargs):
        context = super(TierIndexView, self).get_context_data(**kwargs)
        tier = SiteTierInfo.objects.get_current().tier
        percent_videos_used = min(math.floor((100.0 * context['total_count'])
                                             / tier.video_limit),
                                  100)
        context.update({
            'percent_videos_used': percent_videos_used,
        })
        return context


index = require_site_admin(TierIndexView.as_view())


class TierView(TemplateView):
    """
    Base class for views for changing tiers and confirming any Bad Things that
    might happen as a result.

    """
    template_name = 'localtv/admin/upgrade.html'

    def get_context_data(self, **kwargs):
        context = super(TierView, self).get_context_data(**kwargs)
        tier_info = SiteTierInfo.objects.get_current()

        if tier_info.enforce_payments:
            price = (0 if tier_info.subscription is None
                     else tier_info.subscription.signup_or_modify.amount3)
            try:
                set_tier(price)
            except Tier.DoesNotExist:
                logging.error('No tier matching current subscription.',
                              exc_info=True)
            except Tier.MultipleObjectsReturned:
                logging.error('Multiple tiers found matching current'
                              'subscription.', exc_info=True)

        forms = SortedDict()
        tiers = tier_info.available_tiers.order_by('price')
        for tier in tiers:
            if tier.price < tier_info.tier.price:
                forms[tier] = DowngradeConfirmationForm(tier)
            else:
                if tier_info.enforce_payments:
                    forms[tier] = PayPalSubscriptionForm(tier)
                else:
                    forms[tier] = TierChangeForm(initial={'tier': tier})

        # Here we build a list of prices of current subscriptions, sorted
        # by the date the subscription started. This lets us check in the
        # template whether a tier's subscription should be considered
        # "upcoming" or "old".
        subscriptions = sorted([subscr for subscr in tier_info.subscriptions
                                if not subscr.is_cancelled],
                               key=lambda s: s.signup_or_modify.subscr_date,
                               reverse=True)
        subscription_prices = [subscr.price for subscr in subscriptions]
        context.update({
            'subscription_prices': subscription_prices,
            'cancellation_form': PayPalCancellationForm(),
            'forms': forms,
            'tier_info': tier_info,
        })
        return context


class DowngradeConfirmationView(TemplateView):
    template_name = 'localtv/admin/downgrade_confirm.html'

    def get_context_data(self, **kwargs):
        context = super(DowngradeConfirmationView,
                        self).get_context_data(**kwargs)
        tier_info = SiteTierInfo.objects.get_current()
        slug = self.request.GET.get('tier', '')
        try:
            tier = tier_info.available_tiers.get(slug=slug)
        except Tier.DoesNotExist:
            raise Http404
        if tier.price >= tier_info.tier.price:
            raise Http404
        if tier_info.enforce_payments:
            if tier.price == 0:
                if tier_info.subscription:
                    form = PayPalCancellationForm()
                else:
                    # If they don't have an active subscription, we can't very
                    # well cancel it.
                    form = TierChangeForm(initial={'tier': tier})
            else:
                form = PayPalSubscriptionForm(tier)
        else:
            form = TierChangeForm(initial={'tier': tier})
        context.update({
            'form': form,
            'tier': tier,
            'tier_info': tier_info,
            'admins_to_demote': admins_to_demote(tier),
            'videos_to_deactivate': videos_to_deactivate(tier),
            'have_theme': Theme.objects.filter(default=True).exists()
        })
        return context


class TierChangeView(View):
    """
    Changes the tier and redirects the user back to the admin tier view.

    """
    def finished(self):
        """
        Since this is an intermediate view, we return the user to the same
        place whether or not we've actually done anything.

        """
        return HttpResponseRedirect(reverse('localtv_admin_tier'))

    def handle_form(self, data):
        form = TierChangeForm(data)
        if form.is_valid():
            form.save()

    def get(self, request, *args, **kwargs):
        self.handle_form(request.GET)
        return self.finished()

    def post(self, request, *args, **kwargs):
        self.handle_form(request.POST)
        return self.finished()
