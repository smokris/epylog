#!/usr/bin/perl -w
# mail.mod.pl
# ----------------
#
# Copyright (C) 2001-2002 by Duke University
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
# @Author  Michael D. Stenner <mstenner@phy.duke.edu>
#          Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#
=pod

=head1 NAME

mail.mod.pl - a epylog module.

=head1 DESCRIPTION

This module processes maillog entries. It currently detects and
analyzes entries from sendmail, postfix, and qmail+xinetd.

=head1 OPTIONS

This module accepts one configuration setting passed via the ENV
variable.

=over 5

=item MAIL_MODULE_TOPMOST

How many "topmost" entries max to output. If unset, defaults to 5.

=back

=cut

##
# Strict enforces good coding practices by making you observe the
# variable scope.
# Add other packages, too.
#
use strict;
use epylog;

=pod

=head1 OUTPUT FORMAT OPTIONS

There are three formatting rules that affect the final report.

=over 5

=item $reps = '%-30s: %d';

How to report various totals.

=item $topmosts = '     %s (%d)';

The format of the "topmost" section.

=back

=cut

##
# Sprintf rules.
#
my $reps     = '%-30s: %d';
my $topmosts = '     %s (%d)';

##
# Globals
#
my $struct;

##
# Main module code.
#
my $du = new epylog();
$du->init('mail');
$du->mlog(1, "beginning to read input");

##
# Iterate through all lines in the logs and analyze the ones that
# match.
#
while ($du->islogeof() == 0) {
    my $line = $du->nextline();
    if ($line =~ /postfix\//){
        do_postfix($line);
    } elsif ($line =~ /qmail:/){
        do_qmail($line);
    } elsif ($line =~ /xinetd\S+:\s+START:\s+smtp\s+/) {
        ##
        # Since there is no way to track what message id these
        # correlate to, we will just append these to the
        # separate field in $struct.
        #
        (my $host) = $line =~ m/.*\sfrom=(\S+).*/;
        $du->mlog(1, "doing a DNS lookup on $host");
        $host = $du->gethost($host);
        $struct->{'remotehost'}{$host}++;
        $du->pushfilt($line);
    } elsif ($line =~ /xinetd\S+:\s+EXIT:\s+smtp\s+/) {
        $du->pushfilt($line);
    } elsif ($line =~ /sendmail\[\d+\]:/){
        do_sendmail($line);
    }
}
$du->mlog(1, "finished reading input");

