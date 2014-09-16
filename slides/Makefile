# Makefile to build slides

.PHONY: all
all:	deck reveal

.PHONY: deck
deck:	deck.html

.PHONY: reveal
reveal:		reveal.html

deck.html:	slides.txt
	~/sw/rst2html5/bin/rst2html5 --deck-js --pretty-print-code --embed-content $< > $@
	ln -sf deck.html weld-slides.html

reveal.html:	slides.txt
	~/sw/rst2html5/bin/rst2html5 --jquery --reveal-js --reveal-js-opts theme=simple --pretty-print-code $< > $@

