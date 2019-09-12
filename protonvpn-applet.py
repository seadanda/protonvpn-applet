#!/usr/bin/python
import sys
import re
import subprocess
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, qApp
from PyQt5.QtCore import QSize, QThread
from PyQt5.QtGui import QIcon


def check_single_instance():
    try:
        pid = subprocess.check_output("pgrep protonvpn-applet".split()).decode(sys.stdout.encoding)
    except Exception:
        pid = subprocess.check_output("pgrep protonvpn-applet.py".split()).decode(sys.stdout.encoding)

    try:
        pid.split()[1]
        print("There is an instance already running")
        exit()
    except Exception:
        pass


class Polling(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet

    def __del__(self):
        self.wait()

    def run(self):
        while(self.PApplet.is_polling()):
            try:
                subprocess.check_output("pgrep openvpn".split()).decode(sys.stdout.encoding)
                iplink = subprocess.check_output("ip link".split()).decode(sys.stdout.encoding)
                if (re.search(r'tun[0-9]:', iplink)):
                    self.PApplet.tray_icon.setIcon(QIcon("icons/16x16/protonvpn-connected.png"))
                else:
                    raise Exception
            except Exception:
                self.PApplet.tray_icon.setIcon(QIcon("icons/16x16/protonvpn-disconnected.png"))
            self.sleep(1)


class ConnectVPN(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet

    def __del__(self):
        self.wait()

    def run(self):
        try:
            subprocess.run("sudo protonvpn -l".split())
        except Exception:
            subprocess.run("sudo protonvpn -f".split())
        self.PApplet.status_vpn("dummy")


class DisconnectVPN(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet

    def __del__(self):
        self.wait()

    def run(self):
        subprocess.run("sudo protonvpn -d".split())
        self.PApplet.status_vpn("dummy")


class CheckStatus(QThread):
    def __init__(self, PApplet):
        QThread.__init__(self)
        self.PApplet = PApplet

    def __del__(self):
        self.wait()

    def run(self):
        result = subprocess.check_output("sudo protonvpn --status".split()).decode(sys.stdout.encoding)
        result = result.split('\n')
        try:
            server = result[4].split(':')[1]
            ip = result[3].split(':')[1]
            Notify.Notification.new(f"VPN Connected\nServer: {server}\nIP address: {ip}").show()
            self.PApplet.tray_icon.setIcon(QIcon("icons/16x16/protonvpn-connected.png"))
        except Exception:
            Notify.Notification.new(f"VPN disconnected").show()
            self.PApplet.tray_icon.setIcon(QIcon("icons/16x16/protonvpn-disconnected.png"))


class PVPNApplet(QMainWindow):
    tray_icon = None
    polling = True

    # Override the class constructor
    def __init__(self):
        # Be sure to call the super class method
        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(480, 80))             # Set sizes
        self.setWindowTitle("ProtonVPN Qt")             # Set a title
        central_widget = QWidget(self)                  # Create a central widget
        self.setCentralWidget(central_widget)           # Set the central widget

        # Init QSystemTrayIcon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icons/16x16/protonvpn-disconnected.png"))

        # Init libnotify
        Notify.init("ProtonVPN")

        # Menu actions
        connect_action = QAction("Connect", self)
        disconnect_action = QAction("Disconnect", self)
        status_action = QAction("Status", self)
        quit_action = QAction("Exit", self)

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
        self.pollingThread = Polling(self)
        self.pollingThread.start()

    def connect_vpn(self, event):
        self.kill_polling()
        self.connectThread = ConnectVPN(self)
        self.connectThread.finished.connect(self.start_polling)
        self.connectThread.start()

    def disconnect_vpn(self, event):
        self.disconnectThread = DisconnectVPN(self)
        self.disconnectThread.start()

    def status_vpn(self, event):
        self.statusThread = CheckStatus(self)
        self.statusThread.start()

    # Override closeEvent to intercept the window closing event
    def closeEvent(self, event):
        event.ignore()
        self.hide()


if __name__ == "__main__":
    check_single_instance()
    app = QApplication(sys.argv)
    mw = PVPNApplet()
    sys.exit(app.exec())
