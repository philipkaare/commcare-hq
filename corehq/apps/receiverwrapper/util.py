from collections import namedtuple
import re
from couchdbkit import ResourceNotFound
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.domain.auth import determine_authtype_from_request
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.submission_post import SubmissionPost
from corehq.util.quickcache import quickcache
from couchforms.models import DefaultAuthContext


def get_submit_url(domain, app_id=None):
    if app_id:
        return "/a/{domain}/receiver/{app_id}/".format(domain=domain, app_id=app_id)
    else:
        return "/a/{domain}/receiver/".format(domain=domain)


def submit_form_locally(instance, domain, **kwargs):
    # intentionally leave these unauth'd for now
    kwargs['auth_context'] = kwargs.get('auth_context') or DefaultAuthContext()
    response, xform, cases = SubmissionPost(
        domain=domain,
        instance=instance,
        **kwargs
    ).run()
    if not 200 <= response.status_code < 300:
        raise LocalSubmissionError('Error submitting (status code %s): %s' % (
            response.status_code,
            response.content,
        ))
    return response, xform, cases


def get_meta_appversion_text(form_metadata):
    try:
        text = form_metadata['appVersion']
    except KeyError:
        return None

    # just make sure this is a longish string and not something like '2.0'
    if isinstance(text, (str, unicode)) and len(text) > 5:
        return text
    else:
        return None


@quickcache(['domain', 'build_id'], timeout=24*60*60)
def get_version_from_build_id(domain, build_id):
    """
    fast lookup of app version number given build_id

    implemented as simple caching around _get_version_from_build_id

    """
    if not build_id:
        return None

    try:
        build = ApplicationBase.get(build_id)
    except ResourceNotFound:
        return None
    if not build.copy_of:
        return None
    elif build.domain != domain:
        return None
    else:
        return build.version


def get_version_from_appversion_text(appversion_text):
    """
    >>> # these first two could certainly be replaced
    >>> # with more realistic examples, but I didn't have any on hand
    >>> get_version_from_appversion_text('foofoo #102 barbar')
    102
    >>> get_version_from_appversion_text('foofoo b[99] barbar')
    99
    >>> get_version_from_appversion_text(
    ...     'CommCare ODK, version "2.11.0"(29272). App v65. '
    ...     'CommCare Version 2.11. Build 29272, built on: February-14-2014'
    ... )
    65
    >>> get_version_from_appversion_text(
    ...     'CommCare ODK, version "2.4.1"(10083). App v19.'
    ...     'CommCare Version 2.4. Build 10083, built on: March-12-2013'
    ... )
    19
    """
    patterns = [
        r' #(\d+) ',
        'b\[(\d+)\]',
        r'App v(\d+).',
    ]
    version_string = _first_group_match(appversion_text, patterns)
    if version_string:
        return int(version_string)


def get_commcare_version_from_appversion_text(appversion_text):
    """
    >>> get_commcare_version_from_appversion_text(
    ...     'CommCare ODK, version "2.11.0"(29272). App v65. '
    ...     'CommCare Version 2.11. Build 29272, built on: February-14-2014'
    ... )
    '2.11.0'
    >>> get_commcare_version_from_appversion_text(
    ...     'CommCare ODK, version "2.4.1"(10083). App v19.'
    ...     'CommCare Version 2.4. Build 10083, built on: March-12-2013'
    ... )
    '2.4.1'
    """
    patterns = [
        r'version "([\d.]+)"',
    ]
    return _first_group_match(appversion_text, patterns)


def _first_group_match(text, patterns):
    if text:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.groups()[0]


class BuildVersionSource:
    BUILD_ID = object()
    APPVERSION_TEXT = object()
    XFORM_VERSION = object()
    NONE = object()


AppVersionInfo = namedtuple('AppInfo', ['build_version', 'commcare_version', 'source'])


def get_app_version_info(domain, build_id, xform_version, xform_metadata):
    """
    there are a bunch of unreliable places to look for a build version
    this abstracts that out

    """
    appversion_text = get_meta_appversion_text(xform_metadata)
    commcare_version = get_commcare_version_from_appversion_text(appversion_text)
    build_version = get_version_from_build_id(domain, build_id)
    if build_version:
        return AppVersionInfo(build_version, commcare_version, BuildVersionSource.BUILD_ID)

    build_version = get_version_from_appversion_text(appversion_text)
    if build_version:
        return AppVersionInfo(build_version, commcare_version, BuildVersionSource.APPVERSION_TEXT)

    if xform_version and xform_version != '1':
        return AppVersionInfo(int(xform_version), commcare_version, BuildVersionSource.XFORM_VERSION)

    return AppVersionInfo(None, commcare_version, BuildVersionSource.NONE)


@quickcache(['domain', 'build_or_app_id'], timeout=24*60*60)
def get_app_and_build_ids(domain, build_or_app_id):
    if not build_or_app_id:
        return build_or_app_id, None

    try:
        app_json = ApplicationBase.get_db().get(build_or_app_id)
    except ResourceNotFound:
        pass
    else:
        if domain == app_json.get('domain'):
            copy_of = app_json.get('copy_of')
            if copy_of:
                return copy_of, build_or_app_id
    return build_or_app_id, None


def determine_authtype(request):
    if request.GET.get('authtype'):
        return request.GET['authtype']

    return determine_authtype_from_request(request)
