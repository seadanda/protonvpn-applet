DESTDIR=$(PWD)
PREFIX=/usr
ICONDIR=/icons/16x16

all: options protonvpn-applet

options:
	@echo "Install options:"
	@echo "DESTDIR = $(DESTDIR)"
	@echo "PREFIX  = $(PREFIX)"
	@echo "ICONDIR = $(ICONDIR)"

protonvpn-applet: protonvpn-applet.py
	sed "s@icons/16x16@$(DESTDIR)$(ICONDIR)@g" protonvpn-applet.py > protonvpn-applet
	chmod +x protonvpn-applet

install: options protonvpn-applet
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	cp -f protonvpn-applet $(DESTDIR)$(PREFIX)/bin
	chmod 755 $(DESTDIR)$(PREFIX)/bin/protonvpn-applet
	mkdir -p $(DESTDIR)$(ICONDIR)
	cp -f icons/16x16/protonvpn-connected.png $(DESTDIR)$(ICONDIR)
	chmod 644 $(DESTDIR)$(ICONDIR)/protonvpn-connected.png
	cp -f icons/16x16/protonvpn-disconnected.png $(DESTDIR)$(ICONDIR)
	chmod 644 $(DESTDIR)$(ICONDIR)/protonvpn-disconnected.png

clean:
	rm -f protonvpn-applet

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/protonvpn-applet
	rm -f $(DESTDIR)$(ICONDIR)/protonvpn-connected.png
	rm -f $(DESTDIR)$(ICONDIR)/protonvpn-disconnected.png
