# $Id$

%define _vardir   %{_localstatedir}/lib
%define _perldir  %{_libdir}/perl5/site_perl
%define __perldoc %{_bindir}/perldoc
%define _pydir    %{_libdir}/python2.2/site-packages

Summary: New logs analyzer and parser.
Name: epylog
Version: 0.8
Release: 0.2
License: GPL
Group: Applications/System
Source: http://www.dulug.duke.edu/epylog/download/%{name}-%{version}.tar.gz
Packager: Konstantin Riabitsev <icon@phy.duke.edu>
Vendor: Duke University
BuildRoot: /var/tmp/%{name}-%{version}-root
BuildArch: noarch
BuildPrereq: perl, python, file, gzip, sed
Requires: python >= 2.2, perl >= 5.6, elinks, grep
Obsoletes: dulog
Provides: perl(epylog)

%description
New log notifier and analyzer with modular analysis options.

%prep
%setup -q
##
# Fix version.
#
%{__perl} -pi -e \
    "s/^VERSION\s*=\s*.*/VERSION = '%{name}-%{version}-%{release}'/g" \
    py/epylog/__init__.py

%build
cat <<EOF | %{__python}
from compileall import compile_dir
compile_dir('py')
EOF
cat <<EOF | %{__python} -OO
from compileall import compile_dir
compile_dir('py')
EOF
##
# Build module documentation.
#
MDOCDIR="doc/modules"
%{__mkdir_p} -m 755 $MDOCDIR
for FILE in modules/*; do
  TYPE=`%{__file} -ib $FILE 2>/dev/null`
  case $TYPE in
    application/x-perl)
      %{__perldoc} -t $FILE > $MDOCDIR/`basename $FILE .pl`.txt
      ;;
    application/x-sh)
      %{__grep} -E "^#" $FILE | %{__sed} \
        "/#!\/bin\/bash/d;/#!\/bin\/sh/d;/Copyright/,//d;s/^#//g;s/^ //g" \
        > $MDOCDIR/`basename $FILE .sh`.txt
      ;;
    ##
    # file is a little not right in the head
    # This is really python
    #
    "text/x-java; charset=us-ascii")
      echo "Not doing documentation for python modules yet. FIXME!"
      ;;
    *)
      ;;
  esac
done
# build the perl module manpage
%{__perldoc} epylog.pm > man/epylog.3
##
# TODO: Build python docs
#

##
# Move template.mod.pl into doc.
#
%{__mv} modules/template.mod.pl doc/

%install
%{__rm} -rf %{buildroot}
%{__mkdir_p} -m 700 %{buildroot}%{_vardir}/%{name}
##
# Install the python libraries
#
%{__mkdir_p} -m 755 %{buildroot}%{_pydir}/%{name}
%{__install} -m 644 py/epylog/*.py* %{buildroot}%{_pydir}/%{name}/
##
# Install the configs
#
%{__mkdir_p} -m 755 %{buildroot}%{_sysconfdir}/%{name}/modules.d
%{__install} -m 644 etc/modules.d/*.conf \
    %{buildroot}%{_sysconfdir}/%{name}/modules.d/
for FILE in epylog.conf report_template.html trojans.list weed.list; do
  %{__install} -m 644 etc/$FILE %{buildroot}%{_sysconfdir}/%{name}/$FILE
done
##
# Install the modules
#
%{__mkdir_p} -m 755 %{buildroot}%{_libdir}/%{name}/modules
%{__install} -m 755 modules/* %{buildroot}%{_libdir}/%{name}/modules/
##
# Install the executable
#
%{__mkdir_p} -m 755 %{buildroot}%{_sbindir}
%{__install} -m 755 epylog %{buildroot}%{_sbindir}/%{name}
##
# Install the cron script
#
%{__mkdir_p} -m 755 %{buildroot}%{_sysconfdir}/cron.daily
%{__install} -m 755 cron/epylog-cron.daily \
    %{buildroot}%{_sysconfdir}/cron.daily/%{name}.cron
##
# Install manpages
#
pushd man
for MAN in *.*; do 
	SEC=`echo $MAN | sed "s/.*\.//g"`
	gzip $MAN
    LOC="%{buildroot}%{_mandir}/man$SEC"
    %{__mkdir_p} -m 755 $LOC
    %{__install} -m 644 $MAN.gz $LOC
done
popd
##
# Install the perl module
#
%{__mkdir_p} -m 755 %{buildroot}%{_perldir}
%{__install} -m 644 epylog.pm %{buildroot}%{_perldir}/%{name}.pm

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-,root,root)
%dir %{_vardir}/%{name}
%dir %{_libdir}/%{name}
%{_libdir}/%{name}/modules/*
%{_pydir}/%{name}
%{_sbindir}/%{name}
%{_sysconfdir}/cron.daily/%{name}.cron
%{_perldir}/%{name}.pm
%{_mandir}/man3/*
%{_mandir}/man5/*
%{_mandir}/man8/*
%config(noreplace) %{_sysconfdir}/%{name}
%doc doc/*

%changelog
* Sat Jan 18 2003 Konstantin Riabitsev <icon@phy.duke.edu>
- First attempt at building the epylog version.

* Mon Jun 17 2002 Konstantin Riabitsev <icon@phy.duke.edu>
- Version 0.9.1, 0.9.2, 0.9.3.
- Miscellaneous bugfixes and enhancements.
- Firewall.mod.pl ported to the new module API.

* Thu Jun 13 2002 Konstantin Riabitsev <icon@phy.duke.edu>
- Version 0.9.0
- Preparing for the 1.0 version.
- Added epylog.pm and ported the modules so they use it. As a result, the
  memory footprint dropped DRAMATICALLY. We are talking from 400Mb RAM use
  on a 50Mb logfile to just over 25Mb.
- Added lockfile support in the core.
- weedeater.mod.sh now checks for weed.list.local.
- Wrote man files.

* Wed Mar 27 2002 Konstantin Riabitsev <icon@phy.duke.edu>
- Fixing race condition bugs. Bad, icon, bad!

* Fri Mar 15 2002 Konstantin Riabitsev <icon@phy.duke.edu>
- Changes to connect scan recognition routines in logins.mod.pl so it
  doesn't chop off the trailing octet of the IP address (OpenSSH-3.x
  seems to have changed the strings a tiny bit).

* Tue Feb 19 2002 Konstantin Riabitsev <icon@phy.duke.edu>
- Small changes to logins.mod.pl.
- Added epylog-cron.daily to the source.
- Added epylog.spec to the source.
- RPM build now creates module documentation.

* Mon Feb 18 2002 Konstantin Riabitsev <icon@phy.duke.edu>
- Small fixes to logins.mod.pl, firewall.mod.pl, and weed.list.
- Releasing an 0.3.0

* Thu Feb 14 2002 Icon Riabitsev <icon@phy.duke.edu>
- Added option to append unparsed entries at the top vs. at the bottom.
- Added option to send raw logs gzipped in an attachment (depends on
  metamail)
- Changed the way weeding is done so modules don't conflict with 
  each-other. There will be trade-offs for speed, but integrity in this
  case is more important.
- Full rewrite of logins.mod
- Full rewrite of reboots.mod
- Full rewrite of annoy.mod
- Full rewrite of imp.mod
- sshd.mod was merged with logins.mod
- Changes in weedeater.mod
- Added template.mod.pl, a template for perl modules.
- Modifications to firewall.mod by Michael Stenner.
- Some more docs, and miscellaneous rewrites.

* Wed Jan 16 2002 Icon Riabitsev <icon@phy.duke.edu>
- Replaced ipchains.mod.sh and iptables.mod.pl by a unified firewall.mod.pl
  by Michael Stenner.
- Changing the default dir from /var/epylog to /var/lib/epylog for HFS
  compliance.
- SPEC file cleanups and rewrites.

* Thu Sep 06 2001 Icon Riabitsev <icon@phy.duke.edu>
- Enhancements to modules: reboots, logins
- Bugfixes to modules: annoy, imp, ipchains
- Added module: iptables by Michael Stenner
- Minor changes to the epylog script

* Mon Aug 20 2001 Icon Riabitsev <icon@phy.duke.edu>
- Bugfixes and enhancements of modules.
- IMP module added by Seth Vidal

* Wed Aug 15 2001 Icon Riabitsev <icon@phy.duke.edu>
- dropped the requirement for epylog-init.sh. Now epylog will see if offset
  files are present and if not, then it will initialize them automatically
  at the first run, and make a report based on the last 100 lines of each
  newly-initialized log (or all of them if lines < 100).
- incorporated log-rotation workarounds. If the file was log-rotated, then
  epylog will go out, find the rotated logfile, and append whichever lines
  were added to the logfile before it was rotated. This way no log entries
  go un-analyzed.
- tweaked some modules and fixed some -z bugs.

* Tue Aug 14 2001 Seth Vidal <skvidal@phy.duke.edu>
- first spec file build
