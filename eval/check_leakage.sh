#!/bin/sh
# Leakage check: only files under eval/ may read query.csv or label.csv.
# Search methods, patch resources and training code must never see the eval queries or labels.
# notebooks/ is exploration, not method code, so it is not checked.
hits=$(grep -rn -e 'query\.csv' -e 'label\.csv' -e 'typo50' src loadtest k8s deploy .github 2>/dev/null)
if [ -n "$hits" ]; then
    echo "Leakage: method code reads the eval queries or labels:"
    echo "$hits"
    exit 1
fi
echo "Leakage check passed: no method code reads query.csv or label.csv."
