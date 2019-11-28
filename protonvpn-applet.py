#!/usr/bin/python
import sys
import re
import subprocess
from enum import Enum
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, qApp
from PyQt5.QtCore import QSize, QThread
from PyQt5.QtGui import QIcon


class VPNStatusException(Exception):
    pass


class VPNCommand(Enum):
    status = 'sudo protonvpn s'
    connect_fastest = 'sudo protonvpn c -f'
    disconnect = 'sudo protonvpn d'


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
                    raise VPNStatusException('Cannot parse `ip link` output.')
            except subprocess.CalledProcessError:
                self.PApplet.tray_icon.setIcon(QIcon('icons/16x16/protonvpn-disconnected.png'))
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
        result = subprocess.check_output(VPNCommand.status.value.split()).decode(sys.stdout.encoding)
        result = result.split('\n')

        print(result)

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
        self.show_notifications_action = QAction('Show Notifications')
        self.show_notifications_action.setCheckable(True)
        self.show_notifications_action.setChecked(False)

        # Triggers
        quit_action.triggered.connect(qApp.quit)
        connect_action.triggered.connect(self.connect_vpn)
        disconnect_action.triggered.connect(self.disconnect_vpn)
        status_action.triggered.connect(self.status_vpn)

        # Draw menu
        tray_menu = QMenu()
        tray_menu.addAction(connect_action)
        tray_menu.addAction(disconnect_action)
        tray_menu.addAction(status_action)
        tray_menu.addAction(self.show_notifications_action)
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


if __name__ == '__main__':
    check_single_instance()
    app = QApplication(sys.argv)
    mw = PVPNApplet()
    sys.exit(app.exec())
