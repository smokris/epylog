#!/usr/bin/perl -w
# imp.mod.pl
# -----------
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
#
# To view the help for this module, run "perldoc template.mod.pl"
# To create the text version, run
#      "perldoc -t template.mod.pl > template.mod.txt"
# For help with POD (plain old documentation) see the "perlpod"
# man page.  POD is really easy, so check it out!
#
# $Id$
#
# @Author  Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#
=pod

=head1 NAME

imp.mod.pl - a epylog module.

=head1 DESCRIPTION

Process IMP log entries and ouput them in a nice manner. You can learn
more about IMP at www.horde.org.

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

=item $uname_pattern = '%-8s -> ';

This affects how the username is presented. Default is to left-align
it, but try to fix within 8 spaces.

=item $rhost_pattern = 'from %s (%d)';

This is displayed to the right from the username and is the remote
host from which the login occured.

=item $indent_pattern = '%12s';

If a username logged in more than once from several remote hosts,
every next host will be displayed below the username, but indented so
it aligns with the rhost above.

=back

=cut

##
# Sprintf rules defining the formatting/layout.
#
my $uname_pattern  = '%-8s -> ';
my $rhost_pattern  = 'from %s (%d)';
my $indent_pattern = '%12s';

##
# Define any global variables here.
# $struct        a "struct" (nested hash) to hold the values.
# $ACTION_FAILED and
# $ACTION_LOGIN  root elements of the struct. Yes, I know it's a hack. 
#                Shut up. :)
#
my $struct;
my $ACTION_FAILED = ' FAILURES';
my $ACTION_LOGIN   = 's';

##
# Main module code.
#
my $du = new epylog();
$du->init('imp');
$du->mlog(1, "beginning to read input");

##
# Get the lines and analyze them.
#
while ($du->islogeof() == 0) {
    my $line = $du->nextline();
    if ($line =~ /IMP\[\d*\]/){
	my $host;
	my $action;
	my $user;
	my $rhost;
	($host) = $line =~ m/.* to (\S*) as.*/;
	($user) = $line =~ m/.* as (\S*).*/;
	($rhost) = $line =~ m/.* (\d\S*) to .*/;
	$rhost = $du->gethost($rhost);
	if ($line =~ /: Login/){
	    $action = $ACTION_LOGIN;
	}
	elsif ($line =~ /: FAILED/){
	    $action = $ACTION_FAILED;
	}
	if (defined($struct->{$host}{$action}{$user}{$rhost})){
	    $struct->{$host}{$action}{$user}{$rhost}++;
	} else {
	    $struct->{$host}{$action}{$user}{$rhost}=1;
	}
	$du->pushfilt($line);
    }
}
$du->mlog(1, "finished reading input");

##
# See if we have found anything.
#
if ($du->filtsize() > 0){
    $du->mlog(1, "generating report");
    foreach my $host_key (sort(keys(%{$struct}))){
	foreach my $action_key(sort(keys(%{$struct->{$host_key}}))){
	    $du->pushrep($du->mkrephdr("$host_key IMP login" . $action_key));
	    foreach my $user_key (sort(keys(%{$struct->{$host_key}
						  ->{$action_key}}))){
		my $counter = 0;
		foreach my $rhost_key (keys(%{$struct->{$host_key}{$action_key}
						  ->{$user_key}})){
		    $counter++;
		    my $outline;
		    if ($counter == 1){
			$outline = sprintf($uname_pattern, $user_key);
		    } else {
			$outline = sprintf($indent_pattern, " ");
		    }
		    $outline .= sprintf($rhost_pattern, $rhost_key,
					$struct->{$host_key}{$action_key}
					->{$user_key}{$rhost_key});
		    $du->pushrep($outline);
		}
	    }
	}
    }
}
$du->mlog(1, "Finalizing");
$du->finalize();

__END__

=pod

=head1 AUTHOR

Konstantin Riabitsev, <icon@phy.duke.edu>

=head1 REVISION

$Revision$

=head1 SEE ALSO

epylog(8), epylog-modules(5), epylog(3)

=cut
