# coding: utf-8

from datetime import datetime
import json
import os

from nose.tools import assert_raises

import config  # adds repo_models to sys.path
import identifier

BASE_PATH = '/var/www/media/ddr'


# TODO test_compile_patterns

def test_identify_object():
    patterns = (
        (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)$', '', 'entity'),
        (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)$', '', 'collection'),
    )
    id0 = 'ddr-test-123'
    id1 = 'ddr-test-123-456'
    id2 = 'ddr.test.123.456'
    id0_expected_model = 'collection'
    id1_expected_model = 'entity'
    id2_expected_model = None
    id0_expected_gd = {'repo':'ddr', 'org':'test', 'cid':'123'}
    id1_expected_gd = {'repo':'ddr', 'org':'test', 'cid':'123', 'eid':'456'}
    id2_expected_gd = None
    assert identifier.identify_object(id0, patterns) == (id0_expected_model,id0_expected_gd) 
    assert identifier.identify_object(id1, patterns) == (id1_expected_model,id1_expected_gd)
    assert identifier.identify_object(id2, patterns) == (id2_expected_model,id2_expected_gd)

def test_identify_filepath():
    assert identifier.identify_filepath('something-a.jpg') == 'access'
    assert identifier.identify_filepath('ddr-test-123-456-mezzanine-abc123') == 'mezzanine'
    assert identifier.identify_filepath('ddr-test-123-456-master-abc123') == 'master'
    assert identifier.identify_filepath('nothing in particular') == None

def test_set_idparts():
    i = identifier.Identifier('ddr-test-123-456-master-abcde12345', '/tmp')
    assert i.parts['repo'] == 'ddr'
    assert i.parts['org'] == 'test'
    assert i.parts['cid'] == 123
    assert i.parts['eid'] == 456
    assert i.parts['role'] == 'master'
    assert i.parts['sha1'] == 'abcde12345'

def test_format_id():
    templates = {
        'entity':       '{repo}-{org}-{cid}-{eid}',
        'collection':   '{repo}-{org}-{cid}',
    }
    i0 = 'ddr-test-123'
    i1 = 'ddr-test-123-456'
    assert identifier.format_id(identifier.Identifier(i0), 'collection', templates) == i0
    assert identifier.format_id(identifier.Identifier(i1), 'entity', templates) == i1
    # child identifiers (e.g. entity) can get ID of parents (e.g. collection)
    assert identifier.format_id(identifier.Identifier(i1), 'collection', templates) == i0
    # but not the other way around
    assert_raises(
        KeyError,
        identifier.format_id,
        identifier.Identifier(i0), 'entity', templates
    )

def test_format_path():
    templates = {
        'entity-abs':       '{basepath}/{repo}-{org}-{cid}/files/{repo}-{org}-{cid}-{eid}',
        'collection-abs':   '{basepath}/{repo}-{org}-{cid}',
        'entity-rel':       'files/{repo}-{org}-{cid}-{eid}',
    }
    basepath = '/tmp'
    i0 = 'ddr-test-123'
    i1 = 'ddr-test-123-456'
    i0_abs_expected = '/tmp/ddr-test-123'
    i1_abs_expected = '/tmp/ddr-test-123/files/ddr-test-123-456'
    i1_rel_expected = 'files/ddr-test-123-456'
    # abs, rel
    path0 = identifier.format_path(identifier.Identifier(i0, basepath), 'collection', 'abs', templates)
    path1 = identifier.format_path(identifier.Identifier(i1, basepath), 'entity', 'abs', templates)
    path2 = identifier.format_path(identifier.Identifier(i1, basepath), 'entity', 'rel', templates)
    assert path0 == i0_abs_expected
    assert path1 == i1_abs_expected
    assert path2 == i1_rel_expected
    # missing patterns key
    path3 = identifier.format_path(identifier.Identifier(i1, basepath), 'entity', 'meta-rel', templates)
    assert path3 == None
    # no basepath in identifier
    assert_raises(
        Exception,
        identifier.format_path,
        identifier.Identifier(i0), 'collection', 'abs', templates
    )

