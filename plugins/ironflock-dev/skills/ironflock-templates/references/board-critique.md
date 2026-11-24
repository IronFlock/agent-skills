<!-- Adapted from the design-critique skill of the design plugin, version 1.2.0, by Anthropic (anthropics/knowledge-work-plugins), under the Apache License, Version 2.0; this file is under the same licence. Changed by Record Evolution GmbH in 2026: rewritten as checks of an IronFlock board. The licence text and the notice are in LICENSE-APACHE-2.0.txt and NOTICE in the folder of the skill ironflock-templates (IronFlock/agent-skills), and at https://www.apache.org/licenses/LICENSE-2.0 -->
# Checking a board before you report it

Five checks for a board you built or restyled, run once before you report
it. Each one can be answered from the board's definition: its pages, the
widget type on each tile, the tiles' sizes and positions on the grid, the
titles, the style and the state colours, and what each widget is bound to.
When you can see an image of the board, look at the image as well; the checks
stay the same. The rules they check are in board-design.md, for charts in
board-charts.md, and for the words, sizes and contrast of controls in
board-interaction.md.

## The five checks

1. **First impression.** Look at the home page as the viewer of the brief,
   for two seconds, from where they stand. Which tile draws the eye first: the
   biggest one, then the top left? Is that what people look for first? Do the
   titles alone tell what the page answers? Correct: give the first thing the
   biggest tile at the top left, and title the tiles so the page's question is
   answered by reading them.
2. **Usability.** Walk the board as its user. Every page is reached by
   clicking from home and leads back; every control (a form, a switch, a
   button) says what its click does and sits on a page or a corner of its
   own, at the top of the area it acts on, never between the readings and
   never in the last rows of the grid; every tile shows data now. Correct:
   add the missing link, move the control, reword its label, fix the binding
   of an empty tile or say why it is empty.
3. **Hierarchy.** On each page: states first, then the headline figure, then
   trends, then detail; size follows importance; no more tiles than the
   viewing situation carries (six to nine on a wall screen, six to eight on a
   tablet, about twelve at a desk); no value twice on one page; a table of
   many rows or a form on a page of its own; a table of one row is a card,
   and a single figure is a widget-markdown card, not widget-value. Correct:
   reorder the bands, resize the tiles, split the page, turn the one-row
   table or the figure into a card.
4. **Consistency.** The same state has the same colour on every widget;
   nothing else is coloured but the alarm red of a delete and brand colours on
   the navigation band or the tile border; chart series have the series
   colours of the preset; the same thing has the same shape (one gauge per
   machine, the same size, in the order of the machine list); the same
   quantity has the same unit and precision; titles follow one pattern in one
   language; the style is the preset's, whole. Correct: align the colour maps,
   sizes, units and titles.
5. **Accessibility.** Text and state colours are the preset's, which pass
   contrast (`lobby` only over a picture no lighter behind the tiles than its
   `background_color`); no colour written into markup that the theme cannot
   reach (dark text on a dark board); a state shows its word beside its
   colour; text is no smaller than
   board-design.md's sizes for the viewing distance; on a tablet every
   button and switch has the touch size of board-interaction.md. Correct:
   take the preset's colours, add the state's word, set the font sizes,
   enlarge the tile. For HTML cards, check the narrowest planned size with
   the longest expected value and status detail. All lines should fit inside
   the tile, with visible space around each pill's text. For filters, check the
   selected text and arrow together and the field's contrast against the board.

## Once, and one round

Run the checks once, after the last change of the build and before you
report. Correct what fails in one round of changes. The round includes
re-sending a fix that a tool rejected and closing the coverage and navigation
gaps the tools report after it; a second run of the checks would be a second
round. Do not run them again, even when a correction leaves something to
improve. In your report, name what you left as it is and why: the data does
not allow it, the user asked for it, or a fix would break another rule.
