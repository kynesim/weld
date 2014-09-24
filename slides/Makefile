# Makefile to build slides

.PHONY: all
all:	deck reveal

.PHONY: deck
deck:	deck.html

.PHONY: reveal
reveal:		reveal.html

deck.html:	slides.txt
	rst2html5 --deck-js --pretty-print-code --embed-images $< > $@
	ln -sf deck.html weld-slides.html

reveal.html:	slides.txt
	rst2html5 --jquery --reveal-js --reveal-js-opts theme=simple --pretty-print-code --embed-images $< > $@

clean:
	rm -f deck.html reveal.html weld-slides.html
