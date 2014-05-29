from datetime import datetime
import logging
import os

from dateutil import parser



SAMPLE_OLD_CHANGELOG = """* Added entity file files/ddr-testing-160-1-master-c703e5ece1-a.jpg
-- Geoffrey Jost <geoffrey.jost@densho.org>  Tue, 01 Oct 2013 14:33:35 

* Updated entity file /var/www/media/base/ddr-testing-160/files/ddr-testing-160-1/entity.json
* Updated entity file /var/www/media/base/ddr-testing-160/files/ddr-testing-160-1/mets.xml
-- Geoffrey Jost <geoffrey.jost@densho.org>  Wed, 02 Oct 2013 10:10:45 

* Updated entity file /var/www/media/base/ddr-testing-160/files/ddr-testing-160-1/files/ddr-testing-160-1-master-c703e5ece1.json
-- Geoffrey Jost <geoffrey.jost@densho.org>  Wed, 02 Oct 2013 10:11:08 
"""

def is_old_entry(txt):
    """Indicate whether this is an old entry.
    
    Sample:
    * Added entity file files/ddr-testing-160-1-master-c703e5ece1-a.jpg
    -- Geoffrey Jost <geoffrey.jost@densho.org>  Tue, 01 Oct 2013 14:33:35 
    """
    try:
        frag = txt.strip().split('\n').pop()[:2]
        if frag == '--':
            return True
    except:
        pass
    return False

def read_old_entry(txt):
    """Read old-style changelog and return entries as data.
    """
    lines = txt.strip().split('\n')
    stamp = lines.pop().replace('-- ', '').split('  ')
    user,mail = stamp[0].replace('>', '').split(' <')
    timestamp = parser.parse(stamp[1])
    messages = [l.replace('* ','') for l in lines]
    entry = {'timestamp':timestamp,
             'user':user,
             'mail':mail,
             'messages':messages,}
    return entry

SAMPLE_NEW_CHANGELOG = """2013-10-01 14:33:35 -- Geoffrey Jost <geoffrey.jost@densho.org>
* Added entity file files/ddr-testing-160-1-master-c703e5ece1-a.jpg

2013-10-02 10:10:45 -- Geoffrey Jost <geoffrey.jost@densho.org>
* Updated entity file /var/www/media/base/ddr-testing-160/files/ddr-testing-160-1/entity.json
* Updated entity file /var/www/media/base/ddr-testing-160/files/ddr-testing-160-1/mets.xml

2013-10-02 10:11:08 -- Geoffrey Jost <geoffrey.jost@densho.org>
* Updated entity file /var/www/media/base/ddr-testing-160/files/ddr-testing-160-1/files/ddr-testing-160-1-master-c703e5ece1.json
"""

def is_new_entry(txt):
    """Indicate whether this is a new entry.
    
    Sample:
    2013-10-01 14:33:35 -- Geoffrey Jost <geoffrey.jost@densho.org>
    * Added entity file files/ddr-testing-160-1-master-c703e5ece1-a.jpg
    """
    try:
        ts = parser.parse(txt.strip().split('\n')[0].split(' -- ')[0])
        return isinstance(ts, datetime)
    except:
        pass
    return False

def read_new_entry(txt):
    """Read new-style changelog and return entries as data.
    """
    lines = txt.strip().split('\n')
    stamp = lines[0].strip().split(' -- ')
    user,mail = stamp[1].replace('>', '').split(' <')
    timestamp = parser.parse(stamp[0])
    messages = [l.replace('* ','') for l in lines[1:]]
    entry = {'timestamp':timestamp,
             'user':user,
             'mail':mail,
             'messages':messages,}
    return entry

def read_entries(log):
    entries = []
    for e in log.split('\n\n'):
        entry = None
        if is_old_entry(e):
            entry = read_old_entry(e)
        elif is_new_entry(e):
            entry = read_new_entry(e)
        if entry:
            entries.append(entry)
    return entries

def read_changelog(path):
    """
    @param path: Absolute path to changelog file.
    @returns list of entry dicts
    """
    with open(path, 'r') as f:
        log = f.read()
    return read_entries(log)

def make_entry(messages, user, mail, timestamp=None):
    """Makes a (new-style) changelog entry.
    
    @param messages: List of strings.
    @param user: Person's name.
    @param mail: A valid email address.
    @param timestamp: datetime (optional).
    @returns string
    """
    if not timestamp:
        timestamp = datetime.now()
    stamp = '%s -- %s <%s>' % (timestamp.strftime('%Y-%m-%d %H:%M:%S'), user, mail)
    lines = [stamp] + ['* %s' % m for m in messages]
    return '\n'.join(lines)

def make_changelog(entries):
    cl = [make_entry(e['messages'], e['user'], e['mail'], e['timestamp']) for e in entries]
    return '\n\n'.join(cl)



MODULE_PATH   = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(MODULE_PATH, 'templates')
CHANGELOG_TEMPLATE    = os.path.join(TEMPLATE_PATH, 'changelog.tpl')
CHANGELOG_DATE_FORMAT = os.path.join(TEMPLATE_PATH, 'changelog-date.tpl')

def load_template(filename):
    template = ''
    with open(filename, 'r') as f:
        template = f.read()
    return template

def write_changelog_entry(path, messages, user, email, timestamp=None):
    logging.debug('    write_changelog_entry({})'.format(path))
    template = load_template(CHANGELOG_TEMPLATE)
    date_format = load_template(CHANGELOG_DATE_FORMAT)
    # one line per message
    lines = []
    [lines.append('* {}'.format(m)) for m in messages]
    changes = '\n'.join(lines)
    if not timestamp:
        timestamp = datetime.now()
    # render
    entry = template.format(
        changes=changes,
        user=user,
        email=email,
        date=timestamp.strftime(date_format)
        )
    try:
        preexisting = os.path.getsize(path)
    except:
        preexisting = False
    with open(path, 'a') as f:
        if preexisting:
            f.write('\n')
        f.write(entry)
