"""
example walkthrough:
------------------------------------------------------------------------

HOSTS = [{'host':'192.168.56.101', 'port':9200}]
INDEX = 'documents0'
PATH = '/var/www/media/base/ddr-testing-141'
PATH = '/var/www/media/base/ddr-densho-2'
PATH = '/var/www/media/base/ddr-densho-10'

HOSTS = [{'host':'192.168.56.120', 'port':9200}]
INDEX = 'dev'
PATH = '/var/www/media/ddr'

from DDR import docstore
from DDR import models

docstore.delete_index(HOSTS, INDEX)

docstore.create_index(HOSTS, INDEX)

docstore.put_mappings(HOSTS, INDEX, docstore.MAPPINGS_PATH, models.MODELS_DIR)
docstore.put_facets(HOSTS, INDEX, docstore.FACETS_PATH)

# Delete a collection
docstore.delete(HOSTS, INDEX, os.path.basename(PATH), recursive=True)

# Repository, organization metadata
docstore.post_json(HOSTS, INDEX, 'repository', 'ddr', '%s/ddr/repository.json' % PATH)
# Do this once per organization.
docstore.post_json(HOSTS, INDEX, 'organization', 'REPO-ORG', '%s/REPO-ORG/organization.json' % PATH)

docstore.index(HOSTS, INDEX, PATH, recursive=True, public=True )

------------------------------------------------------------------------
"""
from __future__ import print_function
from datetime import datetime
import json
import logging
logger = logging.getLogger(__name__)
import os

from elasticsearch import Elasticsearch, TransportError

from DDR import natural_sort
from DDR import models
from DDR.models.identifier import Identifier

from DDR import MAPPINGS_PATH
from DDR import FACETS_PATH

MAX_SIZE = 1000000
DEFAULT_PAGE_SIZE = 20

SUCCESS_STATUSES = [200, 201]
STATUS_OK = ['completed']
PUBLIC_OK = [1,'1']

"""
ddr-local

elasticsearch.add_document(settings.ELASTICSEARCH_HOST_PORT, 'ddr', 'collection', os.path.join(collection_path, 'collection.json'))
elasticsearch.index(settings.MEDIA_BASE, settings.ELASTICSEARCH_HOST_PORT, 'ddr')
elasticsearch.status(settings.ELASTICSEARCH_HOST_PORT)
elasticsearch.delete_index(settings.ELASTICSEARCH_HOST_PORT, 'ddr')

ddr-public

modelfields = elasticsearch._model_fields(MODELS_DIR, MODELS)
cached = elasticsearch.query(host=host, index=index, model=model,
raw = elasticsearch.get(HOST, index=settings.DOCUMENT_INDEX, model=Repository.model, id=id)
document = elasticsearch.get(settings.ELASTICSEARCH_HOST_PORT, settings.DOCUMENT_INDEX,
elasticsearch.list_facets():
results = elasticsearch.facet_terms(settings.ELASTICSEARCH_HOST_PORT,
"""


def _get_connection( hosts ):
    es = Elasticsearch(hosts)
    return es

def make_index_name( text ):
    """Takes input text and generates a legal Elasticsearch index name.
    
    I can't find documentation of what constitutes a legal ES index name,
    but index names must work in URLs so we'll say alnum plus _, ., and -.
    
    @param text
    @returns name
    """
    LEGAL_NONALNUM_CHARS = ['-', '_', '.']
    SEPARATORS = ['/', '\\',]
    name = []
    if text:
        text = os.path.normpath(text)
        for n,char in enumerate(text):
            if char in SEPARATORS:
                char = '-'
            if n and (char.isalnum() or (char in LEGAL_NONALNUM_CHARS)):
                name.append(char.lower())
            elif char.isalnum():
                name.append(char.lower())
    return ''.join(name)

def index_exists( hosts, index ):
    """
    @param hosts: list of dicts containing host information.
    @param index:
    @param model:
    @param document_id:
    """
    es = _get_connection(hosts)
    return es.indices.exists(index=index)

def index_names( hosts ):
    """Returns list of index names
    """
    indices = []
    es = _get_connection(hosts)
    status = es.indices.status()
    for name in status['indices'].keys():
        indices.append(name)
    return indices

def _parse_cataliases( cataliases ):
    """
    Sample input:
    u'ddrworkstation documents0 \nwd5000bmv-2 documents0 \n'

    @param cataliases: Raw output of es.cat.aliases(h=['index','alias'])
    @returns: list of (index,alias) tuples
    """
    indices_aliases = []
    for line in cataliases.strip().split('\n'):
        # cat.aliases arranges data in columns so rm extra spaces
        while '  ' in line:
            line = line.replace('  ', ' ')
        if line:
            i,a = line.strip().split(' ')
            indices_aliases.append( (i,a) )
    return indices_aliases

def set_alias( hosts, alias, index, remove=False ):
    """Point alias at specified index; create index if doesn't exist.
    
    IMPORTANT: There is only ever ONE index at a time. All existing
    aliases are deleted before specified one is created.
    
    @param hosts: list of dicts containing host information.
    @param alias: Name of the alias
    @param index: Name of the alias' target index.
    @param remove: boolean
    """
    logger.debug('set_alias(%s, %s, %s, %s)' % (hosts, alias, index, remove))
    alias = make_index_name(alias)
    index = make_index_name(index)
    es = _get_connection(hosts)
    if not index_exists(hosts, index):
        create_index(hosts, index)
    # delete existing aliases
    for i,a in _parse_cataliases(es.cat.aliases(h=['index','alias'])):
        es.indices.delete_alias(index=i, name=a)
    if not remove:
        # set the alias
        es.indices.put_alias(index=index, name=alias, body='')