def test_format_url():
    templates = {
        'editor': {
            'entity':       '/ui/{repo}-{org}-{cid}-{eid}',
            'collection':   '/ui/{repo}-{org}-{cid}',
        },
        'public': {
            'entity':       '/{repo}/{org}/{cid}/{eid}',
            'collection':   '/{repo}/{org}/{cid}',
        },
    }
    basepath = '/tmp'
    i0 = 'ddr-test-123'
    i1 = 'ddr-test-123-456'
    i0_edt_expected = '/ui/ddr-test-123'
    i1_edt_expected = '/ui/ddr-test-123-456'
    i0_pub_expected = '/ddr/test/123'
    i1_pub_expected = '/ddr/test/123/456'
    # editor
    url0 = identifier.format_url(identifier.Identifier(i0, basepath), 'collection', 'editor', templates)
    url1 = identifier.format_url(identifier.Identifier(i1, basepath), 'entity', 'editor', templates)
    # public
    url2 = identifier.format_url(identifier.Identifier(i0, basepath), 'collection', 'public', templates)
    url3 = identifier.format_url(identifier.Identifier(i1, basepath), 'entity', 'public', templates)

def test_matches_pattern():
    patterns = (
        (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)$', '', 'entity'),
        (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)$', '', 'collection'),
    )
    id0 = 'ddr-test-123'
    id1 = 'ddr-test-123-456'
    id2 = '/ddr/test/123'
    id3 = 'ddr-test'
    id0_expected = {'repo': 'ddr', 'org': 'test', 'cid': '123', 'model': 'collection'}
    id1_expected = {'repo': 'ddr', 'org': 'test', 'cid': '123', 'eid': '456', 'model': 'entity'}
    id2_expected = {}
    id3_expected = {}
    assert identifier.matches_pattern(id0, patterns) == id0_expected
    assert identifier.matches_pattern(id1, patterns) == id1_expected
    assert identifier.matches_pattern(id2, patterns) == id2_expected
    assert identifier.matches_pattern(id3, patterns) == id3_expected

# TODO test_is_id
# TODO test_is_path
# TODO test_is_url
# TODO test_is_abspath

def test_parse_args_kwargs():
    keys = identifier.KWARG_KEYS
    args0 = []; kwargs0 = {}
    args1 = []; kwargs1 = {'id':'ddr-bar', 'base_path':'/opt'}
    args2 = ['ddr-foo', '/tmp']; kwargs2 = {}
    args3 = ['ddr-foo', '/tmp']; kwargs3 = {'id':'ddr-bar'}
    args4 = ['ddr-foo', '/tmp']; kwargs4 = {'id':'ddr-bar', 'base_path':'/opt'}
    expected0 = {'url': None, 'path': None, 'parts': None, 'id': None, 'base_path': None}
    expected1 = {'url': None, 'path': None, 'parts': None, 'id': 'ddr-bar', 'base_path': '/opt'}
    expected2 = {'url': None, 'path': None, 'parts': None, 'id': 'ddr-foo', 'base_path': '/tmp'}
    expected3 = {'url': None, 'path': None, 'parts': None, 'id': 'ddr-bar', 'base_path': '/tmp'}
    expected4 = {'url': None, 'path': None, 'parts': None, 'id': 'ddr-bar', 'base_path': '/opt'}
    assert identifier._parse_args_kwargs(keys, args0, kwargs0) == expected0
    assert identifier._parse_args_kwargs(keys, args1, kwargs1) == expected1
    assert identifier._parse_args_kwargs(keys, args2, kwargs2) == expected2
    assert identifier._parse_args_kwargs(keys, args3, kwargs3) == expected3
    assert identifier._parse_args_kwargs(keys, args4, kwargs4) == expected4

# TODO test_module_for_name
# TODO test_class_for_name

def test_identifier_wellformed():
    assert identifier.Identifier.wellformed('id', REPO_ID)
    assert identifier.Identifier.wellformed('id', ORG_ID)
    assert identifier.Identifier.wellformed('id', COLLECTION_ID)
    assert identifier.Identifier.wellformed('id', ENTITY_ID)
    assert identifier.Identifier.wellformed('id', FILE_ID)
    assert_raises(
        Exception,
        identifier.Identifier.wellformed('id', 'ddr_test_123_456_master_abcde12345')
    )
    assert identifier.Identifier.wellformed('path', REPO_PATH_ABS)
    assert identifier.Identifier.wellformed('path', ORG_PATH_ABS)
    assert identifier.Identifier.wellformed('path', COLLECTION_PATH_ABS)
    assert identifier.Identifier.wellformed('path', ENTITY_PATH_ABS)
    assert identifier.Identifier.wellformed('path', FILE_PATH_ABS)

