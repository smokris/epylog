"""
Description will eventually go here.
"""
##
# Copyright (C) 2003 by Duke University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$
#
# @Author Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#

import epylog
import os
import re
import socket
import time
import shutil
import gzip

def make_html_page(template, starttime, endtime, title, module_reports,
                   unparsed, logger):
    logger.put(5, '>make_html_page')
    logger.put(3, 'Making a standard report page')
    fmtstr = re.sub(re.compile('%'), '%%', template)
    fmtstr = re.sub(re.compile('@@STARTTIME@@'), '%(starttime)s', fmtstr)
    fmtstr = re.sub(re.compile('@@ENDTIME@@'), '%(endtime)s', fmtstr)
    fmtstr = re.sub(re.compile('@@TITLE@@'), '%(title)s', fmtstr)
    fmtstr = re.sub(re.compile('@@HOSTNAME@@'), '%(hostname)s', fmtstr)
    fmtstr = re.sub(re.compile('@@MODULE_REPORTS@@'), '%(allrep)s', fmtstr)
    fmtstr = re.sub(re.compile('@@UNPARSED_STRINGS@@'), '%(unparsed)s', fmtstr)
    fmtstr = re.sub(re.compile('@@VERSION@@'), '%(version)s', fmtstr)
    logger.put(5, 'fmtstr=%s' % fmtstr)

    valumap = {}
    valumap['starttime'] = starttime
    valumap['endtime'] = endtime
    valumap['title'] = title
    valumap['hostname'] = socket.gethostname()
    
    logger.put(3, 'Concatenating the module reports together')
    allrep = ''
    for modrep in module_reports:
        logger.puthang(3, 'Processing report for "%s"' % modrep.name)
        allrep = '%s\n<h2>%s</h2>\n%s' % (allrep, modrep.name,
                                          modrep.htmlreport)
        logger.endhang(3)
    if allrep == '':
        allrep = 'No module reports'
    valumap['allrep'] = allrep
    
    if unparsed is not None:
        logger.put(3, 'Regexing <, > and &')
        unparsed = re.sub(re.compile('&'), '&amp;', unparsed)
        unparsed = re.sub(re.compile('<'), '&lt;',  unparsed)
        unparsed = re.sub(re.compile('>'), '&gt;',  unparsed)
        logger.put(3, 'Wrapping unparsed strings into <pre>')
        unparsed = '<pre>\n%s</pre>' % unparsed
    else:
        unparsed = 'No unparsed strings'
    valumap['unparsed'] = unparsed
    valumap['version'] = epylog.VERSION
    
    endpage = fmtstr % valumap
    logger.put(5, 'htmlreport follows:')
    logger.put(5, endpage)
    logger.put(5, '<make_html_page')
    return endpage

def do_chunked_gzip(infh, outfh, filename, logger):
    gzfh = gzip.GzipFile('rawlogs', fileobj=outfh)
    bartotal = infh.tell()
    bardone = 0
    bartitle = 'Gzipping %s' % filename
    infh.seek(0)
    logger.put(3, 'Doing chunked read from infh into gzfh')
    while 1:
        chunk = infh.read(epylog.CHUNK_SIZE)
        if not chunk:
            logger.put(5, 'Reached EOF')
            break
        gzfh.write(chunk)
        bardone += len(chunk)
        logger.progressbar(1, bartitle, bardone, bartotal)
        logger.put(3, 'Wrote %d bytes' % len(chunk))
    gzfh.close()
    logger.endbar(1, bartitle, 'gzipped down to %d bytes' % outfh.tell())

def mail_smtp(smtpserv, fromaddr, toaddr, msg, logger):
    logger.put(5, '>publishers.mail_smtp')
    import smtplib
    logger.puthang(3, 'Mailing it via the SMTP server %s' % smtpserv)
    server = smtplib.SMTP(smtpserv)
    server.sendmail(fromaddr, toaddr, msg)
    server.quit()
    logger.endhang(3)
    logger.put(5, '<publishers.mail_smtp')

def mail_sendmail(sendmail, msg, logger):
    logger.put(5, '>publishers.mail_sendmail')
    logger.puthang(3, 'Mailing the message via sendmail')
    p = os.popen(sendmail, 'w')
    p.write(msg)
    p.close()
    logger.endhang(3)
    logger.put(5, '<publishers.mail_sendmail')
    
