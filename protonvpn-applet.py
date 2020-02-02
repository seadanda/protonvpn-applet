#!/usr/bin/env python3
import sys
import re
import subprocess
import functools
from enum import Enum
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, qApp
from PyQt5.QtCore import QSize, QThread
from PyQt5.QtGui import QIcon

from protonvpn_cli import utils, country_codes


class VPNStatusException(Exception):
    pass


class VPNCommand(Enum):
    status = 'sudo protonvpn s'
    connect_fastest = 'sudo protonvpn c -f'
    disconnect = 'sudo protonvpn d'
    connect_random = 'sudo protonvpn c -r'
    connect_fastest_cc = 'sudo protonvpn c --cc'
    connect_fastest_p2p = 'sudo protonvpn c --p2p'
    connect_fastest_sc = 'sudo protonvpn c --sc'
    connect_fastest_tor = 'sudo protonvpn c --tor'
    reconnect = 'sudo protonvpn r'


def check_single_instance():

    pid = None

    try:
        pid = subprocess.check_output('pgrep protonvpn-applet'.split()).decode(sys.stdout.encoding)
    except subprocess.CalledProcessError:
        try:
            pid = subprocess.check_output('pgrep protonvpn-applet.py'.split()).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError:
            pass

    if pid is not None:
        print('There is an instance already running.')
        sys.exit(1)

    return