def test_identifier_valid():
    COMPONENTS = {
        'repo': ['ddr',],
        'org': ['test', 'testing',],
    }
    in0 = {'repo':'ddr', 'org':'test', 'cid':'123'}
    in1 = {'repo':'ddr', 'org':'blat', 'cid':'123'}
    expected0 = True
    expected1 = ['org']
    assert identifier.Identifier.valid(in0, components=COMPONENTS) == expected0 
    assert identifier.Identifier.valid(in1, components=COMPONENTS) == expected1 

def test_identifier_components():
    in0 = 'ddr'
    in1 = 'ddr-test'
    in2 = 'ddr-test-123'
    in3 = 'ddr-test-123-456'
    in4 = 'ddr-test-123-456-master'
    in5 = 'ddr-test-123-456-master-abcde12345'
    out0 = ['repository', 'ddr']
    out1 = ['organization', 'ddr', 'test']
    out2 = ['collection', 'ddr', 'test', 123]
    out3 = ['entity', 'ddr', 'test', 123, 456]
    out4 = ['file-role', 'ddr', 'test', 123, 456, 'master']
    out5 = ['file', 'ddr', 'test', 123, 456, 'master', 'abcde12345']
    assert identifier.Identifier(id=in0).components() == out0
    assert identifier.Identifier(id=in1).components() == out1
    assert identifier.Identifier(id=in2).components() == out2
    assert identifier.Identifier(id=in3).components() == out3
    assert identifier.Identifier(id=in4).components() == out4
    assert identifier.Identifier(id=in5).components() == out5

# TODO test_identifier_fields_module
# TODO test_identifier_object_class
# TODO test_identifier_object


REPO_ID = 'ddr'
REPO_MODEL = 'repository'
REPO_PARTS = ['ddr']
REPO_REPR = '<DDR.identifier.Identifier repository:ddr>'

ORG_ID = 'ddr-test'
ORG_MODEL = 'organization'
ORG_PARTS = ['ddr', 'test']
ORG_REPR = '<DDR.identifier.Identifier organization:ddr-test>'

COLLECTION_ID = 'ddr-test-123'
COLLECTION_MODEL = 'collection'
COLLECTION_PARTS = ['ddr', 'test', '123']
COLLECTION_REPR = '<DDR.identifier.Identifier collection:ddr-test-123>'

ENTITY_ID = 'ddr-test-123-456'
ENTITY_MODEL = 'entity'
ENTITY_PARTS = ['ddr', 'test', '123', '456']
ENTITY_REPR = '<DDR.identifier.Identifier entity:ddr-test-123-456>'

# FILE_ROLE

FILE_ID = 'ddr-test-123-456-master-a1b2c3d4e5'
FILE_MODEL = 'file'
FILE_PARTS = ['ddr', 'test', '123', '456', 'master', 'a1b2c3d4e5']
FILE_REPR = '<DDR.identifier.Identifier file:ddr-test-123-456-master-a1b2c3d4e5>'


# from_id --------------------------------------------------------------

def test_repository_from_id():
    i0 = identifier.Identifier('ddr')
    i1 = identifier.Identifier('ddr', BASE_PATH)
    assert str(i0)  == str(i1)  == REPO_REPR
    assert i0.id    == i1.id    == REPO_ID
    assert i0.model == i1.model == REPO_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_organization_from_id():
    i0 = identifier.Identifier('ddr-test')
    i1 = identifier.Identifier('ddr-test', BASE_PATH)
    assert str(i0)  == str(i1)  == ORG_REPR
    assert i0.id    == i1.id    == ORG_ID
    assert i0.model == i1.model == ORG_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_collection_from_id():
    i0 = identifier.Identifier('ddr-test-123')
    i1 = identifier.Identifier('ddr-test-123', BASE_PATH)
    assert str(i0)  == str(i1)  == COLLECTION_REPR
    assert i0.id    == i1.id    == COLLECTION_ID
    assert i0.model == i1.model == COLLECTION_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_entity_from_id():
    i0 = identifier.Identifier('ddr-test-123-456')
    i1 = identifier.Identifier('ddr-test-123-456', BASE_PATH)
    assert str(i0)  == str(i1)  == ENTITY_REPR
    assert i0.id    == i1.id    == ENTITY_ID
    assert i0.model == i1.model == ENTITY_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

# TODO test_filerole_from_id

def test_file_from_id():
    i0 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5')
    i1 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5', BASE_PATH)
    assert str(i0)  == str(i1)  == FILE_REPR
    assert i0.id    == i1.id    == FILE_ID
    assert i0.model == i1.model == FILE_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