class MailPublisher:
    name = 'Mail Publisher'
    
    def __init__(self, sec, config, logger):
        logger.put(5, '>MailPublisher.__init__')
        self.logger = logger
        self.tmpprefix = config.tmpprefix
        self.section = sec
        logger.put(3, 'Looking for required elements in mail method config')
        try:
            mailto = config.get(self.section, 'mailto')
            addrs = mailto.split(',')
            self.mailto = []
            for addr in addrs:
                addr = addr.strip()
                logger.put(5, 'adding mailto=%s' % addr)
                self.mailto.append(addr)
        except: self.mailto = ['root']

        try: format = config.get(self.section, 'format')
        except: format = 'both'

        if (format != 'plain') and (format != 'html') and (format != 'both'):
            msg = ('Format for Mail Publisher must be either "html", "plain",'
                   + ' or "both." Format "%s" is unknown') % format
            raise epylog.ConfigError(msg, logger)
        self.format = format

        if format != 'html':
            logger.put(3, 'Plaintext version requested. Checking for lynx')
            try: lynx = config.get(self.section, 'lynx')
            except:
                lynx = '/usr/bin/lynx'
                if not os.access(lynx, os.X_OK):
                    msg = 'Could not find "%s"' % lynx
                    raise epylog.ConfigError(msg, logger)
            self.lynx = lynx
            logger.put(3, 'Lynx found in "%s" and is executable' % self.lynx)

        try:
            include_rawlogs = config.getboolean(self.section,'include_rawlogs')
        except: include_rawlogs = 1

        if include_rawlogs:
            try: rawlogs = int(config.get(self.section, 'rawlogs_limit'))
            except: rawlogs = 200
            self.rawlogs = rawlogs * 1024
        else: self.rawlogs = 0
        
        try: self.smtpserv = config.get(self.section, 'smtpserv')
        except: self.smtpserv = 'localhost'

        logger.put(5, 'format=%s' % self.format)
        logger.put(5, 'rawlogs=%d' % self.rawlogs)
        logger.put(5, 'smtpserv=%s' % self.smtpserv)
        
        logger.put(5, '<MailPublisher.__init__')
        
    def publish(self, template, starttime, endtime, title, module_reports,
                unparsed_strings, rawfh):
        logger = self.logger
        logger.put(5, '>MailPublisher.publish')
        logger.puthang(3, 'Creating a standard html page report')
        html_report = make_html_page(template, starttime, endtime, title,
                                     module_reports, unparsed_strings, logger)
        self.htmlrep = html_report
        logger.endhang(3)

        self.plainrep = None
        if self.format != 'html':
            import mytempfile as tempfile
            tempfile.tempdir = self.tmpprefix
            logger.puthang(3, 'Creating a plaintext format of the report')
            htmlfile = tempfile.mktemp('HTML')
            tfh = open(htmlfile, 'w')
            tfh.write(html_report)
            tfh.close()
            logger.put(3, 'HTML report is in "%s"' % htmlfile)
            plainfile = tempfile.mktemp('PLAIN')
            logger.put(3, 'PLAIN report will go into "%s"' % plainfile)
            logger.put(3, 'Making a syscall to "%s"' % self.lynx)
            exitcode = os.system('%s -dump %s > %s 2>/dev/null'
                                 % (self.lynx, htmlfile, plainfile))
            if exitcode or not os.access(plainfile, os.R_OK):
                msg = 'Error making a call to "%s"' % self.lynx
                raise epylog.SysCallError(msg, logger)
            logger.puthang(3, 'Reading in the plain version')
            tfh = open(plainfile)
            self.plainrep = tfh.read()
            tfh.close()
            logger.put(5, 'plainrep follows:')
            logger.put(5, self.plainrep)
            logger.endhang(3)
            logger.endhang(3)

        if self.rawlogs:
            ##
            # GzipFile doesn't work with StringIO. :/ Bleh.
            #
            import mytempfile as tempfile
            tempfile.tempdir = self.tmpprefix
            outfh = open(tempfile.mktemp('GZIP'), 'w+')
            do_chunked_gzip(rawfh, outfh, 'rawlogs', logger)
            size = outfh.tell()
            if size > self.rawlogs:
                logger.put(1, '%d is over the defined max of "%d"'
                           % (size, self.rawlogs))
                logger.put(1, 'Not attaching the raw logs')
                self.rawlogs = 0
            else:
                logger.put(5, 'Reading in the gzipped logs')
                outfh.seek(0)
                self.gzlogs = outfh.read()
            outfh.close()
            
        ##
        # Using MimeWriter, since package 'email' doesn't come with rhl-7.3
        # Suck-o.
        #
        logger.puthang(3, 'Creating an email message')
        import StringIO, MimeWriter
        fh = StringIO.StringIO()
        logger.put(5, 'Creating a main header')
        mw = MimeWriter.MimeWriter(fh)
        mw.addheader('Subject', title)
        if len(self.mailto) > 1:
            import string
            tostr = string.join(self.mailto, ', ')
        else:
            tostr = self.mailto[0]
        mw.addheader('To', tostr)
        mw.addheader('X-Mailer', epylog.VERSION)
        self.mw = mw
        
        if self.rawlogs > 0 and self.format == 'both':
            logger.put(5, 'Making a html + plain + gzip message')
            self._mk_both_rawlogs()
        elif self.rawlogs > 0 and self.format == 'html':
            logger.put(5, 'Making a html + gzip message')
            self._mk_html_rawlogs()
        elif self.rawlogs > 0 and self.format == 'plain':
            logger.put(5, 'Making a plain + gzip message')
            self._mk_plain_rawlogs()
        elif self.rawlogs == 0 and self.format == 'both':
            logger.put(5, 'Making a html + plain message')
            self._mk_both_nologs()
        elif self.rawlogs == 0 and self.format == 'html':
            logger.put(5, 'Making a html message')
            self._mk_html_nologs()
        elif self.rawlogs == 0 and self.format == 'plain':
            logger.put(5, 'Making a plain message')
            self._mk_plain_nologs()
        logger.endhang(3)

        fh.seek(0)
        msg = fh.read()
        fh.close()
        logger.put(5, 'Message follows')
        logger.put(5, msg)
        logger.put(5, 'End of message')

        logger.put(3, 'Figuring out if we are using sendmail or smtplib')
        if re.compile('^/').search(self.smtpserv):
            mail_sendmail(self.smtpserv, msg, logger)
        else:
            fromaddr = 'root@%s' % socket.gethostname()
            mail_smtp(self.smtpserv, fromaddr, self.mailto, msg, logger)
        logger.put(1, 'Mailed the report to: %s' % tostr)
        logger.put(5, '<MailPublisher.publish')

    def _mk_both_rawlogs(self):
        self.logger.put(5, '>MailPublisher._mk_both_rawlogs')
        import base64
        logger = self.logger
        mixed_mw = self.mw
        mixed_mw.addheader('Mime-Version', '1.0')
        logger.put(5, 'Creating a multipart/mixed part')
        mixed_mw.startmultipartbody('mixed')

        logger.put(5, 'Creating a multipart/alternative part')
        alt_mw = mixed_mw.nextpart()
        alt_mw.startmultipartbody('alternative')

        logger.put(5, 'Creating a text/plain part')
        plain_mw = alt_mw.nextpart()
        plain_mw.addheader('Content-Transfer-Encoding', '8bit')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(self.plainrep)

        logger.put(5, 'Creating a text/html part')
        html_mw = alt_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', '8bit')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(self.htmlrep)

        alt_mw.lastpart()
        logger.put(5, 'Creating an application/gzip part')
        gzip_mw = mixed_mw.nextpart()
        gzip_mw.addheader('Content-Transfer-Encoding', 'base64')
        gzip_mw.addheader('Content-Disposition',
                          'attachment; filename=rawlogs.gz')
        gzip_fh = gzip_mw.startbody('application/gzip; NAME=rawlogs.gz')
        gzip_fh.write(base64.encodestring(self.gzlogs))
        mixed_mw.lastpart()
        self.logger.put(5, '<MailPublisher._mk_both_rawlogs')

    def _mk_html_rawlogs(self):
        self.logger.put(5, '>MailPublisher._mk_html_rawlogs')
        import base64
        logger = self.logger
        mixed_mw = self.mw
        mixed_mw.addheader('Mime-Version', '1.0')
        logger.put(5, 'Creating a multipart/mixed part')
        mixed_mw.startmultipartbody('mixed')

        logger.put(5, 'Creating a text/html part')
        html_mw = mixed_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', '8bit')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(self.htmlrep)

        logger.put(5, 'Creating an application/gzip part')
        gzip_mw = mixed_mw.nextpart()
        gzip_mw.addheader('Content-Transfer-Encoding', 'base64')
        gzip_mw.addheader('Content-Disposition',
                          'attachment; filename=rawlogs.gz')
        gzip_fh = gzip_mw.startbody('application/gzip; NAME=rawlogs.gz')
        gzip_fh.write(base64.encodestring(self.gzlogs))
        mixed_mw.lastpart()
        self.logger.put(5, '<MailPublisher._mk_html_rawlogs')

    def _mk_plain_rawlogs(self):
        self.logger.put(5, '>MailPublisher._mk_plain_rawlogs')
        import base64
        logger = self.logger
        mixed_mw = self.mw
        mixed_mw.addheader('Mime-Version', '1.0')
        logger.put(5, 'Creating a multipart/mixed part')
        mixed_mw.startmultipartbody('mixed')

        logger.put(5, 'Creating a text/plain part')
        plain_mw = mixed_mw.nextpart()
        plain_mw.addheader('Content-Transfer-Encoding', '8bit')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(self.plainrep)

        logger.put(5, 'Creating an application/gzip part')
        gzip_mw = mixed_mw.nextpart()
        gzip_mw.addheader('Content-Transfer-Encoding', 'base64')
        gzip_mw.addheader('Content-Disposition',
                          'attachment; filename=rawlogs.gz')
        gzip_fh = gzip_mw.startbody('application/gzip; NAME=rawlogs.gz')
        gzip_fh.write(base64.encodestring(self.gzlogs))
        mixed_mw.lastpart()
        self.logger.put(5, '<MailPublisher._mk_plain_rawlogs')

    def _mk_both_nologs(self):
        self.logger.put(5, '>MailPublisher._mk_both_nologs')
        logger = self.logger
        alt_mw = self.mw
        alt_mw.addheader('Mime-Version', '1.0')
        logger.put(5, 'Creating a multipart/alternative part')
        alt_mw.startmultipartbody('alternative')

        logger.put(5, 'Creating a text/plain part')
        plain_mw = alt_mw.nextpart()
        plain_mw.addheader('Content-Transfer-Encoding', '8bit')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(self.plainrep)

        logger.put(5, 'Creating a text/html part')
        html_mw = alt_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', '8bit')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(self.htmlrep)

        alt_mw.lastpart()
        self.logger.put(5, '<MailPublisher._mk_both_nologs')

    def _mk_html_nologs(self):
        self.logger.put(5, '>MailPublisher._mk_html_nologs')
        logger = self.logger
        alt_mw = self.mw
        alt_mw.addheader('Mime-Version', '1.0')
        logger.put(5, 'Creating a multipart/alternative part')
        alt_mw.startmultipartbody('alternative')
        logger.put(5, 'Creating a text/html part')
        html_mw = alt_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', '8bit')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(self.htmlrep)
        alt_mw.lastpart()
        self.logger.put(5, '<MailPublisher._mk_html_nologs')

    def _mk_plain_nologs(self):
        self.logger.put(5, '>MailPublisher._mk_plain_nologs')
        logger = self.logger
        plain_mw = self.mw
        logger.put(5, 'Creating a text/plain part')
        plain_mw.addheader('Content-Transfer-Encoding', '8bit')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(self.plainrep)
        self.logger.put(5, '<MailPublisher._mk_plain_nologs')


