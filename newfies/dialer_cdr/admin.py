from django.contrib import admin
from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _
from django.db.models import *
from dialer_cdr.models import *
from dialer_cdr.forms import *
from dialer_cdr.function_def import *
import csv


class CallrequestAdmin(admin.ModelAdmin):
    """Allows the administrator to view and modify certain attributes
    of a Callrequest."""
    fieldsets = (
        ('Standard options', {
            'fields': ('requestuuid', 'campaign', 'callback_time',
                   'status', 'context', 'timeout', 'hangup_cause',
                   'callerid', 'calltype', 'aleg_gateway', 'voipapp', ),
        }),
        ('Advanced options', {
            'classes': ('collapse',),
            'fields': ('extra_data', 'subscriber', 'variable', 'account', )
        }),
    )
    list_display = ('id', 'campaign', 'requestuuid',
                'callback_time', 'status', 'context', 'callerid', 'calltype',
                'num_attempt', 'last_attempt_time',)
    list_display_links = ('id', 'requestuuid', )
    list_filter = ['callerid', 'callback_time', 'status', 'calltype']
    ordering = ('id', )
    search_fields  = ('requestuuid', )
admin.site.register(Callrequest, CallrequestAdmin)


class VoIPCallAdmin(admin.ModelAdmin):
    """Allows the administrator to view and modify certain attributes
    of a VoIPCall."""
    can_add = False
    detail_title = _("Call Report")
    list_display = ('user', 'used_gateway', 'callid', 'uniqueid',
                    'callerid', 'dnid', 'recipient_number', 'starting_date',
                    'sessiontime', 'disposition', 'recipient_dialcode')

    def has_add_permission(self, request):
        """Removed add permission on VoIP Call Report model

        **Logic Description**:

            * Override django admin has_add_permission method to remove add
              permission on VoIP Call Report model
        """
        if not self.can_add:
            return False
        return super(VoIPCall_ReportAdmin, self).has_add_permission(request)

    def get_urls(self):
        urls = super(VoIPCallAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^$', self.admin_site.admin_view(self.changelist_view)),
            (r'^export_voip_report/$',
             self.admin_site.admin_view(self.export_voip_report)),
        )
        return my_urls + urls

    def queryset(self, request):
        """Override queryset method of django-admin for search parameter

        **Logic Description**:

            * Queryset will be changed as per the search parameter selection
              on changelist_view
        """
        kwargs = {}
        if request.method == 'POST':
            kwargs = voipcall_record_common_fun(request)
        else:
            tday = datetime.today()
            kwargs['starting_date__gte'] = datetime(tday.year,
                                                    tday.month,
                                                    tday.day, 0, 0, 0, 0)

        qs = super(VoIPCallAdmin, self).queryset(request)
        return qs.filter(**kwargs).order_by('-starting_date')

    def changelist_view(self, request, extra_context=None):
        """Override changelist_view method of django-admin for search parameter

        **Attributes**:

            * ``form`` - VoipSearchForm
            * ``template`` - admin/dialer_cdr/voipcall/change_list.html

        **Logic Description**:

            * VoIP Report Record Listing with Search Option & Daily Call Report
              Search Parameters: By date, By status, By billed
        """
        opts = VoIPCall._meta
        app_label = opts.app_label
        kwargs = {}
        form = VoipSearchForm()
        if request.method == 'POST':
            form = VoipSearchForm(request.POST)
            kwargs = voipcall_record_common_fun(request)
        else:
            tday = datetime.today()
            kwargs['starting_date__gte'] = datetime(tday.year,
                                                   tday.month,
                                                   tday.day, 0, 0, 0, 0)

        # Session variable is used to get recrod set with searched option
        # into export file
        request.session['voipcall_record_qs'] = \
        super(VoIPCallAdmin, self).queryset(request).filter(**kwargs)\
        .order_by('-starting_date')

        select_data = \
        {"starting_date": "SUBSTR(CAST(starting_date as CHAR(30)),1,10)"}
        total_data = ''
        # Get Total Rrecords from VoIPCall Report table for Daily Call Report
        total_data = VoIPCall.objects.extra(select=select_data)\
                     .values('starting_date')\
                     .filter(**kwargs).annotate(Count('starting_date'))\
                     .annotate(Sum('sessiontime_real'))\
                     .annotate(Avg('sessiontime_real'))\
                     .order_by('-starting_date')

        # Following code will count total voip calls, duration
        if total_data.count() != 0:
            max_duration = \
            max([x['sessiontime_real__sum'] for x in total_data])
            total_duration = \
            sum([x['sessiontime_real__sum'] for x in total_data])
            total_calls = sum([x['starting_date__count'] for x in total_data])
            total_avg_duration = \
            (sum([x['sessiontime_real__avg']\
            for x in total_data])) / total_data.count()
        else:
            max_duration = 0
            total_duration = 0
            total_calls = 0
            total_avg_duration = 0

        ctx = {
            'form': form,
            'total_data': total_data.reverse(),
            'total_duration': total_duration,
            'total_calls': total_calls,
            'total_avg_duration': total_avg_duration,
            'max_duration': max_duration,
            'opts': opts,
            'model_name': opts.object_name.lower(),
            'app_label': _('VoIP Report'),
            'title': _('Call Report'),
        }
        return super(VoIPCallAdmin, self)\
               .changelist_view(request, extra_context=ctx)

    def export_voip_report(self, request):
        """Export CSV file of VoIP call record

        **Important variable**:

            * request.session['voipcall_record_qs'] - stores voipcall query set
        """
        # get the response object, this can be used as a stream.
        response = HttpResponse(mimetype='text/csv')
        # force download.
        response['Content-Disposition'] = 'attachment;filename=export.csv'
        # the csv writer
        writer = csv.writer(response)

        # super(VoIPCall_ReportAdmin, self).queryset(request)
        qs = request.session['voipcall_record_qs']

        writer.writerow(['user', 'callid', 'callerid', 'dnid',
                         'recipient_number', 'starting_date', 'sessiontime',
                         'sessiontime_real', 'disposition',
                         'voipplan', 'gateway'])
        for i in qs:
            writer.writerow([i.user,
                             i.callid,
                             i.callerid,
                             i.dnid,
                             i.recipient_number,
                             i.starting_date,
                             i.sessiontime,
                             i.sessiontime_real,
                             get_disposition_name(i.disposition),
                             i.voipplan,
                             i.gateway,
                             ])
        return response
admin.site.register(VoIPCall, VoIPCallAdmin)
