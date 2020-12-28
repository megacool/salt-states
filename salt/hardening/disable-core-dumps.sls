# Ref. NSA RHEL guide section 2.2.4.2

hardening-disable-suid-core-dumpable:
    sysctl.present:
        - name: fs.suid_dumpable
        - value: 0


hardening-disable-core-dumps:
    file.managed:
        - name: /etc/security/limits.conf
        - contents: |
            ##########################################################
            # File managed by salt state security.disable-core-dumps #
            # Local changes will be overridden                       #
            ##########################################################

            #
            #Each line describes a limit for a user in the form:
            #
            #<domain>        <type>  <item>  <value>
            #
            #Where:
            #<domain> can be:
            #        - a user name
            #        - a group name, with @group syntax
            #        - the wildcard *, for default entry
            #        - the wildcard %, can be also used with %group syntax,
            #                 for maxlogin limit
            #        - NOTE: group and wildcard limits are not applied to root.
            #          To apply a limit to the root user, <domain> must be
            #          the literal username root.
            #
            #<type> can have the two values:
            #        - "soft" for enforcing the soft limits
            #        - "hard" for enforcing hard limits
            #
            #<item> can be one of the following:
            #        - core - limits the core file size (KB)
            #        - data - max data size (KB)
            #        - fsize - maximum filesize (KB)
            #        - memlock - max locked-in-memory address space (KB)
            #        - nofile - max number of open files
            #        - rss - max resident set size (KB)
            #        - stack - max stack size (KB)
            #        - cpu - max CPU time (MIN)
            #        - nproc - max number of processes
            #        - as - address space limit (KB)
            #        - maxlogins - max number of logins for this user
            #        - maxsyslogins - max number of logins on the system
            #        - priority - the priority to run user process with
            #        - locks - max number of file locks the user can hold
            #        - sigpending - max number of pending signals
            #        - msgqueue - max memory used by POSIX message queues (bytes)
            #        - nice - max nice priority allowed to raise to values: [-20, 19]
            #        - rtprio - max realtime priority
            #        - chroot - change root to directory (Debian-specific)

            * hard core 0
            *   hard    nofile  20000
            *   soft    nofile  15000
