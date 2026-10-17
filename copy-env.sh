#!/bin/bash

SOURCE=".env"
TARGET_ROOT="services"

echo "Copying $SOURCE to all subfolders in $TARGET_ROOT (excluding nodejs-socket)..."

for dir in "$TARGET_ROOT"/*/; do
    dirname=$(basename "$dir")

    if [ "$dirname" != "nodejs-socket" ]; then
        cp -f "$SOURCE" "$dir/.env"
        echo "Copied .env to $dirname"
    else
        echo "Skipped $dirname"
    fi
done

echo "Done!"


# bash ./copy-env.sh