##
# See if we've done anything useful.
#
if ($du->filtsize() > 0){
    $du->mlog(1, "generating the report");
    $du->pushrep($du->mkrephdr('MAIL ACTIVITY'));
    ##
    # How many total messages?
    #
    my $total = keys(%{$struct->{'msg'}});
    if ($total > 0){
        $du->pushrep(sprintf($reps, 'Total messages processed', $total));
        if (defined($struct->{'smtpd'}{'reject'})){
            $du->pushrep(sprintf($reps, 'Total SMTP bounces',
                                 $struct->{'smtpd'}{'reject'}));
        }
        if (defined($struct->{'smtpd'}{'warning'})){
            $du->pushrep(sprintf($reps, 'Total SMTP warnings',
                                 $struct->{'smtpd'}{'warning'}));
        }
        my $totalpcm = 0;
        my $totalrel = 0;
        if (defined($struct->{'local'}{'procmail'})){
            $totalpcm = $struct->{'local'}{'procmail'};
        }
        if (defined($struct->{'local'}{'relay'})){
            $totalrel = $struct->{'local'}{'relay'};
        }
        if ($totalpcm > 0){
            $du->pushrep(sprintf($reps, 'Processed by procmail', $totalpcm));
        }
        if ($totalrel > 0){
            $du->pushrep(sprintf($reps, 'Forwarded elsewhere', $totalrel));
        }
        
        ##
        # Iterate through the 'msg' array and process our findings
        #
        my $find;
        my $ident;
        my $totalsize = 0;
        foreach $ident (keys(%{$struct->{'msg'}})){
            my $from = $struct->{'msg'}{$ident}{'from'};
            if (!defined($from)){
                $from = 'unknown';
            }
            my $size = $struct->{'msg'}{$ident}{'size'};
            if (defined($size)){
                $totalsize += $size;
            }
            my $to = $struct->{'msg'}{$ident}{'to'};
            if (!defined($to)){
                $to = 'unknown';
            }
            my $system = $struct->{'msg'}{$ident}{'system'};
            if (!defined($system)){
                $system = 'unknown';
            }
            my $status = $struct->{'msg'}{$ident}{'status'};
            if (!defined($status)){
                $status = 'unknown';
            }
            if (defined($find->{from}{$from})){
                $find->{from}{$from}++;
            } else {
                $find->{from}{$from} = 1;
            }
            if (defined($find->{to}{$to})){
                $find->{to}{$to}++;
            } else {
                $find->{to}{$to} = 1;
            }
            if (defined($find->{system}{$system})){
                $find->{system}{$system}++;
            } else {
                $find->{system}{$system} = 1;
            }
            if (defined($find->{status}{$status})){
                $find->{status}{$status}++;
            } else {
                $find->{status}{$status} = 1;
            }
        }
        if (defined($find->{status}{'success'})){
            $du->pushrep(sprintf($reps, 'Total successful deliveries',
                                 $find->{status}{'success'}));
        }
        if (defined($find->{status}{'failure'})){
            $du->pushrep(sprintf($reps, 'Various delivery failures',
                                 $find->{status}{'failure'}));
        }
        $totalsize = int($totalsize/1024);
        my $unit = 'Kb';
        if ($totalsize > 1024){
            $totalsize = int($totalsize/1024);
            $unit = 'Mb';
        }
        $du->pushrep(sprintf($reps, "Total transferred size ($unit)",
                             $totalsize));
        $du->pushrep('');
        ##
        # Figure out topmosts.
        #
        my $topmost = $du->option('MAIL_MODULE_TOPMOST', 5);
        do_counts($struct, 'remotehost', 'connecting hosts', $topmost);
        do_counts($find, 'from', 'senders', $topmost);
        do_counts($find, 'to', 'recipients', $topmost);
        do_counts($find, 'system', 'active local systems', $topmost);
    }
}

##
# Don't forget to call finalize()!
#
$du->mlog(1, "Finalizing");
$du->finalize();
$du->mlog(1, "Exiting...");


###########################################################
# subroutines

##
# This subroutine counts the total number of a certain type of
# messages and outputs the top NN of them.
#
# @param  $1  The hash reference of the object containing nested 
#              hashes.
# @param  $2  The topmost hash key to analyze.
# @param  $3  The description of what we are doing.
# @param  $4  How many topmost entries to output.
#
sub do_counts {
    my $find = shift;
    my $param = shift;
    ##
    # Should I really be doing this?
    #
    delete($find->{$param}{'unknown'});
    my $totalcount = keys(%{$find->{$param}});
    if ($totalcount <= 0){
        return;
    }
    my $description = shift;
    my $limit = shift;
    my @topname;
    my $count = 0;
    foreach my $key (sort {$find->{$param}{$b} <=> $find->{$param}{$a}}
                     keys(%{$find->{$param}})){
        if ($count >= $limit) {
            last;
        }
        $count++;
        push(@topname, $key);
    }
    $du->pushrep("$limit topmost $description ($totalcount total):");
    foreach my $member (@topname){
        my $rep = sprintf($topmosts, $member, $find->{$param}{$member});
        $du->pushrep($rep);
    }
}