def target_index( hosts, alias ):
    """Get the name of the index to which the alias points
    
    >>> es.cat.aliases(h=['alias','index'])
    u'documents0 wd5000bmv-2 \n'
    
    @param hosts: list of dicts containing host information.
    @param alias: Name of the alias
    @returns: name of target index
    """
    alias = make_index_name(alias)
    target = []
    es = _get_connection(hosts)
    for i,a in _parse_cataliases(es.cat.aliases(h=['index','alias'])):
        if a == alias:
            target = i
    return target

def create_index( hosts, index ):
    """Creates the specified index if it does not already exist.
    
    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @returns: JSON dict with status codes and responses
    """
    logger.debug('_create_index(%s, %s)' % (hosts, index))
    body = {
        'settings': {},
        'mappings': {}
        }
    es = _get_connection(hosts)
    status = es.indices.create(index=index, body=body)
    return status

def delete_index( hosts, index ):
    """Delete the specified index.
    
    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @returns: JSON dict with status code and response
    """
    logger.debug('_delete_index(%s, %s)' % (hosts, index))
    es = _get_connection(hosts)
    if index_exists( hosts, index ):
        status = es.indices.delete(index=index)
        return status
    return '{"status":500, "message":"Index does not exist"}'


# Each item in this list is a mapping dict in the format ElasticSearch requires.
# Mappings for each type have to be uploaded individually (I think).
def _make_mappings( mappings ):
    """Takes MAPPINGS and adds field properties from module.FIELDS['elasticsearch']
    
    Returns a nice list of mapping dicts.
    
    DDR mappings are constructed from 'elasticsearch' var for each field in the FIELDS list in the (collection/entity/file)module in the 'ddr' repo.
    
    Module.FIELDS should be formatted thusly:
        {
            "group": "",
            "name": "record_created",
            ...
            "elasticsearch": {
                "public": true,
                "properties": {
                    "type":"date", "index":"not_analyzed", "store":"yes", "format":"yyyy-MM-dd'T'HH:mm:ss"
                },
                "display": "datetime"
            },
            ...
    
    ['elasticsearch']['public']
    Fields marked '"public":true' will be included with documents are POSTed to ElasticSearch.  Fields without this value are not included at all.
    
    ['elasticsearch']['display']
    Fields with a value in "display" will be included with documents are POSTed to ElasticSearch, and will be displayed in the public interface using the function in the value for "display".  If this is left blank the field will be POSTed but will not be shown in the interface.
    
    ['elasticsearch']['properties']
    The contents of this field will be inserted directly into the mappings document.  See ElasticSearch documentation for more information: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/mapping.html
    
    @param mappings: data structure from loading mappings.json
    @return: List of mappings dicts.
    """
    ID_PROPERTIES = {'type':'string', 'index':'not_analyzed', 'store':True}
    for mapping in mappings['documents']:
        model = mapping.keys()[0]
        module = models.MODULES[model]
        for field in module.FIELDS:
            fname = field['name']
            mapping[model]['properties'][fname] = field['elasticsearch']['properties']
        # mappings for parent_id, etc
        if model == 'collection':
            mapping[model]['properties']['parent_id'] = ID_PROPERTIES
        elif model == 'entity':
            mapping[model]['properties']['parent_id'] = ID_PROPERTIES
            mapping[model]['properties']['collection_id'] = ID_PROPERTIES
        elif model == 'file':
            mapping[model]['properties']['parent_id'] = ID_PROPERTIES
            mapping[model]['properties']['collection_id'] = ID_PROPERTIES
            mapping[model]['properties']['entity_id'] = ID_PROPERTIES
        return mappings
    return []

def put_mappings( hosts, index, mappings_path, models_dir ):
    """Puts mappings from file into ES.
    
    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @param path: Absolute path to dir containing facet files.
    @param mappings_path: Absolute path to mappings JSON.
    @param models_dir: Absolute path to dir containing model definitions.
    @returns: JSON dict with status code and response
    """
    logger.debug('put_mappings(%s, %s, %s, %s)' % (hosts, index, mappings_path, models_dir))
    with open(mappings_path, 'r') as f:
        mappings = json.loads(f.read())
    mappings_list = _make_mappings(mappings)['documents']
    statuses = []
    es = _get_connection(hosts)
    for mapping in mappings_list:
        model = mapping.keys()[0]
        logger.debug(model)
        logger.debug(json.dumps(mapping, indent=4, separators=(',', ': '), sort_keys=True))
        status = es.indices.put_mapping(index=index, doc_type=model, body=mapping)
        statuses.append( {'model':model, 'status':status} )
    return statuses

def put_facets( hosts, index, path=FACETS_PATH ):
    """PUTs facets from file into ES.
    
    curl -XPUT 'http://localhost:9200/meta/facet/format' -d '{ ... }'
    >>> elasticsearch.put_facets('192.168.56.120:9200', 'meta', '/usr/local/src/ddr-cmdln/ddr/DDR/models/facets.json')
    
    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @param path: Absolute path to dir containing facet files.
    @returns: JSON dict with status code and response
    """
    logger.debug('index_facets(%s, %s, %s)' % (hosts, index, path))
    statuses = []
    es = _get_connection(hosts)
    for facet_json in os.listdir(FACETS_PATH):
        facet = facet_json.split('.')[0]
        srcpath = os.path.join(path, facet_json)
        with open(srcpath, 'r') as f:
            data = json.loads(f.read().strip())
            status = es.index(index=index, doc_type='facet', id=facet, body=data)
            statuses.append(status)
    return statuses