# from_idparts ---------------------------------------------------------

def test_repository_from_idparts():
    i0 = identifier.Identifier(
        {'model':'repository', 'repo':'ddr',}
    )
    i1 = identifier.Identifier(
        {'model':'repository', 'repo':'ddr',},
        BASE_PATH
    )
    assert str(i0)  == str(i1)  == REPO_REPR
    assert i0.id    == i1.id    == REPO_ID
    assert i0.model == i1.model == REPO_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_organization_from_idparts():
    i0 = identifier.Identifier(
        {'model':'organization', 'repo':'ddr', 'org':'test',}
    )
    i1 = identifier.Identifier(
        {'model':'organization', 'repo':'ddr', 'org':'test',},
        BASE_PATH
    )
    assert str(i0)  == str(i1)  == ORG_REPR
    assert i0.id    == i1.id    == ORG_ID
    assert i0.model == i1.model == ORG_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_collection_from_idparts():
    i0 = identifier.Identifier(
        {'model':'collection', 'repo':'ddr', 'org':'test', 'cid':123,}
    )
    i1 = identifier.Identifier(
        {'model':'collection', 'repo':'ddr', 'org':'test', 'cid':123,},
        BASE_PATH
    )
    assert str(i0)  == str(i1)  == COLLECTION_REPR
    assert i0.id    == i1.id    == COLLECTION_ID
    assert i0.model == i1.model == COLLECTION_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_entity_from_idparts():
    i0 = identifier.Identifier(
        {'model':'entity', 'repo':'ddr', 'org':'test', 'cid':123, 'eid':456,}
    )
    i1 = identifier.Identifier(
        {'model':'entity', 'repo':'ddr', 'org':'test', 'cid':123, 'eid':456,},
        BASE_PATH
    )
    assert str(i0)  == str(i1)  == ENTITY_REPR
    assert i0.id    == i1.id    == ENTITY_ID
    assert i0.model == i1.model == ENTITY_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

# TODO test_filerole_from_idparts

def test_file_from_idparts():
    idparts = {
            'model':'file',
            'repo':'ddr', 'org':'test', 'cid':123,
            'eid':456, 'role':'master', 'sha1':'a1b2c3d4e5',
        }
    i0 = identifier.Identifier(idparts)
    i1 = identifier.Identifier(idparts, BASE_PATH)
    assert str(i0)  == str(i1)  == FILE_REPR
    assert i0.id    == i1.id    == FILE_ID
    assert i0.model == i1.model == FILE_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

# from_path ------------------------------------------------------------

def test_repository_from_path():
    i0 = identifier.Identifier('/var/www/media/ddr/ddr')
    assert str(i0) == REPO_REPR
    assert i0.id == REPO_ID
    assert i0.model == REPO_MODEL
    assert i0.basepath == BASE_PATH

def test_organization_from_path():
    i0 = identifier.Identifier('/var/www/media/ddr/ddr-test')
    i1 = identifier.Identifier('/var/www/media/ddr/ddr-test/')
    assert str(i0)  == str(i1)  == ORG_REPR
    assert i0.id    == i1.id    == ORG_ID
    assert i0.model == i1.model == ORG_MODEL
    assert i0.basepath == i1.basepath == BASE_PATH

def test_collection_from_path():
    i0 = identifier.Identifier('/var/www/media/ddr/ddr-test-123')
    i1 = identifier.Identifier('/var/www/media/ddr/ddr-test-123/')
    i2 = identifier.Identifier('/var/www/media/ddr/ddr-test-123/collection.json')
    assert str(i0)     == str(i1)     == str(i2)     == COLLECTION_REPR
    assert i0.id       == i1.id       == i2.id       == COLLECTION_ID
    assert i0.model    == i1.model    == i2.model    == COLLECTION_MODEL
    assert i0.basepath == i1.basepath == i2.basepath == BASE_PATH

def test_entity_from_path():
    i0 = identifier.Identifier('/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456')
    i1 = identifier.Identifier('/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/')
    i2 = identifier.Identifier('/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/entity.json')
    assert str(i0)     == str(i1)     == str(i2)     == ENTITY_REPR
    assert i0.id       == i1.id       == i2.id       == ENTITY_ID
    assert i0.model    == i1.model    == i2.model    == ENTITY_MODEL
    assert i0.basepath == i1.basepath == i2.basepath == BASE_PATH
    
    i3 = identifier.Identifier('/mnt/nfsdrive/ddr/ddr-test-123/files/ddr-test-123-456')
    assert i3.id == ENTITY_ID
    assert str(i3) == ENTITY_REPR
    assert i3.model == ENTITY_MODEL
    assert i3.basepath == '/mnt/nfsdrive/ddr'