##
# Analyze postfix-style syslog mail entry.
#
# @param  $1  The syslog line to analyze.
#
sub do_postfix {
    my $service;
    my $line = shift;
    ($service) = $line =~ m/.* postfix\/(\w+)\S*:.*/;
    if (!defined($service)){
        return;
    }
    if ($service eq 'smtpd'){
        ##
        # Ignore connect/disconnect and timeout messages
        #
        if ($line !~ /connect/ && $line !~ /timeout/ && $line !~ /gethostby/){
            my $ident = get_postfix_ident($line);
            if ($ident eq 'reject'){
                if (defined($struct->{'smtpd'}{'reject'})){
                    $struct->{'smtpd'}{'reject'}++;
                } else {
                    $struct->{'smtpd'}{'reject'}=1;
                }
            } elsif ($ident eq 'warning') {
                if (defined($struct->{'smtpd'}{'warning'})){
                    $struct->{'smtpd'}{'warning'}++;
                } else {
                    $struct->{'smtpd'}{'warning'}=1;
                }
            } elsif ($line =~ /client=/) {
                ##
                # Grab the hostname/IP.
                #
                (my $host, my $ip) = $line =~ m/.* client=(\S*)\[(\S*)\].*/;
                if ($host eq 'unknown'){
                    $host = $ip;
                }
                if (defined($struct->{'remotehost'}{$host})){
                    $struct->{'remotehost'}{$host}++;
                } else {
                    $struct->{'remotehost'}{$host} = 1;
                }
            }
        }
        $du->pushfilt($line);
    } elsif ($service eq 'nqmgr'){
        if ($line =~ /from=/){
            ##
            # Grab ident
            #
            my $ident = get_postfix_ident($line);
            ##
            # Grab from and size
            #
            (my $from, my $size) = $line =~ m/.*from=(<.*>), size=(\d*),.*/;
            if (!defined($from)){
                $from = 'unknown';
            } else {
                $from = lc($from);
            }
            if (!defined($size)){
                $size = 0;
            }
            if ($from eq '<>'){
                $from = '<mailer-daemon>';
            }
            $struct->{'msg'}{$ident}{'from'} = $from;
            $struct->{'msg'}{$ident}{'size'} = $size;
            ##
            # Grab system while we're at it.
            #
            my $system = $du->getsystem($line);
            $struct->{'msg'}{$ident}{'system'} = $system;
        } elsif ($line =~ /status=deferred/){
            ##
            # Log and quietly ignore.
            #
            if (defined($struct->{'smtpd'}{'warning'})){
                $struct->{'smtpd'}{'warning'}++;
            } else {
                $struct->{'smtpd'}{'warning'}=1;
            }
        } elsif ($line =~ /status=bounced/){
            ##
            # Log and quietly ignore
            #
            if (defined($struct->{'smtpd'}{'reject'})){
                $struct->{'smtpd'}{'reject'}++;
            } else {
                $struct->{'smtpd'}{'reject'}=1;
            }
        }
        $du->pushfilt($line);
    } elsif ($service eq 'local' && $line =~ /\sstatus=/){
        ##
        # Grab ident
        #
        my $ident = get_postfix_ident($line);
        my $to;
        my $status = 'failure';
        ($to, $status) = $line =~ m/.*to=(<.*>),\s.*\sstatus=(\S*).*/;
        if (!defined($to)){
            $to = 'unknown';
        } else {
            $to = lc($to);
        }
        if (defined($struct->{'msg'}{$ident}{'to'})){
            $struct->{'msg'}{$ident}{'to'} .= ", $to";
        } else {
            $struct->{'msg'}{$ident}{'to'} = $to;
        }
        if ($status eq 'sent'){
            $struct->{'msg'}{$ident}{'status'} = 'success';
        }
        ##
        # See what kind of delivery
        #
        if ($status eq 'sent'){
            (my $tmp) = $line =~ m/.*status=.*\((.*)\).*/;
            if (defined($tmp) && $tmp =~ /procmail/){
                if (defined($struct->{'local'}{'procmail'})){
                    $struct->{'local'}{'procmail'}++;
                } else {
                    $struct->{'local'}{'procmail'}=1;
                }
            }
        }
        $du->pushfilt($line);
    } elsif ($service eq 'smtp'){
        ##
        # Ignore connect lines and PIX <CRLF> warnings.
        #
        if ($line =~ /connect/ || $line =~ /<CRLF>/ || $line =~ /warning:/
            || $line =~ /\sstatus=/){
            if ($line =~ /\sstatus=/){
                ##
                # Grab ident
                #
                my $ident = get_postfix_ident($line);
                my $to;
                my $status = 'failure';
                ($to, $status) = $line =~ m/.*to=(<.*>), .* status=(\S*).*/;
                if (!defined($to)){
                    $to = 'unknown';
                } else {
                    $to = lc($to);
                }
                $struct->{'msg'}{$ident}{'to'} = $to;
                if ($status eq 'sent'){
                    $status = 'success';
                }
                $struct->{'msg'}{$ident}{'status'} = $status;
            }
            $du->pushfilt($line);
        }
    } elsif ($service eq 'pickup'){
        ##
        # Grab ident
        #
        my $ident = get_postfix_ident($line);
        $struct->{'msg'}{$ident}{'remotehost'} = 'postfix-cl';
        $du->pushfilt($line);
    } elsif ($service eq 'cleanup'){
        ##
        # Just push it into filtered.
        #
        $du->pushfilt($line);
    }
}