def list_facets( path=FACETS_PATH ):
    facets = []
    for filename in os.listdir(path):
        fn,ext = os.path.splitext(filename)
        if ext and (ext == '.json'):
            facets.append(fn)
    return facets

def facet_terms( hosts, index, facet, order='term', all_terms=True, model=None ):
    """Gets list of terms for the facet.
    
    $ curl -XGET 'http://192.168.56.101:9200/ddr/entity/_search?format=yaml' -d '{
      "fields": ["id"],
      "query": { "match_all": {} },
      "facets": {
        "genre_facet_result": {
          "terms": {
            "order": "count",
            "field": "genre"
          }
        }
      }
    }'
    Sample results:
        {
          u'_type': u'terms',
          u'missing': 203,
          u'total': 49,
          u'other': 6,
          u'terms': [
            {u'term': u'photograph', u'count': 14},
            {u'term': u'ephemera', u'count': 6},
            {u'term': u'advertisement', u'count': 6},
            {u'term': u'book', u'count': 5},
            {u'term': u'architecture', u'count': 3},
            {u'term': u'illustration', u'count': 2},
            {u'term': u'fieldnotes', u'count': 2},
            {u'term': u'cityscape', u'count': 2},
            {u'term': u'blank_form', u'count': 2},
            {u'term': u'portrait, u'count': 1'}
          ]
        }

    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @param facet: Name of field
    @param order: term, count, reverse_term, reverse_count
    @param model: (optional) Type of object ('collection', 'entity', 'file')
    @returns raw output of facet query
    """
    payload = {
        "fields": ["id"],
        "query": { "match_all": {} },
        "facets": {
            "results": {
                "terms": {
                    "size": MAX_SIZE,
                    "order": order,
                    "all_terms": all_terms,
                    "field": facet
                }
            }
        }
    }
    es = _get_connection(hosts)
    results = es.search(index=index, doc_type=model, body=payload)
    return results['facets']['results']

def repo( hosts, index, path ):
    """Add or update base repository metadata.
    """
    # get and validate file
    with open(path, 'r') as f:
        body = f.read()
    data = json.loads(body)
    if (not (data.get('id') and  data.get('repo'))) or (data.get('org')):
        raise Exception('Data file is not well-formed.')
    document_id = data['id']
    # add/update
    doctype = 'repository'
    es = _get_connection(hosts)
    results = es.index(index=index, doc_type=doctype, id=document_id, body=data)
    return results

def org( hosts, index, path, remove=False):
    """Add/update or remove organization metadata.
    """
    # get and validate file
    with open(path, 'r') as f:
        body = f.read()
    data = json.loads(body)
    if (not (data.get('id') and  data.get('repo') and  data.get('org'))):
        raise Exception('Data file is not well-formed.')
    document_id = data['id']
    # add/update/remove
    doctype = 'organization'
    es = _get_connection(hosts)
    if remove and exists(hosts, index, doctype, document_id):
        results = es.delete(index=index, doc_type=doctype, id=document_id)
    else:
        results = es.index(index=index, doc_type=doctype, id=document_id, body=data)
    return results


# post -----------------------------------------------------------------

def _is_publishable( data ):
    """Determines if object is publishable
    
    TODO not specific to elasticsearch - move this function so other modules can use
    
    TODO Does not inherit status/public of parent(s)!
    TODO This function assumes model contains 'public' and 'status' fields.
    
    >>> data = [{'id': 'ddr-testing-123-1'}]
    >>> _is_publishable(data)
    False
    >>> data = [{'id': 'ddr-testing-123-1'}, {'public':0}, {'status':'inprogress'}]
    >>> _is_publishable(data)
    False
    >>> data = [{'id': 'ddr-testing-123-1'}, {'public':0}, {'status':'completed'}]
    >>> _is_publishable(data)
    False
    >>> data = [{'id': 'ddr-testing-123-1'}, {'public':1}, {'status':'inprogress'}]
    >>> _is_publishable(data)
    False
    >>> data = [{'id': 'ddr-testing-123-1'}, {'public':1}, {'status':'completed'}]
    >>> _is_publishable(data)
    True
    
    @param data: Standard DDR list-of-dicts data structure.
    @returns: True/False
    """
    publishable = False
    status = None
    public = None
    for field in data:
        fieldname = field.keys()[0]
        if   fieldname == 'status': status = field['status']
        elif fieldname == 'public': public = field['public']
    # collections, entities
    if status and public and (status in STATUS_OK) and (public in PUBLIC_OK):
        return True
    # files
    elif (status == None) and public and (public in PUBLIC_OK):
        return True
    return False

