#!/bin/bash

echo "🚀 Building frontend..."
npm run build

echo "📦 Adding cache-busting timestamps to assets..."
TIMESTAMP=$(date +%s)
cd dist/assets
for file in index-*.js; do
  if [ -f "$file" ]; then
    mv "$file" "index-${TIMESTAMP}.js"
    JS_FILE="index-${TIMESTAMP}.js"
  fi
done
for file in index-*.css; do
  if [ -f "$file" ]; then
    mv "$file" "index-${TIMESTAMP}.css"
    CSS_FILE="index-${TIMESTAMP}.css"
  fi
done
cd ../..
sed -i "s|/assets/index-[^\"]*\.js|/assets/${JS_FILE}|g" dist/index.html
sed -i "s|/assets/index-[^\"]*\.css|/assets/${CSS_FILE}|g" dist/index.html
echo "✅ Cache-busting applied: ${JS_FILE}, ${CSS_FILE}"

echo "🎮 Starting Flask backend..."
python app.py
