# protonvpn-applet
Basic systray applet for ProtonVPN written in python + PyQt5 with protonvpn-cli as a backend.

I like systray icons and nothing existed for ProtonVPN so I made one. Warning: low effort content.

## Dependencies
- python3
- libnotify
- sudo (with [passwordless sudo](https://wiki.archlinux.org/index.php/Sudo#Example_entries))
- protonvpn-cli

Python packages:
- pyqt5
- gobject-introspection

## Running
It is possible to clone the repo and just run straight away with

```bash
./protonvpn-applet.py
```
You might have to `chmod +x protonvpn-applet.py` first.

By default, `protonvpn` requires superuser permissions, and therefore `protonvpn-applet` requires them too. If you'd
like to avoid running with elevated permissions every time you launch the applet (for example when running at system
startup), and you don't mind living dangerously, run the following as `root`:

```bash
chmod root:root protonvpn-applet.py  # Change ownership to root
chmod u+s protonvpn-applet.py  # Set the setuid bit.
```


## Installing
### From source
```
make clean
make DESTDIR='' ICONDIR='/usr/share/icons/hicolor/16x16/apps' install
```

### Archlinux: from AUR
```
git clone https://aur.archlinux.org/protonvpn-applet
cd protonvpn-applet
makepkg -si
```

### Archlinux: using an AUR helper (yay for example)
```
yay -Sa protonvpn-applet
```

## Contributing
This is pretty hacky and my first foray into Qt so any tips or improvements welcome. Just make an issue or a pull request and I'll have a look.