def _filter_payload( data, public_fields ):
    """If requested, removes non-public fields from document before sending to ElasticSearch.
    
    >>> data = [{'id': 'ddr-testing-123-1'}, {'title': 'Title'}, {'secret': 'this is a secret'}]
    >>> public_fields = ['id', 'title']
    >>> _filter_payload(data, public_fields)
    removed secret
    >>> data
    [{'id': 'ddr-testing-123-1'}, {'title': 'Title'}]
    
    @param data: Standard DDR list-of-dicts data structure.
    @param public_fields: List of field names; if present, fields not in list will be removed.
    """
    if public_fields and data and isinstance(data, list):
        for field in data[1:]:
            fieldname = field.keys()[0]
            if fieldname not in public_fields:
                data.remove(field)
                logging.debug('removed %s' % fieldname)

def _clean_controlled_vocab( data ):
    """Extract topics IDs from textual control-vocab texts.

    >>> _clean_controlled_vocab('Topics [123]')
    ['123']
    >>> _clean_controlled_vocab(['Topics [123]'])
    ['123']
    >>> _clean_controlled_vocab(['123'])
    ['123']
    >>> _clean_controlled_vocab([123])
    ['123']
    >>> _clean_controlled_vocab('123')
    ['123']
    >>> _clean_controlled_vocab(123)
    ['123']
    
    @param data: contents of data field
    @returns: list of ID strings
    """
    if isinstance(data, int):
        data = str(data)
    if isinstance(data, basestring):
        data = [data]
    cleaned = []
    for x in data:
        if not isinstance(x, basestring):
            x = str(x)
        if ('[' in x) and (']' in x):
            y = x.split('[')[1].split(']')[0] 
        else:
            y = x
        cleaned.append(y)
    return cleaned

def _clean_creators( data ):
    """Normalizes contents of 'creators' field.
    
    There are lots of weird variations on this field.
    We want all of them to end up as simple lists of strings.
    
    >>> _clean_creators([u'Ninomiya, L.A.'])
    [u'Ninomiya, L.A.']
    >>> _clean_creators([u'Mitsuoka, Norio: photographer'])
    [u'Mitsuoka, Norio: photographer']
    >>> _clean_creators([{u'namepart': u'Boyle, Rob:editor', u'role': u'author'}, {u'namepart':
    u'Cross, Brian:editor', u'role': u'author'}])
    [u'Boyle, Rob:editor', u'Cross, Brian:editor']
    >>> _clean_creators([{u'namepart': u'"YMCA:publisher"', u'role': u'author'}])
    [u'"YMCA:publisher"']
    >>> _clean_creators([{u'namepart': u'Heart Mountain YMCA', u'role': u'author'}])
    [u'Heart Mountain YMCA']
    >>> _clean_creators([{u'namepart': u'', u'role': u'author'}])
    []
    
    @param data: contents of data field
    @returns: list of normalized names
    """
    # turn strings into lists
    if isinstance(data, basestring):
        if data == '[]':
            data = []
        elif data == '':
            data = []
        elif ';' in data:
            # ex: "Preliminary Hearing Board"; "YMCA";
            data = [x.strip() for x in data.strip().split(';')]
        elif '\r\n' in data:
            data = [x.strip() for x in data.strip().split('\r\n')]
        elif '\n' in data:
            data = [x.strip() for x in data.strip().split('\n')]
        else:
            # ex: Greenwood, Jonny:composer
            # ex: Snead, John
            data = [data]
    # Get just the name. Don't add a role if none selected.
    names = []
    for element in data:
        name = None
        # make everything into a string
        if isinstance(element, basestring):
            name = element
        elif isinstance(element, dict):
            # only keep the 'namepart' of a dict
            if element.get('namepart', None) and element['namepart']:
                name = element['namepart']
        if name:
            names.append(name)
    return names

def _clean_facility( data ):
    """Extract ID from facility text; force ID numbers to strings.
    
    >>> f0 = 'Tule Lake [10]'
    >>> f1 = '10'
    >>> f2 = 10
    >>> _clean_facility(f0)
    ['10']
    >>> _clean_facility(f1)
    ['10']
    >>> _clean_facility(f2)
    ['10']
    
    @param data: contents of data field
    @returns: list of field ID strings
    """
    return _clean_controlled_vocab(data)

def _clean_parent( data ):
    """Normalizes contents of 'creators' field.
    
    In the mappings this is an object but the UI saves it as a string.
    
    >>> p0 = 'ddr-testing-123'
    >>> p1 = {'href':'', 'uuid':'', 'label':'ddr-testing-123'}
    >>> _clean_parent(p0)
    {'href': '', 'uuid': '', 'label': 'ddr-testing-123'}
    >>> _clean_parent(p1)
    {'href': '', 'uuid': '', 'label': 'ddr-testing-123'}
    
    @param data: contents of data field
    @returns: dict
    """
    if isinstance(data, basestring):
        data = {'href':'', 'uuid':'', 'label':data}
    return data

def _clean_topics( data ):
    """Extract topics IDs from textual topics.

    >>> _clean_topics('Topics [123]')
    ['123']
    >>> _clean_topics(['Topics [123]'])
    ['123']
    >>> _clean_topics(['123'])
    ['123']
    >>> _clean_topics([123])
    ['123']
    >>> _clean_topics('123')
    ['123']
    >>> _clean_topics(123)
    ['123']
    
    @param data: contents of data field
    @returns: list of ID strings
    """
    return _clean_controlled_vocab(data)

def _clean_dict( data ):
    """Remove null or empty fields; ElasticSearch chokes on them.
    
    >>> d = {'a': 'abc', 'b': 'bcd', 'x':'' }
    >>> _clean_dict(d)
    >>> d
    {'a': 'abc', 'b': 'bcd'}
    
    @param data: Standard DDR list-of-dicts data structure.
    """
    if data and isinstance(data, dict):
        for key in data.keys():
            if not data[key]:
                del(data[key])

