import random
import string
from uuid import uuid4

from datetime import datetime

from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.models import XFormInstanceSQL, XFormAttachmentSQL, CommCareCaseSQL, \
    CaseTransaction, CommCareCaseIndexSQL, CaseAttachmentSQL, XFormOperationSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from crispy_forms.tests.utils import override_settings
from dimagi.utils.decorators.memoized import memoized

DOMAIN = 'test-domain'


@override_settings(UNIT_TESTING=True, TESTS_SHOULD_USE_SQL_BACKEND=True)
def test_table_sizes():
    """
    Insert 10000 rows into the form_data table. Run scripts/get_table_sizes.sh to
    output the resulting DB size.
    """
    num_cases = 10000
    forms_per_case = 10

    FormProcessorTestUtils.delete_all_xforms()
    XFormAttachmentSQL.objects.all().delete()
    XFormOperationSQL.objects.all().delete()
    CommCareCaseIndexSQL.objects.all().delete()
    CaseAttachmentSQL.objects.all().delete()
    CaseTransaction.objects.all().delete()
    CommCareCaseSQL.objects.all().delete()
    for i in range(num_cases):
        _create_case_and_forms(forms_per_case)


def _create_case_and_forms(forms_per_case):

    forms = [get_form() for i in range(forms_per_case)]
    case = CommCareCaseSQL(
        case_id=uuid4(),
        domain=DOMAIN,
        type='test case type',
        owner_id=uuid4().hex,
        opened_on=datetime.utcnow(),
        modified_on=datetime.utcnow(),
        modified_by=uuid4().hex,
        server_modified_on=datetime.utcnow(),
        name=_random_string(15),
        case_json=_case_json(100)
    )
    for form in forms[1:]:
        FormProcessorSQL.save_xform(form)

    for form in forms:
        case.track_create(CaseTransaction.form_transaction(case, form))
    cases = [case]
    FormProcessorSQL.save_processed_models([forms[0]], cases)


def get_form():
    form = XFormInstanceSQL(
        form_id=uuid4().hex,
        xmlns='http://openrosa.org/formdesigner/' + str(uuid4()).upper(),
        received_on=datetime.utcnow(),
        user_id=uuid4().hex,
        domain=DOMAIN,
        auth_context=AuthContext(authenticated=True, domain='test-domain', user_id=uuid4().hex).to_json(),
        last_sync_token=uuid4(),
        date_header=datetime.now(),
        initial_processing_complete=True,
        openrosa_headers={
            "HTTP_DATE": "Mon, 11 Apr 2011 18:24:43 GMT"
          },
        submit_ip='127.0.0.1'
    )
    attachments = [XFormAttachmentSQL(
        name='form.xml',
        attachment_id=uuid4(),
        content_type='text/xml',
        md5=_random_string(32),
    )]
    form.unsaved_attachments = attachments
    return form


@memoized
def _case_json(num_props):
    return {_random_string(15): _random_string(50) for i in range(num_props)}


def _random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


if __name__ == '__main__':
    test_table_sizes()
