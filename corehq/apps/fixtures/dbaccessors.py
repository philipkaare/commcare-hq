def get_number_of_fixture_data_types_in_domain(domain):
    from corehq.apps.fixtures.models import FixtureDataType
    num_fixtures = FixtureDataType.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'FixtureDataType'],
        endkey=[domain, 'FixtureDataType', {}],
        reduce=True,
        group_level=2,
    ).first()
    return num_fixtures['value'] if num_fixtures is not None else 0


def get_fixture_data_types_in_domain(domain):
    # We're getting an odd error from cloudant where deleted docs are being
    # returned in the view.  Until that's resolved, we can manually filter out
    # deleted docs here.  See ticket for updates:
    # http://manage.dimagi.com/default.asp?216573
    from corehq.apps.fixtures.models import FixtureDataType
    return [row for row in FixtureDataType.view(
        'by_domain_doc_type_date/view',
        endkey=[domain, 'FixtureDataType'],
        startkey=[domain, 'FixtureDataType', {}],
        reduce=False,
        include_docs=True,
        descending=True,
    ) if isinstance(row, FixtureDataType)]


def get_owner_ids_by_type(domain, owner_type, data_item_id):
    from corehq.apps.fixtures.models import FixtureOwnership
    assert owner_type in FixtureOwnership.owner_type.choices, \
        "Owner type must be in {}".format(FixtureOwnership.owner_type.choices)
    return FixtureOwnership.get_db().view(
        'fixtures/ownership',
        key=[domain, '{} by data_item'.format(owner_type), data_item_id],
        reduce=False,
        wrapper=lambda r: r['value']
    )