class Polling(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        while(self.PApplet.is_polling()):
            try:
                subprocess.check_output('pgrep openvpn'.split()).decode(sys.stdout.encoding)
                iplink = subprocess.check_output('ip link'.split()).decode(sys.stdout.encoding)
                if (re.search(r'tun[0-9]:', iplink)):
                    self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-connected.png'))
                else:
                    pass  # Sometimes ip link doesn't update immediately. Check again at next poll
            except subprocess.CalledProcessError:
                self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
            self.sleep(1)
        return


class ConnectVPN(QThread):
    def __init__(self, PApplet, command):
        QThread.__init__(self)
        self.PApplet = PApplet
        self.command = command
        print(self.command)
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        print('protonvpn-cli-ng currently has an issue getting the status when connected to Tor servers. If you have any doubts, check dnsleaktest.com')
        subprocess.run(self.command.split())
        self.PApplet.status_vpn('dummy')

        return


class DisconnectVPN(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        subprocess.run(VPNCommand.disconnect.value.split())
        self.PApplet.status_vpn('dummy')
        return


class ReconnectVPN(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        subprocess.run(VPNCommand.reconnect.value.split())
        self.PApplet.status_vpn('dummy')
        return


class CheckStatus(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        result = ''
        if self.PApplet.is_tor:
            # rely on polling check and warn
            print('protonvpn-cli-ng currently has an issue getting the status when connected to Tor servers. If you have any doubts, check dnsleaktest.com')
        else:
            result = subprocess.check_output(VPNCommand.status.value.split()).decode(sys.stdout.encoding)
            result = result.split('\n')
            if 'Disconnected' in result[0]:
                if self.PApplet.show_notifications():
                    Notify.Notification.new(f'VPN disconnected').show()
                self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
            elif 'Connected' in result[0]:
                if self.PApplet.show_notifications():
                    Notify.Notification.new('\n'.join(result)).show()
                self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-connected.png'))
            else:
                raise VPNStatusException(f'VPN status could not be parsed: {result}')

        return


class PVPNApplet(QMainWindow):
    tray_icon = None
    polling = True
    tor_connected = False

    # Override the class constructor
    def __init__(self):

        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(480, 80))             # Set sizes
        self.setWindowTitle('ProtonVPN Qt')             # Set a title
        central_widget = QWidget(self)                  # Create a central widget
        self.setCentralWidget(central_widget)           # Set the central widget
        self.country_codes = country_codes              # Keep a list of country codes

        # Init QSystemTrayIcon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))

        # Init libnotify
        Notify.init('ProtonVPN')

        # Refresh server list, store the resulting servers so we can populate the menu
        self.servers = self.update_available_servers()

        # Menu actions
        connect_fastest_action = QAction('Connect', self)
        disconnect_action = QAction('Disconnect', self)
        status_action = QAction('Status', self)
        quit_action = QAction('Exit', self)
        connect_fastest_sc_action = QAction('Secure Core', self)
        connect_fastest_p2p_action = QAction('P2P', self)
        connect_fastest_tor_action = QAction('Tor', self)
        connect_random_action = QAction('Random', self)
        reconnect_action = QAction('Reconnect', self)
        self.show_notifications_action = QAction('Show Notifications')
        self.show_notifications_action.setCheckable(True)
        self.show_notifications_action.setChecked(False)

        # Triggers
        quit_action.triggered.connect(qApp.quit)
        connect_fastest_action.triggered.connect(self.connect_fastest)
        disconnect_action.triggered.connect(self.disconnect_vpn)
        status_action.triggered.connect(self.status_vpn)
        connect_fastest_sc_action.triggered.connect(self.connect_fastest_sc)
        connect_fastest_p2p_action.triggered.connect(self.connect_fastest_p2p)
        connect_fastest_tor_action.triggered.connect(self.connect_fastest_tor)
        connect_random_action.triggered.connect(self.connect_random)
        reconnect_action.triggered.connect(self.reconnect_vpn)

        # Generate connection menu for specific countries
        connect_country_actions = []
        for country_name in self.get_available_countries(self.servers):

            # Get the ISO-3166 Alpha-2 country code
            country_name_to_code = {v: k for k, v in country_codes.country_codes.items()}
            country_code = country_name_to_code[country_name]

            # Dynamically create functions for connecting to each country; each function just passes its respective
            # country code to `self.connect_fastest_cc()`
            setattr(self, f'connect_fastest_{country_code}', functools.partial(self.connect_fastest_cc, country_code))

            # Generate an action for each country; set up the trigger; append to actions list
            country_action = QAction(f'{country_name}', self)
            country_action.triggered.connect(getattr(self, f'connect_fastest_{country_code}'))
            connect_country_actions.append(country_action)

        # Create a scrollable country connection menu
        connect_country_menu = QMenu("Country...", self)
        connect_country_menu.setStyleSheet('QMenu  { menu-scrollable: 1; }')
        connect_country_menu.addActions(connect_country_actions)

        # Generate connection menu
        connection_menu = QMenu("Other connections...", self)
        connection_menu.addMenu(connect_country_menu)
        connection_menu.addAction(connect_fastest_sc_action)
        connection_menu.addAction(connect_fastest_p2p_action)
        connection_menu.addAction(connect_fastest_tor_action)
        connection_menu.addAction(connect_random_action)

        # Draw menu
        tray_menu = QMenu()
        tray_menu.addMenu(connection_menu)
        tray_menu.addAction(connect_fastest_action)
        tray_menu.addAction(disconnect_action)
        tray_menu.addAction(reconnect_action)
        tray_menu.addAction(status_action)
        tray_menu.addAction(self.show_notifications_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Polling thread
        self.start_polling()

        return

    def is_tor(self):
        return self.tor_connected

    def set_tor(self, state: bool):
        self.tor_connected = state
        return

    def is_polling(self):
        return self.polling

    def kill_polling(self):
        self.polling = False
        return

    def start_polling(self):
        self.polling = True
        self.pollingThread = Polling(self)
        self.pollingThread.start()
        return

    def _connect_vpn(self, command):
        self.kill_polling()
        self.connectThread = ConnectVPN(self, command)
        self.connectThread.finished.connect(self.start_polling)
        self.connectThread.start()
        return

    def connect_fastest(self):
        self._connect_vpn(VPNCommand.connect_fastest.value)
        return

    def connect_fastest_p2p(self):
        self._connect_vpn(VPNCommand.connect_fastest_p2p.value)
        return

    def connect_fastest_sc(self):
        self._connect_vpn(VPNCommand.connect_fastest_sc.value)
        return

    def connect_fastest_cc(self, cc):
        command = VPNCommand.connect_fastest_cc.value + f' {cc}'
        self._connect_vpn(command)
        return

    def connect_fastest_tor(self):
        self._connect_vpn(VPNCommand.connect_fastest_tor.value)
        return

    def connect_random(self):
        self._connect_vpn(VPNCommand.connect_random.value)
        return

    def disconnect_vpn(self, event):
        self.disconnectThread = DisconnectVPN(self)
        self.disconnectThread.start()
        return

    def status_vpn(self, event):
        self.statusThread = CheckStatus(self)
        self.statusThread.start()
        return

    def reconnect_vpn(self):
        self.reconnectThread = ReconnectVPN(self)
        self.reconnectThread.start()
        return

    # Override closeEvent to intercept the window closing event
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        return

    def show_notifications(self):
        return self.show_notifications_action.isChecked()

    def update_available_servers(self):
        utils.pull_server_data()
        return utils.get_servers()

    @staticmethod
    def get_available_countries(servers):
        return sorted(list(set([utils.get_country_name(server['ExitCountry']) for server in servers])))


if __name__ == '__main__':
    check_single_instance()
    app = QApplication(sys.argv)
    mw = PVPNApplet()
    sys.exit(app.exec())
