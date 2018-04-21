#!/usr/bin/env python3
# forked from script from Kim Nguyên, see https://bugs.launchpad.net/ubuntu/+source/gnome-settings-daemon/+bug/1722286
# run via sudo systemd-inhibit --who=${USER} --why=because --mode=block --what=handle-lid-switch .../startup-scripts/lid-suspend-manager.py

import subprocess
import gi
from gi.repository import GLib
from gi.repository import Gio

import dbus
from dbus.mainloop.glib import DBusGMainLoop

import subprocess

class Action():
    def blank(self):
        return subprocess.call(['gnome-screensaver-command', '-a'])

    def suspend(self):
        return subprocess.call(['systemctl', 'suspend', '-i'])

    def shutdown(self):
        return subprocess.call(['systemctl', 'poweroff', '-i'])

    def hibernate(self):
        return subprocess.call(['systemctl', 'hibernate', '-i'])

    def interactive(self):
        return subprocess.call(['gnome-session-quit'])

    def nothing(self):
        return

    def logout(self):
        return subprocess.call(['gnome-session-quit', '--no-prompt'])



class LidSuspendManager():
    DBUS_UPOWER_PATH = '/org/freedesktop/UPower'
    DBUS_UPOWER_BUS = 'org.freedesktop.UPower'
    DBUS_PROPERTIES_IFACE = 'org.freedesktop.DBus.Properties'

    UPOWER_lid_is_closed = 'LidIsClosed'
    UPOWER_running_on_battery = 'OnBattery'
    DBUS_PROPERTIES_CHANGED = 'PropertiesChanged'

    action = Action()
    running_on_battery = False
    lid_is_closed = False
    ext_monitor_connected= True
    int_monitor="eDP-1"
    ext_monitor="HDMI-2"
    bus = None

    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()

    def update_monitor_status(self):
        get_screens = subprocess.check_output("xrandr").decode("utf-8").splitlines()
        scr_data = [l for l in get_screens if " connected " in l]
        monitors_number  = len(scr_data)
        if monitors_number == 1:
            print("one display connected")
            self.ext_monitor_connected = False
        if monitors_number == 2:
            print("2 displays connected")
            ext = [s.split()[0] for s in scr_data if not self.int_monitor in s][0]
            print("external display is : %s" % ext)
            self.ext_monitor_connected = True

    # disable the internal display and enable the external display
    def switch_to_ext_monitor(self):
        subprocess.Popen(["xrandr", "--output", self.ext_monitor, "--auto", "--output", self.int_monitor, "--off"])

    def init_status (self):
        upower_object = self.bus.get_object (self.DBUS_UPOWER_BUS, self.DBUS_UPOWER_PATH)
        upower_intf = dbus.Interface (upower_object, self.DBUS_PROPERTIES_IFACE)
        self.lid_is_closed = upower_intf.Get(self.DBUS_UPOWER_BUS, self.UPOWER_lid_is_closed)
        self.running_on_battery = upower_intf.Get(self.DBUS_UPOWER_BUS, self.UPOWER_running_on_battery)

    # get action from dconf setting based on power status
    def action_when_lid_closed_no_ext_monitor (self):
        gsettings = Gio.Settings.new ('org.gnome.settings-daemon.plugins.power')

        # on battery
        if self.running_on_battery:
            return gsettings.get_string ('lid-close-battery-action')
        # on AC
        else:
            return gsettings.get_string ('lid-close-ac-action')

    # get action from dconf setting based on external monitor status and power status
    def action_when_lid_closed (self):
        gsettings = Gio.Settings.new ('org.gnome.settings-daemon.plugins.power')
        if self.ext_monitor_connected:
            prevent_suspend_if_ext_monitor = not gsettings.get_boolean ('lid-close-suspend-with-external-monitor')
            # do not suspend if lid-close-suspend-with-external-monitor
            if prevent_suspend_if_ext_monitor:
                return "nothing"
            # if lid-close-suspend-with-external-monitor not set, chose what to do based on power state
            else:
                return self.action_when_lid_closed_no_ext_monitor()
        # if no external monitor, chose what to do based on power state
        else:
            return self.action_when_lid_closed_no_ext_monitor()

    #
    def update_power_status(self,arg1, arg2, arg3):
        for key in arg2:
            if key == self.UPOWER_lid_is_closed:
                self.lid_is_closed = arg2[key]
            elif  key == self.UPOWER_running_on_battery:
                self.running_on_battery = arg2[key]

    # if lid is closed, find what to do & do it
    def perform_action_if_lid_closed(self):
        if self.lid_is_closed:
            # turn on ext monitor
            if self.ext_monitor_connected:
                self.switch_to_ext_monitor()
            # suspend if needed
            action_string = self.action_when_lid_closed()
            # send the action (suspend, nothing...)
            getattr(self.action, action_string)()
            self.init_status()   # in case the user plugged/unplugged during suspend or hibernate

    # called on event (AC power cable attached, lid closed...)
    def handle_events(self,arg1, arg2, arg3):
        self.update_power_status(arg1, arg2, arg3)
        self.update_monitor_status()
        self.perform_action_if_lid_closed()


    def start (self):
        self.init_status()
        self.perform_action_if_lid_closed()
        self.bus.add_signal_receiver (lambda a,b,c: self.handle_events(a,b,c) ,
                                 self.DBUS_PROPERTIES_CHANGED,
                                 self.DBUS_PROPERTIES_IFACE,
                                 self.DBUS_UPOWER_BUS,
                                 self.DBUS_UPOWER_PATH)
        loop = GLib.MainLoop()
        try:
            loop.run()
        except (KeyboardInterrupt, SystemExit):
            return



if __name__ == '__main__':
    LidSuspendManager().start()
