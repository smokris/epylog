#!/usr/bin/perl -w
# template.mod.pl
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
# To view the help for this module, run "perldoc template.mod.pl"
# To create the text version, run
#      "perldoc -t template.mod.pl > template.mod.txt"
# For help with POD (plain old documentation) see the "perlpod"
# man page.  POD is really easy, so check it out!
#
# $Id$
#
# @Author  Michael D. Stenner <mstenner@phy.duke.edu>
#          Konstantin Ryabitsev <icon@linux.duke.edu>
# @version $Date$
#

##
# Strict enforces good coding practices by making you observe the
# variable scope.
# Add other packages, too.
#
use strict;
use epylog;

##
# Main module code.
#
my $du = new epylog();
$du->init('template');
$du->mlog(1, "beginning to read input");

##
# Iterate through all lines in the logs and analyze the ones that
# match.
#
while ($du->islogeof() == 0) {
    my $line = $du->nextline();
    ##
    # Put line-analyzing code here.
    #

    ##
    # Add any analyzed lines to filter.
    #
    $du->pushfilt($line);
}
$du->mlog(1, "finished reading input");

##
# See if we've done anything useful.
#
if ($du->filtsize() > 0){
    $du->mlog(1, "generating the report");
    $du->pushrep($du->mkrephdr('TEMPLATE ANALYSIS'));
    ##
    # Put your report-formatting code here.
    #
}

##
# Don't forget to call finalize()!
#
$du->mlog(1, "Finalizing");
$du->finalize();
$du->mlog(1, "Exiting...");

__END__

=pod

=head1 NAME

template.mod.pl - template module for epylog.

=head1 DESCRIPTION

This module analyzes <blah> syslog entries and reports them
nicely. Currently supports <blah> and <blah> entry types.

=head1 OPTIONS

This module accepts a number of options.  All options are read from
environment variables.  These options can be set in the epylog config
file (/etc/epylog/epylog.conf by default). The env variables it uses
are:

=over 5

=item BOGUS

This sets BOGUS, making the module output BOGUS.

=back

=head1 AUTHOR

Joe D. Bloe, <joe@bloe.org>

=head1 REVISION

$Revision$

=head1 SEE ALSO

epylog(8), epylog-modules(5), epylog(3)

=cut
