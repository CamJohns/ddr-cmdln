import os
import shutil

import config
import identifier
import inheritance
import models

MODEL_FIELDS_INHERITABLE = [
    {'name':'id',},
    {'name':'record_created',},
    {'name':'record_lastmod',},
    {'name':'status', 'inheritable':True,},
    {'name':'public', 'inheritable':True,},
    {'name':'title',},
]
def test_Inheritance_inheritable_fields():
    assert inheritance.inheritable_fields(MODEL_FIELDS_INHERITABLE) == ['status','public']

# TODO inheritance_inherit
# TODO inheritance_selected_inheritables
# TODO inheritance_update_inheritables


CHILD_JSONS_DIRS = [
    '.git',
    'files/ddr-test-123-1',
    'files/ddr-test-123-2',
    'files/ddr-test-123-2/files',
]
CHILD_JSONS_FILES = [
    'collection.json',
    '.git/config',
    'files/ddr-test-123-1/entity.json',
    'files/ddr-test-123-1/changelog',
    'files/ddr-test-123-2/entity.json',
    'files/ddr-test-123-2/control',
    'files/ddr-test-123-2/files/ddr-test-123-2-master-abc123.jpg',
    'files/ddr-test-123-2/files/ddr-test-123-2-master-abc123.json',
]
CHILD_JSONS_EXPECTED = [
    'files/ddr-test-123-1/entity.json',
    'files/ddr-test-123-2/entity.json',
    'files/ddr-test-123-2/files/ddr-test-123-2-master-abc123.json',
]

def test_child_jsons():
    pass
    basedir = '/tmp/test_DDR.inheritance.child_jsons'
    if os.path.exists(basedir):
        shutil.rmtree(basedir, ignore_errors=1)
    
    # build sample repo
    sampledir = os.path.join(basedir, 'ddr-test-123')
    for d in CHILD_JSONS_DIRS:
        path = os.path.join(sampledir, d)
        os.makedirs(path)
        print('path %s' % path)
    for fn in CHILD_JSONS_FILES:
        path = os.path.join(sampledir, fn)
        print('path %s' % path)
        with open(path, 'w') as f:
            f.write('testing')
    
    def clean(paths):
        base = '%s/' % sampledir
        cleaned = [path.replace(base, '') for path in paths]
        cleaned.sort()
        return cleaned
    
    paths0 = clean(inheritance._child_jsons(sampledir, testing=1))
    print('paths0 %s' % paths0)
    assert paths0 == CHILD_JSONS_EXPECTED

def test_selected_field_values():
    class Thing(object):
        pass
        
    parent = Thing()
    parent.a = 1
    parent.b = 2
    parent.c = 3
    inheritables = ['a', 'b', 'c']
    expected = [
        ('a', 1),
        ('b', 2),
        ('c', 3),
    ]
    values = inheritance._selected_field_values(parent, inheritables)
    assert values == expected

SELECTED_INHERITABLES = ['a', 'b']
SELECTED_DATA = {
    'a': False,
    'b': True,
    'a_inherit': False,
    'b_inherit': True,
}
SELECTED_EXPECTED = ['b']

def test_selected_inheritables():
    selected = inheritance.selected_inheritables(SELECTED_INHERITABLES, SELECTED_DATA)
    assert selected == SELECTED_EXPECTED

def test_inherit():
    # TODO this test depends on particular repo_models modules and fields
    collection = models.Collection(path_abs='/var/www/media/ddr/ddr-test-123')
    entity = models.Entity(path_abs='/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456')
    file_ = models.File(
        path_abs='/var/www/media/ddr/ddr-test-123/files/ddr-test-123-456/files/ddr-test-123-456-master-abc123'
    )
    
    collection.public = True
    entity.public = False
    assert collection.public == True
    assert entity.public == False
    inheritance.inherit(collection, entity)
    assert collection.public == True
    assert entity.public == True
    
    entity.public = True
    file_.public = False
    assert entity.public == True
    assert file_.public == False
    inheritance.inherit(entity, file_)
    assert entity.public == True
    assert file_.public == True
    
    collection.public = True
    file_.public = False
    assert collection.public == True
    assert file_.public == False
    inheritance.inherit(collection, file_)
    assert collection.public == True
    assert file_.public == True
