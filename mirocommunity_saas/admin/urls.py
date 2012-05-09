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

from django.conf.urls.defaults import patterns, include, url

from mirocommunity_saas.admin.forms import (EditSettingsForm, AuthorForm,
                                            AuthorFormSet, VideoFormSet)
from mirocommunity_saas.admin.views import index, TierView, TierChangeView


urlpatterns = patterns('',
    url(r'^admin/$', index, name='localtv_admin_index'),
    url(r'^admin/upgrade/$', TierView.as_view(), name='localtv_admin_tier'),
    url(r'^admin/upgrade/complete/$', TierChangeView.as_view(),
        name='localtv_admin_tier_change'),
    url(r'^admin/paypal/', include('paypal.standard.ipn.urls')),
)

urlpatterns += patterns('mirocommunity_saas.admin.approve_reject_views',
    url(r'^admin/actions/approve_video/$', 'approve_video',
        name='localtv_admin_approve_video'),
    url(r'^admin/actions/feature_video/$', 'feature_video',
        name='localtv_admin_feature_video'),
    url(r'^admin/actions/approve_all/$', 'approve_all',
        name='localtv_admin_approve_all'),
)

urlpatterns += patterns('mirocommunity_saas.admin.design_views',
    url(r'^admin/settings/newsletter/$', 'newsletter_settings',
        name='localtv_admin_newsletter_settings')
)

urlpatterns += patterns('mirocommunity_saas.admin.livesearch_views',
    url(r'^admin/add/approve/$', 'approve',
        name='localtv_admin_search_video_approve')
)
urlpatterns += patterns('localtv.admin',
    url(r'^admin/settings/$', 'design_views.edit_settings',
        {'form_class': EditSettingsForm}, 'localtv_admin_settings'),
    url(r'^admin/users/$', 'user_views.users',
        {'formset_class': AuthorFormSet, 'form_class': AuthorForm},
        'localtv_admin_users'),
    url(r'^admin/bulk_edit/$', 'bulk_edit_views.bulk_edit',
        {'formset_class': VideoFormSet}, 'localtv_admin_bulk_edit')
)