##
# Analyze a qmail-style maillog entry.
#
# @param  $1  maillog line to analyze.
#
sub do_qmail {
    my $line = shift;
    if ($line =~ /new msg/){
        my $inode = get_qmail_inode($line);
        ##
        # Generate an identifier
        #
        if (defined($struct->{'qmail'}{'identcount'})){
            $struct->{'qmail'}{'identcount'}++;
        } else {
            $struct->{'qmail'}{'identcount'} = 0;
        }
        $struct->{'qmail'}{'ident'}{$inode} = $struct->{'qmail'}{'identcount'};
        $du->pushfilt($line);
    } elsif ($line =~ /end msg/) {
        my $inode = get_qmail_inode($line);
        if (defined($struct->{'qmail'}{'ident'}{$inode})){
            delete($struct->{'qmail'}{'ident'}{$inode});
        }
        $du->pushfilt($line);
    } elsif ($line =~ /bounce msg/) {
        if (defined($struct->{'smtpd'}{'reject'})){
            $struct->{'smtpd'}{'reject'}++;
        } else {
            $struct->{'smtpd'}{'reject'} = 1;
        }
        $du->pushfilt($line);
    } elsif ($line =~ /info msg/) {
        ##
        # Grab ident.
        #
        my $ident = get_qmail_ident($line);
        my $from;
        my $size;
        my $system = $du->getsystem($line);
        ($size, $from) = $line =~ m/.*\sbytes\s+(\d+)\s+from\s+(\S+).*/;
        if (!defined($size)){
            $size = 0;
        }
        if (!defined($from)){
            $from = 'unknown';
        } else {
            $from = lc($from);
        }
        if ($from eq '<>' || $from eq '<#@[]>'){
            $from = '<mailer-daemon>';
        }
        $struct->{'msg'}{$ident}{'from'}   = $from;
        $struct->{'msg'}{$ident}{'size'}   = $size;
        $struct->{'msg'}{$ident}{'system'} = $system;
        $du->pushfilt($line);
    } elsif ($line =~ /starting delivery/){
        ##
        # Find out the delivery number and match it against the ident.
        #
        (my $dnum) = $line =~ m/.*\sdelivery\s+(\d+):.*/;
        my $ident = get_qmail_ident($line);
        $struct->{'qmail'}{'deliveries'}{$dnum} = $ident;
        ##
        # Is it remote or local?
        #
        my $status = 'local';
        if ($line =~ /to\s+remote\s+/){
            $status = 'remote';
        }
        if ($status eq 'local'){
            if (defined($struct->{'local'}{'mailbox'})){
                $struct->{'local'}{'mailbox'}++;
            } else {
                $struct->{'local'}{'mailbox'} = 1;
            }
        }
        ##
        # To whom?
        #
        my $to;
        ($to) = $line =~ m/.*\s+to\s+\w+\s+(\S+).*/;
        if (!defined($to)){
            $to = 'unknown';
        } else {
            $to = lc($to);
        }
        $struct->{'msg'}{$ident}{'to'} = $to;
        $du->pushfilt($line);
    } elsif ($line =~ /delivery/) {
        (my $dnum) = $line =~ m/.*\sdelivery\s+(\d+):.*/;
        my $ident = $struct->{'qmail'}{'deliveries'}{$dnum};
        if (!defined($ident)){
            $ident = 'unknown';
        }
        my $status;
        ($status) = $line =~ m/.*\sdelivery\s+\d+:\s+(\S+):.*/;
        if (!defined($status)){
            $status = 'unknown';
        }
        if ($status ne 'success'){
            $status = 'failure';
        }
        $struct->{'msg'}{$ident}{'status'} = $status;
        $du->pushfilt($line);
    } elsif ($line =~ /status: local/) {
        ##
        # Ignore these
        #
        $du->pushfilt($line);
    } elsif ($line =~ /triple bounce:/) {
        ##
        # Add a warning.
        #
        if (defined($struct->{'smtpd'}{'warning'})){
            $struct->{'smtpd'}{'warning'}++;
        } else {
            $struct->{'smtpd'}{'warning'} = 1;
        }
        $du->pushfilt($line);
    }
}

