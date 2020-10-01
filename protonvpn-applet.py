#!/usr/bin/env python3
import sys
import subprocess
import functools
from enum import Enum
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, qApp, QMessageBox
from PyQt5.QtCore import QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

from protonvpn_cli import utils, country_codes
from protonvpn_cli.utils import is_connected


PROTONVPN_APPLET_VERSION = 0.1


class VPNStatusException(Exception):
    """General exception to throw when anything goes wrong
    """


class VPNCommand(Enum):
    """Commands to run the CLI
    """
    status = 'protonvpn s'
    connect_fastest = 'protonvpn c -f'
    disconnect = 'protonvpn d'
    version = 'protonvpn -v'
    connect_random = 'protonvpn c -r'
    connect_fastest_cc = 'protonvpn c --cc'
    connect_fastest_p2p = 'protonvpn c --p2p'
    connect_fastest_sc = 'protonvpn c --sc'
    connect_fastest_tor = 'protonvpn c --tor'
    reconnect = 'protonvpn r'


def check_single_instance():
    """Use pgrep to check if protonvpn-applet is already running
    """
    pid = None

    try:
        pid = subprocess.run('pgrep protonvpn-applet'.split(), check=True, capture_output=True)
    except subprocess.CalledProcessError:
        try:
            pid = subprocess.run('pgrep protonvpn-applet.py'.split(), check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass

    if pid is not None:
        print('There is an instance already running.')
        sys.exit(1)


class Status(Enum):
    """Enum to keep track of the previous connection state
    """
    connected = 'Connected'
    disconnected = 'Disconnected'


class Polling(QThread):
    """Thread to check the VPN state every second and notifies on disconnection
    """
    def __init__(self, applet):
        QThread.__init__(self)
        self.applet = applet

    def __del__(self):
        self.wait()

    def run(self):
        while self.applet.is_polling():
            if is_connected():
                self.applet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-connected.png'))
                self.applet.previous_status = Status.connected
            else:
                # notify on disconnection
                if self.applet.show_notifications() and self.applet.previous_status == Status.connected:
                    CheckStatus(self).start()
                self.applet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
                self.applet.previous_status = Status.disconnected
            self.sleep(1)


class ConnectVPN(QThread):
    """Thread to connect using the specified profile
    """
    def __init__(self, applet, command):
        QThread.__init__(self)
        self.applet = applet
        self.command = command
        print(self.command)

    def __del__(self):
        self.wait()

    def run(self):
        subprocess.run([self.applet.auth] + self.command.split(), check=False)
        self.applet.status_vpn()


class DisconnectVPN(QThread):
    """Thread to disconnect the VPN
    """
    def __init__(self, applet):
        QThread.__init__(self)
        self.applet = applet

    def __del__(self):
        self.wait()

    def run(self):
        subprocess.run([self.applet.auth] + VPNCommand.disconnect.value.split(), check=False)
        self.applet.status_vpn()


class ReconnectVPN(QThread):
    """Thread to connect using previously used profile
    """
    def __init__(self, applet):
        QThread.__init__(self)
        self.applet = applet

    def __del__(self):
        self.wait()

    def run(self):
        subprocess.run([self.applet.auth] + VPNCommand.reconnect.value.split(), check=False)
        self.applet.status_vpn()


class CheckStatus(QThread):
    """Thread to report ProtonVPN status
    """
    def __init__(self, applet):
        QThread.__init__(self)
        self.applet = applet

    def __del__(self):
        self.wait()

    def run(self):
        result = subprocess.run(VPNCommand.status.value.split(), check=False, capture_output=True)
        Notify.Notification.new(result.stdout.decode()).show()


class CheckProtonVPNVersion(QThread):
    """Thread to check version
    """
    protonvpn_version_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.version = 'None'

    def __del__(self):
        self.wait()

    def run(self):
        self.version = subprocess.check_output(VPNCommand.version.value.split()).decode(sys.stdout.encoding)
        self.protonvpn_version_ready.emit(self.version)


class PVPNApplet(QMainWindow):
    """Main applet body
    """
    tray_icon = None
    polling = True
    previous_status = None
    #auth = 'pkexec'
    auth = 'sudo'

    # Override the class constructor
    def __init__(self):
        super(PVPNApplet, self).__init__()

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
        connect_fastest_action = QAction('Connect fastest', self)
        reconnect_action = QAction('Reconnect', self)
        disconnect_action = QAction('Disconnect', self)
        status_action = QAction('Status', self)
        connect_fastest_sc_action = QAction('Secure Core', self)
        connect_fastest_p2p_action = QAction('P2P', self)
        connect_fastest_tor_action = QAction('Tor', self)
        connect_random_action = QAction('Random', self)
        show_protonvpn_applet_version_action = QAction('About ProtonVPN-Applet', self)
        show_protonvpn_version_action = QAction('About ProtonVPN', self)
        quit_action = QAction('Exit', self)
        self.show_notifications_action = QAction('Show Notifications')
        self.show_notifications_action.setCheckable(True)
        self.show_notifications_action.setChecked(False)

        # Triggers
        quit_action.triggered.connect(qApp.quit)
        connect_fastest_action.triggered.connect(self.connect_fastest)
        disconnect_action.triggered.connect(self.disconnect_vpn)
        status_action.triggered.connect(self.status_vpn)
        show_protonvpn_applet_version_action.triggered.connect(self.show_protonvpn_applet_version)
        show_protonvpn_version_action.triggered.connect(self.get_protonvpn_version)
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
        tray_menu.addAction(connect_fastest_action)
        tray_menu.addAction(reconnect_action)
        tray_menu.addMenu(connection_menu)
        tray_menu.addAction(disconnect_action)
        tray_menu.addAction(status_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self.show_notifications_action)
        tray_menu.addAction(show_protonvpn_applet_version_action)
        tray_menu.addAction(show_protonvpn_version_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Polling thread
        self.start_polling()

    def is_polling(self):
        return self.polling

    def kill_polling(self):
        self.polling = False

    def start_polling(self):
        self.polling = True
        self.polling_thread = Polling(self)
        self.polling_thread.start()

    def _connect_vpn(self, command):
        self.kill_polling()
        connect_thread = ConnectVPN(self, command)
        connect_thread.finished.connect(self.start_polling)
        connect_thread.start()

    def connect_fastest(self):
        self._connect_vpn(VPNCommand.connect_fastest.value)

    def connect_fastest_p2p(self):
        self._connect_vpn(VPNCommand.connect_fastest_p2p.value)

    def connect_fastest_sc(self):
        self._connect_vpn(VPNCommand.connect_fastest_sc.value)

    def connect_fastest_cc(self, cc):
        command = VPNCommand.connect_fastest_cc.value + f' {cc}'
        self._connect_vpn(command)

    def connect_fastest_tor(self):
        self._connect_vpn(VPNCommand.connect_fastest_tor.value)

    def connect_random(self):
        self._connect_vpn(VPNCommand.connect_random.value)

    def disconnect_vpn(self):
        disconnect_thread = DisconnectVPN(self)
        disconnect_thread.start()

    def status_vpn(self):
        status_thread = CheckStatus(self)
        status_thread.start()

    def reconnect_vpn(self):
        reconnect_thread = ReconnectVPN(self)
        reconnect_thread.start()

    # Override closeEvent to intercept the window closing event
    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def show_notifications(self):
        return self.show_notifications_action.isChecked()

    def show_protonvpn_applet_version(self):
        """Show the protonvpn-applet version.
        """

        name = '© 2020 Dónal Murray'
        email = 'dmurray654@gmail.com'
        github = 'https://github.com/seadanda/protonvpn-applet'

        info = [f'<center>Version: {PROTONVPN_APPLET_VERSION}',
                f'{name}',
                f"<a href='{email}'>{email}</a>",
                f"<a href='{github}'>{github}</a></center>"]

        centered_text = f'<center>{"<br>".join(info)}</center>'

        QMessageBox.information(self, 'protonvpn-applet', centered_text)

    def get_protonvpn_version(self):
        """Start the CheckProtonVPNVersion thread; when it gets the version, it will call `self.show_protonvpn_version`
        """
        print('called get_protonvpn_version')
        check_protonvpn_version_thread = CheckProtonVPNVersion(self)
        check_protonvpn_version_thread.protonvpn_version_ready.connect(self.show_protonvpn_version)
        check_protonvpn_version_thread.start()

    def show_protonvpn_version(self, version):
        """
        Show the ProtonVPN version in a QMessageBox.

        Parameters
        ----------
        version : str
            Version number to be shown.
        """
        print('called show_protonvpn_version')
        QMessageBox.information(self, 'ProtonVPN Version', f'Version: {version}')

    def update_available_servers(self):
        utils.pull_server_data()
        return utils.get_servers()

    @staticmethod
    def get_available_countries(servers):
        return sorted(list({utils.get_country_name(server['ExitCountry']) for server in servers}))


if __name__ == '__main__':
    check_single_instance()
    app = QApplication(sys.argv)
    mw = PVPNApplet()
    sys.exit(app.exec())