# TODO test_filerole_from_path

def test_file_from_path():
    i0 = identifier.Identifier(
        '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5'
    )
    i1 = identifier.Identifier(
        '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5/'
    )
    i2 = identifier.Identifier(
        '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5.json'
    )
    assert str(i0)     == str(i1)     == str(i2)     == FILE_REPR
    assert i0.id       == i1.id       == i2.id       == FILE_ID
    assert i0.model    == i1.model    == i2.model    == FILE_MODEL
    assert i0.basepath == i1.basepath == i2.basepath == BASE_PATH

# from_url -------------------------------------------------------------

def test_repository_from_url():
    i0 = identifier.Identifier(url='http://192.168.56.101/ddr')
    i1 = identifier.Identifier(url='http://192.168.56.101/ddr/', base_path=BASE_PATH)
    print('i0 %s' % i0)
    assert str(i0)  == str(i1)  == REPO_REPR
    assert i0.id    == i1.id    == REPO_ID
    assert i0.model == i1.model == REPO_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_organization_from_url():
    i0 = identifier.Identifier(url='http://192.168.56.101/ddr/test')
    i1 = identifier.Identifier(url='http://192.168.56.101/ddr/test/', base_path=BASE_PATH)
    assert str(i0)  == str(i1)  == ORG_REPR
    assert i0.id    == i1.id    == ORG_ID
    assert i0.model == i1.model == ORG_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

def test_collection_from_url():
    i0 = identifier.Identifier(url='http://192.168.56.101/ddr/test/123')
    i1 = identifier.Identifier(url='http://192.168.56.101/ddr/test/123/')
    i2 = identifier.Identifier(url='http://192.168.56.101/ddr/test/123/', base_path=BASE_PATH)
    assert_raises(
        Exception,
        identifier.Identifier,
        url='http://192.168.56.101/ddr/test/123/',
        base_path='ddr/test/123'
    )
    assert str(i0)  == str(i1)  == COLLECTION_REPR
    assert i0.id    == i1.id    == COLLECTION_ID
    assert i0.model == i1.model == COLLECTION_MODEL
    assert i0.basepath == i1.basepath == None
    assert i2.basepath == BASE_PATH

def test_entity_from_url():
    i0 = identifier.Identifier(url='http://192.168.56.101/ddr/test/123/456')
    i1 = identifier.Identifier(url='http://192.168.56.101/ddr/test/123/456/', base_path=BASE_PATH)
    assert_raises(
        Exception,
        identifier.Identifier,
        url='http://192.168.56.101/ddr/test/123/456/',
        base_path='ddr/test/123/456'
    )
    assert str(i0)  == str(i1)  == ENTITY_REPR
    assert i0.id    == i1.id    == ENTITY_ID
    assert i0.model == i1.model == ENTITY_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH

# TODO test_filerole_from_id

def test_file_from_url():
    i0 = identifier.Identifier(
        url='http://192.168.56.101/ddr/test/123/456/master/a1b2c3d4e5'
    )
    i1 = identifier.Identifier(
        url='http://192.168.56.101/ddr/test/123/456/master/a1b2c3d4e5/',
        base_path=BASE_PATH
    )
    assert_raises(
        Exception,
        identifier.Identifier,
        url='http://192.168.56.101/ddr/test/123/456/master/a1b2c3d4e5/',
        base_path='ddr/test/123/456/master/a1b2c3d4e5'
    )
    assert str(i0)  == str(i1)  == FILE_REPR
    assert i0.id    == i1.id    == FILE_ID
    assert i0.model == i1.model == FILE_MODEL
    assert i0.basepath == None
    assert i1.basepath == BASE_PATH


REPO_COLLECTION_ID = None
ORG_COLLECTION_ID = None
COLLECTION_COLLECTION_ID = 'ddr-test-123'
ENTITY_COLLECTION_ID = 'ddr-test-123'
FILE_COLLECTION_ID = 'ddr-test-123'

