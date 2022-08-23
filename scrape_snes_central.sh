#!/bin/bash
# Usage:
#   seq -f "%04g" 0 1 1250 | ./scrape_snes_central.sh >> snes_game_codes.csv
#   echo '0517' | ./scrape_snes_central.sh

while read -r game_id; do
  pagedata=$(curl -sS "http://snescentral.com/article.php?id=$game_id")
  title=$(echo "$pagedata" | grep CAPTION | cut -f2 -d\> | cut -f1 -d\<)
  game_code=$(echo "$pagedata" | grep -A1 "Game Code" | tail -1 | cut -f2 -d\> | cut -f1 -d\<)
  echo "\"${game_id}\",\"${title}\",\"${game_code}\""
done