def _clean_payload( data ):
    """Remove null or empty fields; ElasticSearch chokes on them.
    """
    # remove info about DDR release, git-annex version, etc
    if data and isinstance(data, list):
        # skip the initial metadata field
        data = data[1:]
        # remove empty fields
        for field in data:
            for key in field.keys():
                if key == 'creators': field[key] = _clean_creators(field[key])
                if key == 'facility': field[key] = _clean_facility(field[key])
                if key == 'parent':   field[key] = _clean_parent(field[key])
                if key == 'topics':   field[key] = _clean_topics(field[key])
            # rm null or empty fields
            _clean_dict(field)

def _add_id_parts( data ):
    """Add parts of id (e.g. repo, org, cid) to document as separate fields.
    
    >>> data = {'id'}
    >>> _add_id_parts(data)
    >>> data
    {'id':'ddr-test-123', 'repo':'ddr', 'org':'test', 'cid':'123', ...}
    """
    identifier = Identifier.from_id(data['id'])
    for key,val in identifier.parts.iteritems():
        data[key] = val

def post( hosts, index, document, public_fields=[], additional_fields={}, private_ok=False ):
    """Add a new document to an index or update an existing one.
    
    This function can produce ElasticSearch documents in two formats:
    - old-style list-of-dicts used in the DDR JSON files.
    - normal dicts used by ddr-public.
    
    DDR metadata JSON files are structured as a list of fieldname:value dicts.
    This is done so that the fields are always in the same order, making it
    possible to easily see the difference between versions of a file.
    
    In ElasticSearch, documents are structured in a normal dict so that faceting
    works properly.
    
    curl -XPUT 'http://localhost:9200/ddr/collection/ddr-testing-141' -d '{ ... }'
    
    @param hosts: list of dicts containing host information.
    @param index: 
    @param document: The object to post.
    @param public_fields: List of field names; if present, fields not in list will be removed.
    @param additional_fields: dict of fields added during indexing process
    @param private_ok: boolean Publish even if not "publishable".
    @returns: JSON dict with status code and response
    """
    logger.debug('post(%s, %s, %s, %s, %s, %s)' % (hosts, index, document, public_fields, additional_fields, private_ok))
    
    # die if document is public=False or status=incomplete
    if (not _is_publishable(document)) and (not private_ok):
        return {'status':403, 'response':'object not publishable'}
    # remove non-public fields
    _filter_payload(document, public_fields)
    # normalize field contents
    _clean_payload(document)
    
    # restructure from list-of-fields dict to straight dict used by ddr-public
    data = {}
    for field in document:
        for k,v in field.iteritems():
            data[k] = v
    
    identifier = Identifier.from_id(data['id'])
    if identifier.model in ['collection', 'entity']:
        if not (data and data.get('id', None)):
            return {'status':2, 'response':'no id'}
    elif identifier.model in ['file']:
        if not (data and data.get('path_rel', None)):
            return {'status':3, 'response':'no path_rel'}
        filename = None
        extension = None
        if data.get('path_rel',None):
            filename,extension = os.path.splitext(data['path_rel'])
        basename_orig = data.get('basename_orig', None)
        label = data.get('label', None)
        if basename_orig and not label:
            label = basename_orig
        elif filename and not label:
            label = filename
        data['id'] = filename
        data['title'] = label
    # additional_fields
    _add_id_parts(data)
    for key,val in additional_fields.iteritems():
        data[key] = val
    logger.debug('identifier.id %s' % identifier.id)
    
    if identifier.id:
        es = _get_connection(hosts)
        return es.index(index=index, doc_type=identifier.model, id=identifier.id, body=data)
    return {'status':4, 'response':'unknown problem'}

def post_json( hosts, index, doc_type, document_id, path ):
    """POST the specified JSON document as-is.
    
    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @param doc_type: str
    @param document_id: str
    @param path: Absolute path to JSON document.
    @returns: dict Status info.
    """
    logger.debug('post_json(%s, %s, %s, %s, %s)' % (hosts, index, doc_type, document_id, path))
    with open(path, 'r') as f:
        json_text = f.read()
    es = _get_connection(hosts)
    return es.index(index=index, doc_type=doc_type, id=document_id, body=json_text)

def exists( hosts, index, model, document_id ):
    """
    @param hosts: list of dicts containing host information.
    @param index:
    @param model:
    @param document_id:
    """
    es = _get_connection(hosts)
    return es.exists(index=index, doc_type=model, id=document_id)


def get( hosts, index, model, document_id, fields=None ):
    """
    @param hosts: list of dicts containing host information.
    @param index:
    @param model:
    @param document_id:
    """
    es = _get_connection(hosts)
    if exists(hosts, index, model, document_id):
        if fields is not None:
            return es.get(index=index, doc_type=model, id=document_id, fields=fields)
        return es.get(index=index, doc_type=model, id=document_id)
    return None


REPOSITORY_LIST_FIELDS = ['id', 'title', 'description', 'url',]
ORGANIZATION_LIST_FIELDS = ['id', 'title', 'description', 'url',]
COLLECTION_LIST_FIELDS = ['id', 'title', 'description', 'signature_file',]
ENTITY_LIST_FIELDS = ['id', 'title', 'description', 'signature_file',]
FILE_LIST_FIELDS = ['id', 'basename_orig', 'label', 'access_rel','sort',]