def test_collection_id():
    i0 = identifier.Identifier('ddr')
    i1 = identifier.Identifier('ddr-test')
    i2 = identifier.Identifier('ddr-test-123')
    i3 = identifier.Identifier('ddr-test-123-456')
    i4 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5')
    assert_raises(Exception, i0, 'collection_id')
    assert_raises(Exception, i1, 'collection_id')
    assert i2.collection_id() == COLLECTION_COLLECTION_ID
    assert i3.collection_id() == ENTITY_COLLECTION_ID
    assert i4.collection_id() == FILE_COLLECTION_ID

REPO_COLLECTION_PATH = None
ORG_COLLECTION_PATH = None
COLLECTION_COLLECTION_PATH = '/var/www/media/ddr/ddr-test-123'
ENTITY_COLLECTION_PATH = '/var/www/media/ddr/ddr-test-123'
FILE_COLLECTION_PATH = '/var/www/media/ddr/ddr-test-123'

def test_collection_path():
    i0 = identifier.Identifier('ddr')
    i1 = identifier.Identifier('ddr-test')
    i2 = identifier.Identifier('ddr-test-123')
    i3 = identifier.Identifier('ddr-test-123-456')
    i4 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5')
    assert_raises(Exception, i0, 'collection_path')
    assert_raises(Exception, i1, 'collection_path')
    assert_raises(Exception, i2, 'collection_path')
    assert_raises(Exception, i3, 'collection_path')
    assert_raises(Exception, i4, 'collection_path')
    
    i0 = identifier.Identifier('ddr', BASE_PATH)
    i1 = identifier.Identifier('ddr-test', BASE_PATH)
    i2 = identifier.Identifier('ddr-test-123', BASE_PATH)
    i3 = identifier.Identifier('ddr-test-123-456', BASE_PATH)
    i4 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5', BASE_PATH)
    assert_raises(Exception, i0, 'collection_path')
    assert_raises(Exception, i1, 'collection_path')
    assert i2.collection_path() == COLLECTION_COLLECTION_PATH
    assert i3.collection_path() == ENTITY_COLLECTION_PATH
    assert i4.collection_path() == FILE_COLLECTION_PATH

# TODO test_identifier_collection


PARENT_REPO_ID = 'ddr'
PARENT_ORG_ID = 'ddr-test'
PARENT_COLLECTION_ID = 'ddr-test-123'
PARENT_ENTITY_ID = 'ddr-test-123-456'
PARENT_FILEROLE_ID = 'ddr-test-123-456-master'
PARENT_FILE_ID = 'ddr-test-123-456-master-a1b2c3d4e5'

def test_parent_id():
    rep = identifier.Identifier(PARENT_REPO_ID)
    org = identifier.Identifier(PARENT_ORG_ID)
    col = identifier.Identifier(PARENT_COLLECTION_ID)
    ent = identifier.Identifier(PARENT_ENTITY_ID)
    rol = identifier.Identifier(PARENT_FILEROLE_ID)
    fil = identifier.Identifier(PARENT_FILE_ID)
    assert col.parent_id() == None
    assert ent.parent_id() == PARENT_COLLECTION_ID
    assert fil.parent_id() == PARENT_ENTITY_ID
    assert rep.parent_id(stubs=1) == None
    assert org.parent_id(stubs=1) == PARENT_REPO_ID
    assert col.parent_id(stubs=1) == PARENT_ORG_ID
    assert ent.parent_id(stubs=1) == PARENT_COLLECTION_ID
    assert rol.parent_id(stubs=1) == PARENT_ENTITY_ID
    assert fil.parent_id(stubs=1) == PARENT_FILEROLE_ID

# TODO test_parent_path

def test_parent():
    i = identifier.Identifier(id='ddr-test-123-456-master-abcde12345')
    assert i.parent().id == 'ddr-test-123-456'
    assert i.parent(stubs=1).id == 'ddr-test-123-456-master'
    assert i.parent().__class__ == i.__class__
    assert i.parent(stubs=1).__class__ == i.__class__

def test_child():
    i = identifier.Identifier(id='ddr-test-123')
    assert i.child('entity', {'eid':'456'}).id == 'ddr-test-123-456'
    assert i.child('entity', {'eid':'456'}).__class__ == i.__class__
    assert_raises(
        Exception,
        i.child,
        'file', {'eid':'456'}
    )

