from corehq.util.couch_helpers import paginate_view
from pillowtop.reindexer.change_providers.interface import ChangeProvider


class CouchViewChangeProvider(ChangeProvider):

    def __init__(self, document_class, view_name, chunk_size=100, view_kwargs=None):
        self.document_class = document_class
        self._couch_db = document_class.get_db()
        self._view_name = view_name
        self._chunk_size = chunk_size
        self._view_kwargs = view_kwargs or {}

    def iter_changes(self, start_from=None):
        view_kwargs = copy(self._view_kwargs)
        if start_from is not None:
            # todo: should we abstract out how the keys work inside this class?
            view_kwargs['startkey'] = start_from
        for item in paginate_view(self._couch_db, self._view_name, self._chunk_size, **view_kwargs):
            # todo: need to transform to a `Change` object
            yield item
