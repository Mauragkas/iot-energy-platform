all: main.pdf

main.pdf: main.tex figures/*
	latexmk -pdf -interaction=nonstopmode main.tex

clean:
	latexmk -c
	rm -f main.pdf main.bbl

.PHONY: all clean
