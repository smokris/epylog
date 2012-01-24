"""
This module is used to publish the report into a set of predefined
publisher classes. You can write your own, as long as they contain the
__init__ and publish methods.
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
# @Author Konstantin Ryabitsev <icon@linux.duke.edu>
# @version $Date$
#

import epylog
import os
import re
import socket
import time
import shutil
import gzip
import tempfile

if 'mkdtemp' not in dir(tempfile):
    ##
    # Must be python < 2.3
    #
    del tempfile
    import mytempfile as tempfile

def make_html_page(template, starttime, endtime, title, module_reports,
                   unparsed, logger):
    """
    Make a html page out of a set of parameters, which include
    module reports. Used by most, if not all, publishers.
    """
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
    """
    A memory-friendly way of compressing the data.
    """
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
    """
    Send mail using smtp.
    """
    logger.put(5, '>publishers.mail_smtp')
    import smtplib
    logger.puthang(3, 'Mailing it via the SMTP server %s' % smtpserv)
    server = smtplib.SMTP(smtpserv)
    server.sendmail(fromaddr, toaddr, msg)
    server.quit()
    logger.endhang(3)
    logger.put(5, '<publishers.mail_smtp')

def mail_sendmail(sendmail, msg, logger):
    """
    Send mail using sendmail.
    """
    logger.put(5, '>publishers.mail_sendmail')
    logger.puthang(3, 'Mailing the message via sendmail')
    p = os.popen(sendmail, 'w')
    p.write(msg)
    p.close()
    logger.endhang(3)
    logger.put(5, '<publishers.mail_sendmail')
    
class MailPublisher:
    """
    This publisher sends the results of an epylog run as an email message.
    """
    
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

        try:
            self.gpg_encrypt = config.getboolean(self.section, 'gpg_encrypt')

            try:
                # Copy the keyring specified into tmpprefix
                gpg_keyring = config.get(self.section, 'gpg_keyring')
                logger.put(5, 'Copying %s into %s' % (gpg_keyring, self.tmpprefix))
                shutil.copyfile(gpg_keyring, os.path.join(self.tmpprefix, 'pubring.gpg'))
                self.gpg_keyringdir = self.tmpprefix
            except:
                self.gpg_keyringdir = None

            try:
                gpg_recipients = config.get(self.section, 'gpg_recipients')
                addrs = gpg_recipients.split(',')
                self.gpg_recipients = []
                for addr in addrs:
                    addr = addr.strip()
                    logger.put(5, 'adding gpg_recipient=%s' % addr)
                    self.gpg_recipients.append(addr)
            except:
                # Will use all recipients found in the keyring
                self.gpg_recipients = None

        except:
            self.gpg_encrypt = 0
        
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
            tempfile.tempdir = self.tmpprefix
            logger.puthang(3, 'Creating a plaintext format of the report')
            htmlfile = tempfile.mktemp('.html')
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
            
        logger.puthang(3, 'Creating an email message')
        from email.mime.base      import MIMEBase
        from email.mime.text      import MIMEText
        from email.mime.multipart import MIMEMultipart

        logger.put(5, 'Creating a main header')

        root_part = MIMEMultipart('mixed')
        root_part.preamble = 'This is a multi-part message in MIME format.'

        logger.put(5, 'Creating the text/plain part')
        text_part = MIMEText(self.plainrep, 'plain', 'utf-8')
        logger.put(5, 'Creating the text/html part')
        html_part = MIMEText(self.htmlrep, 'html', 'utf-8')
        
        if self.rawlogs > 0:
            logger.put(5, 'Creating the application/x-gzip part')
            attach_part = MIMEBase('application', 'x-gzip')
            attach_part.set_payload(self.gzlogs)
            from email.encoders import encode_base64
            logger.put(5, 'Encoding the gzipped raw logs with base64')
            encode_base64(attach_part)
            attach_part.add_header('Content-Disposition', 'attachment', 
                                   filename='raw.log.gz')
        
        if self.format == 'both':
            # create another multipart for text+html
            alt_part = MIMEMultipart('alternative')
            alt_part.attach(text_part)
            alt_part.attach(html_part)
            root_part.attach(alt_part)
        elif self.format == 'html':
            root_part.attach(html_part)
        elif self.format == 'plain':
            root_part.attach(text_part)

        if self.rawlogs > 0:
            root_part.attach(attach_part)

        logger.endhang(3)

        if self.gpg_encrypt:
            logger.puthang(3, 'Encrypting the message')

            from StringIO import StringIO
            try:
                import gpgme

                if self.gpg_keyringdir and os.path.exists(self.gpg_keyringdir):
                    logger.put(5, 'Setting keyring dir to %s' % self.gpg_keyringdir)
                    os.environ['GNUPGHOME'] = self.gpg_keyringdir

                msg = root_part.as_string()
                logger.put(5, 'Cleartext follows')
                logger.put(5, msg)
                logger.put(5, 'Cleartext ends')

                cleartext = StringIO(msg)
                ciphertext = StringIO()

                ctx = gpgme.Context()
                ctx.armor = True

                recipients = []
                logger.put(5, 'self.gpg_recipients = %s' % self.gpg_recipients)

                if self.gpg_recipients is not None:
                    for recipient in self.gpg_recipients:
                        logger.puthang(5, 'Looking for a key for %s' % recipient)
                        recipients.append(ctx.get_key(recipient))
                        logger.endhang(5)
                else:
                    logger.put(5, 'Looking for all keys in the keyring')
                    for key in ctx.keylist():
                        for subkey in key.subkeys:
                            if subkey.can_encrypt:
                                logger.put(5, 'Found key=%s' % subkey.keyid)
                                recipients.append(key)
                                break

                ctx.encrypt(recipients, gpgme.ENCRYPT_ALWAYS_TRUST,
                            cleartext, ciphertext)

                gpg_envelope_part = MIMEMultipart('encrypted')
                gpg_envelope_part.set_param('protocol', 'application/pgp-encrypted', 
                                            header='Content-Type')
                gpg_envelope_part.preamble = 'This is an OpenPGP/MIME encrypted message (RFC 2440 and 3156)'

                gpg_mime_version_part = MIMEBase('application', 'pgp-encrypted')
                gpg_mime_version_part.add_header('Content-Disposition', 
                                                 'PGP/MIME version identification')
                gpg_mime_version_part.set_payload('Version: 1')

                gpg_payload_part = MIMEBase('application', 'octet-stream', 
                                            name='encrypted.asc')
                gpg_payload_part.add_header('Content-Disposition', 
                                            'OpenPGP encrypted message')
                gpg_payload_part.add_header('Content-Disposition', 'inline',
                                            filename='encrypted.asc')
                gpg_payload_part.set_payload(ciphertext.getvalue())

                gpg_envelope_part.attach(gpg_mime_version_part)
                gpg_envelope_part.attach(gpg_payload_part)

                root_part = gpg_envelope_part

            except ImportError:
                logger.endhang(3)
                logger.put(0, 'Install pygpgme for GPG encryption support.')
                logger.put(0, 'Not mailing the report out of caution.')
                return

            logger.endhang(3)

        root_part['Subject'] = title
        root_part['To'] = ', '.join(self.mailto)
        root_part['X-Mailer'] = epylog.VERSION
        
        logger.put(5, 'Creating the message as string')
        msg = root_part.as_string()

        logger.put(5, 'Message follows')
        logger.put(5, msg)
        logger.put(5, 'End of message')

        logger.put(3, 'Figuring out if we are using sendmail or smtplib')
        if re.compile('^/').search(self.smtpserv):
            mail_sendmail(self.smtpserv, msg, logger)
        else:
            fromaddr = 'root@%s' % socket.gethostname()
            mail_smtp(self.smtpserv, fromaddr, self.mailto, msg, logger)
        logger.put(1, 'Mailed the report to: %s' % ','.join(self.mailto))
        logger.put(5, '<MailPublisher.publish')


class FilePublisher:
    """
    FilePublisher publishes the results of an Epylog run into a set of files
    and directories on the hard drive.
    """
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

        logger.put(3, 'Looking if we should save rawlogs')
        try: self.save_rawlogs = config.getboolean(sec, 'save_rawlogs')
        except: self.save_rawlogs = 0
        if self.save_rawlogs:
            logger.put(3, 'Saving raw logs in the reports directory')
        
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
        """
        Removes the directories that are older than a certain date.
        """
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

            from email.mime.text import MIMEText
            eml = MIMEText('New Epylog report is available at:\r\n%s' % publoc)

            eml['Subject'] = '%s (report notification)' % title
            eml['To'] = ', '.join(self.notify)
            eml['X-Mailer'] = epylog.VERSION

            msg = eml.as_string()

            logger.put(3, 'Figuring out if we are using sendmail or smtplib')
            if re.compile('^/').search(self.smtpserv):
                mail_sendmail(self.smtpserv, msg, logger)
            else:
                fromaddr = 'root@%s' % socket.gethostname()
                mail_smtp(self.smtpserv, fromaddr, self.notify, msg, logger)
            logger.put(1, 'Notification mailed to: %s' % ','.join(self.notify))

        if self.save_rawlogs:
            logfilen = '%s.log' % self.filename
            logfile = os.path.join(self.path, '%s.gz' % logfilen)
            logger.put(3, 'Gzipping logs and writing them to %s' % logfilen)
            outfh = open(logfile, 'w+')
            do_chunked_gzip(rawfh, outfh, logfilen, logger)
            outfh.close()
            logger.put(1, 'Gzipped logs saved in: %s' % self.path)
        
        logger.put(5, '<FilePublisher.publish')