REPOSITORY_LIST_SORT = [
    {'repo':'asc'},
]
ORGANIZATION_LIST_SORT = [
    {'repo':'asc'},
    {'org':'asc'},
]
COLLECTION_LIST_SORT = [
    {'repo':'asc'},
    {'org':'asc'},
    {'cid':'asc'},
    {'id':'asc'},
]
ENTITY_LIST_SORT = [
    {'repo':'asc'},
    {'org':'asc'},
    {'cid':'asc'},
    {'eid':'asc'},
    {'id':'asc'},
]
FILE_LIST_SORT = [
    {'repo':'asc'},
    {'org':'asc'},
    {'cid':'asc'},
    {'eid':'asc'},
    {'sort':'asc'},
    {'role':'desc'},
    {'id':'asc'},
]

def all_list_fields():
    LIST_FIELDS = []
    for mf in [REPOSITORY_LIST_FIELDS, ORGANIZATION_LIST_FIELDS,
               COLLECTION_LIST_FIELDS, ENTITY_LIST_FIELDS, FILE_LIST_FIELDS]:
        for f in mf:
            if f not in LIST_FIELDS:
                LIST_FIELDS.append(f)
    return LIST_FIELDS

class InvalidPage(Exception):
    pass
class PageNotAnInteger(InvalidPage):
    pass
class EmptyPage(InvalidPage):
    pass

def _validate_number(number, num_pages):
        """Validates the given 1-based page number.
        see django.core.pagination.Paginator.validate_number
        """
        try:
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger('That page number is not an integer')
        if number < 1:
            raise EmptyPage('That page number is less than 1')
        if number > num_pages:
            if number == 1:
                pass
            else:
                raise EmptyPage('That page contains no results')
        return number

def _page_bottom_top(total, index, page_size):
        """
        Returns a Page object for the given 1-based page number.
        """
        num_pages = total / page_size
        if total % page_size:
            num_pages = num_pages + 1
        number = _validate_number(index, num_pages)
        bottom = (number - 1) * page_size
        top = bottom + page_size
        return bottom,top,num_pages

def massage_query_results( results, thispage, page_size ):
    """Takes ES query, makes facsimile of original object; pads results for paginator.
    
    Problem: Django Paginator only displays current page but needs entire result set.
    Actually, it just needs a list that is the same size as the actual result set.
    
    GOOD:
    Do an ElasticSearch search, without ES paging.
    Loop through ES results, building new list, process only the current page's hits
    hits outside current page added as placeholders
    
    BETTER:
    Do an ElasticSearch search, *with* ES paging.
    Loop through ES results, building new list, processing all the hits
    Pad list with empty objects fore and aft.
    
    @param results: ElasticSearch result set (non-empty, no errors)
    @param thispage: Value of GET['page'] or 1
    @param page_size: Number of objects per page
    @returns: list of hit dicts, with empty "hits" fore and aft of current page
    """
    def unlistify(o, fieldname):
        if o.get(fieldname, None):
            if isinstance(o[fieldname], list):
                o[fieldname] = o[fieldname][0]
    
    objects = []
    if results and results['hits']:
        total = results['hits']['total']
        bottom,top,num_pages = _page_bottom_top(total, thispage, page_size)
        # only process this page
        for n,hit in enumerate(results['hits']['hits']):
            o = {'n':n,
                 'id': hit['_id'],
                 'placeholder': True}
            if (n >= bottom) and (n < top):
                # if we tell ES to only return certain fields, the object is in 'fields'
                if hit.get('fields', None):
                    o = hit['fields']
                elif hit.get('_source', None):
                    o = hit['_source']
                # copy ES results info to individual object source
                o['index'] = hit['_index']
                o['type'] = hit['_type']
                o['model'] = hit['_type']
                o['id'] = hit['_id']
                # ElasticSearch wraps field values in lists when you use a 'fields' array in a query
                for fieldname in all_list_fields():
                    unlistify(o, fieldname)
            objects.append(o)
    return objects

def _clean_sort( sort ):
    """Take list of [a,b] lists, return comma-separated list of a:b pairs
    
    >>> _clean_sort( 'whatever' )
    >>> _clean_sort( [['a', 'asc'], ['b', 'asc'], 'whatever'] )
    >>> _clean_sort( [['a', 'asc'], ['b', 'asc']] )
    'a:asc,b:asc'
    """
    cleaned = ''
    if sort and isinstance(sort,list):
        all_lists = [1 if isinstance(x, list) else 0 for x in sort]
        if not 0 in all_lists:
            cleaned = ','.join([':'.join(x) for x in sort])
    return cleaned

