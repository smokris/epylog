#!/usr/bin/python -tt
import sys
import re

##
# This is for testing purposes, so you can invoke this from the
# modules directory. See also the testing notes at the end of the
# file.
#
sys.path.insert(0, '../py/')
from epylog import InternalModule

class weeder_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
        rc = re.compile

        weed_dist   = opts.get('weed_dist', '/etc/epylog/weed_dist.cf')
        weed_local  = opts.get('weed_local', '/etc/epylog/weed.local.cf')

        weed_dist = weed_dist.strip()
        weed_local = weed_local.strip()
        
        logger.put(5, 'weed_dist=%s' % weed_dist)
        logger.put(5, 'weed_local=%s' % weed_local)
        weed = {}
        self.regex_map = {}
        self.section_re = rc('^\s*\[(.*)\]\s*$')
        self.comment_re = rc('^\s*#')
        self.empty_re = rc('^\s*$')

        for weedfile in [weed_dist, weed_local]:
            try: weed = self._read_weed(open(weedfile), weed)
            except: logger.put(5, 'Error reading %s' % weedfile)
        if not weed: return

        if 'REMOVE' in weed:
            removes = weed['REMOVE']
            del weed['REMOVE']
            for remove in removes:
                for key in weed.keys():
                    if remove in weed[key]:
                        regexes = weed[key]
                        weed[key] = []
                        for regex in regexes:
                            if regex != remove: weed[key].append(regex)
        
        enable = opts.get('enable', '').split(',')
        if 'ADD' in weed: enable.append('ADD')
        for key in enable:
            key = key.strip()
            regexes = weed.get(key, [])
            for regex in regexes:
                try: regex_re = rc(regex)
                except:
                    logger.put(5, 'Error compiling regex "%s"' % regex)
                    continue
                self.regex_map[regex_re] = self.do_weed
        
    def _read_weed(self, fh, weed):
        section = 'default'
        while 1:
            line = fh.readline()
            if not line: break
            if self.comment_re.search(line): continue
            if self.empty_re.search(line): continue
            mo = self.section_re.search(line)
            if mo: section = mo.group(1)
            else:
                try: weed[section].append(line.strip())
                except KeyError: weed[section] = [line.strip()]
        return weed
            
    ##
    # Line-matching routines
    #
    def do_weed(self, linemap):
        return {1: linemap['multiplier']}

    def finalize(self, rs):
        report = '<p>Total messages weeded: <b>%d</b></p>' % rs[1]
        return report

if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(weeder_mod, sys.argv)
