import datetime
from collections import namedtuple

import pytz
from django.test import SimpleTestCase
from mock import patch

from corehq.apps.export.filters import FormSubmittedByFilter
from corehq.apps.export.forms import FilterFormESExportDownloadForm


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
class TestFilterFormESExportDownloadForm(SimpleTestCase):

    def setUp(self):
        DomainObject = namedtuple('DomainObject', ['uses_locations', 'name'])
        self.project = DomainObject(False, "foo")

    def test_get_datespan_filter(self):
        form_data = {'date_range': '2015-06-25 to 2016-02-19'}
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid())
        datespan_filter = form._get_datespan_filter()
        self.assertEqual(datespan_filter.lt, datetime.datetime(2016, 2, 20, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.gte, datetime.datetime(2015, 6, 25, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.lte, None)
        self.assertEqual(datespan_filter.gt, None)

    def test_get_group_filter(self):
        """
        Confirm that FilterFormESExportDownloadForm._get_group_filter() returns
        a filter with the correct group_id and correct base_filter.
        """
        form_data = {
            'type_or_group': 'group',
            'group': 'some_group_id',
            'date_range': '2015-06-25 to 2016-02-19',
        }
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid(), "Form had the following errors: {}".format(form.errors))
        group_filter = form._get_group_filter()
        self.assertEqual(group_filter.group_id, 'some_group_id')
        self.assertEqual(group_filter.base_filter, FormSubmittedByFilter)

    def test_get_user_filter(self):
        """
        Confirm that FilterFormESExportDownloadForm._get_user_filter()
        returns a FormSubmittedByFilter with the correct user ids. This test
        DOES NOT verify that BaseFilterExportDownloadForm._get_filtered_users()
        retrieves the correct user ids from the database.
        """
        form_data = {
            'type_or_group': 'type',
            'user_types': ['mobile', 'unknown'],
            'group': '',
            'date_range': '2015-06-25 to 2016-02-19',
        }

        def mock_users_matching_filter(domain, user_filters):
            return [None, "some_user_id", "some_other_user_id"]

        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)

        self.assertTrue(form.is_valid(), "Form had the following errors: {}".format(form.errors))
        with patch("corehq.apps.export.forms.users_matching_filter", mock_users_matching_filter):
            user_filter = form._get_user_filter()
        self.assertEqual(user_filter.submitted_by, [None, "some_user_id", "some_other_user_id"])