def test_lineage():
    re = identifier.Identifier(id='ddr')
    og = identifier.Identifier(id='ddr-test')
    co = identifier.Identifier(id='ddr-test-123')
    en = identifier.Identifier(id='ddr-test-123-456')
    fr = identifier.Identifier(id='ddr-test-123-456-master')
    fi = identifier.Identifier(id='ddr-test-123-456-master-abcde12345')
    
    def sameclass(i, lineage):
        matches = [x.__class__ for x in lineage if x.__class__ == i.__class__]
        return len(matches) == len(lineage)

    assert sameclass(fi, fi.lineage()) == True
    assert sameclass(fi, fi.lineage(stubs=1)) == True
    assert len(fi.lineage()) == 3
    assert len(fi.lineage(stubs=1)) == 6



REPO_PATH_ABS       = '/var/www/media/ddr/ddr'
ORG_PATH_ABS        = '/var/www/media/ddr/ddr-test'
COLLECTION_PATH_ABS = '/var/www/media/ddr/ddr-test-123'
ENTITY_PATH_ABS     = '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456'
FILE_PATH_ABS       = '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5'
REPO_PATH_ABS_JSON       = '/var/www/media/ddr/ddr/repository.json'
ORG_PATH_ABS_JSON        = '/var/www/media/ddr/ddr-test/organization.json'
COLLECTION_PATH_ABS_JSON = '/var/www/media/ddr/ddr-test-123/collection.json'
ENTITY_PATH_ABS_JSON     = '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/entity.json'
FILE_PATH_ABS_JSON       = '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5.json'
FILE_PATH_ABS_ACCESS = '/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5-a.jpg'

def test_path_abs():
    ri0 = identifier.Identifier(
        'ddr'
    )
    assert_raises(Exception, ri0, 'path_abs')
    assert_raises(Exception, ri0, 'path_abs', 'json')
    assert_raises(Exception, ri0, 'path_abs', 'BAD')
    ri1 = identifier.Identifier(
        'ddr',
        BASE_PATH
    )
    assert ri1.path_abs()       == REPO_PATH_ABS
    assert ri1.path_abs('json') == REPO_PATH_ABS_JSON
    assert_raises(Exception, ri1, 'path_abs', 'BAD')
    
    oi0 = identifier.Identifier(
        'ddr-test'
    )
    assert_raises(Exception, oi0, 'path_abs')
    assert_raises(Exception, oi0, 'path_abs', 'json')
    assert_raises(Exception, oi0, 'path_abs', 'BAD')
    oi1 = identifier.Identifier(
        'ddr-test',
        BASE_PATH
    )
    assert oi1.path_abs()       == ORG_PATH_ABS
    assert oi1.path_abs('json') == ORG_PATH_ABS_JSON
    assert_raises(Exception, oi1, 'path_abs', 'BAD')
    
    ci0 = identifier.Identifier(
        'ddr-test-123'
    )
    assert_raises(Exception, ci0, 'path_abs')
    assert_raises(Exception, ci0, 'path_abs', 'json')
    assert_raises(Exception, ci0, 'path_abs', 'BAD')
    ci1 = identifier.Identifier(
        'ddr-test-123',
        BASE_PATH
    )
    assert ci1.path_abs()       == COLLECTION_PATH_ABS
    assert ci1.path_abs('json') == COLLECTION_PATH_ABS_JSON
    assert_raises(Exception, ci1, 'path_abs', 'BAD')
    
    ei0 = identifier.Identifier(
        'ddr-test-123-456'
    )
    assert_raises(Exception, ei0, 'path_abs')
    assert_raises(Exception, ei0, 'path_abs', 'json')
    assert_raises(Exception, ei0, 'path_abs', 'BAD')
    ei1 = identifier.Identifier(
        'ddr-test-123-456',
        BASE_PATH
    )
    assert ei1.path_abs()       == ENTITY_PATH_ABS
    assert ei1.path_abs('json') == ENTITY_PATH_ABS_JSON
    assert_raises(Exception, ei1, 'path_abs', 'BAD')
    
    fi0 = identifier.Identifier(
        'ddr-test-123-456-master-a1b2c3d4e5'
    )
    assert_raises(Exception, fi0, 'path_abs')
    assert_raises(Exception, fi0, 'path_abs', 'access')
    assert_raises(Exception, fi0, 'path_abs', 'json')
    assert_raises(Exception, fi0, 'path_abs', 'BAD')
    fi1 = identifier.Identifier(
        'ddr-test-123-456-master-a1b2c3d4e5',
        BASE_PATH
    )
    assert fi1.path_abs()         == FILE_PATH_ABS
    assert fi1.path_abs('access') == FILE_PATH_ABS_ACCESS
    assert fi1.path_abs('json')   == FILE_PATH_ABS_JSON
    assert_raises(Exception, fi1, 'path_abs', 'BAD')
    
    fi2 = identifier.Identifier('/mnt/nfsdrive/ddr/ddr-test-123/files/ddr-test-123-456')
    assert fi2.path_abs()       == '/mnt/nfsdrive/ddr/ddr-test-123/files/ddr-test-123-456'
    assert fi2.path_abs('json') == '/mnt/nfsdrive/ddr/ddr-test-123/files/ddr-test-123-456/entity.json'