def search( hosts, index, model='', query='', term={}, filters={}, sort=[], fields=[], first=0, size=MAX_SIZE ):
    """Run a query, get a list of zero or more hits.
    
    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @param model: Type of object ('collection', 'entity', 'file')
    @param query: User's search text
    @param term: dict
    @param filters: dict
    @param sort: list of (fieldname,direction) tuples
    @param fields: str
    @param first: int Index of document from which to start results
    @param size: int Number of results to return
    @returns raw ElasticSearch query output
    """
    logger.debug('search( hosts=%s, index=%s, model=%s, query=%s, term=%s, filters=%s, sort=%s, fields=%s, first=%s, size=%s' % (hosts, index, model, query, term, filters, sort, fields, first, size))
    _clean_dict(filters)
    _clean_dict(sort)
    body = {}
    if term:
        body['query'] = {}
        body['query']['term'] = term
    if filters:
        body['filter'] = {'term':filters}
    logger.debug(json.dumps(body))
    sort_cleaned = _clean_sort(sort)
    fields = ','.join(fields)
    es = _get_connection(hosts)
    if query:
        results = es.search(
            index=index,
            doc_type=model,
            q=query,
            body=body,
            sort=sort_cleaned,
            size=size,
            _source_include=fields,
        )
    else:
        results = es.search(
            index=index,
            doc_type=model,
            body=body,
            sort=sort_cleaned,
            size=size,
            _source_include=fields,
        )
    return results

def delete( hosts, index, document_id, recursive=False ):
    """Delete a document and optionally its children.
    
    @param hosts: list of dicts containing host information.
    @param index:
    @param document_id:
    @param recursive: True or False
    """
    identifier = Identifier.from_id(document_id)
    es = _get_connection(hosts)
    if recursive:
        if identifier.model == 'collection': doc_type = 'collection,entity,file'
        elif identifier.model == 'entity': doc_type = 'entity,file'
        elif identifier.model == 'file': doc_type = 'file'
        query = 'id:"%s"' % identifier.id
        try:
            return es.delete_by_query(index=index, doc_type=doc_type, q=query)
        except TransportError:
            pass
    else:
        try:
            return es.delete(index=index, doc_type=identifier.model, id=identifier.id)
        except TransportError:
            pass


# index ----------------------------------------------------------------

def _public_fields():
    """Lists public fields for each model
    
    IMPORTANT: Adds certain dynamically-created fields
    
    @returns: Dict
    """
    public_fields = {}
    for model,module in models.MODULES.iteritems():
        mfields = []
        for field in module.FIELDS:
            if field.get('elasticsearch',None) and field['elasticsearch'].get('public',None):
                mfields.append(field['name'])
        public_fields[model] = mfields
    # add dynamically created fields
    public_fields['file'].append('path_rel')
    public_fields['file'].append('id')
    return public_fields

def _parents_status( paths ):
    """Stores value of public,status for each collection,entity so entities,files can inherit.
    
    @param paths
    @returns: dict
    """
    parents = {}
    def _make_coll_ent(path):
        """Store values of id,public,status for a collection or entity.
        """
        p = {'id':None,
             'public':None,
             'status':None,}
        with open(path, 'r') as f:
            data = json.loads(f.read())
        for field in data:
            fname = field.keys()[0]
            if fname in p.keys():
                p[fname] = field[fname]
        return p
    for path in paths:
        if ('collection.json' in path) or ('entity.json' in path):
            o = _make_coll_ent(path)
            parents[o.pop('id')] = o
    return parents

def _file_parent_ids(identifier):
    """Calculate the parent IDs of an entity or file from the filename.
    
    TODO not specific to elasticsearch - move this function so other modules can use
    
    >>> _file_parent_ids('collection', '.../ddr-testing-123/collection.json')
    []
    >>> _file_parent_ids('entity', '.../ddr-testing-123-1/entity.json')
    ['ddr-testing-123']
    >>> _file_parent_ids('file', '.../ddr-testing-123-1-master-a1b2c3d4e5.json')
    ['ddr-testing-123', 'ddr-testing-123-1']
    
    @param identifier: Identifier
    @returns: parent_ids
    """
    if identifier.model == 'file':
        return [identifier.collection_id, identifier.parent_id()]
    elif identifier.model == 'entity':
        return [identifier.collection_id]
    return []

def _publishable_or_not( paths, parents ):
    """Determines which paths represent publishable paths and which do not.
    
    @param paths
    @param parents
    @returns successful_paths,bad_paths
    """
    successful_paths = []
    bad_paths = []
    for path in paths:
        identifier = Identifier.from_path(path)
        # see if item's parents are incomplete or nonpublic
        # TODO Bad! Bad! Generalize this...
        UNPUBLISHABLE = []
        parent_ids = _file_parent_ids(identifier)
        for parent_id in parent_ids:
            parent = parents.get(parent_id, {})
            for x in parent.itervalues():
                if (x not in STATUS_OK) and (x not in PUBLIC_OK):
                    if parent_id not in UNPUBLISHABLE:
                        UNPUBLISHABLE.append(parent_id)
        if UNPUBLISHABLE:
            response = 'parent unpublishable: %s' % UNPUBLISHABLE
            bad_paths.append((path,403,response))
        if not UNPUBLISHABLE:
            if path and index and identifier.model:
                successful_paths.append(path)
            else:
                logger.error('missing information!: %s' % path)
    return successful_paths,bad_paths

def _has_access_file( identifier ):
    """Determines whether the path has a corresponding access file.
    
    @param path: Absolute or relative path to JSON file.
    @param suffix: Suffix that is applied to File ID to get access file.
    @returns: True,False
    """
    access_abs = identifier.path_abs('access')
    if os.path.exists(access_abs) or os.path.islink(access_abs):
        return True
    return False

