#!/bin/sh

errorExit() {
    echo "*** $*" 1>&2
    exit 1
}

curl --silent --max-time 2 --insecure https://localhost:${BACKENDPORT}/ -o /dev/null || errorExit "Error GET https://localhost:${BACKENDPORT}/"
if ip addr | grep -q ${KUBEAPI}; then
    curl --silent --max-time 2 --insecure https://${KUBEAPI}:${BACKENDPORT}/ -o /dev/null || errorExit "Error GET https://${KUBEAPI}:${BACKENDPORT}/"
fi