REPO_PATH_REL       = None
ORG_PATH_REL        = None
COLLECTION_PATH_REL = None
ENTITY_PATH_REL     = 'files/ddr-test-123-456'
FILE_PATH_REL       = 'files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5'
REPO_PATH_REL_JSON       = 'repository.json'
ORG_PATH_REL_JSON        = 'organization.json'
COLLECTION_PATH_REL_JSON = 'collection.json'
ENTITY_PATH_REL_JSON     = 'files/ddr-test-123-456/entity.json'
FILE_PATH_REL_JSON       = 'files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5.json'    
FILE_PATH_REL_ACCESS     = 'files/ddr-test-123-456/files/ddr-test-123-456-master-a1b2c3d4e5-a.jpg'

def test_path_rel():
    i0 = identifier.Identifier('ddr')
    assert i0.path_rel()         == REPO_PATH_REL
    assert i0.path_rel('json')   == REPO_PATH_REL_JSON
    assert_raises(Exception, i0, 'path_rel', 'BAD')
    
    i1 = identifier.Identifier('ddr-test')
    assert i1.path_rel()         == ORG_PATH_REL
    assert i1.path_rel('json')   == ORG_PATH_REL_JSON
    assert_raises(Exception, i1, 'path_rel', 'BAD')
    
    i2 = identifier.Identifier('ddr-test-123')
    assert i2.path_rel()         == COLLECTION_PATH_REL
    assert i2.path_rel('json')   == COLLECTION_PATH_REL_JSON
    assert_raises(Exception, i2, 'path_rel', 'BAD')
    
    i3 = identifier.Identifier('ddr-test-123-456')
    assert i3.path_rel()         == ENTITY_PATH_REL
    assert i3.path_rel('json')   == ENTITY_PATH_REL_JSON
    assert_raises(Exception, i3, 'path_rel', 'BAD')
    
    i4 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5')
    assert i4.path_rel()         == FILE_PATH_REL
    assert i4.path_rel('access') == FILE_PATH_REL_ACCESS
    assert i4.path_rel('json')   == FILE_PATH_REL_JSON
    assert_raises(Exception, i4, 'path_rel', 'BAD')


REPO_EDITOR_URL       = '/ui/ddr'
ORG_EDITOR_URL        = '/ui/ddr-test'
COLLECTION_EDITOR_URL = '/ui/ddr-test-123'
ENTITY_EDITOR_URL     = '/ui/ddr-test-123-456'
FILE_EDITOR_URL       = '/ui/ddr-test-123-456-master-a1b2c3d4e5'
REPO_PUBLIC_URL       = '/ddr'
ORG_PUBLIC_URL        = '/ddr/test'
COLLECTION_PUBLIC_URL = '/ddr/test/123'
ENTITY_PUBLIC_URL     = '/ddr/test/123/456'
FILE_PUBLIC_URL       = '/ddr/test/123/456/master/a1b2c3d4e5'

def test_urlpath():
    i0 = identifier.Identifier('ddr')
    assert i0.urlpath('editor') == REPO_EDITOR_URL
    assert i0.urlpath('public') == REPO_PUBLIC_URL
    
    i1 = identifier.Identifier('ddr-test')
    assert i1.urlpath('editor') == ORG_EDITOR_URL
    assert i1.urlpath('public') == ORG_PUBLIC_URL
    
    i2 = identifier.Identifier('ddr-test-123')
    assert i2.urlpath('editor') == COLLECTION_EDITOR_URL
    assert i2.urlpath('public') == COLLECTION_PUBLIC_URL
    
    i3 = identifier.Identifier('ddr-test-123-456')
    assert i3.urlpath('editor') == ENTITY_EDITOR_URL
    assert i3.urlpath('public') == ENTITY_PUBLIC_URL
    
    i4 = identifier.Identifier('ddr-test-123-456-master-a1b2c3d4e5')
    assert i4.urlpath('editor') == FILE_EDITOR_URL
    assert i4.urlpath('public') == FILE_PUBLIC_URL