##
# Analyze a sendmail-style entry in the maillog.
#
# @param  $1  A sendmail-style maillog entry.
#
sub do_sendmail {
    my $line = shift;
    my $ident = get_sendmail_ident($line);
    if (exists($struct->{'ignores'}{$ident})){
        $du->pushfilt($line);
        return;
    }
    if ($line =~ /reject=/ || $line =~ /stat=User unknown/){
        if (defined($struct->{'smtpd'}{'reject'})){
            $struct->{'smtpd'}{'reject'}++;
        } else {
            $struct->{'smtpd'}{'reject'} = 1;
        }
        $struct->{'ignores'}{$ident} = 1;
        $du->pushfilt($line);
    } elsif ($line =~ /:\s+from=/) {
        (my $from) = $line =~ m/.*\sfrom=(\S+),\s+.*/;
        if (!defined($from)){
            $from = 'unknown';
        } else {
            $from = lc($from);
        }
        $struct->{'msg'}{$ident}{'from'} = $from;
        (my $size) = $line =~ m/.*,\s+size=(\d+),\s+.*/;
        $struct->{'msg'}{$ident}{'size'} = $size;
        my $host;
        if ($line =~ /relay=\[/){
            ($host) = $line =~ m/.*\srelay=\[(\S+)\].*/;
        } else {
            ($host) = $line =~ m/.*\srelay=(\S+)\s+\[.*/;
        }
        if (!defined($host)){
            $host = 'unknown';
        }
        if (defined($struct->{'remotehost'}{$host})){
            $struct->{'remotehost'}{$host}++;
        } else {
            $struct->{'remotehost'}{$host} = 1;
        }
        
        my $system = $du->getsystem($line);
        $struct->{'msg'}{$ident}{'system'} = $system;
        $du->pushfilt($line);
    } elsif ($line =~ /\sError\s+\d+/){
        if (defined($struct->{'smtpd'}{'warning'})){
            $struct->{'smtpd'}{'warning'}++;
        } else {
            $struct->{'smtpd'}{'warning'} = 1;
        }
        $struct->{'ignores'}{$ident} = 1;
        $du->pushfilt($line);
    } else {
        if ($line =~ /\sto=\"\|/ || $line =~ /\sto=\|/) {
            my $to;
            ($to) = $line =~ m/.*\sctladdr=(\S+)\s+.*/;
            if (!defined($to)){
                $to = 'unknown';
            } else {
                $to = lc($to);
            }
            $struct->{'msg'}{$ident}{'to'} = $to;
            if ($line =~ /procmail/){
                if (defined($struct->{'local'}{'procmail'})){
                    $struct->{'local'}{'procmail'}++;
                } else {
                    $struct->{'local'}{'procmail'} = 1;
                }
            }
            ##
            # Get the status
            #
            my $status;
            ($status) = $line =~ m/.*,\s+stat=(\S+).*/;
            if (!defined($status)){
                $status = 'unknown';
            } else {
                if ($status ne 'Sent'){
                    $status = 'failure';
                } else {
                    $status = 'success';
                }
            }
            $struct->{'msg'}{$ident}{'status'} = $status;
            $du->pushfilt($line);
        } elsif ($line =~ /\sctladdr=/) {
            ##
            # This is a relay of some sort.
            #
            my $to;
            ($to) = $line =~ m/.*\sctladdr=(\S+)\s+.*/;
            if (!defined($to)){
                $to = 'unknown';
            }
            $struct->{'msg'}{$ident}{'to'} = $to;
            if (defined($struct->{'local'}{'relay'})){
                $struct->{'local'}{'relay'}++;
            } else {
                $struct->{'local'}{'relay'} = 1;
            }
            ##
            # Get the status
            #
            my $status;
            ($status) = $line =~ m/.*,\s+stat=(\S+).*/;
            if (!defined($status)){
                $status = 'unknown';
            } else {
                if ($status ne 'Sent'){
                    $status = 'failure';
                } else {
                    $status = 'success';
                }
            }
            $struct->{'msg'}{$ident}{'status'} = $status;
            $du->pushfilt($line);
        } else {
            my $to;
            ($to) = $line =~ m/.*\sto=(\S+),\s+.*/;
            if (!defined($to)){
                $to = 'unknown';
            } else {
                $to = lc($to);
            }
            $struct->{'msg'}{$ident}{'to'} = $to;
            ##
            # Get the status
            #
            my $status;
            ($status) = $line =~ m/.*,\s+stat=(\S+).*/;
            if (!defined($status)){
                $status = 'unknown';
            } else {
                if ($status ne 'Sent'){
                    $status = 'failure';
                } else {
                    $status = 'success';
                }
            }
            $struct->{'msg'}{$ident}{'status'} = $status;
            $du->pushfilt($line);
        }
    }
}

##
# Grab the message identifier from a postfix-style entry.
#
# @return    a message identifier.
#
sub get_postfix_ident {
    my $line = shift;
    my $ident;
    ($ident) = $line =~ m/.*\spostfix\/\w+\[\d+\]:\s+(\S+):\s+/;
    if (!defined($ident)){
        $ident = 'unknown';
    }
    return $ident;
}

##
# Figure out a qmail message identifier.
#
# @return    a message identifier.
#
sub get_qmail_ident {
    my $line  = shift;
    my $inode = get_qmail_inode($line);
    my $ident = $struct->{'qmail'}{'ident'}{$inode};
    if (!defined($ident)){
        $ident = 'unknown';
    }
    return $ident;
}

##
# Qmail does things a little differently -- it does not assign each
# message it processes a unique identifier, but instead shows which
# inode that message occupies in the queue. get_qmail_ident uses that
# to generate a unique identifier so we can use the same routines as
# postfix and sendmail.
#
# @return    the qmail inode identifier.
#
sub get_qmail_inode {
    my $line = shift;
    (my $inode) = $line =~ m/.*msg\s*(\d+).*/;
    if (!defined($inode)){
        $inode = 'unknown';
    }
    return $inode;
}

##
# Get a sendmail-style message identifier.
#
# @return    a message identifier.
#
sub get_sendmail_ident {
    my $line = shift;
    my $ident;
    ($ident) = $line =~ m/.*\ssendmail\[\d+\]:\s+(\S+):\s+/;
    if (!defined($ident)){
        $ident = 'unknown';
    }
    return $ident;
}

__END__

=pod

=head1 AUTHOR

Konstantin Riabitsev, <icon@phy.duke.edu>

=head1 REVISION

$Revision$

=head1 SEE ALSO

epylog(8), epylog-modules(5), epylog(3)

=cut
