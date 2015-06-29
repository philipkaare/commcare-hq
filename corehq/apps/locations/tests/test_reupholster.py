import itertools
from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain

from ..models import Location, SQLLocation, LocationType
from .test_locations import LocationTestBase
from .util import make_loc, delete_all_locations


def _couch_root_locations(domain):
    results = Location.get_db().view('locations/hierarchy',
                                     startkey=[domain], endkey=[domain, {}],
                                     reduce=True, group_level=2)
    ids = [res['key'][-1] for res in results]
    locs = [Location.get(id) for id in ids]
    return [loc for loc in locs if not loc.is_archived]


def _key_bounds(location):
    startkey = list(itertools.chain([location.domain], location.path, ['']))
    endkey = list(itertools.chain(startkey[:-1], [{}]))
    return startkey, endkey


def _couch_descendants(location):
    """return list of all locations that have this location as an ancestor"""
    startkey, endkey = _key_bounds(location)
    return location.view('locations/hierarchy', startkey=startkey,
                         endkey=endkey, reduce=False, include_docs=True).all()


def _couch_children(location):
    """return list of immediate children of this location"""
    startkey, endkey = _key_bounds(location)
    depth = len(location.path) + 2  # 1 for domain, 1 for next location level
    q = location.view('locations/hierarchy', startkey=startkey, endkey=endkey, group_level=depth)
    keys = [e['key'] for e in q if len(e['key']) == depth]
    return location.view('locations/hierarchy', keys=keys, reduce=False, include_docs=True).all()


class TestReupholster(TestCase):
    """
    These tests were written to drive removal of sepecific queries. It
    is safe to delete this when the reuholstering of Location is done
    and somone has written test coverage for the methods used in here.
    """
    @classmethod
    def setUpClass(cls):
        delete_all_locations()
        cls.domain = create_domain('locations-test')
        cls.domain.locations_enabled = True
        bootstrap_location_types(cls.domain.name)

        cls.state = make_loc("Florida", type='state')
        cls.district = make_loc("Duval", type='district', parent=cls.state)
        cls.block = make_loc("Jacksonville", type='block', parent=cls.district)

    @classmethod
    def tearDownClass(cls):
        delete_all_locations()

    def test_root_locations(self):
        self.assertEqual(
            set(_couch_root_locations(self.domain.name)),
            set(Location.root_locations(self.domain.name)),
        )

    def test_descendants(self):
        self.assertEqual(
            _couch_descendants(self.state),
            self.state.descendants,
        )

    def test_children(self):
        self.assertEqual(
            _couch_children(self.state),
            self.state.children,
        )

    def test_replace_all_ids(self):
        original_result = set([r['id'] for r in Location.get_db().view(
            'locations/by_name',
            reduce=False,
        ).all()])

        new_result = set(SQLLocation.objects.location_ids())

        self.assertEqual(original_result, new_result)

    def test_site_codes_for_domain(self):
        original_result = set([r['key'][1] for r in Location.get_db().view(
            'locations/prop_index_site_code',
            reduce=False,
            startkey=[self.domain.name],
            endkey=[self.domain.name, {}],
        ).all()])

        new_result = {
            code.lower() for code in
            (SQLLocation.objects.filter(domain=self.domain)
                                .values_list('site_code', flat=True))
        }

        self.assertEqual(original_result, new_result)

    def test_by_site_code_exists(self):
        couch = _couch_by_site_code(self.domain.name, self.district.site_code)
        sql = _sql_by_site_code(self.domain.name, self.district.site_code)
        self.assertEqual(couch, sql)
        self.assertNotEqual(None, couch)

    def test_by_site_code_doesnt_exist(self):
        couch = _couch_by_site_code(self.domain.name, 'nonexistant_code')
        sql = _sql_by_site_code(self.domain.name, 'nonexistant_code')
        self.assertEqual(couch, sql)
        self.assertEqual(None, couch)


def _couch_by_site_code(domain, site_code):
    # This view coerces the site code to lowercase, so you must also
    # make sure your code is lowercase.  This means that this hasn't been
    # working for all locations: loc.by_site_code(loc.domain, loc.site_code)
    result = Location.get_db().view(
        'locations/prop_index_site_code',
        reduce=False,
        startkey=[domain, site_code.lower()],
        endkey=[domain, site_code.lower(), {}],
    ).first()
    return Location.get(result['id']) if result else None


def _sql_by_site_code(domain, site_code):
    try:
        return (SQLLocation.objects.get(domain=domain, site_code=site_code)
                .couch_location)
    except SQLLocation.DoesNotExist:
        return None


class TestPath(LocationTestBase):
    def test_path(self):
        locs = [
            ('Mass', 'state'),
            ('Suffolk', 'district'),
            ('Boston', 'block'),
        ]
        parent = None
        for name, type_ in locs:
            parent = make_loc(name, type=type_, parent=parent)
        boston = parent
        self.assertEqual(boston.path, boston.sql_location.path)


class TestNoCouchLocationTypes(TestCase):
    @classmethod
    def setUpClass(cls):
        LocationType.objects.create(domain='test-domain', name='test-type')

    @classmethod
    def tearDownClass(cls):
        LocationType.objects.all().delete()

    def setUp(self):
        self.loc = Location(
            domain='test-domain',
            name='test-type',
            location_type='test-type',
        )
        self.loc.save()

    def tearDown(self):
        delete_all_locations()

    def test_change_location_type_name(self):
        loc_type = LocationType.objects.create(domain='test-domain',
                                               name='old-name')
        loc = Location(
            domain='test-domain',
            name='Somewhere',
            location_type='old-name'
        )
        loc.save()
        loc_type.name = 'new-name'
        loc_type.save()
        # You need to look up the location from the db again, because the
        # in-memory version stores the location_type it was created with
        self.assertEqual(Location.get(loc._id).location_type, 'new-name')

    def test_no_location_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            loc = Location(name="Something")
            loc.save()

    def test_type_set_correctly(self):
        self.assertEqual(self.loc.location_type, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')

    def test_get_and_save(self):
        # Get a location from the db, wrap it, access location_type, and save
        loc = Location.get(self.loc._id)
        self.assertEqual(loc.location_type, 'test-type')
        loc.save()

    def test_change_type_later(self):
        new_type = LocationType.objects.create(domain='test-domain',
                                               name='new-type')
        self.loc.location_type = 'new-type'
        self.loc.save()
        self.assertEqual(self.loc.location_type, 'new-type')
        self.assertEqual(self.loc.sql_location.location_type, new_type)
        new_type.delete()

    def test_change_to_nonexistent_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            self.loc.location_type = 'nonexistent-type'
            self.loc.save()
        self.assertEqual(self.loc.location_type, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')