class FilePublisher:
    name = 'File Publisher'
    def __init__(self, sec, config, logger):
        logger.put(5, '>FilePublisher.__init__')
        self.logger = logger
        self.tmpprefix = config.tmpprefix
        logger.put(3, 'Looking for required elements in file method config')
        msg = 'Required attribute "%s" not found'
        try: expire = int(config.get(sec, 'expire_in'))
        except: epylog.ConfigError(msg % 'expire_in', logger)
        
        try: dirmask = config.get(sec, 'dirmask')
        except: epylog.ConfigError(msg % 'dirmask', logger)
        try: filemask = config.get(sec, 'filemask')
        except: epylog.ConfigError(msg % 'filemask', logger)

        logger.put(3, 'Verifying dirmask and filemask')
        msg = 'Invalid mask for %s: %s'
        try: self.dirname = time.strftime(dirmask, time.localtime())
        except: epylog.ConfigError(msg % ('dirmask', dirmask), logger)
        try: path = config.get(sec, 'path')
        except: epylog.ConfigError(msg % 'path', logger)
        try: self.filename = time.strftime(filemask, time.localtime())
        except: epylog.ConfigError(msg % ('filemask', filemask), logger)
        self._prune_old(path, dirmask, expire)
        self.path = os.path.join(path, self.dirname)

        logger.put(3, 'Checking if notify is set')
        self.notify = []
        try:
            notify = config.get(sec, 'notify')
            for addy in notify.split(','):
                addy = addy.strip()
                logger.put(3, 'Will notify: %s' % addy)
                self.notify.append(addy)
        except: pass
        try: self.smtpserv = config.get(sec, 'smtpserv')
        except: self.smtpserv = '/usr/sbin/sendmail -t'
        if self.notify:
            try:
                self.pubroot = config.get(sec, 'pubroot')
                logger.put(5, 'pubroot=%s' % self.pubroot)
            except:
                msg = 'File publisher requires a pubroot when notify is set'
                raise epylog.ConfigError(msg, logger)
        
        logger.put(5, 'path=%s' % self.path)
        logger.put(5, 'filename=%s' % self.filename)
        logger.put(5, '<FilePublisher.__init__')

    def _prune_old(self, path, dirmask, expire):
        logger = self.logger
        logger.put(5, '>FilePublisher._prune_old')
        logger.put(3, 'Pruning directories older than %d days' % expire)
        expire_limit = int(time.time()) - (86400 * expire)
        logger.put(5, 'expire_limit=%d' % expire_limit)
        if not os.path.isdir(path):
            logger.put(3, 'Dir %s not found -- skipping pruning' % path)
            logger.put(5, '<FilePublisher._prune_old')
            return
        for entry in os.listdir(path):
            logger.put(5, 'Found: %s' % entry)
            if os.path.isdir(os.path.join(path, entry)):
                logger.put(3, 'Found directory %s' % entry)
                logger.put(4, 'Trying to strptime it into a timestamp')
                try: stamp = time.mktime(time.strptime(entry, dirmask))
                except ValueError, e:
                    logger.put(3, 'Dir %s did not match dirmask %s: %s'
                               % (entry, dirmask, e))
                    logger.put(3, 'Skipping %s' % entry)
                    continue
                if stamp < expire_limit:
                    logger.put(3, '%s is older than expire limit')
                    shutil.rmtree(os.path.join(path, entry))
                    logger.put(1, 'File Publisher: Pruned old directory: %s'
                               % entry)
                else:
                    logger.put(3, '%s is still active' % entry)
            else:
                logger.put(3, '%s is not a directory. Skipping.' % entry)
        logger.put(3, 'Finished with pruning')
        logger.put(5, '<FilePublisher._prune_old')
        
    def publish(self, template, starttime, endtime, title, module_reports,
                unparsed_strings, rawfh):
        logger = self.logger
        logger.put(5, '>FilePublisher.publish')
        logger.put(3, 'Checking and creating the report directories')
        if not os.path.isdir(self.path):
            try: os.makedirs(self.path)
            except OSError, e:
                logger.put(0, 'Error creating directory "%s": %s' %
                           (self.path, e))
                logger.put(0, 'File publisher exiting.')
                return
        logger.puthang(3, 'Creating a standard html page report')
        html_report = make_html_page(template, starttime, endtime, title,
                                     module_reports, unparsed_strings, logger)
        logger.endhang(3)
        filename = '%s.html' % self.filename
        repfile = os.path.join(self.path, filename)
        logger.put(3, 'Dumping the report into %s' % repfile)
        fh = open(repfile, 'w')
        fh.write(html_report)
        fh.close()
        logger.put(1, 'Report saved in: %s' % self.path)
        if self.notify:
            logger.puthang(3, 'Creating an email message')
            publoc = '%s/%s/%s' % (self.pubroot, self.dirname, filename)
            msg = 'New Epylog report is available at:\r\n%s' % publoc
            import StringIO, MimeWriter
            fh = StringIO.StringIO()
            logger.put(3, 'Creating a main header')
            mw = MimeWriter.MimeWriter(fh)
            mw.addheader('Subject', '%s (report notification)' % title)
            tostr = ', '.join(self.notify)
            mw.addheader('To', tostr)
            mw.addheader('X-Mailer', epylog.VERSION)
            mw.addheader('Content-Transfer-Encoding', '8bit')
            bfh = mw.startbody('text/plain; charset=iso-8859-1')
            bfh.write(msg)
            fh.seek(0)
            msg = fh.read()
            fh.close()
            logger.put(3, 'Figuring out if we are using sendmail or smtplib')
            if re.compile('^/').search(self.smtpserv):
                mail_sendmail(self.smtpserv, msg, logger)
            else:
                fromaddr = 'root@%s' % socket.gethostname()
                mail_smtp(self.smtpserv, fromaddr, self.notify, msg, logger)
            logger.put(1, 'Notification mailed to: %s' % tostr)

        logfilen = '%s.log' % self.filename
        logfile = os.path.join(self.path, '%s.gz' % logfilen)
        logger.put(3, 'Gzipping logs and writing them to %s' % logfilen)
        outfh = open(logfile, 'w+')
        do_chunked_gzip(rawfh, outfh, logfilen, logger)
        outfh.close()
        logger.put(1, 'Gzipped logs saved in: %s' % self.path)
        logger.put(5, '<FilePublisher.publish')
