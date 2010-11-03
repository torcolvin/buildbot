#!/usr/bin/env python
"""
github_buildbot.py is based on git_buildbot.py

github_buildbot.py will determine the repository information from the JSON 
HTTP POST it receives from github.com and build the appropriate repository.
If your github repository is private, you must add a ssh key to the github
repository for the user who initiated the build on the buildslave.

"""

import logging
import re
import sys
import traceback
from buildbot.changes.changes import Change
import datetime
from twisted.python import log
import calendar

try:
    import json
    assert json
except ImportError:
    import simplejson as json

# python is silly about how it handles timezones
class fixedOffset(datetime.tzinfo):
    """
    fixed offset timezone
    """
    def __init__(self, minutes, hours, offsetSign = 1):
        self.minutes = int(minutes) * offsetSign
        self.hours   = int(hours)   * offsetSign
        self.offset  = datetime.timedelta(minutes = self.minutes,
                                         hours   = self.hours)

    def utcoffset(self, dt):
        return self.offset

    def dst(self, dt):
        return datetime.timedelta(0)
    
def convertTime(myTestTimestamp):
    #"1970-01-01T00:00:00+00:00"
    matcher = re.compile(r'(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)([-+])(\d\d):(\d\d)')
    result  = matcher.match(myTestTimestamp)
    (year, month, day, hour, minute, second, offsetsign, houroffset, minoffset) = \
        result.groups()
    if offsetsign == '+':
        offsetsign = 1
    else:
        offsetsign = -1
    
    offsetTimezone = fixedOffset( minoffset, houroffset, offsetsign )
    myDatetime = datetime.datetime( int(year),
                                    int(month),
                                    int(day),
                                    int(hour),
                                    int(minute),
                                    int(second),
                                    0,
                                    offsetTimezone)
    return calendar.timegm( myDatetime.utctimetuple() )

def getChanges(request, options = None):
        """
        Reponds only to POST events and starts the build process
        
        :arguments:
            request
                the http request object
        """
        try:
            payload = json.loads(request.args['payload'][0])
            user = payload['repository']['owner']['name']
            repo = payload['repository']['name']
            repo_url = payload['repository']['url']
            # This field is unused:
            #private = payload['repository']['private']
            changes = process_change(payload, user, repo, repo_url)
            log.msg("Received %s changes from github" % len(changes))
            return changes
        except Exception:
            logging.error("Encountered an exception:")
            for msg in traceback.format_exception(*sys.exc_info()):
                logging.error(msg.strip())

def process_change(payload, user, repo, repo_url):
        """
        Consumes the JSON as a python object and actually starts the build.
        
        :arguments:
            payload
                Python Object that represents the JSON sent by GitHub Service
                Hook.
        """
        changes = []
        newrev = payload['after']
        refname = payload['ref']
        log.msg( "in process_change" )
        # We only care about regular heads, i.e. branches
        match = re.match(r"^refs\/heads\/(.+)$", refname)
        if not match:
            logging.info("Ignoring refname `%s': Not a branch" % refname)

        branch = match.group(1)
        if re.match(r"^0*$", newrev):
            log.msg("Branch `%s' deleted, ignoring" % branch)
            return []
        else: 
            for commit in payload['commits']:
                files = []
                if 'added' in commit:
                    files.extend(commit['added'])
                if 'modified' in commit:
                    files.extend(commit['modified'])
                if 'removed' in commit:
                    files.extend(commit['removed'])
                when =  convertTime( commit['timestamp'])
                change = {'revision': commit['id'],
                     'revlink': commit['url'],
                     'comments': commit['message'],
                     'branch': branch,
                     'who': commit['author']['name'] 
                            + " <" + commit['author']['email'] + ">",
                     'files': files,
                     'links': [commit['url']],
                     'properties': {'repository': repo_url},
                }
    
                log.msg("New revision: %s" % change['revision'][:8])
                for key, value in change.iteritems():
                    logging.debug("  %s: %s" % (key, value))
                    changeObject = Change(\
                        who      = commit['author']['name'] 
                                    + " <" + commit['author']['email'] + ">",
                        files    = files,
                        comments = commit['message'], 
                        links    = [commit['url']],
                        revision = commit['id'],
                        when     = when,
                        branch   = branch,
                        revlink  = commit['url'], 
                        repository = repo_url)  
                changes.append(changeObject) 
            return changes
        