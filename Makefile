DESTDIR=$(PWD)
PREFIX=/usr
ICONDIR=/icons/16x16

all: options pvpn-applet

options:
	@echo "Install options:"
	@echo "DESTDIR = $(DESTDIR)"
	@echo "PREFIX  = $(PREFIX)"
	@echo "ICONDIR = $(ICONDIR)"

pvpn-applet: pvpn-applet.py
	sed "s@icons/16x16@$(DESTDIR)$(ICONDIR)@g" pvpn-applet.py > pvpn-applet
	chmod +x pvpn-applet

install: pvpn-applet
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	cp -f pvpn-applet $(DESTDIR)$(PREFIX)/bin
	chmod 755 $(DESTDIR)$(PREFIX)/bin/pvpn-applet
	mkdir -p $(DESTDIR)$(ICONDIR)
	cp -f icons/16x16/protonvpn-connected.png $(DESTDIR)$(ICONDIR)
	chmod 644 $(DESTDIR)$(ICONDIR)/protonvpn-connected.png
	cp -f icons/16x16/protonvpn-disconnected.png $(DESTDIR)$(ICONDIR)
	chmod 644 $(DESTDIR)$(ICONDIR)/protonvpn-disconnected.png

clean:
	rm -f pvpn-applet

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/pvpn-applet
	rm -f $(DESTDIR)$(ICONDIR)/protonvpn-connected.png
	rm -f $(DESTDIR)$(ICONDIR)/protonvpn-disconnected.png
