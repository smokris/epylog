# $Id$

%define _vardir   /var/lib
%define _perldir  /usr/lib/perl5/site_perl
%define __perldoc /usr/bin/perldoc

Summary: New logs analyzer and parser.
Name: epylog
Version: 0.9.3
Release: 1
License: GPL
Group: Applications/System
Source: http://www.dulug.duke.edu/epylog/download/%{name}-%{version}.tar.gz
Packager: Konstantin Riabitsev <icon@phy.duke.edu>
Vendor: Duke University <epylog-list@lists.dulug.duke.edu>
BuildRoot: /var/tmp/%{name}-%{version}-root
BuildArch: noarch
Requires: metamail mktemp perl >= 5.6

%description
New log notifier and analyzer with modular analysis options.

%prep
%setup -q -n %{name}-%{version}
# fix version
%{__perl} -pi -e "s/^VERSION=.*/VERSION='%{name}-%{version}-%{release}'/g" epylog

%build
# build module documentation.
MDOCDIR="doc/modules"
mkdir -m0755 -p $MDOCDIR
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
    *)
      ;;
  esac
done
# build the perl module manpage
%{__perldoc} epylog.pm > man/epylog.3

# move template.mod.pl into doc.
mv modules/template.mod.pl doc/

%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
mkdir -m0755 -p $RPM_BUILD_ROOT%{_sysconfdir}/epylog
mkdir -m0755 -p $RPM_BUILD_ROOT%{_sysconfdir}/cron.daily
mkdir -m0700 -p $RPM_BUILD_ROOT%{_vardir}/epylog
mkdir -m0755 -p $RPM_BUILD_ROOT%{_libdir}/epylog/modules
mkdir -m0755 -p $RPM_BUILD_ROOT%{_sbindir}

install -m0755 modules/* $RPM_BUILD_ROOT%{_libdir}/epylog/modules/
install -m0644 etc/* $RPM_BUILD_ROOT%{_sysconfdir}/epylog/
install -m0755 epylog $RPM_BUILD_ROOT%{_sbindir}
install -m0755 cron/epylog-cron.daily \
	$RPM_BUILD_ROOT%{_sysconfdir}/cron.daily/epylog.cron

# install manpages
pushd man
for MAN in *.*; do 
	SEC=`echo $MAN | sed "s/.*\.//g"`
	gzip $MAN
        LOC="$RPM_BUILD_ROOT%{_mandir}/man$SEC"
        mkdir -m0755 -p $LOC
        install -m0644 $MAN.gz $LOC
done
popd

# install the perl module
mkdir -m0755 -p $RPM_BUILD_ROOT%{_perldir}
install -m0644 epylog.pm $RPM_BUILD_ROOT%{_perldir}

%clean
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%dir %{_vardir}/epylog
%dir %{_libdir}/epylog
%dir %{_libdir}/epylog/modules
%{_libdir}/epylog/modules/*
%{_sbindir}/epylog
%{_sysconfdir}/cron.daily/epylog.cron
%{_perldir}/epylog.pm
%{_mandir}/man3/*
%{_mandir}/man5/*
%{_mandir}/man8/*
%config %dir %{_sysconfdir}/epylog
%config(noreplace) %{_sysconfdir}/epylog/*
%doc doc/*

%changelog
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
