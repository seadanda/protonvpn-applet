# protonvpn-applet
Basic systray applet for ProtonVPN written in python + PyQt5 with protonvpn-cli as a backend.

I like systray icons and nothing existed for ProtonVPN so I made one. Warning: low effort content.

## Running
It is possible to clone the repo and just run straight away with
```
./protonvpn-applet.py
```
You might have to `chmod +x protonvpn-applet` first

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