def _store_signature_file( signatures, identifier, master_substitute ):
    """Store signature file for collection,entity if it is "earlier" than current one.
    
    IMPORTANT: remember to change 'zzzzzz' back to 'master'
    """
    if _has_access_file(identifier):
        # replace 'master' with something so mezzanine wins in sort
        thumbfile_mezzfirst = identifier.id.replace('master', master_substitute)
        # # nifty little bit of code that extracts the sort field from file.json
        # import re
        # sort = ''
        # with open(path, 'r') as f:
        #     for line in f.readlines():
        #         if '"sort":' in line:
        #             sort = re.findall('\d+', line)[0]
        
        # if this entity_id is "earlier" than the existing one, add it
        def _store( signatures, object_id, file_id ):
            if signatures.get(object_id,None):
                filenames = [signatures[object_id], file_id]
                first = natural_sort(filenames)[0]
                if file_id == first:
                    signatures[object_id] = file_id
            else:
                signatures[object_id] = file_id
        
        _store(signatures, identifier.collection_id, thumbfile_mezzfirst)
        _store(signatures, identifier.parent_id, thumbfile_mezzfirst)

def _choose_signatures( paths ):
    """Iterate through paths, storing signature_url for each collection, entity.
    paths listed files first, then entities, then collections
    
    @param paths
    @returns: dict signature_files
    """
    SIGNATURE_MASTER_SUBSTITUTE = 'zzzzzz'
    signature_files = {}
    for path in paths:
        identifier = Identifier.from_path(path)
        if identifier.model == 'file':
            # decide whether to store this as a collection/entity signature
            _store_signature_file(signature_files, identifier, SIGNATURE_MASTER_SUBSTITUTE)
        else:
            # signature_urls will be waiting for collections,entities below
            pass
    # restore substituted roles
    for key,value in signature_files.iteritems():
        signature_files[key] = value.replace(SIGNATURE_MASTER_SUBSTITUTE, 'master')
    return signature_files

def load_document_json( json_path, model, object_id ):
    """Load object from JSON and add some essential fields.
    """
    with open(json_path, 'r') as f:
        document = json.loads(f.read())
    if model == 'file':
        document.append( {'id':object_id} )
    return document

def index( hosts, index, path, models_dir=models.MODELS_DIR, recursive=False, public=True ):
    """(Re)index with data from the specified directory.
    
    After receiving a list of metadata files, index() iterates through the list several times.  The first pass weeds out paths to objects that can not be published (e.g. object or its parent is unpublished).
    
    The second pass goes through the files and assigns a signature file to each entity or collection ID.
    There is some logic that tries to pick the first file of the first entity to be the collection signature, and so on.  Mezzanine files are preferred over master files.
    
    In the final pass, a list of public/publishable fields is chosen based on the model.  Additional fields not in the model (e.g. parent ID, parent organization/collection/entity ID, the signature file) are packaged.  Then everything is sent off to post().

    @param hosts: list of dicts containing host information.
    @param index: Name of the target index.
    @param path: Absolute path to directory containing object metadata files.
    @param models_dir: Absolute path to directory containing model JSON files.
    @param recursive: Whether or not to recurse into subdirectories.
    @param public: For publication (fields not marked public will be ommitted).
    @param paths: Absolute paths to directory containing collections.
    @returns: number successful,list of paths that didn't work out
    """
    logger.debug('index(%s, %s, %s)' % (hosts, index, path))
    
    public_fields = _public_fields()
    
    # process a single file if requested
    if os.path.isfile(path):
        paths = [path]
    else:
        # files listed first, then entities, then collections
        paths = models.metadata_files(path, recursive, files_first=1)
    
    # Store value of public,status for each collection,entity.
    # Values will be used by entities and files to inherit these values from their parent.
    parents = _parents_status(paths)
    
    # Determine if paths are publishable or not
    successful_paths,bad_paths = _publishable_or_not(paths, parents)
    
    # iterate through paths, storing signature_url for each collection, entity
    # paths listed files first, then entities, then collections
    signature_files = _choose_signatures(successful_paths)
    print('Signature files')
    keys = signature_files.keys()
    keys.sort()
    for key in keys:
        print(key, signature_files[key])
    
    successful = 0
    for path in successful_paths:
        identifier = Identifier.from_path(path)
        parent_id = identifier.parent_id()
        
        publicfields = []
        if public and identifier.model:
            publicfields = public_fields[identifier.model]
        
        additional_fields = {'parent_id': parent_id}
        if identifier.model == 'collection': additional_fields['organization_id'] = parent_id
        if identifier.model == 'entity': additional_fields['collection_id'] = parent_id
        if identifier.model == 'file': additional_fields['entity_id'] = parent_id
        if identifier.model in ['collection', 'entity']:
            additional_fields['signature_file'] = signature_files.get(identifier.id, '')
        
        # HERE WE GO!
        document = load_document_json(path, identifier.model, identifier.id)
        try:
            existing = get(hosts, index, identifier.model, identifier.id, fields=[])
        except:
            existing = None
        result = post(hosts, index, document, publicfields, additional_fields)
        # success: created, or version number incremented
        if result.get('_id', None):
            if existing:
                existing_version = existing.get('version', None)
                if not existing_version:
                    existing_version = existing.get('_version', None)
            else:
                existing_version = None
            result_version = result.get('version', None)
            if not result_version:
                result_version = result.get('_version', None)
            if result['created'] or (existing_version and (result_version > existing_version)):
                successful += 1
        else:
            bad_paths.append((path, result['status'], result['response']))
            #print(status_code)
    logger.debug('INDEXING COMPLETED')
    return {'total':len(paths), 'successful':successful, 'bad':bad_paths}
