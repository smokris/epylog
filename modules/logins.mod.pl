#!/usr/bin/perl -w
# logins.mod.pl
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

logins.mod.pl - a epylog module.

=head1 DESCRIPTION

This module processes login information, usually present in
/var/log/secure, and outputs them in a nice, sane format.

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

There are several formatting rules that affect the final report.

=over 5

=item $report_pattern = '%-10s-> %10s: ';

This tells the module how to output the initial report line. What the
default value tells it to do is align the user name to the left, pad
it with spaces until total width reaches 10, then provide the facility
aligned to the right and padded with spaces to the left, then
everything else.

=item $next_line_pattern = '%23s: ';

Sometimes there will be more than one facility reporting per
system. This tells how many spaces to indent the report.

=item $sysindent_pattern = '%23s  ';

Sometimes the list of systems will be too long, so the module will
wrap it. This tells it how many spaces to indent the next line with.

=item $sysreport pattern = '%s(%d) ';

This defines how to report the system name and how many times the
login occurred at that system.

=item $notice_pattern = '%s from %s: %d times';

Some events will generate notices in the log file. This tells the
module how to output the notices in the final report.

=item $wrap = 76;

If the system list is too lengthy, this will wrap it at this position.

=back

=cut

##
# Formatting options
#
my $report_pattern      = '%-10s-> %10s: ';
my $next_line_pattern   = '%23s: ';
my $sysindent_pattern   = '%23s  ';
my $sysreport_pattern   = '%s(%d) ';
my $notice_pattern      = '%s from %s: %d times';
my $wrap = 76;

##
# Define some constants as the root hash elements of the struct.
# Root's constants are 10 more than users' so we can just add 10
# to it and arrive to roots' when we do the parsing.
#
my $ACTION_FAILURE      = 0;
my $ACTION_OPENED       = 1;
my $ACTION_CLOSED       = 2;
my $ACTION_ROOT_FAILURE = 10;
my $ACTION_ROOT_OPENED  = 11;
my $ACTION_ROOT_CLOSED  = 12;
my $ACTION_IGNORE       = 3;
my $ACTION_NOTICE       = 4;
##
# This is a "struct" that holds nested hashes.
#
my $struct;

##
# Do the magic.
#
my $du = new epylog();
$du->init("logins");

$du->mlog(1, "beginning to read input");

##
# Process the lines first
#
while ($du->islogeof() == 0) {
    my $line = $du->nextline();
    my @ry = processLine($line);
    ##
    # $ry[0] will be undefined if the line wasn't caught by the
    # processLine subroutine.
    #
    if (defined($ry[0])){
        ##
        # Add it to filtered.
        #
        $du->pushfilt($line);
        ##
        # Make sure it's not ACTION_IGNORE
        #
        if ($ry[0] != $ACTION_IGNORE){
            if (defined($ry[3]) && $ry[3] eq "root"){
                ##
                # root user gets a different layout.
                # we don't care about xscreensaver, because it will always
                # scream as if someone is trying to log in as root.
                #
                if ($ry[2] ne "xscreensaver"){
                    if (!defined($ry[4])){
                        $ry[4] = "";
                    }
                    if (!defined($ry[5])){
                        $ry[5] = "";
                    }
                    my $ruhost = $ry[4].'@'.$ry[5];
                    $ruhost =~ s/\@$//;
                    if ($ruhost eq ""){
                        $ruhost = 'unknown';
                    }
                    if (!defined($struct->{$ry[0]}{'root'}{$ry[1]}{$ry[2]}->
                                 {$ruhost})){
                        $struct->{$ry[0]}{'root'}{$ry[1]}{$ry[2]}{$ruhost}=1;
                    } else {
                        $struct->{$ry[0]}{'root'}{$ry[1]}{$ry[2]}{$ruhost}++;
                    }
                }
            } else {
                if ($ry[0] == $ACTION_NOTICE){
                    ##
                    # notices get special treatment
                    #
                    if (defined($struct->{$ACTION_NOTICE}{$ry[1]}{$ry[2]})){
                        $struct->{$ACTION_NOTICE}{$ry[1]}{$ry[2]}++;
                    } else {
                        $struct->{$ACTION_NOTICE}{$ry[1]}{$ry[2]}=1;
                    }		
                } else {
                    ##
                    # general users
                    #
                    if (!defined($struct->{$ry[0]}{$ry[3]}{$ry[2]}{$ry[1]})){
                        $struct->{$ry[0]}{$ry[3]}{$ry[2]}{$ry[1]}=1;
                    } else {
                        $struct->{$ry[0]}{$ry[3]}{$ry[2]}{$ry[1]}++;
                    }
                }
            }
        }
    }
}
$du->mlog(1, "Finished reading input");

