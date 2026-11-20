# Source attribution and licenses

## OpenIntro Statistics, Fourth Edition

Authors: **David Diez, Mine Çetinkaya-Rundel and Christopher D Barr**. Copyright © 2019. The supplied PDF states that it was updated December 30, 2024.

Source: https://www.openintro.org/book/os/

Resource license: **Creative Commons Attribution-ShareAlike 3.0 Unported**, except where otherwise indicated by the source.

- License deed: https://creativecommons.org/licenses/by-sa/3.0/
- License legal code: https://creativecommons.org/licenses/by-sa/3.0/legalcode
- OpenIntro license/exceptions: https://www.openintro.org/license/
- OpenIntro textbook source license: https://github.com/OpenIntroStat/openintro-statistics/blob/master/LICENSE.md

The original PDF is included unchanged. AccessÉdu adds a separate search interface, extracted selectable text, source-linked highlighting, AI explanations and unofficial English/Canadian French translation. Adaptations of the textbook text, including translations and reformatted excerpts, are distributed under **CC BY-SA 3.0** and must retain appropriate attribution and identification of changes. External web materials retain their own licenses; a search result does not grant redistribution rights.

AccessÉdu is an independent demonstration. It is not an OpenIntro product, official translation, or endorsed service. No OpenIntro logo or book-cover branding is used as the app's branding. OpenIntro's trademarks, website, cover branding and other specifically excluded materials retain their separate protections. References to the original textbook title identify the source.

## Software and other dependencies

Flask, OpenAI's Python SDK, Gunicorn, python-dotenv and PyMuPDF retain their own licenses. PyMuPDF is offered under AGPL and commercial terms; its obligations are separate from the textbook's Creative Commons license. Review the package licenses when redistributing or changing hosting arrangements. This delivery includes the app's editable source and deployment instructions. No new blanket license is imposed on third-party works, and this notice does not replace their license texts.

The prior Kysely package was consulted as a functional reference. Its Finnish PDF, Anthropic-specific code, hockey/Finland modules, virtual environment, Git history and secrets are not part of this project.

## Active Calculus, Second Edition — HTML snapshot

Matthew Boelkins; contributing authors David Austin, Christina Safranski and Steven Schlicker.
Source: https://mattboelkins.github.io/active-calculus-single-mbx/html2e/ (snapshot 2026-11-19).
CC BY-SA 4.0, except where otherwise noted: https://creativecommons.org/licenses/by-sa/4.0/ .
Local adaptation removes site navigation and scripts, adds paragraph anchors, and links images to their original URLs. Source notices and exceptions remain in the chapters.

## MathJax 3.2.2

Local formula rendering bundle and fonts from the official MathJax npm package, under Apache License 2.0. License: `static/vendor/mathjax/LICENSE`. https://www.mathjax.org/

## Writing for Success — 1st Canadian Edition (HTML)

Tara Horkoff and an author removed at the request of the original publisher. © 2015.
Source: https://opentextbc.ca/writingforsuccess/ . CC BY-NC-SA 4.0, except where otherwise noted: https://creativecommons.org/licenses/by-nc-sa/4.0/ .
Imported from the complete official XHTML download (publisher export filename dated December 2021), obtained through the browser on 2026-11-19 because automated chapter requests were blocked. The unmodified export is retained as `content/writing-for-success-html/source.xhtml`. All 12 main chapters, preface and appendix are included. Local adaptation removes navigation/scripts and adds local paragraph IDs. Images link to original URLs. Original notices and third-party exceptions remain applicable. Download the original for free from BCcampus: https://open.bccampus.ca/ .

## Liberté, Volume 1 : Première édition canadienne (HTML)

Authors listed by the publisher: Larry Steele, Julia Hines, Olivia Bazot, Alexandra Tsedryk, Juliette Valcke, Gretchen V. Angelo and Emmanuelle Remy. Canadian adaptation copyright © 2025 Alexandra Tsedryk, Juliette Valcke and Gretchen V. Angelo.
Source: https://pressbooks.atlanticoer-relatlantique.ca/liberte1/ . Canadian adaptation CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/), based on Liberté © 2003 Gretchen V. Angelo under CC BY-NC-SA 3.0 (https://creativecommons.org/licenses/by-nc-sa/3.0/), except where otherwise noted.
Imported from the publisher's complete official XHTML download (export filename dated June 2025), downloaded through the browser on 2026-11-19. The original is preserved as `content/liberte1-html/source.xhtml`. All 30 exported TOC entries are present, including the three chapters, activities, grammar sections and supplementary modules. The adaptation sanitizes scripts/navigation and adds paragraph anchors; images link to original URLs and embedded interactive activities require the original website. English grammar explanations in the source remain English; the configured reply language can be Canadian French.

## Local image and structural import repair — 2026-11-20

Images previously linked to the source websites are now copied locally with the surrounding books' original attribution and third-party exceptions retained. Active Calculus images were taken from the publisher's `gh-pages` commit `f45f25761f6cbcc614531574293c525b34a9994b`; Writing and Liberté images were taken from their official EPUB exports (the same editions as the XHTML snapshots). Per-image source/provenance appears in each book's `media.json`. Alt text is retained and indexed, and tables/teaching boxes are grouped into complete evidence blocks. No original textbook wording is supplied by an AI model.

Writing's original `image1.jpeg` and `image21.jpeg` return 404 and are absent from the publisher's EPUB. Locally generated SVG notices mark these unavailable originals and display existing source alt text when informative; they do not reconstruct or claim to be the original images. The copied example text remains under the book's CC BY-NC-SA terms.


## Marked 18.2.1 and DOMPurify 3.4.18

Client-side Markdown parsing and HTML sanitization use the official npm distributions, vendored locally. Marked is MIT licensed (`static/vendor/marked/LICENSE`); DOMPurify offers Apache-2.0 or MPL-2.0 (`static/vendor/dompurify/LICENSE`). See https://marked.js.org/ and https://github.com/cure53/DOMPurify . HTML is sanitized before insertion; MathJax additionally restricts TeX-created URLs and supplies assistive MathML.
