#!/usr/bin/env python3
import sys
import re
import subprocess
from enum import Enum
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, qApp, QMessageBox
from PyQt5.QtCore import QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon


PROTONVPN_APPLET_VERSION = 0.1


class VPNStatusException(Exception):
    pass


class VPNCommand(Enum):
    status = 'sudo protonvpn s'
    connect_fastest = 'sudo protonvpn c -f'
    disconnect = 'sudo protonvpn d'
    version = 'sudo protonvpn -v'


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


class Status(Enum):
    connected = 'Connected'
    disconnected = 'Disconnected'


def check_status(applet, previous_status=None, log=False):
    """
    Checks the VPN status with `protonvpn status` command.
    """
    result = subprocess.check_output(VPNCommand.status.value.split()).decode(sys.stdout.encoding)

    if log:
        print(result)

    prev_not = lambda s: previous_status is None or previous_status != s

    if Status.disconnected.value in result:
        if applet.show_notifications() and prev_not(Status.disconnected):
            Notify.Notification.new(f'VPN disconnected').show()
        applet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
        applet.previous_status = Status.disconnected
    elif Status.connected.value in result:
        if applet.show_notifications() and prev_not(Status.connected):
            Notify.Notification.new(result).show()
        applet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-connected.png'))
        applet.previous_status = Status.connected
    else:
        raise VPNStatusException(f'VPN status could not be parsed: {result}')

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
                check_status(self.PApplet, self.PApplet.previous_status)
            except VPNStatusException as err:
                if self.PApplet.show_notifications():
                    Notify.Notification.new(str(err)).show()
                self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
                self.PApplet.previous_status = Status.disconnected
            except subprocess.CalledProcessError:
                self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
                self.PApplet.previous_status = Status.disconnected
            self.sleep(1)
        return


class ConnectVPN(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        subprocess.run(VPNCommand.connect_fastest.value.split())
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


class CheckStatus(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet
        return

    def __del__(self):
        self.wait()
        return

    def run(self):
        return check_status(self.PApplet, log=True)


class CheckProtonVPNVersion(QThread):

    protonvpn_version_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.version = 'None'

    def __del__(self):
        self.wait()
        return

    def run(self):
        self.version = subprocess.check_output(VPNCommand.version.value.split()).decode(sys.stdout.encoding)
        self.protonvpn_version_ready.emit(self.version)
        return


class PVPNApplet(QMainWindow):

    tray_icon = None
    polling = True
    previous_status = None

    # Override the class constructor
    def __init__(self):

        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(480, 80))             # Set sizes
        self.setWindowTitle('ProtonVPN Qt')             # Set a title
        central_widget = QWidget(self)                  # Create a central widget
        self.setCentralWidget(central_widget)           # Set the central widget

        # Init QSystemTrayIcon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))

        # Init libnotify
        Notify.init('ProtonVPN')

        # Menu actions
        connect_action = QAction('Connect', self)
        disconnect_action = QAction('Disconnect', self)
        status_action = QAction('Status', self)
        quit_action = QAction('Exit', self)
        show_protonvpn_applet_version_action = QAction('About ProtonVPN-Applet', self)
        show_protonvpn_version_action = QAction('About ProtonVPN', self)
        self.show_notifications_action = QAction('Show Notifications')
        self.show_notifications_action.setCheckable(True)
        self.show_notifications_action.setChecked(False)

        # Triggers
        quit_action.triggered.connect(qApp.quit)
        connect_action.triggered.connect(self.connect_vpn)
        disconnect_action.triggered.connect(self.disconnect_vpn)
        status_action.triggered.connect(self.status_vpn)
        show_protonvpn_applet_version_action.triggered.connect(self.show_protonvpn_applet_version)
        show_protonvpn_version_action.triggered.connect(self.get_protonvpn_version)

        # Draw menu
        tray_menu = QMenu()
        tray_menu.addAction(show_protonvpn_applet_version_action)
        tray_menu.addAction(show_protonvpn_version_action)
        tray_menu.addAction(self.show_notifications_action)
        tray_menu.addAction(connect_action)
        tray_menu.addAction(disconnect_action)
        tray_menu.addAction(status_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Polling thread
        self.start_polling()

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

    def connect_vpn(self, event):
        self.kill_polling()
        self.connectThread = ConnectVPN(self)
        self.connectThread.finished.connect(self.start_polling)
        self.connectThread.start()
        return

    def disconnect_vpn(self, event):
        self.disconnectThread = DisconnectVPN(self)
        self.disconnectThread.start()
        return

    def status_vpn(self, event):
        self.statusThread = CheckStatus(self)
        self.statusThread.start()
        return

    # Override closeEvent to intercept the window closing event
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        return

    def show_notifications(self):
        return self.show_notifications_action.isChecked()

    def show_protonvpn_applet_version(self):
        """Show the protonvpn-applet version.
        """

        name = '© 2019 Dónal Murray'
        email = 'dmurray654@gmail.com'
        github = 'https://github.com/seadanda/protonvpn-applet'

        info = [f'<center>Version: {PROTONVPN_APPLET_VERSION}',
                f'{name}',
                f"<a href='{email}'>{email}</a>",
                f"<a href='{github}'>{github}</a></center>"]

        centered_text = f'<center>{"<br>".join(info)}</center>'

        QMessageBox.information(self, 'protonvpn-applet', centered_text)

        return

    def get_protonvpn_version(self):
        """Start the CheckProtonVPNVersion thread; when it gets the version, it will call `self.show_protonvpn_version`
        """
        print('called get_protonvpn_version')
        self.check_protonvpn_version_thread = CheckProtonVPNVersion(self)
        self.check_protonvpn_version_thread.protonvpn_version_ready.connect(self.show_protonvpn_version)
        self.check_protonvpn_version_thread.start()
        return

    def show_protonvpn_version(self, version):
        """Show the ProtonVPN version in a QMessageBox.

        Parameters
        ----------
        version : str
            Version number to be shown.
        """
        print('called show_protonvpn_version')
        QMessageBox.information(self, 'ProtonVPN Version', f'Version: {version}')
        return


if __name__ == '__main__':
    check_single_instance()
    app = QApplication(sys.argv)
    mw = PVPNApplet()
    sys.exit(app.exec())
