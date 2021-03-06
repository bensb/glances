# -*- coding: utf-8 -*-
#
# This file is part of Glances.
#
# Copyright (C) 2015 Nicolargo <nicolas@nicolargo.com>
#
# Glances is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Glances is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Process list plugin."""

# Import sys libs
import operator
import os
from datetime import timedelta

# Import Glances libs
from glances.core.glances_globals import is_windows
from glances.core.glances_processes import glances_processes
from glances.plugins.glances_plugin import GlancesPlugin


class Plugin(GlancesPlugin):

    """Glances' processes plugin.

    stats is a list
    """

    def __init__(self, args=None):
        """Init the plugin."""
        GlancesPlugin.__init__(self, args=args)

        # We want to display the stat in the curse interface
        self.display_curse = True

        # Note: 'glances_processes' is already init in the glances_processes.py script

    def get_key(self):
        """Return the key of the list"""
        return 'pid'

    def reset(self):
        """Reset/init the stats."""
        self.stats = []

    def update(self):
        """Update processes stats using the input method."""
        # Reset stats
        self.reset()

        if self.get_input() == 'local':
            # Update stats using the standard system lib
            # Note: Update is done in the processcount plugin
            # Just return the processes list
            if glances_processes.is_tree_enabled():
                self.stats = glances_processes.gettree()
            else:
                self.stats = glances_processes.getlist()
        elif self.get_input() == 'snmp':
            # No SNMP grab for processes
            pass

        return self.stats

    def get_process_tree_curses_data(self, node, args, first_level=True, max_node_count=None):
        """ Get curses data to display for a process tree. """
        ret = []
        node_count = 0
        if (not node.is_root) and ((max_node_count is None) or (max_node_count > 0)):
            node_data = self.get_process_curses_data(node.stats, False, args)
            node_count += 1
            ret.extend(node_data)
        for child in node.iter_children():
            # stop if we have enough nodes to display
            if (max_node_count is not None) and (node_count >= max_node_count):
                break

            if max_node_count is None:
                children_max_node_count = None
            else:
                children_max_node_count = max_node_count - node_count
            child_data = self.get_process_tree_curses_data(child,
                                                           args,
                                                           first_level=node.is_root,
                                                           max_node_count=children_max_node_count)
            if max_node_count is None:
                node_count += len(child)
            else:
                node_count += min(children_max_node_count, len(child))

            if not node.is_root:
                child_data = self.add_tree_decoration(child_data, child is node.children[-1], first_level)
            ret.extend(child_data)
        return ret

    def add_tree_decoration(self, child_data, is_last_child, first_level):
        """ Add tree curses decoration and indentation to a subtree. """
        # find process command indices in messages
        pos = []
        for i, m in enumerate(child_data):
            if (m["msg"] == "\n") and (m is not child_data[-1]):
                # new line pos + 12
                # TODO find a way to get rid of hardcoded 12 value
                pos.append(i + 12)

        # add new curses items for tree decoration
        new_child_data = []
        new_pos = []
        for i, m in enumerate(child_data):
            if i in pos:
                new_pos.append(len(new_child_data))
                new_child_data.append(self.curse_add_line(""))
            new_child_data.append(m)
        child_data = new_child_data
        pos = new_pos

        # draw node prefix
        if is_last_child:
            prefix = "└─"
        else:
            prefix = "├─"
        child_data[pos[0]]["msg"] = prefix

        # add indentation
        for i in pos:
            spacing = 2
            if first_level:
                spacing = 1
            elif is_last_child and (i is not pos[0]):
                # compensate indentation for missing '│' char
                spacing = 3
            child_data[i]["msg"] = "%s%s" % (" " * spacing, child_data[i]["msg"])

        if not is_last_child:
            # add '│' tree decoration
            for i in pos[1:]:
                old_str = child_data[i]["msg"]
                if first_level:
                    child_data[i]["msg"] = " │" + old_str[2:]
                else:
                    child_data[i]["msg"] = old_str[:2] + "│" + old_str[3:]
        return child_data

    def get_process_curses_data(self, p, first, args):
        """ Get curses data to display for a process. """
        ret = []
        ret.append(self.curse_new_line())
        # CPU
        if 'cpu_percent' in p and p['cpu_percent'] is not None and p['cpu_percent'] != '':
            msg = '{0:>6.1f}'.format(p['cpu_percent'])
            ret.append(self.curse_add_line(msg,
                                           self.get_alert(p['cpu_percent'], header="cpu")))
        else:
            msg = '{0:>6}'.format('?')
            ret.append(self.curse_add_line(msg))
        # MEM
        if 'memory_percent' in p and p['memory_percent'] is not None and p['memory_percent'] != '':
            msg = '{0:>6.1f}'.format(p['memory_percent'])
            ret.append(self.curse_add_line(msg,
                                           self.get_alert(p['memory_percent'], header="mem")))
        else:
            msg = '{0:>6}'.format('?')
            ret.append(self.curse_add_line(msg))
        # VMS/RSS
        if 'memory_info' in p and p['memory_info'] is not None and p['memory_info'] != '':
            # VMS
            msg = '{0:>6}'.format(self.auto_unit(p['memory_info'][1], low_precision=False))
            ret.append(self.curse_add_line(msg, optional=True))
            # RSS
            msg = '{0:>6}'.format(self.auto_unit(p['memory_info'][0], low_precision=False))
            ret.append(self.curse_add_line(msg, optional=True))
        else:
            msg = '{0:>6}'.format('?')
            ret.append(self.curse_add_line(msg))
            ret.append(self.curse_add_line(msg))
        # PID
        msg = '{0:>6}'.format(p['pid'])
        ret.append(self.curse_add_line(msg))
        # USER
        if 'username' in p:
            # docker internal users are displayed as ints only, therefore str()
            msg = ' {0:9}'.format(str(p['username'])[:9])
            ret.append(self.curse_add_line(msg))
        else:
            msg = ' {0:9}'.format('?')
            ret.append(self.curse_add_line(msg))
        # NICE
        if 'nice' in p:
            nice = p['nice']
            if nice is None:
                nice = '?'
            msg = '{0:>5}'.format(nice)
            if isinstance(nice, int) and ((is_windows and nice != 32) or
                                          (not is_windows and nice != 0)):
                ret.append(self.curse_add_line(msg, decoration='NICE'))
            else:
                ret.append(self.curse_add_line(msg))
        else:
            msg = '{0:>5}'.format('?')
            ret.append(self.curse_add_line(msg))
        # STATUS
        if 'status' in p:
            status = p['status']
            msg = '{0:>2}'.format(status)
            if status == 'R':
                ret.append(self.curse_add_line(msg, decoration='STATUS'))
            else:
                ret.append(self.curse_add_line(msg))
        else:
            msg = '{0:>2}'.format('?')
            ret.append(self.curse_add_line(msg))
        # TIME+
        if self.tag_proc_time:
            try:
                dtime = timedelta(seconds=sum(p['cpu_times']))
            except Exception:
                # Catched on some Amazon EC2 server
                # See https://github.com/nicolargo/glances/issues/87
                self.tag_proc_time = False
            else:
                msg = '{0}:{1}.{2}'.format(str(dtime.seconds // 60 % 60),
                                           str(dtime.seconds % 60).zfill(2),
                                           str(dtime.microseconds)[:2].zfill(2))
        else:
            msg = ' '
        msg = '{0:>9}'.format(msg)
        ret.append(self.curse_add_line(msg, optional=True))
        # IO read/write
        if 'io_counters' in p:
            # IO read
            io_rs = int((p['io_counters'][0] - p['io_counters'][2]) / p['time_since_update'])
            if io_rs == 0:
                msg = '{0:>6}'.format("0")
            else:
                msg = '{0:>6}'.format(self.auto_unit(io_rs, low_precision=True))
            ret.append(self.curse_add_line(msg, optional=True, additional=True))
            # IO write
            io_ws = int((p['io_counters'][1] - p['io_counters'][3]) / p['time_since_update'])
            if io_ws == 0:
                msg = '{0:>6}'.format("0")
            else:
                msg = '{0:>6}'.format(self.auto_unit(io_ws, low_precision=True))
            ret.append(self.curse_add_line(msg, optional=True, additional=True))
        else:
            msg = '{0:>6}'.format("?")
            ret.append(self.curse_add_line(msg, optional=True, additional=True))
            ret.append(self.curse_add_line(msg, optional=True, additional=True))

        # Command line
        # If no command line for the process is available, fallback to
        # the bare process name instead
        cmdline = p['cmdline']
        if cmdline == "" or args.process_short_name:
            msg = ' {0}'.format(p['name'])
            ret.append(self.curse_add_line(msg, splittable=True))
        else:
            try:
                cmd = cmdline.split()[0]
                argument = ' '.join(cmdline.split()[1:])
                path, basename = os.path.split(cmd)
                if os.path.isdir(path):
                    msg = ' {0}'.format(path) + os.sep
                    ret.append(self.curse_add_line(msg, splittable=True))
                    ret.append(self.curse_add_line(basename, decoration='PROCESS', splittable=True))
                else:
                    msg = ' {0}'.format(basename)
                    ret.append(self.curse_add_line(msg, decoration='PROCESS', splittable=True))
                msg = " {0}".format(argument)
                ret.append(self.curse_add_line(msg, splittable=True))
            except UnicodeEncodeError:
                ret.append(self.curse_add_line("", splittable=True))

        # Add extended stats but only for the top processes
        # !!! CPU consumption ???
        # TODO: extended stats into the web interface
        if first and 'extended_stats' in p:
            # Left padding
            xpad = ' ' * 13
            # First line is CPU affinity
            if 'cpu_affinity' in p and p['cpu_affinity'] is not None:
                ret.append(self.curse_new_line())
                msg = xpad + _('CPU affinity: ') + str(len(p['cpu_affinity'])) + _(' cores')
                ret.append(self.curse_add_line(msg, splittable=True))
            # Second line is memory info
            if 'memory_info_ex' in p and p['memory_info_ex'] is not None:
                ret.append(self.curse_new_line())
                msg = xpad + _('Memory info: ')
                for k, v in p['memory_info_ex']._asdict().items():
                    # Ignore rss and vms (already displayed)
                    if k not in ['rss', 'vms'] and v is not None:
                        msg += k + ' ' + self.auto_unit(v, low_precision=False) + ' '
                if 'memory_swap' in p and p['memory_swap'] is not None:
                    msg += _('swap ') + self.auto_unit(p['memory_swap'], low_precision=False)
                ret.append(self.curse_add_line(msg, splittable=True))
            # Third line is for open files/network sessions
            msg = ''
            if 'num_threads' in p and p['num_threads'] is not None:
                msg += _('threads ') + str(p['num_threads']) + ' '
            if 'num_fds' in p and p['num_fds'] is not None:
                msg += _('files ') + str(p['num_fds']) + ' '
            if 'num_handles' in p and p['num_handles'] is not None:
                msg += _('handles ') + str(p['num_handles']) + ' '
            if 'tcp' in p and p['tcp'] is not None:
                msg += _('TCP ') + str(p['tcp']) + ' '
            if 'udp' in p and p['udp'] is not None:
                msg += _('UDP ') + str(p['udp']) + ' '
            if msg != '':
                ret.append(self.curse_new_line())
                msg = xpad + _('Open: ') + msg
                ret.append(self.curse_add_line(msg, splittable=True))
            # Fouth line is IO nice level (only Linux and Windows OS)
            if 'ionice' in p and p['ionice'] is not None:
                ret.append(self.curse_new_line())
                msg = xpad + _('IO nice: ')
                k = _('Class is ')
                v = p['ionice'].ioclass
                # Linux: The scheduling class. 0 for none, 1 for real time, 2 for best-effort, 3 for idle.
                # Windows: On Windows only ioclass is used and it can be set to 2 (normal), 1 (low) or 0 (very low).
                if is_windows:
                    if v == 0:
                        msg += k + 'Very Low'
                    elif v == 1:
                        msg += k + 'Low'
                    elif v == 2:
                        msg += _('No specific I/O priority')
                    else:
                        msg += k + str(v)
                else:
                    if v == 0:
                        msg += _('No specific I/O priority')
                    elif v == 1:
                        msg += k + 'Real Time'
                    elif v == 2:
                        msg += k + 'Best Effort'
                    elif v == 3:
                        msg += k + 'IDLE'
                    else:
                        msg += k + str(v)
                #  value is a number which goes from 0 to 7.
                # The higher the value, the lower the I/O priority of the process.
                if hasattr(p['ionice'], 'value') and p['ionice'].value != 0:
                    msg += _(' (value %s/7)') % str(p['ionice'].value)
                ret.append(self.curse_add_line(msg, splittable=True))

        return ret

    def msg_curse(self, args=None):
        """Return the dict to display in the curse interface."""
        # Init the return message
        ret = []

        # Only process if stats exist and display plugin enable...
        if not self.stats or args.disable_process:
            return ret

        # Compute the sort key
        process_sort_key = glances_processes.getsortkey()
        sort_style = 'SORT'

        # Header
        msg = '{0:>6}'.format(_("CPU%"))
        ret.append(self.curse_add_line(msg, sort_style if process_sort_key == 'cpu_percent' else 'DEFAULT'))
        msg = '{0:>6}'.format(_("MEM%"))
        ret.append(self.curse_add_line(msg, sort_style if process_sort_key == 'memory_percent' else 'DEFAULT'))
        msg = '{0:>6}'.format(_("VIRT"))
        ret.append(self.curse_add_line(msg, optional=True))
        msg = '{0:>6}'.format(_("RES"))
        ret.append(self.curse_add_line(msg, optional=True))
        msg = '{0:>6}'.format(_("PID"))
        ret.append(self.curse_add_line(msg))
        msg = ' {0:10}'.format(_("USER"))
        ret.append(self.curse_add_line(msg))
        msg = '{0:>4}'.format(_("NI"))
        ret.append(self.curse_add_line(msg))
        msg = '{0:>2}'.format(_("S"))
        ret.append(self.curse_add_line(msg))
        msg = '{0:>9}'.format(_("TIME+"))
        ret.append(self.curse_add_line(msg, sort_style if process_sort_key == 'cpu_times' else 'DEFAULT', optional=True))
        msg = '{0:>6}'.format(_("IOR/s"))
        ret.append(self.curse_add_line(msg, sort_style if process_sort_key == 'io_counters' else 'DEFAULT', optional=True, additional=True))
        msg = '{0:>6}'.format(_("IOW/s"))
        ret.append(self.curse_add_line(msg, sort_style if process_sort_key == 'io_counters' else 'DEFAULT', optional=True, additional=True))
        msg = ' {0:8}'.format(_("Command"))
        ret.append(self.curse_add_line(msg))

        # Trying to display proc time
        self.tag_proc_time = True

        if glances_processes.is_tree_enabled():
            ret.extend(self.get_process_tree_curses_data(self.sortstats(process_sort_key),
                                                         args,
                                                         first_level=True,
                                                         max_node_count=glances_processes.get_max_processes()))
        else:
            # Loop over processes (sorted by the sort key previously compute)
            first = True
            for p in self.sortstats(process_sort_key):
                ret.extend(self.get_process_curses_data(p, first, args))
                # End of extended stats
                first = False

        # Return the message with decoration
        return ret

    def sortstats(self, sortedby=None):
        """Return the stats sorted by sortedby variable."""
        if sortedby is None:
            # No need to sort...
            return self.stats

        sortedreverse = True
        if sortedby == 'name':
            sortedreverse = False

        tree = glances_processes.is_tree_enabled()

        if sortedby == 'io_counters' and not tree:
            # Specific case for io_counters
            # Sum of io_r + io_w
            try:
                # Sort process by IO rate (sum IO read + IO write)
                self.stats.sort(key=lambda process: process[sortedby][0] -
                                process[sortedby][2] + process[sortedby][1] -
                                process[sortedby][3],
                                reverse=sortedreverse)
            except Exception:
                self.stats.sort(key=operator.itemgetter('cpu_percent'),
                                reverse=sortedreverse)
        else:
            # Others sorts
            if tree:
                self.stats.set_sorting(sortedby, sortedreverse)
            else:
                try:
                    self.stats.sort(key=operator.itemgetter(sortedby),
                                    reverse=sortedreverse)
                except (KeyError, TypeError):
                    self.stats.sort(key=operator.itemgetter('name'),
                                    reverse=False)

        return self.stats
