#!/bin/sh

# Recreate config file
rm -rf ./public/env-config.js
touch ./public/env-config.js

# Add assignment 
echo "window.__ENV = {" >> ./public/env-config.js

# Read each line in .env file
# Each line represents key=value pairs
# We only want NEXT_PUBLIC_ variables to be exposed
printenv | grep NEXT_PUBLIC_ | while read -r line; do
  # Split env var by character `=`
  if printf '%s\n' "$line" | grep -q -e '='; then
    varname=$(printf '%s\n' "$line" | sed -e 's/=.*//')
    varvalue=$(printf '%s\n' "$line" | sed -e 's/^[^=]*=//')
  fi

  # Read value of current variable if exists as Environment Variable
  value=$(printf '%s\n' "${varvalue}" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
  
  # Append configuration property to JS file
  echo "  $varname: \"$value\"," >> ./public/env-config.js
done

echo "};" >> ./public/env-config.js

# Execute the passed command
exec "$@"