if ($du->filtsize() > 0){
    ##
    # Process root failures.
    #
    if (defined($struct->{$ACTION_ROOT_FAILURE})){
        $du->mlog(1, "Writing root login failures");
        $du->pushrep($du->mkrephdr('ROOT LOGIN FAILURES'));
        outputRootEntries($ACTION_ROOT_FAILURE);
    }
    
    ##
    # Process root successes
    #
    if (defined($struct->{$ACTION_ROOT_OPENED})){
        $du->mlog(1, "Writing root logins");
        $du->pushrep($du->mkrephdr('ROOT LOGINS'));
        outputRootEntries($ACTION_ROOT_OPENED);
    }
    
    ##
    # Process user failures.
    #
    if (defined($struct->{$ACTION_FAILURE})){
        $du->mlog(1, "Writing user login failures");
        $du->pushrep($du->mkrephdr('User login FAILURES'));
        outputUserEntries($ACTION_FAILURE);
    }
    
    ##
    # Process user successes.
    #
    if (defined($struct->{$ACTION_OPENED})){
        $du->mlog(1, "Writing user logins");
        $du->pushrep($du->mkrephdr('User logins'));
        outputUserEntries($ACTION_OPENED);
    }
    
    ##
    # Process notices.
    #
    if (defined($struct->{$ACTION_NOTICE})){
        $du->mlog(1, "Writing notices");
        $du->pushrep($du->mkrephdr('Login module notes'));
        foreach my $descr_key (keys(%{$struct->{$ACTION_NOTICE}})){
            foreach my $rhost_key (keys(%{$struct->{$ACTION_NOTICE}->
                                          {$descr_key}})){
                my $outline = sprintf ($notice_pattern, $descr_key, $rhost_key,
                                       $struct->{$ACTION_NOTICE}{$descr_key}->
                                       {$rhost_key});
                $du->pushrep($outline);
            }
        }
    }
    ##
    # Write processed strings to the file, if we processed any.
    #
}
$du->finalize();


###################################################################
# subs and salads

##
# This sub wraps the lines so they are $wrap width max.
#
# @param  $1 The string to wrap.
# @return    The same string cleanly wrapped.
#
sub cleanWrap {
    (my $lline) = @_;
    my @retlines;
    if (length($lline)>$wrap){
        while (length($lline)>0){
            (my $str, my $rest) = $lline =~ m/^(.{0,$wrap})\s(.*)/;
            push(@retlines, $str);
            if (length($rest)>0){
                $lline = sprintf($sysindent_pattern, " ") . $rest;
            } else {
                $lline = "";
            }
        }
        return join("\n", @retlines);
    } else {
        return $lline;
    }
}

##
# This sub outputs noticed root entries in a nice format.
#
# @param  $1 the root element of the struct to process.
# @return    void.
#
sub outputRootEntries {
    (my $ACT) = @_;
    foreach my $system_key (sort(keys(%{$struct->{$ACT}{'root'}}))){
        my $counter = 0;
        foreach my $service_key (keys(%{$struct->{$ACT}{'root'}->
                                        {$system_key}})){
            $counter++;
            my $longline;
            if ($counter == 1){
                $longline = sprintf($report_pattern, $system_key,
                                    $service_key);
            } else {
                $longline = sprintf($next_line_pattern, $service_key);
            }
            foreach my $ruhost_key (keys(%{$struct->{$ACT}->
                                           {'root'}{$system_key}->
                                       {$service_key}})){
                $longline .= sprintf($sysreport_pattern, $ruhost_key,
                                     $struct->{$ACT}{'root'}->
                                     {$system_key}{$service_key}->
                                     {$ruhost_key});
            }
            $du->pushrep(cleanWrap($longline));
        }
    }
}

