import uuid
from django.test import TestCase, SimpleTestCase
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from corehq.form_processor.backends.couch.casedb import CaseDbCacheCouch
from corehq.form_processor.backends.sql.casedb import CaseDbCacheSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface


class CaseDbCacheTest(TestCase):
    """
    Tests the functionality of the CaseDbCache object
    """
    @classmethod
    def setUpClass(cls):
        cls.interface = FormProcessorInterface()

    def testDomainCheck(self):
        id = uuid.uuid4().hex
        FormProcessorInterface().post_case_blocks([
                CaseBlock(
                    create=True, case_id=id,
                    user_id='some-user'
                ).as_xml()
            ], {'domain': 'good-domain'}
        )
        bad_cache = self.interface.casedb_cache(domain='bad-domain')
        try:
            bad_cache.get(id)
            self.fail('domain security check failed to raise exception')
        except IllegalCaseId:
            pass
        good_cache = self.interface.casedb_cache(domain='good-domain')
        case = good_cache.get(id)
        self.assertEqual('some-user', case.user_id) # just sanity check it's the right thing

    def testDocTypeCheck(self):
        id = uuid.uuid4().hex
        CommCareCase.get_db().save_doc({
            "_id": id,
            "doc_type": "AintNoCasesHere"
        })
        cache = self.interface.casedb_cache()
        try:
            cache.get(id)
            self.fail('doc type security check failed to raise exception')
        except IllegalCaseId:
            pass

        doc_back = CommCareCase.get_db().get(id)
        self.assertEqual("AintNoCasesHere", doc_back['doc_type'])

    def testGetPopulatesCache(self):
        case_ids = _make_some_cases(3)
        cache = self.interface.casedb_cache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        for i, id in enumerate(case_ids):
            case = cache.get(id)
            self.assertEqual(str(i), case.my_index)

        for id in case_ids:
            self.assertTrue(cache.in_cache(id))

    def testSetPopulatesCache(self):
        case_ids = _make_some_cases(3)
        cache = self.interface.casedb_cache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        for id in case_ids:
            cache.set(id, CommCareCase.get(id))

        for i, id in enumerate(case_ids):
            self.assertTrue(cache.in_cache(id))
            case = cache.get(id)
            self.assertEqual(str(i), case.my_index)

    def testPopulate(self):
        case_ids = _make_some_cases(3)
        cache = self.interface.casedb_cache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        cache.populate(case_ids)
        for id in case_ids:
            self.assertTrue(cache.in_cache(id))

        #  sanity check
        for i, id in enumerate(case_ids):
            case = cache.get(id)
            self.assertEqual(str(i), case.my_index)

    def testStripHistory(self):
        case_ids = _make_some_cases(3)

        history_cache = self.interface.casedb_cache()
        for i, id in enumerate(case_ids):
            self.assertFalse(history_cache.in_cache(id))
            case = history_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) > 0)

        nohistory_cache = self.interface.casedb_cache(strip_history=True)
        for i, id in enumerate(case_ids):
            self.assertFalse(nohistory_cache.in_cache(id))
            case = nohistory_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) == 0)

        more_case_ids = _make_some_cases(3)
        history_cache.populate(more_case_ids)
        nohistory_cache.populate(more_case_ids)

        for i, id in enumerate(more_case_ids):
            self.assertTrue(history_cache.in_cache(id))
            case = history_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) > 0)

        for i, id in enumerate(more_case_ids):
            self.assertTrue(nohistory_cache.in_cache(id))
            case = nohistory_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) == 0)

    def test_nowrap(self):
        case_ids = _make_some_cases(1)
        cache = self.interface.casedb_cache(wrap=False)
        case = cache.get(case_ids[0])
        self.assertTrue(isinstance(case, dict))
        self.assertFalse(isinstance(case, CommCareCase))


class CaseDbCacheNoDbTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.interface = FormProcessorInterface()

    def test_couch_wrap_lock_dependency_couch(self):
        # valid combinations
        CaseDbCacheCouch(domain='some-domain', lock=False, wrap=True)
        CaseDbCacheCouch(domain='some-domain', lock=False, wrap=False)
        CaseDbCacheCouch(domain='some-domain', lock=True, wrap=True)
        with self.assertRaises(ValueError):
            # invalid
            CaseDbCacheCouch(domain='some-domain', lock=True, wrap=False)

    def test_sql_wrap_support(self):
        CaseDbCacheSQL(domain='some-domain', wrap=True)
        with self.assertRaises(ValueError):
            # invalid
            CaseDbCacheSQL(domain='some-domain', wrap=False)


def _make_some_cases(howmany, domain='dbcache-test'):
    ids = [uuid.uuid4().hex for i in range(howmany)]
    FormProcessorInterface().post_case_blocks([
        CaseBlock(
            create=True,
            case_id=ids[i],
            user_id='some-user',
            update={
                'my_index': i,
            }
        ).as_xml() for i in range(howmany)
    ], {'domain': domain})
    return ids