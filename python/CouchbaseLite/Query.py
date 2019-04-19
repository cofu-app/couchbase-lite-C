from ._PyCBL import ffi, lib
from .common import *
from .Collections import *
import json

JSONLanguage = 0
N1QLLanguage = 1

class Query (CBLObject):

    def __init__(self, database, queryString, language = N1QLLanguage):
        CBLObject.__init__(self,
                           lib.CBLQuery_New(database._ref, language, cstr(queryString), gError),
                           "Couldn't create query", gError)
        self.database = database
        self.columnCount = lib.CBLQuery_ColumnCount(self._ref)
        self.sourceCode = queryString

    def __repr__(self):
        return self.__class__.__name__ + "['" + self.sourceCode + "']"

    @property
    def explanation(self):
        return sliceToString(lib.CBLQuery_Explain(self._ref))

    @property
    def columnNames(self):
        if not "_columns" in self.__dict__:
            cols = []
            for i in range(self.columnCount):
                name = sliceToString( lib.CBLQuery_ColumnName(self._ref, i) )
                cols.append(name)
            self._columns = cols
        return self._columns

    def setParameters(self, params):
        jsonStr = json.dumps(params)
        lib.CBLQuery_SetParametersFromJSON(self._ref, cstr(jsonStr))

    def execute(self):
        """Executes the query and returns a Generator of QueryResult objects."""
        results = lib.CBLQuery_Execute(self._ref, gError)
        if not results:
            raise CBLException("Query failed", gError)
        try:
            lastResult = None
            while lib.CBLResultSet_Next(results):
                if lastResult:
                    lastResult.invalidate()
                lastResult = QueryResult(self, results)
                yield lastResult
        finally:
            lib.CBL_Release(results)


class JSONQuery (Query):
    def __init__(self, database, jsonQuery):
        if not isinstance(jsonQuery, str):
            jsonQuery = json.dumps(jsonQuery)
        Query.__init__(self, database, jsonQuery, JSONLanguage)

class N1QLQuery (Query):
    def __init__(self, database, n1ql):
        Query.__init__(self, database, n1ql, N1QLLanguage)


class QueryResult (object):
    """A container representing a query result. It can be indexed using either
       integers (to access columns in the order they were declared in the query)
       or strings (to access columns by name.)"""
    def __init__(self, query, results):
        self.query = query
        self._ref = results

    def __repr__(self):
        if self._ref == None:
            return "QueryResult[invalidated]"
        return "QueryResult" + json.dumps(self.asDictionary())

    def invalidate(self):
        self._ref = None
        self.query = None

    def __len__(self):
        return self.query.columnCount

    def __getitem__(self, key):
        if self._ref == None:
            raise CBLException("Accessing a non-current query result row")
        if isinstance(key, int):
            if key < 0 or key >= self.query.columnCount:
                raise IndexError("Column index out of range")
            item = lib.CBLResultSet_ValueAtIndex(self._ref, key)
        elif isinstance(key, str):
            item = lib.CBLResultSet_ValueForKey(self._ref, key)
            if item == None:
                raise KeyError("No such column in Query")
        else:
            # TODO: Handle slices
            raise KeyError("invalid query result key")
        return decodeFleece(item)

    def __contains__(self, key):
        if self._ref == None:
            raise CBLException("Accessing a non-current query result row")
        if isinstance(key, int):
            if key < 0 or key >= self.query.columnCount:
                return False
            return (lib.CBLResultSet_ValueAtIndex(self._ref, key) != None)
        elif isinstance(key, str):
            return (lib.CBLResultSet_ValueForKey(self._ref, key) != None)
        else:
            return False

    def asArray(self):
        result = []
        for i in range(0, self.query.columnCount):
            result.append(self[i])
        return result

    def asDictionary(self):
        result = {}
        keys = self.query.columnNames
        for i in range(0, self.query.columnCount):
            item = lib.CBLResultSet_ValueAtIndex(self._ref, i)
            if lib.FLValue_GetType(item) != lib.kFLUndefined:
                result[keys[i]] = decodeFleece(item)
        return result