##
# This sub outputs user entries in a nice format.
#
# @param  $1 The root element of the struct to process.
# @return    void.
#
sub outputUserEntries {
    (my $ACT) = @_;
    foreach my $user_key (sort(keys(%{$struct->{$ACT}}))){
        my $counter = 0;
        foreach my $service_key (keys(%{$struct->{$ACT}{$user_key}})){
            $counter++;
            my $longline;
            if ($counter == 1){
                $longline = sprintf($report_pattern, $user_key,
                                    $service_key);
            } else {
                $longline = sprintf($next_line_pattern, $service_key);
            }
            foreach my $system_key (sort(keys(%{$struct->{$ACT}->
                                                {$user_key}->
                                            {$service_key}}))){
                $longline .= sprintf($sysreport_pattern, $system_key,
                                     $struct->{$ACT}{$user_key}->
                                     {$service_key}{$system_key});
            }
            $du->pushrep(cleanWrap($longline));
        }
    }
}

##
# This sub does all the processing. It's long and painful. ;)
#
# @param  $1 takes a log line.
# @return    an array of parameters. They vary depending on whether it's
#            a root-user, common user, or a notice.
#
sub processLine {
    my $action;
    my $system;
    my $service;
    my $user;
    my $byuser;
    my $rhost;
    my $descr;
    (my $line) = @_;
    $system = $du->getsystem($line);
    
    ##
    # Analyze per-report style.
    #

    ################## pam_unix #################
    if ($line =~ /(pam_unix)/){
        ##
        # the line we're looking for would be service(pam_unix)
        #
        ($service) = $line =~ m/.*\s(\S*)\(pam_unix\).*/;
        if ($line =~ /authentication failure/){
            $action = $ACTION_FAILURE;
            ($user) = $line =~ m/.*\suser=(\S*).*/;
            ($byuser) = $line =~ m/.*\slogname=(\S*).*/;
            ($rhost) = $line =~ m/.*\srhost=(\S*).*/;
        }
        elsif ($service eq "sshd"){
            ##
            # ignore sshd closes and successes
            #
            $action = $ACTION_IGNORE;
        } else {
            if ($line =~ /session opened/){
                $action = $ACTION_OPENED;
                ($user) = $line =~ m/.* for user (\S*).*/;
                ($byuser) = $line =~ m/.* by.*\(uid=(\S*)\).*/;
                $byuser = $du->getuname($byuser);
            }
            elsif ($line =~ /session closed/){
                $action = $ACTION_CLOSED;
                ($user) = $line =~ m/.* for user (\S*).*/;
            }
            ##
            # misc failure lines
            #
            elsif ($line =~ /bad username/){
                $action = $ACTION_FAILURE;
                ($user) = $line =~ m/.*\[(.*)\].*/;
            }
            elsif ($line =~ /auth could not identify password for/){
                $action = $ACTION_FAILURE;
                ($user) = $line =~ m/.*\[(.*)\].*/;
            }
            elsif ($line =~ /check pass;/){
                $action = $ACTION_FAILURE;
                ($user) = $line =~ m/.* user (\S*).*/;
            }
        }
    }
    ######################## xinetd ################
    elsif ($line =~ /xinetd\[\S*\]:/){
        ($service) = $line =~ m/.* xinetd\[\S*\]: \S*: (\S*) .*/;
        if ($line =~ /START:/){
            $action = $ACTION_OPENED;
            if ($line !~ /<no address>/){
                ($rhost) = $line =~ m/.* from=(\S*).*/;
                $rhost = $du->gethost($rhost);
            } else {
                $rhost = 'unknown';
            }
        }
        elsif ($line =~ /EXIT:/){
            $action = $ACTION_CLOSED;
        }
        ##
        # catch and ignore imap, since we process separate
        # logins from them.
        #
        elsif ($line =~ / imap/){
            $action = $ACTION_IGNORE;
        }
    }
    ######################## PAM_unix ####################
    elsif ($line =~ /PAM_unix\[/){
        ($service) = $line =~ m/.*PAM_unix\[\S*\]: \((\S*)\) .*/;
        if ($line =~ /authentication failure/){
            $action = $ACTION_FAILURE;
            ($service) = $line =~ m/.* for (\S*) service.*/;
            ($user) = $line =~ m/.*-> (\S*) .*/;
            ($byuser) = $line =~ m/.* failure; \(uid=(\S*)\) .*/;
            $byuser = $du->getuname($byuser);
        }
        ##
        # ignore sshd successes and closes, since we do them later
        #
        elsif ($service eq "sshd") {
            $action = $ACTION_IGNORE;
        } else {
            if ($line =~ /session opened/){
                $action = $ACTION_OPENED;
                ($user) = $line =~ m/.* for user (\S*) .*/;
                ($byuser) = $line =~ m/.* by \(uid=(\S*)\).*/;
                $byuser = $du->getuname($byuser);
            }
            elsif ($line =~ /session closed/){
                $action = $ACTION_CLOSED;
                ($user) = $line =~ m/.* for user (\S*).*/;
            }
        }
    }
    ##
    # PAM_unix and PAM_pwdb are nearly identical, but not entirely.
    #
    
    ######################## PAM_pwdb ####################
    elsif ($line =~ /PAM_pwdb\[/){
        if ($line =~ /authentication failure/){
            $action = $ACTION_FAILURE;
            ($service) = $line =~ m/.* for (\S*) service.*/;
            ($user) = $line =~ m/.*-> (\S*) .*/;
            ($byuser) = $line =~ m/.* failure; \(uid=(\S*)\) .*/;
            $byuser = $du->getuname($byuser);
        }
        ##
        # ignore sshd, since we'll process it separately
        #
        elsif ($line =~ /\(sshd\)/){
            $action = $ACTION_IGNORE;
        } else {
            if ($line =~ m/.*PAM_pwdb\[\S*\]: \((\S*)\) .*/){
                ($service) = $line =~ m/.*PAM_pwdb\[\S*\]: \((\S*)\) .*/;
            } else {
                $service = 'unknown';
            }
            if ($line =~ /session opened/){
                $action = $ACTION_OPENED;
                ($user) = $line =~ m/.* for user (\S*) .*/;
                ($byuser) = $line =~ m/.*\(uid=(\S*)\).*/;
                $byuser = $du->getuname($byuser);
            }
            elsif ($line =~ /session closed/){
                $action = $ACTION_CLOSED;
                ($user) = $line =~ m/.* for user (\S*).*/;
            }
        }
    }
    ########################### sshd #########################
    elsif ($line =~ /sshd\[/){
        if ($line =~ /ssh2/){
            $service = "ssh2";
        } else {
            $service = "ssh1";
        }
        if ($line =~ /: Accepted/){
            $action = $ACTION_OPENED;
            ($user) = $line =~ m/.* for (\S*) from.*/;
            ($byuser) = $line =~ m/.* ruser (\S).*/;
            ($rhost) = $line =~ m/.* from (\d\S*)/;
            $rhost = $du->gethost($rhost);
            (my $method) = $line =~ m/.*: Accepted (\S*) for.*/;
            if ($method eq "password"){
                $service .= "(pw)";
            } elsif ($method eq "publickey"){
                $service .= "(pk)";
            } elsif ($method eq "rhosts-rsa" || $method eq "rsa"){
                $service .= "(rsa)";
            }
        }
        elsif ($line =~ /: Connection closed/){
            $action = $ACTION_CLOSED;
            ($rhost) = $line =~ m/.* closed by (\S*).*/;
            ##
            # don't do this, as we are currently ignoring the closes.
            #
            #$rhost = $du->gethost($rhost);
        }
        elsif ($line =~ /: Failed/){
            ##
            # ignore these, since pam_unix catches these better
            #
            $action = $ACTION_IGNORE;
        }
        elsif ($line =~ /: Rhosts authentication refused/){
            $action = $ACTION_FAILURE;
            $service = "ssh(rsa)";
            ($user) = $line =~ m/.*refused for (\S*):.*/;
        }
        ##
        # recognize and add some notes
        #
        elsif ($line =~ /Did not receive ident/){
            $action = $ACTION_NOTICE;
            ($rhost) = $line =~ m/.*string from (\d\S*).*/;
            $rhost = $du->gethost($rhost);
            $descr = "SSH connect scan";
        }
        elsif ($line =~ /Version_Mapper/){
            $action = $ACTION_IGNORE;
            ($rhost) = $line =~ m/.*scanned from (\d\S*).*/;
            $rhost = $du->gethost($rhost);
            $descr = "SSH version mapper scan";
        }
        ##
        # Some silliness with ROOT vs root.
        #
        if (defined($user) && $user eq "ROOT"){
            $user = "root";
        }
    }
    ############# imapd ##############
    elsif ($line =~ /imapd\[\d*\]:/){
        $service = 'imap';
        if ($line =~ /host=/){
            ($user) = $line =~ m/.* user=(\S*).*/;
            ($rhost)= $line =~ m/.*host=(\S*).*/;
            if (!defined($rhost)){
                ($rhost) = $line =~ m/.*host=.*\[\S*\].*/;
                $rhost = $du->gethost($rhost);
            }
        } else {
            $user = 'unknown';
            $rhost = 'unknown';
        }
        if ($line =~ /Authenticated user/ || $line =~ /Login user/){
            $action = $ACTION_OPENED;
        }
        elsif ($line =~ /Logout/ || $line =~ /Killed/ 
               || $line =~ /Autologout/){
            $action = $ACTION_CLOSED;
        }
        elsif ($line =~ /Login failure/ || $line =~ /Login failed/){
            $action = $ACTION_FAILURE;
        }
        elsif ($line =~ /AUTHENTICATE LOGIN/ ||
               $line =~ /AUTHENTICATE PLAIN/){
            ##
            # ignore these since they just duplicate the ones we
            # already caught above.
            #
            $action = $ACTION_IGNORE;
        }
    }
    ############# ipop3d ##############
    elsif ($line =~ /ipop3d\[\d*\]:/){
        $service = 'pop3';
        if ($line =~ /host=/){
            ($user) = $line =~ m/.* user=(\S*).*/;
            ($rhost)= $line =~ m/.*host=(\S*).*/;
            if (!defined($rhost)){
                ($rhost) = $line =~ m/.*host=.*\[\S*\].*/;
                $rhost = $du->gethost($rhost);
            }
        } else {
            $user = 'unknown';
            $rhost = 'unknown';
        }
        if ($line =~ /Auth user/ || $line =~ /Login user/){
            $action = $ACTION_OPENED;
        }
        elsif ($line =~ /Logout/ || $line =~ /Killed/ 
               || $line =~ /Autologout/){
            $action = $ACTION_CLOSED;
        }
        elsif ($line =~ /Login failure/ || $line =~ /Login failed/){
            $action = $ACTION_FAILURE;
        }
    }

    ##
    # Catch and ignore xscreensaver, since pam_unix catches it.
    #
    elsif ($line =~ /xscreensaver\[\d*\]: FAILED LOGIN/){
        $action = $ACTION_IGNORE;
    }
    
    if (defined($action)){
        if ($action == $ACTION_NOTICE){
            return ($action, $descr, $rhost);
        } else {
            if (!defined($user)){
                $user = "unknown";
            }
            if ($user eq "root"){
                ##
                # up it by 10 to get root-level actions.
                #
                $action += 10;
            }
            return ($action, $system, $service, $user, $byuser, $rhost);
        }
    } else {
        return (undef);
    }
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
