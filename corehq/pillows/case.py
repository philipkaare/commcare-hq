import copy
from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.form_processor.change_providers import SqlCaseChangeProvider
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX
from dimagi.utils.couch import LockManager
from dimagi.utils.decorators.memoized import memoized
from .base import HQPillow
import logging
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.es_utils import doc_exists, ElasticsearchIndexMeta
from pillowtop.listener import lock_manager
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import PillowReindexer


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"
CASE_ES_TYPE = 'case'


pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)


class CasePillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = CommCareCase
    couch_filter = "case/casedocs"
    es_alias = "hqcases"
    es_type = CASE_ES_TYPE

    es_index = CASE_INDEX
    default_mapping = CASE_MAPPING

    def change_trigger(self, changes_dict):
        doc_dict, lock = lock_manager(
            super(CasePillow, self).change_trigger(changes_dict)
        )
        if doc_dict and doc_dict['doc_type'] == 'CommCareCase-Deleted':
            if doc_exists(self, doc_dict):
                self.get_es_new().delete(self.es_index, self.es_type, doc_dict['_id'])
            return None
        else:
            return LockManager(doc_dict, lock)

    @classmethod
    @memoized
    def calc_meta(cls):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return cls.calc_mapping_hash({
            'es_meta': cls.es_meta,
            'mapping': cls.default_mapping,
        })

    def change_transform(self, doc_dict):
        return transform_case_for_elasticsearch(doc_dict)


def transform_case_for_elasticsearch(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    if not doc_ret.get("owner_id"):
        if doc_ret.get("user_id"):
            doc_ret["owner_id"] = doc_ret["user_id"]
    return doc_ret


def get_sql_case_to_elasticsearch_pillow():
    checkpoint = PillowCheckpoint(
        'sql-cases-to-elasticsearch',
    )
    case_processor = ElasticProcessor(
        elasticseach=get_es_new(),
        index_meta=ElasticsearchIndexMeta(index=CASE_INDEX, type=CASE_ES_TYPE),
        doc_prep_fn=transform_case_for_elasticsearch
    )
    return ConstructedPillow(
        name='SqlCaseToElasticsearchPillow',
        document_store=None,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.CASE_SQL], group_id='sql-cases-to-es'),
        processor=case_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_couch_case_reindexer():
    return PillowReindexer(CasePillow(), CouchViewChangeProvider(
        document_class=CommCareCase,
        view_name='cases_by_owner/view'
    ))


def get_sql_case_reindexer():
    return PillowReindexer(get_sql_case_to_elasticsearch_pillow(), SqlCaseChangeProvider())
